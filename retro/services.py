import secrets

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


def _destroy_anonymous_authorship(retro):
    """Sever the authorship link of every anonymous card on the cycle."""
    retro.cycle.cards.filter(is_anonymous=True).update(author=None)


def _shuffle_positions(retro):
    """Reassign every card a contiguous 1..n position in a shuffled order so
    reveal order leaks nothing about creation order."""
    card_ids = list(
        retro.cycle.cards.order_by('position', 'created_at').values_list('pk', flat=True)
    )
    shuffled = card_ids[:]
    for i in range(len(shuffled) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    cards = retro.cycle.cards.in_bulk(shuffled)
    for position, card_id in enumerate(shuffled, start=1):
        cards[card_id].position = position
        cards[card_id].save(update_fields=['position'])


def _enqueue_clustering(retro):
    """Kick off the auto-clustering job. No-ops when the service is not
    available so the MVP runs without a worker or LLM configured."""
    try:
        from config.tasks import enqueue_clustering_task
    except ImportError:
        return
    enqueue_clustering_task(retro.id)


def _reveal_side_effects(retro):
    """Make every card visible: destroy anonymous authorship, shuffle order,
    and enqueue clustering."""
    _destroy_anonymous_authorship(retro)
    _shuffle_positions(retro)
    _enqueue_clustering(retro)


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
