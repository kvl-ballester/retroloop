from .models import Retrospective

STAGES = [
    Retrospective.Stage.DRAFT,
    Retrospective.Stage.REVEAL,
    Retrospective.Stage.CLUSTER,
    Retrospective.Stage.VOTE,
    Retrospective.Stage.DISCUSS,
    Retrospective.Stage.COMPLETE,
]
VOTE_INDEX = STAGES.index(Retrospective.Stage.VOTE)


def serialize_state(retro, viewer):
    """Render the board state for a viewer.

    A pure function of the retro and the requesting member. Visibility is
    enforced here, never by the template.
    """
    stage_index = STAGES.index(retro.stage)

    payload = {
        'stage': retro.stage,
        'version': retro.version,
        'cycle': retro.cycle_id,
        'votes_revealed': stage_index > VOTE_INDEX,
        'votes_per_member': retro.votes_per_member,
        'cards': [],
    }
    if stage_index > 0:  # revealed: every card's text is visible, by position
        payload['cards'] = [
            {
                'id': card.id,
                'category': card.category,
                'text': card.text,
                'is_anonymous': card.is_anonymous,
                'author': card.author.username if card.author else None,
            }
            for card in retro.cycle.cards.order_by('position')
        ]
    return payload
