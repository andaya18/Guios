from django.db import IntegrityError

from apps.evaluations import workflow
from apps.evaluations.models import Evaluation, Software

from .test_workflow import EvaluationTestCase


class SoftwareModelTests(EvaluationTestCase):
    def test_str_joins_name_and_version(self):
        self.assertEqual(str(self.libreoffice), "LibreOffice 24.2")
        without_version = Software.objects.create(
            organization=self.unemi, name="Moodle", license_type="libre"
        )
        self.assertEqual(str(without_version), "Moodle")

    def test_unique_per_organization_name_and_version(self):
        with self.assertRaises(IntegrityError):
            Software.objects.create(
                organization=self.unemi, name="LibreOffice", version="24.2", license_type="otro"
            )


class EvaluationModelTests(EvaluationTestCase):
    def test_absolute_url_points_to_history_detail(self):
        evaluation = workflow.create_evaluation(self.ana, self.libreoffice)
        self.assertEqual(evaluation.get_absolute_url(), f"/historial/{evaluation.pk}/")
        self.assertIn("LibreOffice 24.2", str(evaluation))

    def test_finalized_evaluation_cannot_be_saved_or_deleted(self):
        evaluation = self.finished(self.ana)

        evaluation.current_step = 1
        with self.assertRaises(PermissionError):
            evaluation.save()
        with self.assertRaises(PermissionError):
            evaluation.delete()

        stored = Evaluation.objects.get(pk=evaluation.pk)
        self.assertEqual((stored.status, stored.current_step), ("finalizada", 3))
