# Weekly Team Feedback Tool — Task Backlog

Each task is sized for one working session and is self-contained: it can be
picked up by someone who has not read the other tasks. Dependency notes call
out only what must already exist in the repo.

Companion docs: [plan.md](plan.md) (product decisions) and
[architecture.md](architecture.md) (stack and data model).

## 1. Bootstrap the Django project with a passing test

Goal: A new Django project runs and its default test suite passes.

Description: Create a Python virtual environment, install Django 6.0 and the
dev tooling (pytest, pytest-django, ruff) pinned to the versions in
architecture.md, and run `django-admin startproject config .`. Configure the
settings for PostgreSQL in dev (SQLite fallback), add a trivial smoke test so
`pytest` passes, and set up ruff as the linter. Commit the scaffold with a
CI-visible way to run tests and lint, e.g. a `Makefile` or a Compose/service
command. The deliverable is an empty project where `pytest` and `ruff` both
pass.

## 2. Add accounts app with signup and login

Goal: Users can sign up and log in with username/password.

Description: Add the `accounts` app (thin wrapper over
`django.contrib.auth`). Wire `config/urls.py` to include
`django.contrib.auth.urls` for login/logout, and add a single signup form view
using username + password (no email, per architecture.md). Add template pages
for login and signup with links between them, and redirect logged-in users away
from the login page. No email backend, no password reset. Cover with tests.

## 3. Add projects app with membership and join links

Goal: A logged-in user can create a project and others can join by link.

Description: Add the `projects` app with `Project` (name, owner, `join_token`,
`created_at`) and `Membership` (project, user, role `{MEMBER, FACILITATOR}`,
`joined_at`, unique on project+user). Add views to create a project, show its
project page, and a `/join/<token>/` view that makes the logged-in user a
`MEMBER`. Support rotating the `join_token` from the project page, which revokes
existing links. Add the central permission predicates file
(`projects/permissions.py`) as plain functions (e.g. `is_member`, `is_facilitator`)
even if most are stubbed initially. Cover with tests.

## 4. Add cycles app: feedback cycle creation and status

Goal: A facilitator can create a feedback cycle for a project.

Description: Add the `cycles` app with `FeedbackCycle` (project, `week_start`,
`opens_at`, `closes_at`, `facilitator -> User`, status `{COLLECTING, CLOSED}`)
and `CycleParticipation` (cycle, user, `card_count`, `submitted_at`, unique on
cycle+user). Add a view for a facilitator to create a cycle on a project, and a
view to close it. Default the facilitator to the project owner. Show the current
cycle and its submission status on the project page. Cover with tests, including
that only facilitators can create/close.

## 5. Add feedback form: submit Start/Stop/Continue cards

Goal: A member submits private feedback cards under the three categories.

Description: Add the `Card` model (cycle, category `{START, STOP, CONTINUE}`,
text, `author -> User` nullable, `is_anonymous`, `created_at`, `position`) plus
the feedback form view. Members on the cycle can add multiple cards per category
and optionally mark each entry anonymous. Before the retro a member sees and can
edit or delete only their own cards; other members' cards are never returned.
Anonymous cards keep an `author` link only in this phase so owners can edit,
while the query layer must never expose authorship to others. Update
`CycleParticipation` counts on submit. Cover with tests.

## 6. Add retro app: create a retrospective linked to a cycle

Goal: A facilitator can start a retrospective in `DRAFT` stage.

Description: Add the `retro` app with `Retrospective` (cycle 1:1, `stage`,
`started_at`, `completed_at`, `version` int, `votes_per_member` default 3) and a
create view restricted to the cycle facilitator. Only one retrospective per
cycle. Initialize `version` to 0. Add a `Retrospective`-scoped permission helper
(`can_facilitate(user, retro)`). Cover with tests.

## 7. Implement the stage machine and board state endpoint

Goal: The retrospective advances through its forward-only stages with synced
state.

Description: Implement `advance_stage()` in `retro/services.py` guarded
server-side, moving forward through
`DRAFT -> REVEAL -> CLUSTER -> VOTE -> DISCUSS -> COMPLETE`. Enforce that stage
transitions are facilitator-only and forward-only. Add a `GET /retros/<id>/state`
endpoint that serializes the current board state (clusters, cards, votes,
notes) and omits fields per the current stage (e.g. vote totals hidden during
`VOTE`, other members' cards before `REVEAL`). Provide a `version`-aware
short-response path (client sends `?v=`; respond lightly if unchanged). Cover
stage transitions and state serialization with tests.

## 8. Implement the REVEAL-side effects: anonymize and shuffle

Goal: Revealing a retro destroys anonymous authorship and shuffles cards.

Description: In the `-> REVEAL` transition, run, in the same transaction, the
SQL to null `Card.author` for `is_anonymous` cards, assign shuffled
`Card.position` values to all cards, and enqueue the auto-clustering job (which
the AI task fills in later — for now enqueue only if a service function exists,
or leave a TODO). Ensure participation metrics survive via `CycleParticipation`
since authorship is gone. Cover the anonymization and shuffle behavior with
tests, including that the author link is truly gone after reveal.

## 9. Build the retro board page and basic editing

Goal: The board renders clusters/cards and supports elementary moves.

Description: Create the board view and template that render the current retro
state for the stage. Add mutation endpoints for an authorized member to move a
card between clusters (or to ungrouped), merge clusters, split a cluster, and
rename a cluster. Each mutation runs in one transaction and bumps
`Retrospective.version`, then returns the refreshed board state. Clusters are
ranked and sorted by `position`. Keep this server-rendered with HTMX partial
updates. Cover the mutations and version bumping with tests.

## 10. Add the React board island (Vite bundle)

Goal: The board gets a single React island for a richer interaction surface.

Description: Introduce a Vite build (React 19.2, per architecture.md) that
mounts one component tree in `board.html`, taking the serialized initial state
from the page. The island polls `GET /retros/<id>/state?v=<known_version>` every
1.5s and replaces state when the version changes; mutations POST and update
state from the response. Add drag-to-move-card interaction backed by the
existing move endpoint. Wire the build output into one Django template that
includes the bundle. No React anywhere else. Build tooling so the bundle builds
in CI.

## 11. Add voting with hidden totals

Goal: Each member casts up to N stackable votes, totals hidden until close.

Description: Add the `Vote` model (retrospective, cluster, user, `weight`
1..3, unique on retro+cluster+user). Add endpoints to cast and retract votes
during the `VOTE` stage, freely reassignable. Add a "close voting" action
(flag `votes_revealed`) for the facilitator. Ensure vote totals are omitted from
the serialized state during the vote stage — never sent to the browser — and
appear, ranked, once voting closes or the retro passes `VOTE`. On `-> DISCUSS`,
compute the ranked agenda by total votes. Cover with tests.

## 12. Add clustering suggestions via OpenAI structured output

Goal: On reveal, the system proposes thematic clusters that the team can edit.

Description: In `ai/`, add a `cluster_cards(cards)` service that calls the
text model (gpt-5.6-terra per architecture.md) using structured outputs, sending
each card's `{id, category, text}` and receiving `{name, card_ids}` back. Write
the result as `Cluster` rows with `is_auto_generated=True`; a card left
unmentioned stays ungrouped. Wire this as the enqueued job from task 8.
Suggestions must never overwrite later team edits — the flag is display-only.
Quote the DEV `OPENAI_API_KEY` integration; keep the LLM call mockable so tests
run offline. Provide a settings flag to disable the call for offline dev.

## 13. Add the feedback reveal UI flow

Goal: Facilitator reveals all cards and the team clusters them on the board.

Description: Build the facilitator-facing reveal and cluster flows in the board
UI. When the retro is in `DRAFT`, show the facilitator a "Reveal" action that
triggers `advance_stage` to `REVEAL` (running the side effects), then renders
all cards grouped/suggested. During `CLUSTER`, provide controls to create a
manual cluster, move cards, merge, split, rename, and leave ungrouped, all
backed by the endpoints from task 9. Keep the state poll running so concurrent
editors converge. Cover the reveal trigger and cluster actions with tests.

## 14. Add notes during the discussion stage

Goal: Members can record notes, decisions, and open action items in-meeting.

Description: Add the `Note` model (retrospective, cluster nullable, author,
text, `created_at`) and the `Decision` model (retrospective, cluster nullable,
text, source `{MANUAL, EXTRACTED}`, status `{DRAFT, CONFIRMED}`), plus the
`ActionItem` model (retrospective, cluster nullable, description, owner->User
nullable, `due_date` nullable, status `{OPEN, DONE}`, source, review_status
`{DRAFT, CONFIRMED}`). Add views to create manual notes, decisions, and action
items during `DISCUSS`, and to update an action item's status/owner (owner or
facilitator only). Cover with tests.

## 15. Add the stage discussion workflow

Goal: The facilitator works through prioritized topics and marks their status.

Description: During `DISCUSS`, show the ranked agenda (from task 11). Add an
endpoint for the facilitator to set a cluster's status to
`DISCUSSED`, `SKIPPED`, or `DEFERRED` on the `Cluster` model. On `-> COMPLETE`,
lock the board so no further mutations are accepted and the summary becomes the
read surface. Add an action to transition `DISCUSS -> COMPLETE`. Cover the
status-marking and completion locking with tests.

## 16. Add the meeting upload page

Goal: Facilitator uploads media or pasted text to start processing.

Description: Add the `meetings` app with `MeetingRecord` (retrospective,
`uploaded_by`, kind `{AUDIO, VIDEO, TRANSCRIPT_FILE, PASTED_TEXT}`, `temp_path`
nullable, `original_filename`, `size_bytes`, status
`{UPLOADED, TRANSCRIBING, EXTRACTING, READY, FAILED}`, `attempts`,
`error_message`, `created_at`, `media_deleted_at`) and `Transcript` (1:1, text,
language, `duration_seconds`). Add the upload view accepting the four inputs,
writing media to a shared scratch dir (streaming to disk, cap 500 MB, low
`FILE_UPLOAD_MAX_MEMORY_SIZE`), and creating a `MeetingRecord(UPLOADED)`. The
upload page polls record status over HTMX. Cover with tests.

## 17. Add the transcription worker step

Goal: Uploaded media is transcribed into a durable Transcript.

Description: Add the `process_meeting_record` background task using
`django.tasks` with the ORM backend from `django-tasks-db`. The task runs
ffmpeg to strip video to audio and downsample to 16 kHz mono Opus, splits into
chunks under 25 MB when needed, and calls the transcription model
(`gpt-4o-transcribe-diarize`, per architecture.md) per chunk, stitching results
with speaker labels into a `Transcript`. Pasted text / transcript files skip the
audio steps. In a `finally`, delete the scratch file and null `temp_path` —
always, even on failure. On failure set status `FAILED` with `error_message`.
Cover the non-API logic with tests, mocking the transcription call.

## 18. Add the extraction worker step

Goal: The transcript produces draft decisions, actions, and a summary.

Description: Extend `process_meeting_record` (or add a second task) that sends
the diarized transcript plus the ranked agenda and project roster to the text
model (gpt-5.6-terra, structured outputs) and gets back decisions, action items
with owner *names*, due dates, and a short summary. Write them as rows with
`source=EXTRACTED` and status `{DRAFT, CONFIRMED}`; resolve owner names to
`User` by fuzzy match against the roster, leaving `owner` null on no match.
Set the record `READY` when done. Mark the pipeline mockable so tests run
offline. Cover with tests.

## 19. Add the facilitator confirmation screen

Goal: Extracted drafts are reviewed and either confirmed or rejected.

Description: Build a single facilitator-only screen listing all DRAFT extracted
decisions and action items with per-item accept / edit / reject controls. On
confirm, set each confirmed item's status to `CONFIRMED`; edits apply before
confirming; rejected items are deleted or marked rejected. Nothing is published
until the facilitator acts. Confirm the few remaining DRAFT manual items too.
Complement the existing manual notes flow. Use HTMX for partial updates. Cover
the confirm/edit/reject workflow with tests.

## 20. Build the retrospective summary page

Goal: A locked, read-only summary of the completed retrospective.

Description: Add the summary view and template shown once a retro is `COMPLETE`
(or viewable after COMPLETE). Render the ranked top topics, key notes, confirmed
decisions, confirmed action items, attendance/participation (from
`CycleParticipation`), and the original feedback cards. Add a finished
retrospective listing plus open action items to the project page, querying
across that project's retros for open actions. Cover with tests.

## 21. Add media pipeline hardening and error UX

Goal: Upload and processing failures are surfaced clearly to the facilitator.

Description: Verify the pipeline's failure paths: a failed transcription leaves
no scratch file on disk, the record shows a readable `error_message` in `FAILED`
state, and the upload page explains that retrying means re-uploading (since the
recording is discarded). Remove any "retry" button that cannot work. Add an
`attempts` increment on each run and guard against the missing-media case.
Cover the failure and cleanup paths with tests.

## 22. Add pyproject linting and CI pipeline

Goal: Tests, lint, and the Vite build run automatically on changes.

Description: Finalize `pyproject.toml` for ruff (including formatting), ensure
pytest-django discovers the suite, and add a CI configuration (GitHub Actions or
the repo's preferred runner) that runs ruff, pytest, and the Vite build on every
push. Add a DB service for Postgres-backed tests, keeping an SQLite path for
local dev. Confirm all tests pass in CI with the `OPENAI_API_KEY` calls mocked
or disabled. This task makes the whole backlog verifiable.

## 23. Write Docker Compose deployment config

Goal: The app runs with `docker compose up`.

Description: Add the three-service Compose file per architecture.md: `db`
(postgres:18, named volume), `web` (gunicorn, shares a `scratch` volume, ffmpeg
in the image), and `worker` (the `django-tasks-db` worker command, same image,
same `scratch` mount). Wire everything through env vars (`DATABASE_URL`,
`OPENAI_API_KEY`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG`) with no storage or
mail credentials. Ensure `web` and `worker` mount the same scratch filesystem.
Document the compose commands and the "only `db` is backed up" note in a README.

## 24. Smoke-test the end-to-end MVP flow

Goal: The full weekly workflow works from signup to published summary.

Description: Manually walk and script the complete happy path: sign up, create a
project, join by link, create a cycle, submit Start/Stop/Continue cards
(anonymous and attributed), reveal, auto-cluster, re-cluster by hand, vote with
hidden totals, close voting, run the discussion marking cluster statuses, upload
a short audio file, confirm the transcribed/extracted drafts, and publish the
summary. Fix any integration gaps surfaced across apps. Add one end-to-end test
covering this path. This is the release gate for the MVP.
