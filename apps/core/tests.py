from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.core.context_processors import organization_label
from apps.core.templatetags.ui import ago_short, pm


class ShellTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        self.user = User.objects.create_user(
            email="maria@unemi.edu.ec", password="Correcta123", first_name="María",
            last_name="Pérez", organization=self.organization, area="Dirección TIC",
        )

    def test_organization_label_includes_area_only_when_present(self):
        self.assertEqual(organization_label(self.user), "UNEMI – Dirección TIC")
        self.user.area = ""
        self.assertEqual(organization_label(self.user), "UNEMI")

    def test_decisor_dashboard_uses_shell_and_greets_user(self):
        self.client.force_login(self.user)

        response = self.client.get("/")

        for text in ("Hola, María", "Este es el avance de tus evaluaciones.", "Panel de inicio",
                     "UNEMI – Dirección TIC", "+ Nueva evaluación", "Aún no has finalizado evaluaciones",
                     "Ayuda · Guía GUIOS", "Decisor · UNEMI – Dirección TIC"):
            self.assertContains(response, text)

    def test_admin_is_sent_to_management_panel(self):
        admin = User.objects.create_user(email="admin@guios.local", password="Correcta123", role="administrador")
        self.client.force_login(admin)

        self.assertRedirects(self.client.get("/"), "/gestion/", fetch_redirect_response=False)


class FilterTests(TestCase):
    def test_pm_uses_two_decimals_and_comma(self):
        self.assertEqual(pm(Decimal("2.875")), "2,88")
        self.assertEqual(pm(Decimal("3")), "3,00")

    def test_ago_short_compacts_hours(self):
        self.assertEqual(ago_short(timezone.now() - timedelta(hours=2, minutes=5)), "2 h")
