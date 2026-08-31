from django.core.management import call_command
from django.test import SimpleTestCase


class SmokeTests(SimpleTestCase):
    def test_settings_load(self):
        from django.conf import settings

        self.assertTrue(settings.INSTALLED_APPS)

    def test_system_checks_pass(self):
        call_command('check')

    def test_installed_apps_are_configured(self):
        from django.apps import apps

        for label in ['admin', 'auth', 'contenttypes']:
            with self.subTest(app=label):
                self.assertTrue(apps.get_app_config(label))
