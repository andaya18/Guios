import os
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import User


class ProvisionTestUsersCommandTests(TestCase):
    environment = {
        "GUIOS_TEST_ADMIN_EMAIL": "admin@pruebas.edu.ec",
        "GUIOS_TEST_DECISOR_EMAIL": "decisor@pruebas.edu.ec",
        "GUIOS_TEST_ADMIN_PASSWORD": "V3rdeCascada2026!",
        "GUIOS_TEST_DECISOR_PASSWORD": "N4r4njaMontana2026!",
    }

    def setUp(self):
        self.environment_patch = patch.dict(os.environ, self.environment, clear=False)
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)

    def test_requires_confirmation(self):
        with self.assertRaisesMessage(CommandError, "con --confirm"):
            call_command("provision_test_users")

        self.assertEqual(User.objects.count(), 0)

    def test_creates_admin_and_decisor_with_same_password(self):
        call_command("provision_test_users", confirm=True)

        admin = User.objects.get(email=self.environment["GUIOS_TEST_ADMIN_EMAIL"])
        decisor = User.objects.get(email=self.environment["GUIOS_TEST_DECISOR_EMAIL"])
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertEqual(admin.role, "administrador")
        self.assertEqual(decisor.role, "decisor")
        self.assertFalse(decisor.is_staff)
        self.assertTrue(
            admin.check_password(self.environment["GUIOS_TEST_ADMIN_PASSWORD"])
        )
        self.assertTrue(
            decisor.check_password(self.environment["GUIOS_TEST_DECISOR_PASSWORD"])
        )

    def test_existing_users_are_not_modified(self):
        call_command("provision_test_users", confirm=True)
        original_password = self.environment["GUIOS_TEST_ADMIN_PASSWORD"]
        os.environ["GUIOS_TEST_ADMIN_PASSWORD"] = "OtraClaveSegura2026!"

        with self.assertRaisesMessage(CommandError, "no coincide"):
            call_command("provision_test_users", confirm=True)

        self.assertTrue(
            User.objects.get(email=self.environment["GUIOS_TEST_ADMIN_EMAIL"]).check_password(
                original_password
            )
        )

    def test_rejects_reusing_one_email_for_both_roles(self):
        os.environ["GUIOS_TEST_DECISOR_EMAIL"] = self.environment["GUIOS_TEST_ADMIN_EMAIL"]

        with self.assertRaisesMessage(CommandError, "correos distintos"):
            call_command("provision_test_users", confirm=True)

        self.assertEqual(User.objects.count(), 0)
