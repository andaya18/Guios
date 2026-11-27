from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import CatalogVersion, Factor, FactorVersion
from apps.literature.models import Citation, Document, ImportanceRun
from apps.literature.tests.test_services import FakeVerifier
from apps.management.tests.helpers import make_admin, make_decisor, make_organization

URL = "/gestion/catalogo/importancia-sugerida/"


class SuggestedImportanceViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", verbosity=0)
        call_command("cargar_literatura", verbosity=0)
        cls.admin = make_admin()

    def setUp(self):
        self.client.force_login(self.admin)

    def test_decisor_gets_403(self):
        self.client.force_login(make_decisor(make_organization()))

        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_without_ai_shows_fallback_clearly(self):
        response = self.client.get(URL)

        self.assertContains(response, "Valores de respaldo")
        self.assertContains(response, "La IA no está configurada")
        self.assertContains(response, "Butler et al. (2022)")
        self.assertEqual(ImportanceRun.objects.get().origin, "respaldo")

    def test_with_ai_shows_formula_values_and_sources(self):
        with patch("apps.literature.services.get_verifier", return_value=FakeVerifier()):
            self.client.post(f"{URL}recalcular/")
            response = self.client.get(URL)

        self.assertContains(response, "Calculada con IA")
        self.assertContains(response, "fake-model")
        self.assertContains(response, "https://example.org")
        self.assertContains(response, "Justificación breve.")

    def test_get_twice_does_not_call_ai_again(self):
        with patch("apps.literature.services.get_verifier", return_value=FakeVerifier()):
            self.client.get(URL)
        verifier = FakeVerifier()
        with patch("apps.literature.services.get_verifier", return_value=verifier):
            self.client.get(URL)

        self.assertEqual(verifier.calls, [])

    def test_deleting_a_citation_recalculates_on_next_view(self):
        with patch("apps.literature.services.get_verifier", return_value=FakeVerifier()):
            self.client.post(f"{URL}recalcular/")
        citation = Citation.objects.filter(document__key="kereu-2024").get()

        response = self.client.post(f"{URL}citas/{citation.pk}/eliminar/")

        self.assertRedirects(response, URL, fetch_redirect_response=False)
        self.assertFalse(Citation.objects.filter(pk=citation.pk).exists())
        verifier = FakeVerifier()
        with patch("apps.literature.services.get_verifier", return_value=verifier):
            self.client.get(URL)
            self.client.post(f"{URL}recalcular/")
        self.assertEqual(ImportanceRun.objects.filter(origin="ia").first().factors.get(factor__name="Coste total de propiedad (TCO)").tc, 2)

    def test_get_does_not_block_on_ai_calculation(self):
        with patch("apps.literature.views.services.compute", side_effect=AssertionError("GET must not calculate")), \
             patch("apps.literature.views.services.get_verifier", return_value=FakeVerifier()):
            response = self.client.get(URL)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-auto-recalculate=\"true\"")

    def test_recalculate_supports_json_response(self):
        with patch("apps.literature.services.get_verifier", return_value=FakeVerifier()):
            response = self.client.post(f"{URL}recalcular/", HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["origin"], "ia")

    def test_add_document_with_citation(self):
        factor = Factor.objects.get(name="Casos de estudio de adopción FLOSS")
        response = self.client.post(f"{URL}documentos/nuevo/", {
            "authors": "Pérez et al.", "year": "2024", "title": "Casos de adopción", "source": "Revista X",
            "url": "https://doi.org/10.1/xyz", "database": "Scopus", "subfactors": [factor.subfactors.get().pk],
        })

        self.assertRedirects(response, URL, fetch_redirect_response=False)
        document = Document.objects.get(title="Casos de adopción")
        self.assertEqual(document.key, "perez-2024")
        self.assertEqual(list(document.citations.values_list("subfactor__factor__name", flat=True)), [factor.name])

    def test_delete_document(self):
        document = Document.objects.get(key="jha-2024")

        self.client.post(f"{URL}documentos/{document.pk}/eliminar/")

        self.assertFalse(Document.objects.filter(pk=document.pk).exists())

    def test_create_draft_from_ai_values(self):
        with patch("apps.literature.services.get_verifier", return_value=FakeVerifier(scores_by_document={"li-2022": 0})):
            self.client.post(f"{URL}recalcular/")
        run = ImportanceRun.objects.get(origin="ia")

        response = self.client.post(f"{URL}crear-borrador/")

        draft = CatalogVersion.objects.get(status="borrador")
        self.assertRedirects(response, f"/gestion/catalogo/{draft.number}/", fetch_redirect_response=False)
        for row in run.factors.all():
            self.assertEqual(FactorVersion.objects.get(version=draft, factor=row.factor).suggested_importance, row.value)

    def test_fallback_values_cannot_create_a_draft(self):
        self.client.get(URL)

        response = self.client.post(f"{URL}crear-borrador/", follow=True)

        self.assertContains(response, "Solo se puede crear un borrador con valores calculados por la IA.")
        self.assertFalse(CatalogVersion.objects.filter(status="borrador").exists())
