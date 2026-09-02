from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cycles.models import Card, CycleParticipation, FeedbackCycle
from projects.models import Membership, Project


def make_user(username, password='correct-horse-battery-staple'):
    return User.objects.create_user(username=username, password=password)


def dt(year, month, day, hour=0, minute=0):
    return timezone.make_aware(timezone.datetime(year, month, day, hour, minute))


def make_open_cycle(owner, *, facilitator=None):
    project = Project.objects.create(name='Website', owner=owner)
    Membership.objects.create(project=project, user=owner, role=Membership.Role.FACILITATOR)
    cycle = FeedbackCycle.objects.create(
        project=project,
        week_start=dt(2026, 9, 7).date(),
        opens_at=dt(2026, 9, 7),
        closes_at=dt(2026, 9, 14),
        facilitator=facilitator or owner,
    )
    return project, cycle


def join(project, username):
    user = make_user(username)
    Membership.objects.create(project=project, user=user)
    return user


class FeedbackFormTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_open_cycle(self.owner)
        self.member = join(self.project, 'member')
        self.client.login(username='member', password='correct-horse-battery-staple')

    def test_feedback_page_renders_three_sections(self):
        url = reverse('feedback', args=[self.cycle.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Start')
        self.assertContains(response, 'Stop')
        self.assertContains(response, 'Continue')

    def test_add_card_creates_card_and_participation(self):
        url = reverse('feedback', args=[self.cycle.id])
        response = self.client.post(
            url, {'category': 'START', 'text': 'Start doing standups', 'is_anonymous': 'on'}
        )
        self.assertRedirects(response, url)
        card = Card.objects.get(cycle=self.cycle, author=self.member)
        self.assertEqual(card.category, Card.Category.START)
        self.assertEqual(card.text, 'Start doing standups')
        self.assertTrue(card.is_anonymous)
        participation = CycleParticipation.objects.get(cycle=self.cycle, user=self.member)
        self.assertEqual(participation.card_count, 1)
        self.assertIsNotNone(participation.submitted_at)

    def test_multiple_cards_increment_card_count(self):
        url = reverse('feedback', args=[self.cycle.id])
        for category in ['START', 'STOP']:
            self.client.post(url, {'category': category, 'text': f'{category} text'})
        participation = CycleParticipation.objects.get(cycle=self.cycle, user=self.member)
        self.assertEqual(participation.card_count, 2)

    def test_anonymous_card_author_still_sees_own_card(self):
        url = reverse('feedback', args=[self.cycle.id])
        self.client.post(
            url, {'category': 'CONTINUE', 'text': 'Keep doing great work', 'is_anonymous': 'on'}
        )
        response = self.client.get(url)
        self.assertContains(response, 'Keep doing great work')

    def test_member_never_sees_another_members_card(self):
        other = join(self.project, 'other')
        Card.objects.create(
            cycle=self.cycle,
            category=Card.Category.START,
            text='SECRET OTHER CARD',
            author=other,
            position=1,
        )
        response = self.client.get(reverse('feedback', args=[self.cycle.id]))
        self.assertNotContains(response, 'SECRET OTHER CARD')

    def test_empty_text_rejected(self):
        url = reverse('feedback', args=[self.cycle.id])
        response = self.client.post(url, {'category': 'START', 'text': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required')
        self.assertFalse(Card.objects.filter(cycle=self.cycle, author=self.member).exists())

    def test_whitespace_text_rejected(self):
        url = reverse('feedback', args=[self.cycle.id])
        response = self.client.post(url, {'category': 'START', 'text': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Card.objects.filter(cycle=self.cycle, author=self.member).exists())

    def test_over_max_length_rejected(self):
        url = reverse('feedback', args=[self.cycle.id])
        response = self.client.post(url, {'category': 'START', 'text': 'x' * 1001})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'at most 1000 characters')
        self.assertFalse(Card.objects.filter(cycle=self.cycle, author=self.member).exists())


class FeedbackGuardTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_open_cycle(self.owner)

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(reverse('feedback', args=[self.cycle.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_non_member_gets_404(self):
        make_user('stranger')
        self.client.login(username='stranger', password='correct-horse-battery-staple')
        response = self.client.get(reverse('feedback', args=[self.cycle.id]))
        self.assertEqual(response.status_code, 404)


class EditCardTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_open_cycle(self.owner)
        self.member = join(self.project, 'member')
        self.card = Card.objects.create(
            cycle=self.cycle,
            category=Card.Category.START,
            text='original text',
            author=self.member,
            is_anonymous=True,
            position=1,
        )
        self.client.login(username='member', password='correct-horse-battery-staple')

    def test_edit_changes_text_and_category_preserves_anonymous(self):
        url = reverse('edit_card', args=[self.cycle.id, self.card.id])
        response = self.client.post(url, {'category': 'STOP', 'text': 'changed text'})
        self.assertRedirects(response, reverse('feedback', args=[self.cycle.id]))
        self.card.refresh_from_db()
        self.assertEqual(self.card.text, 'changed text')
        self.assertEqual(self.card.category, Card.Category.STOP)
        self.assertTrue(self.card.is_anonymous)

    def test_cannot_edit_closed_cycle(self):
        self.cycle.status = FeedbackCycle.Status.CLOSED
        self.cycle.save()
        url = reverse('edit_card', args=[self.cycle.id, self.card.id])
        response = self.client.post(url, {'category': 'START', 'text': 'nope'})
        self.assertEqual(response.status_code, 404)
        self.card.refresh_from_db()
        self.assertEqual(self.card.text, 'original text')


class DeleteCardTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_open_cycle(self.owner)
        self.member = join(self.project, 'member')
        self.card = Card.objects.create(
            cycle=self.cycle,
            category=Card.Category.START,
            text='to delete',
            author=self.member,
            position=1,
        )
        # simulate a participation with submitted_at set
        self.participation, _ = CycleParticipation.objects.get_or_create(
            cycle=self.cycle, user=self.member
        )
        self.participation.submitted_at = dt(2026, 9, 8)
        self.participation.card_count = 1
        self.participation.save()
        self.submitted_at = self.participation.submitted_at
        self.client.login(username='member', password='correct-horse-battery-staple')

    def test_delete_removes_card_decrements_count_keeps_submitted_at(self):
        url = reverse('delete_card', args=[self.cycle.id, self.card.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('feedback', args=[self.cycle.id]))
        self.assertFalse(Card.objects.filter(id=self.card.id).exists())
        self.participation.refresh_from_db()
        self.assertEqual(self.participation.card_count, 0)
        self.assertEqual(self.participation.submitted_at, self.submitted_at)


class ClosedCycleFeedbackTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_open_cycle(self.owner)
        self.cycle.status = FeedbackCycle.Status.CLOSED
        self.cycle.save()
        self.member = join(self.project, 'member')
        self.client.login(username='member', password='correct-horse-battery-staple')

    def test_closed_cycle_renders_read_only(self):
        Card.objects.create(
            cycle=self.cycle,
            category=Card.Category.START,
            text='existing',
            author=self.member,
            position=1,
        )
        response = self.client.get(reverse('feedback', args=[self.cycle.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'existing')
        self.assertNotContains(response, 'Add start card')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'existing')
        self.assertNotContains(response, 'Add start card')

    def test_post_to_closed_cycle_rejected_no_state_change(self):
        self.client.post(
            reverse('feedback', args=[self.cycle.id]),
            {'category': 'START', 'text': 'should not save'},
        )
        self.assertFalse(Card.objects.filter(cycle=self.cycle, author=self.member).exists())
