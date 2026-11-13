from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.catalog.models import CatalogVersion
from apps.evaluations import workflow
from apps.evaluations.models import Evaluation, EvaluationFactor, EvaluationSubfactor
from apps.evaluations.services import TEXTOS_RECOMENDACION


def activate_version(number):
    """Switch the active catalog version the way M03 does (one active at a time)."""
    for version in CatalogVersion.objects.filter(status="activa"):
        version.status = "publicada"
        version.save()
    target = CatalogVersion.objects.get(number=number)
    target.status = "activa"
    target.save()


class EvaluationTestCase(TestCase):
    """Loaded catalog, two decisors of UNEMI (Ana, Luis) and one of another organization."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", stdout=StringIO())
        cls.unemi = Organization.objects.create(
            name="UNEMI", domain="unemi.edu.ec", sector="publico"
        )
        cls.other_org = Organization.objects.create(
            name="Acme", domain="acme.com", sector="privado"
        )
        cls.ana = User.objects.create_user(
            "ana@unemi.edu.ec", "Clave123", first_name="Ana", organization=cls.unemi
        )
        cls.luis = User.objects.create_user(
            "luis@unemi.edu.ec", "Clave123", first_name="Luis", organization=cls.unemi
        )
        cls.pedro = User.objects.create_user(
            "pedro@acme.com", "Clave123", first_name="Pedro", organization=cls.other_org
        )
        cls.libreoffice = workflow.register_software(cls.unemi, "LibreOffice", "24.2", "libre")

    # Helpers shared by the selector tests.

    @staticmethod
    def factor(evaluation, name):
        return evaluation.factors.get(factor__name=name)

    @classmethod
    def assign_all(cls, evaluation, default=1, **by_name):
        """Give every factor an ID; with ID 1 only the IS 3 factors stay relevant (IR 2)."""
        for ev_factor in evaluation.factors.select_related("factor"):
            value = by_name.get(ev_factor.factor.name, default)
            workflow.set_decision_importance(ev_factor, value)

    @staticmethod
    def answer_all(evaluation, value=3, low=(), skip=0):
        """Answer every subfactor of the relevant factors; `low` factors get 1, `skip` leaves N empty."""
        answers = EvaluationSubfactor.objects.filter(
            evaluation_factor__evaluation=evaluation, evaluation_factor__is_relevant=True
        ).select_related("evaluation_factor__factor")
        answers = list(answers.order_by("evaluation_factor__factor__order", "subfactor__order"))
        for answer in answers[: len(answers) - skip]:
            given = 1 if answer.evaluation_factor.factor.name in low else value
            workflow.answer_subfactor(evaluation, answer.pk, given)

    @classmethod
    def finished(cls, user, software=None, ids=None, low=()):
        evaluation = workflow.create_evaluation(user, software or cls.libreoffice)
        cls.assign_all(evaluation, **(ids or {}))
        workflow.start_stage_two(evaluation)
        cls.answer_all(evaluation, low=low)
        workflow.finalize(evaluation)
        evaluation.refresh_from_db()
        return evaluation

    @classmethod
    def ready_draft(cls, user, **kwargs):
        evaluation = workflow.create_evaluation(user, cls.libreoffice)
        cls.assign_all(evaluation, **kwargs)
        workflow.start_stage_two(evaluation)
        return evaluation


class RegisterSoftwareTests(EvaluationTestCase):
    def test_get_or_create_is_unique_per_organization_name_and_version(self):
        again = workflow.register_software(self.unemi, "LibreOffice", "24.2", "libre")
        other_version = workflow.register_software(self.unemi, "LibreOffice", "7.6", "libre")
        other_org = workflow.register_software(self.other_org, "LibreOffice", "24.2", "libre")
        self.assertEqual(again.pk, self.libreoffice.pk)
        self.assertNotEqual(other_version.pk, self.libreoffice.pk)
        self.assertNotEqual(other_org.pk, self.libreoffice.pk)

    def test_rejects_unknown_license(self):
        with self.assertRaises(ValidationError):
            workflow.register_software(self.unemi, "Moodle", "4.3", "gratis")


class CreateEvaluationTests(EvaluationTestCase):
    def test_draft_on_active_version_with_18_factors_copied(self):
        evaluation = workflow.create_evaluation(self.ana, self.libreoffice)

        self.assertEqual(evaluation.status, "borrador")
        self.assertEqual(evaluation.current_step, 1)
        self.assertEqual(evaluation.organization, self.unemi)
        self.assertEqual(evaluation.author, self.ana)
        self.assertEqual(evaluation.catalog_version.number, 2)
        self.assertEqual(evaluation.factors.count(), 18)
        compatibilidad = self.factor(evaluation, "Compatibilidad")
        self.assertEqual(compatibilidad.suggested_importance, 2)  # v2 value, v1 is 3
        self.assertEqual(compatibilidad.scope, "externo")
        self.assertIsNone(compatibilidad.decision_importance)
        self.assertEqual(self.factor(evaluation, "Soporte").scope, "interno")

    def test_software_of_another_organization_is_refused(self):
        with self.assertRaises(PermissionDenied):
            workflow.create_evaluation(self.pedro, self.libreoffice)
        self.assertFalse(Evaluation.objects.exists())


class StageOneTests(EvaluationTestCase):
    def setUp(self):
        self.evaluation = workflow.create_evaluation(self.ana, self.libreoffice)
        self.compatibilidad = self.factor(self.evaluation, "Compatibilidad")

    def test_decision_importance_recomputes_ir_and_relevance(self):
        workflow.set_decision_importance(self.compatibilidad, 4)
        self.compatibilidad.refresh_from_db()
        self.assertEqual(self.compatibilidad.relative_importance, 3)
        self.assertTrue(self.compatibilidad.is_relevant)

        workflow.set_decision_importance(self.compatibilidad, 1)
        self.compatibilidad.refresh_from_db()
        self.assertEqual(self.compatibilidad.relative_importance, 1)
        self.assertFalse(self.compatibilidad.is_relevant)

    def test_decision_importance_out_of_range_changes_nothing(self):
        for value in (0, 5, "x", None):
            with self.assertRaises(ValidationError):
                workflow.set_decision_importance(self.compatibilidad, value)
        self.compatibilidad.refresh_from_db()
        self.assertIsNone(self.compatibilidad.decision_importance)
        self.assertIsNone(self.compatibilidad.relative_importance)

    def test_each_save_touches_updated_at(self):
        later = timezone.now() + timedelta(hours=1)
        with mock.patch("django.utils.timezone.now", return_value=later):
            workflow.set_decision_importance(self.compatibilidad, 3)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.updated_at, later)

    def test_scope_is_validated_and_saved(self):
        workflow.set_scope(self.compatibilidad, "interno")
        self.compatibilidad.refresh_from_db()
        self.assertEqual(self.compatibilidad.scope, "interno")
        with self.assertRaises(ValidationError):
            workflow.set_scope(self.compatibilidad, "global")
        self.compatibilidad.refresh_from_db()
        self.assertEqual(self.compatibilidad.scope, "interno")


class StartStageTwoTests(EvaluationTestCase):
    def setUp(self):
        self.evaluation = workflow.create_evaluation(self.ana, self.libreoffice)

    def test_requires_the_18_decision_importances(self):
        workflow.set_decision_importance(self.factor(self.evaluation, "Compatibilidad"), 4)
        with self.assertRaises(ValidationError):
            workflow.start_stage_two(self.evaluation)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.current_step, 1)

    def test_requires_at_least_one_relevant_factor(self):
        # Every IS 3 factor keeps IR 2, so force IS 2 to reach "all irrelevant".
        EvaluationFactor.objects.filter(evaluation=self.evaluation).update(suggested_importance=2)
        self.assign_all(self.evaluation, default=1)
        with self.assertRaisesMessage(
            ValidationError, "Debes marcar al menos un factor como relevante para continuar."
        ):
            workflow.start_stage_two(self.evaluation)

    def test_creates_answers_for_relevant_factors_only(self):
        self.assign_all(self.evaluation, default=1, Compatibilidad=4)
        workflow.start_stage_two(self.evaluation)

        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.current_step, 2)
        self.assertEqual(self.factor(self.evaluation, "Compatibilidad").answers.count(), 8)
        self.assertEqual(self.factor(self.evaluation, "Documentación").answers.count(), 0)
        self.assertTrue(
            all(a.value is None for a in self.factor(self.evaluation, "Soporte").answers.all())
        )

    def test_going_back_to_stage_one_never_deletes_answers(self):
        self.assign_all(self.evaluation, default=1, Compatibilidad=4)
        workflow.start_stage_two(self.evaluation)
        compatibilidad = self.factor(self.evaluation, "Compatibilidad")
        first = compatibilidad.answers.first()
        workflow.answer_subfactor(self.evaluation, first.pk, 4)

        workflow.set_decision_importance(compatibilidad, 1)  # becomes irrelevant
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.current_step, 1)
        workflow.start_stage_two(self.evaluation)
        workflow.set_decision_importance(compatibilidad, 4)  # relevant again
        workflow.start_stage_two(self.evaluation)

        first.refresh_from_db()
        self.assertEqual(first.value, 4)
        self.assertEqual(compatibilidad.answers.count(), 8)


class StageTwoTests(EvaluationTestCase):
    def setUp(self):
        self.evaluation = self.ready_draft(self.ana)
        self.soporte = self.factor(self.evaluation, "Soporte")

    def test_answer_is_validated(self):
        answer = self.soporte.answers.first()
        with self.assertRaises(ValidationError):
            workflow.answer_subfactor(self.evaluation, answer.pk, 5)
        answer.refresh_from_db()
        self.assertIsNone(answer.value)

    def test_answer_of_another_evaluation_is_not_found(self):
        other = self.ready_draft(self.luis)
        foreign = self.factor(other, "Soporte").answers.first()
        with self.assertRaises(EvaluationSubfactor.DoesNotExist):
            workflow.answer_subfactor(self.evaluation, foreign.pk, 3)

    def test_factor_progress_reports_live_pm(self):
        answers = list(self.soporte.answers.order_by("subfactor__order"))
        workflow.answer_subfactor(self.evaluation, answers[0].pk, 4)
        workflow.answer_subfactor(self.evaluation, answers[1].pk, 3)

        progress = {row["factor"].factor.name: row for row in workflow.factor_progress(self.evaluation)}
        self.assertEqual(len(progress), 9)  # only relevant factors
        self.assertEqual(progress["Soporte"]["answered"], 2)
        self.assertEqual(progress["Soporte"]["total"], 6)
        self.assertEqual(progress["Soporte"]["pm"], Decimal("3.5"))
        self.assertIsNone(progress["Fiabilidad"]["pm"])

    def test_go_to_results_only_when_nothing_is_missing(self):
        self.answer_all(self.evaluation, skip=1)
        with self.assertRaises(workflow.IncompleteEvaluation):
            workflow.go_to_results(self.evaluation)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.current_step, 2)

        self.answer_all(self.evaluation)
        workflow.go_to_results(self.evaluation)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.current_step, 3)


class MissingItemsTests(EvaluationTestCase):
    def test_new_evaluation_lists_missing_decision_importances(self):
        evaluation = workflow.create_evaluation(self.ana, self.libreoffice)
        self.assertEqual(
            workflow.missing_items(evaluation),
            [
                {
                    "message": "Etapa 1: faltan 18 factores por asignar importancia",
                    "url": f"/evaluaciones/{evaluation.pk}/etapa-1/",
                }
            ],
        )

    def test_names_each_factor_with_missing_subfactors(self):
        evaluation = self.ready_draft(self.ana, Compatibilidad=4)
        self.answer_all(evaluation)
        compatibilidad = self.factor(evaluation, "Compatibilidad")
        answers = list(compatibilidad.answers.order_by("subfactor__order"))
        for answer in answers[:3]:
            answer.value = None
            answer.save()
        tco = self.factor(evaluation, "Coste total de propiedad (TCO)").answers.last()
        tco.value = None
        tco.save()

        self.assertEqual(
            workflow.missing_items(evaluation),
            [
                {
                    "message": "Compatibilidad: faltan 3 subfactores",
                    "url": f"/evaluaciones/{evaluation.pk}/etapa-2/?factor={compatibilidad.factor_id}",
                },
                {
                    "message": "Coste total de propiedad (TCO): falta 1 subfactor",
                    "url": f"/evaluaciones/{evaluation.pk}/etapa-2/?factor={tco.evaluation_factor.factor_id}",
                },
            ],
        )

    def test_no_relevant_factor_is_reported(self):
        evaluation = workflow.create_evaluation(self.ana, self.libreoffice)
        EvaluationFactor.objects.filter(evaluation=evaluation).update(suggested_importance=2)
        self.assign_all(evaluation, default=1)
        self.assertEqual(
            [item["message"] for item in workflow.missing_items(evaluation)],
            ["Debes marcar al menos un factor como relevante para continuar."],
        )


class FinalizeTests(EvaluationTestCase):
    def test_one_unanswered_subfactor_blocks_finalize_and_names_it(self):
        evaluation = self.ready_draft(self.ana)
        self.answer_all(evaluation, skip=1)  # the last one belongs to TCO

        with self.assertRaises(workflow.IncompleteEvaluation) as raised:
            workflow.finalize(evaluation)

        self.assertEqual(
            [item["message"] for item in raised.exception.items],
            ["Coste total de propiedad (TCO): falta 1 subfactor"],
        )
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.status, "borrador")
        self.assertIsNone(evaluation.finished_at)
        self.assertFalse(evaluation.factors.exclude(pm=None).exists())

    def test_saves_pm_foda_recommendation_and_status(self):
        evaluation = self.ready_draft(self.ana)
        self.answer_all(evaluation)
        soporte = list(self.factor(evaluation, "Soporte").answers.order_by("subfactor__order"))
        workflow.answer_subfactor(evaluation, soporte[-1].pk, 2)  # 17 / 6 = 2.8333

        workflow.finalize(evaluation)

        evaluation.refresh_from_db()
        self.assertEqual(evaluation.status, "finalizada")
        self.assertEqual(evaluation.current_step, 3)
        self.assertIsNotNone(evaluation.finished_at)
        self.assertEqual(evaluation.recommendation, "B")  # Soporte has IR 2
        saved = self.factor(evaluation, "Soporte")
        self.assertEqual(saved.pm, Decimal("2.8333"))
        self.assertEqual(saved.foda, "Debilidad")
        fiabilidad = self.factor(evaluation, "Fiabilidad")
        self.assertEqual((fiabilidad.pm, fiabilidad.foda), (Decimal("3.0000"), "Oportunidad"))
        irrelevant = self.factor(evaluation, "Compatibilidad")
        self.assertEqual((irrelevant.pm, irrelevant.foda), (None, ""))

    def test_problem_with_important_ir_gives_c(self):
        evaluation = self.finished(self.ana, ids={"Soporte": 4}, low={"Soporte"})
        self.assertEqual(evaluation.recommendation, "C")

    def test_saving_on_a_finalized_evaluation_is_refused(self):
        evaluation = self.finished(self.ana)
        soporte = self.factor(evaluation, "Soporte")
        answer = soporte.answers.first()

        with self.assertRaises(PermissionDenied):
            workflow.answer_subfactor(evaluation, answer.pk, 1)
        with self.assertRaises(PermissionDenied):
            workflow.set_decision_importance(soporte, 4)
        with self.assertRaises(PermissionDenied):
            workflow.set_scope(soporte, "externo")
        with self.assertRaises(PermissionDenied):
            workflow.finalize(evaluation)

        answer.refresh_from_db()
        soporte.refresh_from_db()
        self.assertEqual(answer.value, 3)
        self.assertEqual((soporte.decision_importance, soporte.scope), (1, "interno"))


class ResultsTests(EvaluationTestCase):
    def test_draft_results_are_computed_without_saving(self):
        evaluation = self.ready_draft(self.ana)
        self.answer_all(evaluation, low={"Soporte"})

        result = workflow.results(evaluation)

        self.assertEqual(result["recommendation"], "B")
        self.assertEqual(result["text"], TEXTOS_RECOMENDACION["B"])
        self.assertEqual(len(result["factors"]), 9)
        self.assertEqual([row.factor.name for row in result["supporting"]], ["Soporte"])
        soporte = result["supporting"][0]
        self.assertEqual((soporte.scope, soporte.relative_importance), ("interno", 2))
        self.assertEqual((soporte.pm, soporte.cumple, soporte.foda), (Decimal(1), False, "Debilidad"))
        self.assertFalse(evaluation.factors.exclude(pm=None).exists())

    def test_recommendation_a_is_supported_by_all_relevant_factors(self):
        evaluation = self.finished(self.ana)
        result = workflow.results(evaluation)
        self.assertEqual(result["recommendation"], "A")
        self.assertEqual(len(result["supporting"]), 9)

    def test_finalized_results_read_saved_values(self):
        evaluation = self.finished(self.ana, low={"Soporte"})
        EvaluationFactor.objects.filter(evaluation=evaluation, factor__name="Soporte").update(
            pm=Decimal("1.2345")
        )

        result = workflow.results(evaluation)

        soporte = next(row for row in result["factors"] if row.factor.name == "Soporte")
        self.assertEqual(soporte.pm, Decimal("1.2345"))
        self.assertEqual(result["recommendation"], "B")


class DuplicateTests(EvaluationTestCase):
    def test_duplicate_keeps_answers_and_leaves_the_original_intact(self):
        original = self.finished(self.ana, ids={"Compatibilidad": 4}, low={"Soporte"})
        original_answers = list(
            EvaluationSubfactor.objects.filter(evaluation_factor__evaluation=original)
            .order_by("subfactor_id")
            .values_list("subfactor_id", "value")
        )

        copy, warning = workflow.duplicate(original, self.luis)

        self.assertIsNone(warning)
        self.assertEqual(copy.status, "borrador")
        self.assertEqual(copy.current_step, 1)
        self.assertEqual(copy.author, self.luis)
        self.assertEqual(copy.software, original.software)
        self.assertEqual(copy.duplicated_from, original)
        self.assertEqual(copy.recommendation, "")
        copied_answers = list(
            EvaluationSubfactor.objects.filter(evaluation_factor__evaluation=copy)
            .order_by("subfactor_id")
            .values_list("subfactor_id", "value")
        )
        self.assertEqual(copied_answers, original_answers)
        self.assertEqual(
            list(copy.factors.order_by("factor__order").values_list("decision_importance", "scope")),
            list(original.factors.order_by("factor__order").values_list("decision_importance", "scope")),
        )
        self.assertFalse(copy.factors.exclude(pm=None).exists())

        original.refresh_from_db()
        self.assertEqual(original.status, "finalizada")
        self.assertEqual(original.recommendation, "B")
        self.assertEqual(
            EvaluationSubfactor.objects.filter(evaluation_factor__evaluation=original).count(),
            len(original_answers),
        )

    def test_duplicate_on_a_new_active_version_recopies_is_and_warns(self):
        activate_version(1)
        original = self.finished(self.ana, ids={"Compatibilidad": 3})
        self.assertEqual(self.factor(original, "Compatibilidad").relative_importance, 3)
        activate_version(2)

        copy, warning = workflow.duplicate(original, self.ana)

        self.assertEqual(copy.catalog_version.number, 2)
        self.assertEqual(
            warning, "Esta evaluación usa el catálogo versión 2, distinto al de la original"
        )
        compatibilidad = self.factor(copy, "Compatibilidad")
        self.assertEqual(compatibilidad.suggested_importance, 2)
        self.assertEqual(compatibilidad.relative_importance, 2)
        self.assertEqual(compatibilidad.answers.count(), 8)

    def test_only_finalized_evaluations_of_the_same_organization(self):
        draft = self.ready_draft(self.ana)
        with self.assertRaises(ValidationError):
            workflow.duplicate(draft, self.ana)
        finished = self.finished(self.ana)
        with self.assertRaises(PermissionDenied):
            workflow.duplicate(finished, self.pedro)


class DeleteDraftTests(EvaluationTestCase):
    def test_only_the_author_deletes_a_draft(self):
        draft = workflow.create_evaluation(self.ana, self.libreoffice)
        with self.assertRaises(PermissionDenied):
            workflow.delete_draft(draft, self.luis)
        self.assertTrue(Evaluation.objects.filter(pk=draft.pk).exists())

        workflow.delete_draft(draft, self.ana)
        self.assertFalse(Evaluation.objects.filter(pk=draft.pk).exists())
        self.assertFalse(EvaluationFactor.objects.filter(evaluation_id=draft.pk).exists())

    def test_finalized_evaluation_is_never_deleted(self):
        finished = self.finished(self.ana)
        with self.assertRaises(PermissionDenied):
            workflow.delete_draft(finished, self.ana)
        self.assertTrue(Evaluation.objects.filter(pk=finished.pk).exists())


class ResumeTests(EvaluationTestCase):
    def test_stage_one_label_and_progress(self):
        evaluation = workflow.create_evaluation(self.ana, self.libreoffice)
        for ev_factor in evaluation.factors.order_by("factor__order")[:12]:
            workflow.set_decision_importance(ev_factor, 3)
        evaluation.refresh_from_db()

        self.assertEqual(
            workflow.resume_label(evaluation),
            "Etapa 1 de 3 · Factores relevantes · 12 de 18 factores",
        )
        self.assertEqual(workflow.resume_progress(evaluation), 22)  # (0 + 12/18) / 3

    def test_stage_two_points_to_first_relevant_factor_with_pending_subfactors(self):
        evaluation = self.ready_draft(self.ana, Compatibilidad=4)
        answers = list(self.factor(evaluation, "Compatibilidad").answers.order_by("subfactor__order"))
        for answer in answers[:5]:
            workflow.answer_subfactor(evaluation, answer.pk, 3)
        evaluation.refresh_from_db()

        self.assertEqual(
            workflow.resume_label(evaluation),
            "Etapa 2 de 3 · Ponderación · Factor: Compatibilidad (5 de 8 subfactores)",
        )
        self.assertEqual(workflow.resume_progress(evaluation), 39)  # (1 + 5/29) / 3
        self.assertEqual(
            workflow.resume_url(evaluation),
            f"/evaluaciones/{evaluation.pk}/etapa-2/?factor={answers[0].evaluation_factor.factor_id}",
        )

    def test_stage_three_label(self):
        evaluation = self.ready_draft(self.ana)
        self.answer_all(evaluation)
        workflow.go_to_results(evaluation)
        evaluation.refresh_from_db()

        self.assertEqual(workflow.resume_label(evaluation), "Etapa 3 de 3 · Resultado")
        self.assertEqual(workflow.resume_progress(evaluation), 67)
        self.assertEqual(workflow.resume_url(evaluation), f"/evaluaciones/{evaluation.pk}/etapa-3/")


class CatalogVersionSwitchTests(EvaluationTestCase):
    def test_switching_2_to_1_to_2_keeps_old_evaluations_version(self):
        on_two = workflow.create_evaluation(self.ana, self.libreoffice)
        activate_version(1)
        on_one = workflow.create_evaluation(self.ana, self.libreoffice)
        activate_version(2)
        again_two = workflow.create_evaluation(self.ana, self.libreoffice)

        on_two.refresh_from_db()
        on_one.refresh_from_db()
        self.assertEqual(on_two.catalog_version.number, 2)
        self.assertEqual(on_one.catalog_version.number, 1)
        self.assertEqual(again_two.catalog_version.number, 2)
        self.assertEqual(self.factor(on_one, "Compatibilidad").suggested_importance, 3)
        self.assertEqual(self.factor(on_two, "Compatibilidad").suggested_importance, 2)
