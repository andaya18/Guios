from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Organization, User
from apps.catalog.models import CatalogVersion
from apps.evaluations import workflow
from apps.evaluations.models import Evaluation, Software
from apps.evaluations.services import MENSAJE_EMPATE
from apps.evaluations.tests.factories import finished_evaluation


class HistoryViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", verbosity=0)
        cls.org = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        cls.other_org = Organization.objects.create(name="ESPOL", domain="espol.edu.ec", sector="publico")
        cls.ana = User.objects.create_user(email="ana@unemi.edu.ec", password="Correcta123", first_name="Ana", organization=cls.org)
        cls.luis = User.objects.create_user(email="luis@unemi.edu.ec", password="Correcta123", first_name="Luis", organization=cls.org)
        cls.eva = User.objects.create_user(email="eva@espol.edu.ec", password="Correcta123", first_name="Eva", organization=cls.other_org)
        cls.libre = Software.objects.create(organization=cls.org, name="LibreOffice", version="24.2", license_type="libre")
        cls.odoo = Software.objects.create(organization=cls.org, name="Odoo", version="17", license_type="libre")
        cls.moodle = Software.objects.create(organization=cls.other_org, name="Moodle", version="4.4", license_type="libre")
        cls.ana_final = finished_evaluation(cls.ana, cls.libre)
        cls.ana_draft = workflow.create_evaluation(cls.ana, cls.odoo)
        cls.other_final = finished_evaluation(cls.eva, cls.moodle)

    def test_list_shows_org_finalized_and_only_own_drafts(self):
        self.client.force_login(self.luis)

        response = self.client.get("/historial/")

        self.assertContains(response, "LibreOffice 24.2")
        self.assertNotContains(response, "Odoo 17")
        self.assertNotContains(response, "Moodle")
        self.assertContains(response, "Todas · 1")

    def test_author_sees_own_draft_with_continue(self):
        self.client.force_login(self.ana)

        response = self.client.get("/historial/")

        self.assertContains(response, "Borrador · Etapa 1")
        self.assertContains(response, "Mis borradores · 1")

    def test_filters_by_status_and_search(self):
        self.client.force_login(self.ana)

        self.assertNotContains(self.client.get("/historial/?estado=finalizada"), "Odoo 17")
        self.assertNotContains(self.client.get("/historial/?q=odoo"), "LibreOffice 24.2")

    def test_detail_of_org_finalized_is_readonly_with_actions(self):
        self.client.force_login(self.luis)

        response = self.client.get(f"/historial/{self.ana_final.pk}/")

        for text in ("LibreOffice 24.2", "Finalizada", "Duplicar para reevaluar", "Exportar", "Adoptar"):
            self.assertContains(response, text)

    def test_detail_of_other_organization_is_404(self):
        self.client.force_login(self.luis)

        self.assertEqual(self.client.get(f"/historial/{self.other_final.pk}/").status_code, 404)

    def test_duplicate_creates_draft_for_current_user_and_opens_stage_one(self):
        self.client.force_login(self.luis)

        response = self.client.post(f"/historial/{self.ana_final.pk}/duplicar/")

        copy = Evaluation.objects.get(duplicated_from=self.ana_final)
        self.assertEqual((copy.author, copy.status), (self.luis, "borrador"))
        self.assertRedirects(response, f"/evaluaciones/{copy.pk}/etapa-1/", fetch_redirect_response=False)
        self.ana_final.refresh_from_db()
        self.assertEqual(self.ana_final.status, "finalizada")

    def test_other_user_cannot_delete_draft(self):
        self.client.force_login(self.luis)

        response = self.client.post(f"/historial/{self.ana_draft.pk}/eliminar/")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Evaluation.objects.filter(pk=self.ana_draft.pk).exists())


class CompareViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", verbosity=0)
        cls.org = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        cls.ana = User.objects.create_user(email="ana@unemi.edu.ec", password="Correcta123", first_name="Ana", organization=cls.org)
        cls.a = finished_evaluation(cls.ana, Software.objects.create(organization=cls.org, name="OnlyOffice", version="8.1", license_type="libre"))
        cls.c = finished_evaluation(cls.ana, Software.objects.create(organization=cls.org, name="Moodle", version="4.4", license_type="libre"), importance=4, answer=1)
        cls.a2 = finished_evaluation(cls.ana, Software.objects.create(organization=cls.org, name="GLPI", version="10", license_type="libre"))

    def setUp(self):
        self.client.force_login(self.ana)

    def test_less_than_two_shows_empty_state(self):
        self.assertContains(self.client.get(f"/comparar/?ids={self.a.pk}"), "Elige al menos dos evaluaciones")

    def test_best_alternative_is_announced(self):
        response = self.client.get(f"/comparar/?ids={self.c.pk}&ids={self.a.pk}")

        self.assertContains(response, "Mejor alternativa: OnlyOffice 8.1")
        self.assertContains(response, "1.º")

    def test_tie_message_from_guide(self):
        response = self.client.get(f"/comparar/?ids={self.a.pk}&ids={self.a2.pk}")

        self.assertContains(response, MENSAJE_EMPATE)

    def test_different_catalog_versions_are_not_compared(self):
        CatalogVersion.objects.filter(number=2).update(status="publicada")
        CatalogVersion.objects.filter(number=1).update(status="activa")
        old = finished_evaluation(self.ana, Software.objects.create(organization=self.org, name="Nextcloud", version="29", license_type="libre"))

        response = self.client.get(f"/comparar/?ids={self.a.pk}&ids={old.pk}")

        self.assertContains(response, "versiones de catálogo distintas")
        self.assertNotContains(response, "Mejor alternativa")
