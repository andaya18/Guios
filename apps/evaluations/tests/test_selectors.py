from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.evaluations import permissions, selectors, workflow
from apps.evaluations.models import Evaluation

from .test_workflow import EvaluationTestCase


class VisibilityTests(EvaluationTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.ana_draft = workflow.create_evaluation(cls.ana, cls.libreoffice)
        cls.ana_finished = cls.finished(cls.ana)
        moodle = workflow.register_software(cls.other_org, "Moodle", "4.3", "libre")
        cls.pedro_finished = cls.finished(cls.pedro, software=moodle)

    def test_ana_draft_is_hidden_from_luis_and_her_finalized_one_is_visible(self):
        visible = set(permissions.visible_evaluations(self.luis))
        self.assertEqual(visible, {self.ana_finished})
        self.assertEqual(
            set(permissions.visible_evaluations(self.ana)), {self.ana_draft, self.ana_finished}
        )

    def test_other_organization_sees_none_of_unemi(self):
        self.assertEqual(set(permissions.visible_evaluations(self.pedro)), {self.pedro_finished})
        with self.assertRaises(Http404):
            permissions.get_visible_evaluation(self.pedro, self.ana_finished.pk)
        with self.assertRaises(Http404):
            permissions.get_visible_evaluation(self.luis, self.ana_draft.pk)
        self.assertEqual(
            permissions.get_visible_evaluation(self.luis, self.ana_finished.pk), self.ana_finished
        )

    def test_editable_draft_only_for_its_author(self):
        self.assertEqual(permissions.get_editable_draft(self.ana, self.ana_draft.pk), self.ana_draft)
        with self.assertRaises(PermissionDenied):
            permissions.get_editable_draft(self.luis, self.ana_draft.pk)
        with self.assertRaises(PermissionDenied):
            permissions.get_editable_draft(self.ana, self.ana_finished.pk)
        with self.assertRaises(Http404):
            permissions.get_editable_draft(self.pedro, self.ana_draft.pk)


class DashboardTests(EvaluationTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.ana_a = cls.finished(cls.ana)
        cls.ana_b = cls.finished(cls.ana, low={"Soporte"})
        cls.luis_c = cls.finished(cls.luis, ids={"Soporte": 4}, low={"Soporte"})
        cls.ana_draft = workflow.create_evaluation(cls.ana, cls.libreoffice)
        cls.luis_old_draft = workflow.create_evaluation(cls.luis, cls.libreoffice)
        cls.luis_draft = cls.ready_draft(cls.luis, Compatibilidad=4)
        answers = cls.luis_draft.factors.get(factor__name="Compatibilidad").answers
        for answer in answers.order_by("subfactor__order")[:5]:
            workflow.answer_subfactor(cls.luis_draft, answer.pk, 3)
        moodle = workflow.register_software(cls.other_org, "Moodle", "4.3", "libre")
        cls.finished(cls.pedro, software=moodle)

    def test_numbers_match_the_database(self):
        summary = selectors.decisor_dashboard(self.luis)

        finished = Evaluation.objects.filter(organization=self.unemi, status="finalizada")
        self.assertEqual(summary.finished_count, finished.count())
        self.assertEqual(summary.finished_count, 3)
        self.assertEqual(
            summary.drafts_count,
            Evaluation.objects.filter(author=self.luis, status="borrador").count(),
        )
        self.assertEqual(summary.drafts_count, 2)
        self.assertEqual(summary.last, self.luis_c)
        self.assertEqual(summary.recent, [self.luis_c, self.ana_b, self.ana_a])
        self.assertEqual(
            [(row["letter"], row["count"], row["percent"]) for row in summary.by_letter],
            [("A", 1, 33), ("B", 1, 33), ("C", 1, 33)],
        )

    def test_resume_is_the_most_recently_edited_own_draft(self):
        resume = selectors.decisor_dashboard(self.luis).resume

        self.luis_draft.refresh_from_db()
        compatibilidad = self.luis_draft.factors.get(factor__name="Compatibilidad")
        self.assertEqual(resume.evaluation, self.luis_draft)
        self.assertEqual(resume.software, self.libreoffice)
        self.assertEqual(
            resume.step_label,
            "Etapa 2 de 3 · Ponderación · Factor: Compatibilidad (5 de 8 subfactores)",
        )
        self.assertEqual(resume.progress, 39)
        self.assertEqual(resume.updated_at, self.luis_draft.updated_at)
        self.assertEqual(
            resume.url,
            f"/evaluaciones/{self.luis_draft.pk}/etapa-2/?factor={compatibilidad.factor_id}",
        )

    def test_user_without_evaluations(self):
        newcomer = type(self.luis).objects.create_user(
            "eva@unemi.edu.ec", "Clave123", organization=self.unemi
        )
        summary = selectors.decisor_dashboard(newcomer)
        self.assertEqual((summary.finished_count, summary.drafts_count), (3, 0))
        self.assertIsNone(summary.last)
        self.assertIsNone(summary.resume)

    def test_recent_shows_the_last_four_finalized_of_the_organization(self):
        newest = [self.finished(self.ana) for _ in range(2)]
        recent = selectors.decisor_dashboard(self.luis).recent
        self.assertEqual(recent, [newest[1], newest[0], self.luis_c, self.ana_b])

    def test_history_count_is_org_finalized_plus_own_drafts(self):
        self.assertEqual(selectors.history_count(self.luis), 5)
        self.assertEqual(selectors.history_count(self.ana), 4)

    def test_history_filters(self):
        self.assertEqual(len(selectors.history(self.luis)), 5)
        self.assertEqual(
            set(selectors.history(self.luis, status="borrador")),
            {self.luis_old_draft, self.luis_draft},
        )
        self.assertEqual(list(selectors.history(self.luis, recommendation="B")), [self.ana_b])
        self.assertEqual(len(selectors.history(self.luis, query="libre")), 5)
        self.assertEqual(list(selectors.history(self.luis, query="moodle")), [])
