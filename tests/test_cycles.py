from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cycles.models import CycleParticipation, FeedbackCycle
from projects.models import Membership, Project


def make_user(username, password='correct-horse-battery-staple'):
    return User.objects.create_user(username=username, password=password)


def dt(year, month, day, hour=0, minute=0):
    return timezone.make_aware(timezone.datetime(year, month, day, hour, minute))


def make_project(owner):
    return Project.objects.create(name='Website', owner=owner)


class CreateCycleTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project = make_project(self.owner)
        Membership.objects.create(
            project=self.project, user=self.owner, role=Membership.Role.FACILITATOR
        )
        self.facil = make_user('facil')
        Membership.objects.create(
            project=self.project, user=self.facil, role=Membership.Role.FACILITATOR
        )
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)
        self.client.login(username='owner', password='correct-horse-battery-staple')

    def test_plain_member_gets_404_on_create_cycle_page(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.get(reverse('create_cycle', args=[self.project.id]))
        self.assertEqual(response.status_code, 404)

    def test_facilitator_can_open_create_page(self):
        self.client.login(username='facil', password='correct-horse-battery-staple')
        response = self.client.get(reverse('create_cycle', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        # Form pre-fills with default facilitator = project owner
        self.assertEqual(response.context['form'].initial['facilitator'], self.owner.id)

    def test_create_cycle_uses_provided_values(self):
        week_start = dt(2026, 9, 7).date()
        opens = dt(2026, 9, 7, 9)
        closes = opens + timedelta(days=7)
        response = self.client.post(
            reverse('create_cycle', args=[self.project.id]),
            {
                'week_start': week_start.isoformat(),
                'opens_at': opens.isoformat(),
                'closes_at': closes.isoformat(),
                'facilitator': self.facil.id,
            },
        )
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        cycle = FeedbackCycle.objects.get(project=self.project)
        self.assertEqual(cycle.week_start, week_start)
        self.assertEqual(cycle.facilitator, self.facil)
        self.assertEqual(cycle.status, FeedbackCycle.Status.COLLECTING)

    def test_missing_facilitator_defaults_to_owner(self):
        week_start = dt(2026, 9, 7).date()
        opens = dt(2026, 9, 7, 9)
        closes = opens + timedelta(days=7)
        self.client.post(
            reverse('create_cycle', args=[self.project.id]),
            {
                'week_start': week_start.isoformat(),
                'opens_at': opens.isoformat(),
                'closes_at': closes.isoformat(),
            },
        )
        cycle = FeedbackCycle.objects.get(project=self.project)
        self.assertEqual(cycle.facilitator, self.owner)

    def test_duplicate_open_cycle_rejected(self):
        FeedbackCycle.objects.create(
            project=self.project,
            week_start=dt(2026, 9, 7).date(),
            opens_at=dt(2026, 9, 7, 9),
            closes_at=dt(2026, 9, 14, 9),
            facilitator=self.owner,
        )
        week_start = dt(2026, 9, 14).date()
        opens = dt(2026, 9, 14, 9)
        closes = opens + timedelta(days=7)
        response = self.client.post(
            reverse('create_cycle', args=[self.project.id]),
            {
                'week_start': week_start.isoformat(),
                'opens_at': opens.isoformat(),
                'closes_at': closes.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already collecting')
        self.assertEqual(FeedbackCycle.objects.filter(project=self.project).count(), 1)

    def test_closes_before_opens_is_rejected(self):
        opens = dt(2026, 9, 7, 9)
        closes = opens - timedelta(days=1)
        response = self.client.post(
            reverse('create_cycle', args=[self.project.id]),
            {
                'week_start': opens.date().isoformat(),
                'opens_at': opens.isoformat(),
                'closes_at': closes.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Closes must be after it opens')
        self.assertFalse(FeedbackCycle.objects.filter(project=self.project).exists())

    def test_anonymous_visitor_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('create_cycle', args=[self.project.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_non_member_gets_404_on_create(self):
        make_user('stranger')
        self.client.login(username='stranger', password='correct-horse-battery-staple')
        response = self.client.get(reverse('create_cycle', args=[self.project.id]))
        self.assertEqual(response.status_code, 404)


class CloseCycleTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project = make_project(self.owner)
        Membership.objects.create(
            project=self.project, user=self.owner, role=Membership.Role.FACILITATOR
        )
        self.facil = make_user('facil')
        Membership.objects.create(
            project=self.project, user=self.facil, role=Membership.Role.FACILITATOR
        )
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)
        self.cycle = FeedbackCycle.objects.create(
            project=self.project,
            week_start=dt(2026, 9, 7).date(),
            opens_at=dt(2026, 9, 7, 9),
            closes_at=dt(2026, 9, 14, 9),
            facilitator=self.facil,
        )
        self.close_url = reverse('close_cycle', args=[self.project.id, self.cycle.id])
        self.client.login(username='member', password='correct-horse-battery-staple')

    def test_plain_member_closing_gets_404_and_cycle_stays_collecting(self):
        response = self.client.post(self.close_url)
        self.assertEqual(response.status_code, 404)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, FeedbackCycle.Status.COLLECTING)

    def test_cycle_facilitator_can_close(self):
        self.client.login(username='facil', password='correct-horse-battery-staple')
        response = self.client.post(self.close_url)
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, FeedbackCycle.Status.CLOSED)

    def test_project_facilitator_can_close(self):
        self.client.login(username='owner', password='correct-horse-battery-staple')
        response = self.client.post(self.close_url)
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, FeedbackCycle.Status.CLOSED)

    def test_anonymous_closing_is_sent_to_login(self):
        self.client.logout()
        response = self.client.post(self.close_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


class ProjectCycleDisplayTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project = make_project(self.owner)
        Membership.objects.create(
            project=self.project, user=self.owner, role=Membership.Role.FACILITATOR
        )
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)
        self.client.login(username='owner', password='correct-horse-battery-staple')

    def test_project_page_shows_no_cycle_when_none(self):
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Start a cycle')

    def test_project_page_shows_current_cycle_and_participation(self):
        cycle = FeedbackCycle.objects.create(
            project=self.project,
            week_start=dt(2026, 9, 7).date(),
            opens_at=dt(2026, 9, 7, 9),
            closes_at=dt(2026, 9, 14, 9),
            facilitator=self.member,
        )
        CycleParticipation.objects.create(cycle=cycle, user=self.member, card_count=2)
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertContains(response, '1 of 2 members have submitted')
        self.assertContains(response, 'member')
        self.assertContains(response, 'Collecting')

    def test_project_page_lists_closed_cycles(self):
        FeedbackCycle.objects.create(
            project=self.project,
            week_start=dt(2026, 8, 31).date(),
            opens_at=dt(2026, 8, 31, 9),
            closes_at=dt(2026, 9, 7, 9),
            facilitator=self.owner,
            status=FeedbackCycle.Status.CLOSED,
        )
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertContains(response, 'Previous cycles')


class CycleParticipationUniqueTests(TestCase):
    def test_unique_together_holds(self):
        owner = make_user('owner')
        project = make_project(owner)
        cycle = FeedbackCycle.objects.create(
            project=project,
            week_start=dt(2026, 9, 7).date(),
            opens_at=dt(2026, 9, 7, 9),
            closes_at=dt(2026, 9, 14, 9),
            facilitator=owner,
        )
        CycleParticipation.objects.create(cycle=cycle, user=owner)
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            dup = CycleParticipation(cycle=cycle, user=owner)
            dup.save()
