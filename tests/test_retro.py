from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cycles.models import FeedbackCycle
from projects.models import Membership, Project
from projects.permissions import can_facilitate
from retro.models import Retrospective


def make_user(username, password='correct-horse-battery-staple'):
    return User.objects.create_user(username=username, password=password)


def dt(year, month, day, hour=0, minute=0):
    return timezone.make_aware(timezone.datetime(year, month, day, hour, minute))


def make_closed_cycle(owner, *, facilitator=None):
    project = Project.objects.create(name='Website', owner=owner)
    Membership.objects.create(project=project, user=owner, role=Membership.Role.FACILITATOR)
    cycle = FeedbackCycle.objects.create(
        project=project,
        week_start=dt(2026, 9, 14).date(),
        opens_at=dt(2026, 9, 14),
        closes_at=dt(2026, 9, 21),
        facilitator=facilitator or owner,
        status=FeedbackCycle.Status.CLOSED,
    )
    return project, cycle


def join(project, username, role=Membership.Role.MEMBER):
    user = make_user(username)
    Membership.objects.create(project=project, user=user, role=role)
    return user


class CreateRetroTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_closed_cycle(self.owner)
        self.facilitator = join(self.project, 'facilitator', Membership.Role.FACILITATOR)
        self.member = join(self.project, 'member')

    def test_facilitator_can_start_retro(self):
        self.client.login(username='facilitator', password='correct-horse-battery-staple')
        response = self.client.post(reverse('create_retro', args=[self.project.id, self.cycle.id]))
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        retro = Retrospective.objects.get(cycle=self.cycle)
        self.assertEqual(retro.stage, Retrospective.Stage.DRAFT)
        self.assertEqual(retro.version, 0)
        self.assertEqual(retro.votes_per_member, 3)

    def test_owner_can_start_retro(self):
        self.client.login(username='owner', password='correct-horse-battery-staple')
        self.client.post(reverse('create_retro', args=[self.project.id, self.cycle.id]))
        self.assertEqual(Retrospective.objects.filter(cycle=self.cycle).count(), 1)

    def test_at_most_one_retro_per_cycle(self):
        retro = Retrospective.objects.create(cycle=self.cycle)
        self.client.login(username='owner', password='correct-horse-battery-staple')
        response = self.client.post(reverse('create_retro', args=[self.project.id, self.cycle.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Retrospective.objects.filter(cycle=self.cycle).count(), 1)
        self.assertEqual(Retrospective.objects.get(id=retro.id).version, 0)

    def test_plain_member_gets_403(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.post(reverse('create_retro', args=[self.project.id, self.cycle.id]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Retrospective.objects.filter(cycle=self.cycle).exists())

    def test_cycle_designated_facilitator_can_start(self):
        self.client.login(username='owner', password='correct-horse-battery-staple')
        # designated facilitator is already owner here; test a separate cycle
        # whose designated facilitator is a plain member
        other_cycle = FeedbackCycle.objects.create(
            project=self.project,
            week_start=dt(2026, 9, 28).date(),
            opens_at=dt(2026, 9, 28),
            closes_at=dt(2026, 10, 5),
            facilitator=self.member,
            status=FeedbackCycle.Status.CLOSED,
        )
        self.client.logout()
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.post(reverse('create_retro', args=[self.project.id, other_cycle.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Retrospective.objects.filter(cycle=other_cycle).exists())


class CreateRetroGuardTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_closed_cycle(self.owner)

    def test_anonymous_visitor_sent_to_login(self):
        response = self.client.post(reverse('create_retro', args=[self.project.id, self.cycle.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_non_member_gets_404(self):
        make_user('stranger')
        self.client.login(username='stranger', password='correct-horse-battery-staple')
        response = self.client.post(reverse('create_retro', args=[self.project.id, self.cycle.id]))
        self.assertEqual(response.status_code, 404)


class CreateRetroCollectingGuardTests(TestCase):
    def test_cannot_start_on_collecting_cycle(self):
        owner = make_user('owner')
        project = Project.objects.create(name='Website', owner=owner)
        Membership.objects.create(project=project, user=owner, role=Membership.Role.FACILITATOR)
        cycle = FeedbackCycle.objects.create(
            project=project,
            week_start=dt(2026, 9, 14).date(),
            opens_at=dt(2026, 9, 14),
            closes_at=dt(2026, 9, 21),
            facilitator=owner,
        )
        self.client.login(username='owner', password='correct-horse-battery-staple')
        response = self.client.post(reverse('create_retro', args=[project.id, cycle.id]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Retrospective.objects.filter(cycle=cycle).exists())


class CanFacilitateTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_closed_cycle(self.owner)

    def test_returns_true_for_cycle_facilitator(self):
        member_facilitator = join(self.project, 'member_facilitator')
        self.cycle.facilitator = member_facilitator
        self.cycle.save()
        retro = Retrospective.objects.create(cycle=self.cycle)
        self.assertTrue(can_facilitate(member_facilitator, retro))

    def test_returns_true_for_project_facilitator_and_owner(self):
        retro = Retrospective.objects.create(cycle=self.cycle)
        facilitator = join(self.project, 'facilitator', Membership.Role.FACILITATOR)
        self.assertTrue(can_facilitate(facilitator, retro))
        self.assertTrue(can_facilitate(self.owner, retro))

    def test_returns_false_for_plain_member(self):
        member = join(self.project, 'member')
        retro = Retrospective.objects.create(cycle=self.cycle)
        self.assertFalse(can_facilitate(member, retro))

    def test_returns_false_for_non_member(self):
        stranger = make_user('stranger')
        retro = Retrospective.objects.create(cycle=self.cycle)
        self.assertFalse(can_facilitate(stranger, retro))
        self.assertFalse(can_facilitate(None, retro))


class ProjectPageRetroPanelTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project, self.cycle = make_closed_cycle(self.owner)
        self.member = join(self.project, 'member')

    def test_facilitator_sees_start_action_on_closed_cycle(self):
        self.client.login(username='owner', password='correct-horse-battery-staple')
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertContains(response, 'Start retrospective')

    def test_plain_member_does_not_see_start_action(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertNotContains(response, 'Start retrospective')

    def test_stage_shown_once_retro_exists(self):
        Retrospective.objects.create(cycle=self.cycle)
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertContains(response, 'Draft')
        self.assertNotContains(response, 'Start retrospective')
