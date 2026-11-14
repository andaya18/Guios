import csv
import io

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.evaluations import workflow
from apps.evaluations.models import Software
from apps.evaluations.tests.factories import finished_evaluation
from apps.exports import services

CSV_HEADER = [
    "evaluación", "software", "factor", "alcance", "ID", "IS", "IR",
    "relevante", "PM", "FODA", "subfactor", "calificación",
]


class ExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", verbosity=0)
        cls.org = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        cls.other_org = Organization.objects.create(name="ESPOL", domain="espol.edu.ec", sector="publico")
        cls.ana = User.objects.create_user(email="ana@unemi.edu.ec", password="Correcta123", first_name="Ana", organization=cls.org)
        cls.luis = User.objects.create_user(email="luis@unemi.edu.ec", password="Correcta123", first_name="Luis", organization=cls.org)
        cls.eva = User.objects.create_user(email="eva@espol.edu.ec", password="Correcta123", first_name="Eva", organization=cls.other_org)
        cls.admin = User.objects.create_user(email="admin@guios.local", password="Correcta123", role="administrador")
        software = Software.objects.create(organization=cls.org, name="LibreOffice", version="24.2", license_type="libre")
        cls.finished = finished_evaluation(cls.ana, software)
        cls.draft = workflow.create_evaluation(cls.ana, Software.objects.create(organization=cls.org, name="Odoo", version="17", license_type="libre"))
        cls.other = finished_evaluation(cls.eva, Software.objects.create(organization=cls.other_org, name="Moodle", version="4.4", license_type="libre"))

    def setUp(self):
        self.client.force_login(self.luis)

    def url(self, evaluation, fmt):
        return f"/historial/{evaluation.pk}/exportar/?formato={fmt}"

    def expected_name(self, ext):
        day = timezone.localtime(self.finished.finished_at).strftime("%Y-%m-%d")
        return f"GUIOS_LibreOffice_24.2_{day}.{ext}"

    def test_csv_has_bom_header_and_one_row_per_subfactor(self):
        response = self.client.get(self.url(self.finished, "csv"))

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(self.expected_name("csv"), response["Content-Disposition"])
        self.assertTrue(response.content.startswith("\ufeff".encode("utf-8")))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(rows[0], CSV_HEADER)
        self.assertEqual(len(rows) - 1, 61)
        first = rows[1]
        self.assertEqual(first[1], "LibreOffice 24.2")
        self.assertEqual((first[7], first[8], first[11]), ("Sí", "4,00", "4"))

    def test_pdf_is_a_pdf_with_suggested_name(self):
        response = self.client.get(self.url(self.finished, "pdf") + "&incluir=recomendacion&incluir=respuestas")

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(self.expected_name("pdf"), response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_report_data_has_header_table_and_recommendation(self):
        report = services.report_data(self.finished)

        self.assertEqual(report["header"]["Organización"], "UNEMI")
        self.assertEqual(report["header"]["Software"], "LibreOffice 24.2")
        self.assertEqual(report["header"]["Versión de catálogo"], "v2")
        self.assertEqual(len(report["factors"]), 18)
        self.assertTrue(report["recommendation_text"].startswith("Recomendación A: Adoptar."))

    def test_unknown_format_is_rejected(self):
        self.assertEqual(self.client.get(self.url(self.finished, "xlsx")).status_code, 400)

    def test_drafts_are_not_exportable(self):
        self.client.force_login(self.ana)

        self.assertEqual(self.client.get(self.url(self.draft, "csv")).status_code, 404)

    def test_other_organization_is_404(self):
        self.assertEqual(self.client.get(self.url(self.other, "pdf")).status_code, 404)

    def test_administrator_gets_403(self):
        self.client.force_login(self.admin)

        self.assertEqual(self.client.get(self.url(self.finished, "csv")).status_code, 403)
