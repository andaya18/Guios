from django.test import TestCase

from apps.catalog.models import CatalogVersion, Factor, FactorVersion
from apps.catalog.services import load_catalog
from apps.management import services

from .helpers import make_admin

PUBLISH_DATA = {
    "justification": "Revisión bibliográfica 2026",
    "authorized_by": "PhD. Victor Hugo Rea Sanchez",
    "name": "Actualización 2026",
    "authorized_at": "2026-11-10",
    "confirmed": "on",
}


class CatalogViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_catalog()
        cls.admin = make_admin()

    def setUp(self):
        self.client.force_login(self.admin)

    def test_versions_page_lists_versions_with_status(self):
        response = self.client.get("/gestion/catalogo/")
        self.assertContains(response, "Catálogo metodológico")
        self.assertContains(response, "3 dimensiones · 18 factores · 61 subfactores")
        self.assertEqual([v.number for v in response.context["versions"]], [2, 1])
        self.assertContains(response, '<span class="pill pill--draft">Activa</span>', html=True)
        self.assertContains(response, '<span class="pill pill--neutral">Publicada</span>', html=True)
        self.assertContains(response, "Marcar como activa", count=1)

    def test_versions_page_shows_who_published(self):
        self.client.post("/gestion/catalogo/nueva/")
        number = CatalogVersion.objects.get(status="borrador").number
        self.client.post(f"/gestion/catalogo/{number}/publicar/", PUBLISH_DATA)

        response = self.client.get("/gestion/catalogo/")

        self.assertContains(response, "<th>Por</th>", html=False)
        self.assertContains(response, self.admin.get_full_name())
        self.assertContains(response, "Sistema")

    def test_versions_page_shows_changes_of_the_active_version(self):
        response = self.client.get("/gestion/catalogo/")
        self.assertContains(response, "Cambios de v2")
        self.assertEqual(len(response.context["changes"]), 6)

    def test_compare_highlights_the_six_differences(self):
        response = self.client.get("/gestion/catalogo/comparar/?a=1&b=2")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cambios de v2 respecto a v1")
        self.assertContains(response, "data-change", count=6)

    def test_compare_with_unknown_version_is_404(self):
        self.assertEqual(self.client.get("/gestion/catalogo/comparar/?a=1&b=9").status_code, 404)
        self.assertEqual(self.client.get("/gestion/catalogo/comparar/?a=x&b=2").status_code, 404)

    def test_activate_published_version(self):
        response = self.client.post("/gestion/catalogo/1/activar/")
        self.assertRedirects(response, "/gestion/catalogo/")
        self.assertEqual(CatalogVersion.objects.get(status="activa").number, 1)

    def test_create_draft_redirects_to_editor(self):
        response = self.client.post("/gestion/catalogo/nueva/")
        self.assertRedirects(response, "/gestion/catalogo/3/")
        self.assertEqual(CatalogVersion.objects.get(number=3).status, "borrador")

    def test_editor_of_active_version_is_read_only(self):
        response = self.client.get("/gestion/catalogo/2/")
        self.assertContains(response, "Crear versión en borrador")
        self.assertNotContains(response, "Guardar en borrador")
        self.assertNotContains(response, "Agregar nuevo factor")
        self.assertNotContains(response, "Agregar subfactor")

    def test_editor_shows_selected_factor_with_subfactors(self):
        draft = services.create_draft()
        factor = Factor.objects.get(name="Formación")
        response = self.client.get(f"/gestion/catalogo/{draft.number}/?factor={factor.pk}")
        self.assertContains(response, "Guardar en borrador")
        self.assertContains(response, "Subfactores (4)")
        self.assertContains(response, "Organizacional")
        self.assertNotContains(response, "Ambos")
        self.assertNotContains(response, "Quitar")

    def test_editor_saves_factor_values_in_draft(self):
        draft = services.create_draft()
        factor = Factor.objects.get(name="Formación")
        response = self.client.post(
            f"/gestion/catalogo/{draft.number}/?factor={factor.pk}",
            {"suggested_importance": "2", "default_scope": "externo"},
        )
        self.assertRedirects(response, f"/gestion/catalogo/{draft.number}/?factor={factor.pk}")
        value = FactorVersion.objects.get(version=draft, factor=factor)
        self.assertEqual((value.suggested_importance, value.default_scope), (2, "externo"))
        page = self.client.get(f"/gestion/catalogo/{draft.number}/?factor={factor.pk}")
        self.assertContains(page, "Modificado")
        self.assertRegex(page.content.decode(), r"[12] cambios? sin publicar")

    def test_posting_to_active_version_changes_nothing(self):
        factor = Factor.objects.get(name="Formación")
        before = FactorVersion.objects.get(version__number=2, factor=factor)
        response = self.client.post(
            f"/gestion/catalogo/2/?factor={factor.pk}",
            {"suggested_importance": "1", "default_scope": "externo"},
        )
        self.assertEqual(response.status_code, 403)
        after = FactorVersion.objects.get(version__number=2, factor=factor)
        self.assertEqual(
            (after.suggested_importance, after.default_scope),
            (before.suggested_importance, before.default_scope),
        )

    def test_publish_page_lists_changes_against_active(self):
        draft = services.create_draft()
        factor = Factor.objects.get(name="Formación")
        services.update_draft_factor(draft, factor, 1, "externo")
        response = self.client.get(f"/gestion/catalogo/{draft.number}/publicar/")
        self.assertContains(response, "Revisar y publicar cambios")
        self.assertContains(response, "Paso obligatorio: solo se publican cambios validados y autorizados (RF-22).")
        self.assertContains(response, "Cambios respecto a v2")
        self.assertContains(response, "Publicar versión v3")
        self.assertGreaterEqual(len(response.context["changes"]), 1)

    def test_publish_requires_validation_fields(self):
        draft = services.create_draft()
        response = self.client.post(f"/gestion/catalogo/{draft.number}/publicar/", {"name": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo es obligatorio.")
        draft.refresh_from_db()
        self.assertEqual(draft.status, "borrador")

    def test_publish_page_has_authorization_date_and_disabled_button(self):
        draft = services.create_draft()

        response = self.client.get(f"/gestion/catalogo/{draft.number}/publicar/")

        self.assertContains(response, "Fecha de autorización *")
        self.assertContains(response, 'type="date"')
        self.assertContains(response, "data-publish-submit disabled")

    def test_publish_records_the_authorization_date(self):
        import datetime

        draft = services.create_draft()

        self.client.post(f"/gestion/catalogo/{draft.number}/publicar/", PUBLISH_DATA)

        draft.refresh_from_db()
        self.assertEqual(draft.authorized_at, datetime.date(2026, 11, 10))

    def test_authorization_date_cannot_be_in_the_future(self):
        draft = services.create_draft()

        response = self.client.post(f"/gestion/catalogo/{draft.number}/publicar/", {**PUBLISH_DATA, "authorized_at": "2999-01-01"})

        self.assertContains(response, "La fecha de autorización no puede ser futura.")
        draft.refresh_from_db()
        self.assertEqual(draft.status, "borrador")

    def test_publish_activates_the_draft(self):
        draft = services.create_draft()
        response = self.client.post(f"/gestion/catalogo/{draft.number}/publicar/", PUBLISH_DATA)
        self.assertRedirects(response, "/gestion/catalogo/")
        draft.refresh_from_db()
        self.assertEqual(draft.status, "activa")
        self.assertEqual(draft.authorized_by, "PhD. Victor Hugo Rea Sanchez")
        self.assertEqual(CatalogVersion.objects.get(number=2).status, "publicada")

    def test_publish_page_of_published_version_is_403(self):
        self.assertEqual(self.client.get("/gestion/catalogo/1/publicar/").status_code, 403)
        response = self.client.post("/gestion/catalogo/1/publicar/", PUBLISH_DATA)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(CatalogVersion.objects.get(number=1).status, "publicada")
