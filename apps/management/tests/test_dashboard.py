from django.test import TestCase

from apps.catalog.models import FactorVersion
from apps.catalog.services import load_catalog
from apps.management import services

from .helpers import make_admin, make_decisor, make_organization


class AdminDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_catalog()
        cls.admin = make_admin()
        unemi = make_organization()
        gad = make_organization("GAD Milagro", "milagro.gob.ec")
        make_organization("Agroexport", "agro.com", sector="privado")
        make_organization("Consultora XYZ", "xyz.com", sector="privado", is_active=False)
        make_decisor(unemi)
        make_decisor(gad, email="sofia@milagro.gob.ec")
        make_decisor(unemi, email="old@unemi.edu.ec", is_active=False)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_shows_user_counts(self):
        response = self.client.get("/gestion/")
        self.assertEqual(response.context["summary"]["users_active"], 3)
        self.assertEqual(response.context["summary"]["users_inactive"], 1)
        self.assertContains(response, "Panel de administración")
        self.assertContains(response, "Ver usuarios")

    def test_shows_organization_counts_and_sectors(self):
        response = self.client.get("/gestion/")
        summary = response.context["summary"]
        self.assertEqual((summary["organizations_active"], summary["organizations_inactive"]), (3, 1))
        self.assertContains(response, "2 públicas · 1 privada. Las desactivadas conservan sus evaluaciones.")
        self.assertContains(response, "Gestionar organizaciones")

    def test_shows_active_catalog_without_draft(self):
        response = self.client.get("/gestion/")
        self.assertContains(response, "v2 vigente")
        self.assertContains(response, "Factores")
        self.assertContains(response, "Subfactores")
        self.assertEqual(response.context["summary"]["factors"], 18)
        self.assertEqual(response.context["summary"]["subfactors"], 61)
        self.assertNotContains(response, "Cambios sin publicar")
        self.assertNotContains(response, "Revisar y publicar")
        self.assertContains(response, "Ir al catálogo")

    def test_shows_pending_changes_of_the_draft(self):
        draft = services.create_draft()
        factor_value = draft.factor_values.first()
        other_scope = "externo" if factor_value.default_scope == "interno" else "interno"
        services.update_draft_factor(
            draft, factor_value.factor, factor_value.suggested_importance % 4 + 1, other_scope
        )
        response = self.client.get("/gestion/")
        self.assertEqual(response.context["summary"]["draft_changes"], 2)
        self.assertContains(response, "Cambios sin publicar")
        self.assertContains(response, f"/gestion/catalogo/{draft.number}/publicar/")

    def test_does_not_build_registration_requests(self):
        response = self.client.get("/gestion/")
        self.assertNotContains(response, "Solicitudes de registro pendientes")
        self.assertNotContains(response, "Aprobar")
        self.assertNotContains(response, "por atender")

    def test_draft_fixture_does_not_touch_active_values(self):
        before = list(FactorVersion.objects.filter(version__number=2).values_list("suggested_importance", flat=True))
        services.create_draft()
        after = list(FactorVersion.objects.filter(version__number=2).values_list("suggested_importance", flat=True))
        self.assertEqual(before, after)
