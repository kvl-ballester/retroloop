from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cycles.models import Card, FeedbackCycle
from projects.models import Membership, Project
from retro.models import Retrospective
from retro.serializers import serialize_state
from retro.services import STAGE_ORDER, advance_stage


def make_user(username, password='correct-horse-battery-staple'):
    return User.objects.create_user(username=username, password=password)


def make_retro(owner, *, status=FeedbackCycle.Status.CLOSED, facilitator=None):
    project = Project.objects.create(name='Website', owner=owner)
    Membership.objects.create(project=project, user=owner, role=Membership.Role.FACILITATOR)
    cycle = FeedbackCycle.objects.create(
        project=project,
        week_start=timezone.localdate(),
        opens_at=timezone.now(),
        closes_at=timezone.now() + timezone.timedelta(days=1),
        facilitator=facilitator or owner,
        status=status,
    )
    retro = Retrospective.objects.create(cycle=cycle)
    return project, cycle, retro


def make_card(cycle, author, text='card text', is_anonymous=False):
    return Card.objects.create(
        cycle=cycle,
        category=Card.Category.START,
        text=text,
        author=author,
        is_anonymous=is_anonymous,
    )


class AdvanceStageTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle, self.retro = make_retro(self.owner)
        self.facilitator = make_user('facilitator')
        Membership.objects.create(
            project=self.project, user=self.facilitator, role=Membership.Role.FACILITATOR
        )
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)

    def test_draft_advances_one_step_to_reveal(self):
        result = advance_stage(self.retro, self.owner)
        self.assertIsNotNone(result)
        self.assertEqual(self.retro.stage, Retrospective.Stage.REVEAL)
        self.assertEqual(self.retro.version, 1)

    def test_transition_moves_to_actual_next_stage_not_skipping(self):
        advance_stage(self.retro, self.owner)
        self.assertEqual(self.retro.stage, Retrospective.Stage.REVEAL)
        version = self.retro.version
        advance_stage(self.retro, self.owner)
        self.assertEqual(self.retro.stage, Retrospective.Stage.CLUSTER)
        self.assertEqual(self.retro.version, version + 1)

    def test_advance_on_complete_rejected_no_version_change(self):
        for _ in range(len(STAGE_ORDER) - 1):
            advance_stage(self.retro, self.owner)
        self.assertEqual(self.retro.stage, Retrospective.Stage.COMPLETE)
        self.assertIsNotNone(self.retro.completed_at)
        version = self.retro.version
        self.assertIsNone(advance_stage(self.retro, self.owner))
        self.assertEqual(self.retro.stage, Retrospective.Stage.COMPLETE)
        self.assertEqual(self.retro.version, version)

    def test_completed_at_set_on_complete(self):
        for _ in range(len(STAGE_ORDER) - 1):
            advance_stage(self.retro, self.owner)
        self.assertIsNotNone(self.retro.completed_at)

    def test_version_bumps_once_per_valid_advance(self):
        advance_stage(self.retro, self.owner)
        self.assertEqual(self.retro.version, 1)
        advance_stage(self.retro, self.owner)
        self.assertEqual(self.retro.version, 2)

    def test_reveal_hook_invoked_on_draft_to_reveal(self):
        with mock.patch('retro.services._reveal_side_effects') as hook:
            advance_stage(self.retro, self.owner)
            hook.assert_called_once_with(self.retro)

    def test_reveal_hook_not_invoked_on_later_advances(self):
        advance_stage(self.retro, self.owner)
        with mock.patch('retro.services._reveal_side_effects') as hook:
            advance_stage(self.retro, self.owner)
            hook.assert_not_called()

    def test_plain_member_cannot_advance(self):
        result = advance_stage(self.retro, self.member)
        self.assertIsNone(result)
        self.assertEqual(self.retro.stage, Retrospective.Stage.DRAFT)
        self.assertEqual(self.retro.version, 0)

    def test_facilitator_can_advance(self):
        self.retro.cycle.facilitator = self.facilitator
        self.retro.cycle.save()
        result = advance_stage(self.retro, self.facilitator)
        self.assertIsNotNone(result)
        self.assertEqual(self.retro.stage, Retrospective.Stage.REVEAL)


class AdvanceViewPermissionTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle, self.retro = make_retro(self.owner)
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)

    def test_plain_member_post_gets_403(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.post(reverse('advance_retro', args=[self.retro.id]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_visitor_sent_to_login(self):
        response = self.client.post(reverse('advance_retro', args=[self.retro.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_non_member_gets_404(self):
        make_user('stranger')
        self.client.login(username='stranger', password='correct-horse-battery-staple')
        response = self.client.post(reverse('advance_retro', args=[self.retro.id]))
        self.assertEqual(response.status_code, 404)

    def test_facilitator_advances_and_redirects(self):
        self.client.login(username='owner', password='correct-horse-battery-staple')
        response = self.client.post(reverse('advance_retro', args=[self.retro.id]))
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        self.retro.refresh_from_db()
        self.assertEqual(self.retro.stage, Retrospective.Stage.REVEAL)


class StateSerializationTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle, self.retro = make_retro(self.owner)
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)
        make_card(self.cycle, self.owner, text='OWNER CARD')
        make_card(self.cycle, self.member, text='MEMBER CARD')

    def test_payload_has_stage_version_cycle(self):
        payload = serialize_state(self.retro, self.member)
        self.assertEqual(payload['stage'], 'DRAFT')
        self.assertEqual(payload['version'], 0)
        self.assertEqual(payload['cycle'], self.cycle.id)

    def test_no_card_content_before_reveal(self):
        payload = serialize_state(self.retro, self.member, with_cards=True)
        self.assertNotIn('OWNER CARD', str(payload))
        self.assertNotIn('MEMBER CARD', str(payload))
        self.assertEqual(payload['cards'], [])

    def test_vote_totals_omitted_during_vote(self):
        while self.retro.stage != Retrospective.Stage.VOTE:
            self.retro = advance_stage(self.retro, self.owner) or self.retro
        self.assertEqual(self.retro.stage, Retrospective.Stage.VOTE)
        payload = serialize_state(self.retro, self.member, with_cards=True)
        self.assertNotIn('votes', payload)
        self.assertFalse(payload['votes_revealed'])

    def test_votes_revealed_after_vote(self):
        while self.retro.stage != Retrospective.Stage.DISCUSS:
            self.retro = advance_stage(self.retro, self.owner) or self.retro
        payload = serialize_state(self.retro, self.member, with_cards=True)
        self.assertTrue(payload['votes_revealed'])


class StateEndpointTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle, self.retro = make_retro(self.owner)
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)

    def test_member_gets_state(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.get(reverse('retro_state', args=[self.retro.id]))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['stage'], 'DRAFT')
        self.assertEqual(body['version'], 0)
        self.assertEqual(body['cycle'], self.cycle.id)

    def test_equal_version_returns_304(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        url = reverse('retro_state', args=[self.retro.id])
        response = self.client.get(url, {'v': 0})
        self.assertEqual(response.status_code, 304)

    def test_stale_version_returns_full_payload(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.get(reverse('retro_state', args=[self.retro.id]), {'v': -1})
        self.assertEqual(response.status_code, 200)

    def test_missing_v_returns_full_payload(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.get(reverse('retro_state', args=[self.retro.id]))
        self.assertEqual(response.status_code, 200)

    def test_non_member_gets_404(self):
        make_user('stranger')
        self.client.login(username='stranger', password='correct-horse-battery-staple')
        response = self.client.get(reverse('retro_state', args=[self.retro.id]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_sent_to_login(self):
        response = self.client.get(reverse('retro_state', args=[self.retro.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
