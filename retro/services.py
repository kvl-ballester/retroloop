from django.db import transaction
from django.utils import timezone

from .models import Retrospective

STAGE_ORDER = [
    Retrospective.Stage.DRAFT,
    Retrospective.Stage.REVEAL,
    Retrospective.Stage.CLUSTER,
    Retrospective.Stage.VOTE,
    Retrospective.Stage.DISCUSS,
    Retrospective.Stage.COMPLETE,
]


def _reveal_side_effects(retro):
    """Applied on DRAFT -> REVEAL. Stubbed here; implemented in #10."""
    pass


@transaction.atomic
def advance_stage(retro, user):
    """Move a retro one step forward through DRAFT -> ... -> COMPLETE.

    Facilitator-only, forward-only. Returns the retro (with an updated
    version) or None when the advance is not permitted or impossible. Every
    transition, version bump, and side effect share one transaction.
    """
    from projects.permissions import can_facilitate

    if not can_facilitate(user, retro):
        return None
    if retro.stage == Retrospective.Stage.COMPLETE:
        return None
    index = STAGE_ORDER.index(retro.stage)
    next_stage = STAGE_ORDER[index + 1]
    if retro.stage == Retrospective.Stage.DRAFT:
        _reveal_side_effects(retro)
    retro.stage = next_stage
    retro.version = retro.version + 1
    if next_stage == Retrospective.Stage.COMPLETE:
        retro.completed_at = timezone.now()
    retro.save(update_fields=['stage', 'version', 'completed_at'])
    return retro
