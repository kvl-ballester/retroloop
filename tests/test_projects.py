from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from projects.models import Membership, Project
from projects.permissions import is_facilitator, is_member


def make_user(username='alice', password='correct-horse-battery-staple'):
    return User.objects.create_user(username=username, password=password)


class HomeProjectListTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_anonymous_home_has_no_project_controls(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('create_project'))

    def test_logged_in_home_shows_new_project_control(self):
        self.client.login(username='alice', password='correct-horse-battery-staple')
        response = self.client.get(reverse('home'))
        self.assertContains(response, reverse('create_project'))

    def test_logged_in_home_lists_projects_user_belongs_to(self):
        project = Project.objects.create(name='Website', owner=self.user)
        Membership.objects.create(project=project, user=self.user)
        other = make_user('bob')
        other_project = Project.objects.create(name='Other', owner=other)
        Membership.objects.create(project=other_project, user=other)
        self.client.login(username='alice', password='correct-horse-battery-staple')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Website')
        self.assertNotContains(response, 'Other')


class CreateProjectTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.login(username='alice', password='correct-horse-battery-staple')

    def test_anonymous_cannot_create_project(self):
        self.client.logout()
        response = self.client.get(reverse('create_project'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_create_page_renders_name_field_only(self):
        response = self.client.get(reverse('create_project'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['form'].fields), ['name'])
        self.assertContains(response, 'name="name"')

    def test_create_project_creates_project_and_owner_facilitator_membership(self):
        response = self.client.post(reverse('create_project'), {'name': 'Website'})
        project = Project.objects.get(name='Website')
        self.assertRedirects(response, reverse('project_detail', args=[project.id]))
        self.assertEqual(project.owner, self.user)
        membership = Membership.objects.get(project=project, user=self.user)
        self.assertEqual(membership.role, Membership.Role.FACILITATOR)
        self.assertIsNotNone(project.join_token)

    def test_blank_name_rerenders_with_error(self):
        response = self.client.post(reverse('create_project'), {'name': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required.')


class ProjectDetailTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project = Project.objects.create(name='Website', owner=self.owner)
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)

    def test_logged_out_visitor_is_sent_to_login(self):
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_authenticated_non_member_gets_404(self):
        make_user('stranger')
        self.client.login(username='stranger', password='correct-horse-battery-staple')
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertEqual(response.status_code, 404)

    def test_member_sees_join_url_members_and_no_facilitator_control(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        join_path = reverse('join_project', kwargs={'token': self.project.join_token})
        self.assertContains(response, join_path)
        self.assertContains(response, 'member')
        self.assertContains(response, 'Member')
        self.assertNotContains(response, reverse('rotate_join_link', args=[self.project.id]))

    def test_owner_sees_facilitator_rotate_control(self):
        self.client.login(username='owner', password='correct-horse-battery-staple')
        response = self.client.get(reverse('project_detail', args=[self.project.id]))
        self.assertContains(response, reverse('rotate_join_link', args=[self.project.id]))


class JoinProjectTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project = Project.objects.create(name='Website', owner=self.owner)

    def test_visitor_joins_and_lands_on_project_page(self):
        visitor = make_user('carol')
        self.client.login(username='carol', password='correct-horse-battery-staple')
        join_path = reverse('join_project', kwargs={'token': self.project.join_token})
        response = self.client.get(join_path)
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        membership = Membership.objects.get(project=self.project, user=visitor)
        self.assertEqual(membership.role, Membership.Role.MEMBER)

    def test_existing_member_rejoining_creates_no_duplicate(self):
        self.client.login(username='owner', password='correct-horse-battery-staple')
        join_path = reverse('join_project', kwargs={'token': self.project.join_token})
        response = self.client.get(join_path)
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        self.assertEqual(
            Membership.objects.filter(project=self.project, user=self.owner).count(), 0
        )

    def test_logged_out_visitor_is_sent_to_login_and_redirects_back(self):
        join_path = reverse('join_project', kwargs={'token': self.project.join_token})
        response = self.client.get(join_path)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
        self.assertIn(join_path, response.url)

    def test_render_linked(self):
        # Verify the join links and the redirect target resolve cleanly.
        self.assertTrue(reverse('join_project', kwargs={'token': self.project.join_token}))
        self.assertTrue(reverse('project_detail', args=[self.project.id]))

    def test_unknown_token_returns_404_and_creates_no_membership(self):
        make_user('dave')
        self.client.login(username='dave', password='correct-horse-battery-staple')
        from uuid import uuid4

        response = self.client.get(reverse('join_project', kwargs={'token': uuid4()}))
        self.assertEqual(response.status_code, 404)


class RotateJoinLinkTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project = Project.objects.create(name='Website', owner=self.owner)
        self.facil = make_user('facil')
        Membership.objects.create(
            project=self.project, user=self.facil, role=Membership.Role.FACILITATOR
        )
        self.member = make_user('member')
        Membership.objects.create(project=self.project, user=self.member)
        self.old_token = self.project.join_token
        self.old_path = reverse('join_project', kwargs={'token': self.old_token})

    def test_owner_rotates_and_old_link_breaks_new_one_works(self):
        self.client.login(username='owner', password='correct-horse-battery-staple')
        rotate_url = reverse('rotate_join_link', args=[self.project.id])
        response = self.client.post(rotate_url)
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        self.project.refresh_from_db()
        self.assertNotEqual(self.project.join_token, self.old_token)
        # old link now 404s
        make_user('stranger2')
        self.client.login(username='stranger2', password='correct-horse-battery-staple')
        self.assertEqual(self.client.get(self.old_path).status_code, 404)
        # new link works
        new_path = reverse('join_project', kwargs={'token': self.project.join_token})
        self.assertEqual(self.client.get(new_path).status_code, 302)

    def test_facilitator_can_rotate(self):
        self.client.login(username='facil', password='correct-horse-battery-staple')
        rotate_url = reverse('rotate_join_link', args=[self.project.id])
        response = self.client.post(rotate_url)
        self.assertRedirects(response, reverse('project_detail', args=[self.project.id]))
        self.project.refresh_from_db()
        self.assertNotEqual(self.project.join_token, self.old_token)

    def test_plain_member_gets_404_and_token_unchanged(self):
        self.client.login(username='member', password='correct-horse-battery-staple')
        rotate_url = reverse('rotate_join_link', args=[self.project.id])
        response = self.client.post(rotate_url)
        self.assertEqual(response.status_code, 404)
        self.project.refresh_from_db()
        self.assertEqual(self.project.join_token, self.old_token)

    def test_non_member_gets_404(self):
        make_user('stranger3')
        self.client.login(username='stranger3', password='correct-horse-battery-staple')
        rotate_url = reverse('rotate_join_link', args=[self.project.id])
        self.assertEqual(self.client.post(rotate_url).status_code, 404)


class PermissionPredicateTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.project = Project.objects.create(name='Website', owner=self.owner)

    def test_owner_is_member_and_facilitator_without_membership_row(self):
        self.assertTrue(is_member(self.owner, self.project))
        self.assertTrue(is_facilitator(self.owner, self.project))

    def test_plain_member_is_member_not_facilitator(self):
        member = make_user('member')
        Membership.objects.create(project=self.project, user=member)
        self.assertTrue(is_member(member, self.project))
        self.assertFalse(is_facilitator(member, self.project))

    def test_facilitator_role_is_facilitator(self):
        facil = make_user('facil')
        Membership.objects.create(
            project=self.project, user=facil, role=Membership.Role.FACILITATOR
        )
        self.assertTrue(is_facilitator(facil, self.project))

    def test_non_member_and_anonymous_false(self):
        stranger = make_user('stranger')
        self.assertFalse(is_member(stranger, self.project))
        self.assertFalse(is_facilitator(stranger, self.project))
        self.assertFalse(is_member(None, self.project))
        self.assertFalse(is_facilitator(None, self.project))

    def test_facilitator_of_one_project_not_other(self):
        other_owner = make_user('other_owner')
        other = Project.objects.create(name='Other', owner=other_owner)
        facil = make_user('facil')
        Membership.objects.create(
            project=self.project, user=facil, role=Membership.Role.FACILITATOR
        )
        self.assertTrue(is_facilitator(facil, self.project))
        self.assertFalse(is_facilitator(facil, other))
        self.assertFalse(is_member(facil, other))

    def test_is_member_of_project_aliases(self):
        member = make_user('member')
        Membership.objects.create(project=self.project, user=member)
        from projects.permissions import is_facilitator_of_project, is_member_of_project

        self.assertTrue(is_member_of_project(member, self.project))
        self.assertTrue(is_facilitator_of_project(self.owner, self.project))
