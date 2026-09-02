from .models import Retrospective

VOTE_STAGE_INDEX = 3  # index of VOTE in the stage order


def serialize_state(retro, viewer, *, with_cards=False):
    """Render the board state for a viewer.

    A pure function of the retro and the requesting member. Visibility is
    enforced here, never by the template.
    """
    stage_index = [
        Retrospective.Stage.DRAFT,
        Retrospective.Stage.REVEAL,
        Retrospective.Stage.CLUSTER,
        Retrospective.Stage.VOTE,
        Retrospective.Stage.DISCUSS,
        Retrospective.Stage.COMPLETE,
    ].index(retro.stage)

    payload = {
        'stage': retro.stage,
        'version': retro.version,
        'cycle': retro.cycle_id,
        'votes_revealed': stage_index > VOTE_STAGE_INDEX,
        'votes_per_member': retro.votes_per_member,
        'cards': [],
    }
    if with_cards and stage_index > 0:
        payload['cards'] = [
            {
                'id': card.id,
                'category': card.category,
                'text': card.text,
                'is_anonymous': card.is_anonymous,
                'author': card.author.username,
            }
            for card in retro.cycle.cards.order_by('position', 'created_at')
        ]
    return payload
