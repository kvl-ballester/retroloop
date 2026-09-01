from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class SignupViewTests(TestCase):
    def test_signup_page_renders_exactly_three_fields(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['form'].fields), ['username', 'password1', 'password2']
        )
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')
        self.assertNotContains(response, 'name="email"')

    def test_valid_signup_creates_user_logs_in_and_redirects_home(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'alice',
                'password1': 'correct-horse-battery-staple',
                'password2': 'correct-horse-battery-staple',
            },
        )
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(username='alice')
        self.assertEqual(self.client.session['_auth_user_id'], str(user.pk))
        self.assertTrue(user.is_authenticated)

    def test_new_user_password_is_stored_hashed(self):
        raw = 'correct-horse-battery-staple'
        self.client.post(
            reverse('signup'),
            {'username': 'alice', 'password1': raw, 'password2': raw},
        )
        user = User.objects.get(username='alice')
        self.assertNotEqual(user.password, raw)
        self.assertTrue(user.password.startswith(('pbkdf2_', 'argon2', 'bcrypt', 'scrypt')))
        self.assertTrue(user.check_password(raw))

    def test_duplicate_username_rerenders_with_error_and_creates_no_user(self):
        User.objects.create_user(username='alice', password='some-password')
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'alice',
                'password1': 'correct-horse-battery-staple',
                'password2': 'correct-horse-battery-staple',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A user with that username already exists')
        self.assertEqual(User.objects.count(), 1)

    def test_password_validators_rerender_with_matching_error_and_creates_no_user(self):
        cases = [
            ('too-short', 'pw1', 'too short'),
            ('common', 'password', 'too common'),
            ('numeric', '12345678', 'entirely numeric'),
        ]
        for username, password, fragment in cases:
            with self.subTest(case=username):
                response = self.client.post(
                    reverse('signup'),
                    {'username': username, 'password1': password, 'password2': password},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, fragment, msg_prefix=username)
                self.assertFalse(User.objects.filter(username=username).exists())

    def test_password_similar_to_username_rerenders_with_error(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'alice',
                'password1': 'alice123',
                'password2': 'alice123',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'too similar to the username')
        self.assertFalse(User.objects.filter(username='alice').exists())

    def test_logged_in_user_visiting_signup_is_redirected_home(self):
        User.objects.create_user(username='bob', password='some-password')
        self.assertTrue(self.client.login(username='bob', password='some-password'))
        response = self.client.get(reverse('signup'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(response.url, reverse('home'))


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice', password='correct-horse-battery-staple'
        )

    def test_login_page_renders_username_and_password_form(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertEqual(list(response.context['form'].fields), ['username', 'password'])

    def test_valid_credentials_log_in_and_redirect_home(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'alice', 'password': 'correct-horse-battery-staple'},
        )
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(self.client.session['_auth_user_id'], str(self.user.pk))

    def test_login_honors_next(self):
        response = self.client.post(
            reverse('login') + '?next=/next-page/',
            {'username': 'alice', 'password': 'correct-horse-battery-staple'},
        )
        self.assertRedirects(response, '/next-page/', fetch_redirect_response=False)
        self.assertEqual(response.url, '/next-page/')

    def test_invalid_credentials_rerender_with_generic_error_and_no_session(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'alice', 'password': 'wrong-password'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Please enter a correct username and password. Note that both fields may be '
            'case-sensitive.',
        )
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn('username', response.context['form'].errors)
        self.assertNotIn('password', response.context['form'].errors)
        self.assertIn('__all__', response.context['form'].errors)

    def test_logged_in_user_visiting_login_is_redirected_home(self):
        self.client.login(username='alice', password='correct-horse-battery-staple')
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(response.url, reverse('home'))


class HomeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice', password='correct-horse-battery-staple'
        )

    def test_anonymous_home_shows_signup_login_links_and_no_account_controls(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("signup")}"')
        self.assertContains(response, f'href="{reverse("login")}"')
        self.assertNotContains(response, reverse('logout'))
        self.assertNotContains(response, 'alice')

    def test_logged_in_home_shows_username_and_logout_link(self):
        self.client.login(username='alice', password='correct-horse-battery-staple')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alice')
        self.assertContains(response, f'action="{reverse("logout")}"')

    def test_logout_link_clears_session_and_home_returns_to_anonymous(self):
        self.client.login(username='alice', password='correct-horse-battery-staple')
        self.client.get(reverse('home'))
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('_auth_user_id', self.client.session)
        home = self.client.get(reverse('home'))
        self.assertNotContains(home, 'alice')
        self.assertContains(home, f'href="{reverse("signup")}"')


class CrossLinkTests(TestCase):
    def test_login_and_signup_pages_link_to_each_other(self):
        login_page = self.client.get(reverse('login'))
        self.assertContains(login_page, f'href="{reverse("signup")}"')
        signup_page = self.client.get(reverse('signup'))
        self.assertContains(signup_page, f'href="{reverse("login")}"')


class SessionLifecycleTests(TestCase):
    def test_full_journey(self):
        signup = self.client.post(
            reverse('signup'),
            {
                'username': 'alice',
                'password1': 'correct-horse-battery-staple',
                'password2': 'correct-horse-battery-staple',
            },
        )
        self.assertRedirects(signup, reverse('home'))
        self.assertIn('_auth_user_id', self.client.session)
        home = self.client.get(reverse('home'))
        self.assertContains(home, 'alice')
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotContains(self.client.get(reverse('home')), 'alice')
