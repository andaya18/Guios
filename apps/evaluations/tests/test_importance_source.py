"""HU-24 to HU-27: the decisor sees where the suggested importance of an evaluation comes from."""
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Organization, User
from apps.catalog.models import CatalogVersion
from apps.evaluations import workflow
from apps.evaluations.models import Software
from apps.literature import services as literature
from apps.literature.tests.test_services import FakeVerifier
from apps.management import services as catalog

LIMITATION = "registros académicos abiertos"


class ImportanceSourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", verbosity=0)
        call_command("cargar_literatura", verbosity=0)
        cls.org = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        cls.ana = User.objects.create_user(email="ana@unemi.edu.ec", password="Correcta123", first_name="Ana", organization=cls.org)
        cls.software = Software.objects.create(organization=cls.org, name="Odoo", version="17", license_type="libre")

    def setUp(self):
        self.client.force_login(self.ana)

    def publish_ai_version(self):
        with patch("apps.literature.services.get_verifier", return_value=FakeVerifier()):
            run = literature.compute()
        draft = literature.apply_to_draft(run)
        catalog.publish_version(draft, justification="IA 2020-2025", authorized_by="Docente", name="IA")
        return run, CatalogVersion.objects.get(pk=draft.pk)

    def test_ai_version_keeps_the_run_that_produced_it(self):
        run, version = self.publish_ai_version()

        self.assertEqual(version.importance_run, run)

    def test_stage_one_shows_ai_origin_date_and_link_to_sources(self):
        run, _ = self.publish_ai_version()
        evaluation = workflow.create_evaluation(self.ana, self.software)

        response = self.client.get(f"/evaluaciones/{evaluation.pk}/etapa-1/")

        self.assertContains(response, "Importancia sugerida calculada con IA")
        self.assertContains(response, run.model)
        self.assertContains(response, f"/evaluaciones/{evaluation.pk}/importancia-sugerida/")

    def test_stage_one_identifies_fallback_values(self):
        evaluation = workflow.create_evaluation(self.ana, self.software)  # active v2 from the initial load

        response = self.client.get(f"/evaluaciones/{evaluation.pk}/etapa-1/")

        self.assertContains(response, "Importancia sugerida de respaldo")
        self.assertNotContains(response, "calculada con IA")

    def test_sources_page_shows_status_date_values_and_sources(self):
        run, _ = self.publish_ai_version()
        evaluation = workflow.create_evaluation(self.ana, self.software)

        response = self.client.get(f"/evaluaciones/{evaluation.pk}/importancia-sugerida/")

        for text in ("Calculada con IA", run.model, "Compatibilidad", "Butler et al. (2022)", "https://example.org", LIMITATION):
            self.assertContains(response, text)

    def test_sources_page_for_fallback_says_no_ai_query(self):
        evaluation = workflow.create_evaluation(self.ana, self.software)

        response = self.client.get(f"/evaluaciones/{evaluation.pk}/importancia-sugerida/")

        self.assertContains(response, "Valores de respaldo")
        self.assertContains(response, "no proviene de una consulta de IA")

    def test_resuming_a_draft_never_queries_the_ai(self):
        self.publish_ai_version()
        evaluation = workflow.create_evaluation(self.ana, self.software)
        before = list(evaluation.factors.values_list("suggested_importance", flat=True))

        with patch("apps.literature.services.get_verifier") as verifier:
            self.client.get(f"/evaluaciones/{evaluation.pk}/etapa-1/")
            self.client.get(f"/evaluaciones/{evaluation.pk}/importancia-sugerida/")

        verifier.assert_not_called()
        self.assertEqual(list(evaluation.factors.values_list("suggested_importance", flat=True)), before)

    def test_other_organization_cannot_see_the_sources(self):
        evaluation = workflow.create_evaluation(self.ana, self.software)
        other = Organization.objects.create(name="ESPOL", domain="espol.edu.ec", sector="publico")
        self.client.force_login(User.objects.create_user(email="eva@espol.edu.ec", password="x", first_name="Eva", organization=other))

        self.assertEqual(self.client.get(f"/evaluaciones/{evaluation.pk}/importancia-sugerida/").status_code, 404)
