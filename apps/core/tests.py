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


class HelpAndErrorPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("cargar_catalogo", verbosity=0)
        cls.organization = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        cls.decisor = User.objects.create_user(
            email="maria@unemi.edu.ec", password="Correcta123", first_name="María", organization=cls.organization,
        )
        cls.admin = User.objects.create_user(email="admin@guios.local", password="Correcta123", role="administrador")

    def test_help_requires_login(self):
        self.assertRedirects(self.client.get("/ayuda/"), "/acceso/?next=/ayuda/", fetch_redirect_response=False)

    def test_help_shows_guide_sections_and_catalog_factors(self):
        self.client.force_login(self.decisor)

        response = self.client.get("/ayuda/")

        for text in ("Guía GUIOS", "Cómo funciona · 6 pasos en 3 etapas", "Escalas", "Clasificación FODA",
                     "Analizar y posponer la adopción", "Los 18 factores", "Tecnológica · 9 factores",
                     "Organizacional · 8 factores", "Económica · 1 factor", "Compatibilidad"):
            self.assertContains(response, text)

    def test_help_is_available_to_administrators_with_their_shell(self):
        self.client.force_login(self.admin)

        response = self.client.get("/ayuda/")

        self.assertContains(response, "Catálogo metodológico")
        self.assertNotContains(response, "+ Nueva evaluación")

    def test_403_page_matches_figma_copy(self):
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory

        from apps.core.views import permission_denied

        request = RequestFactory().get("/gestion/")
        request.user = self.decisor
        response = permission_denied(request, PermissionDenied())

        self.assertEqual(response.status_code, 403)
        for text in ("403", "No tienes permiso para ver esta página", "Esta sección es solo para administradores.", "Volver al panel"):
            self.assertIn(text, response.content.decode())

    def test_404_page_uses_same_design(self):
        from django.test import RequestFactory

        from apps.core.views import page_not_found

        request = RequestFactory().get("/no-existe/")
        request.user = self.decisor
        response = page_not_found(request, Exception())

        self.assertEqual(response.status_code, 404)
        self.assertIn("No encontramos esta página", response.content.decode())


class FilterTests(TestCase):
    def test_pm_uses_two_decimals_and_comma(self):
        self.assertEqual(pm(Decimal("2.875")), "2,88")
        self.assertEqual(pm(Decimal("3")), "3,00")

    def test_ago_short_compacts_hours(self):
        self.assertEqual(ago_short(timezone.now() - timedelta(hours=2, minutes=5)), "2 h")
