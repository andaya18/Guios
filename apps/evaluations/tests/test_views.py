from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Organization, User
from apps.evaluations import workflow
from apps.evaluations.models import Evaluation, EvaluationSubfactor, Software

HTMX = {"HTTP_HX_REQUEST": "true"}


class EvaluationViewsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", verbosity=0)
        cls.org = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        cls.ana = User.objects.create_user(email="ana@unemi.edu.ec", password="Correcta123", first_name="Ana", organization=cls.org)
        cls.luis = User.objects.create_user(email="luis@unemi.edu.ec", password="Correcta123", first_name="Luis", organization=cls.org)
        cls.admin = User.objects.create_user(email="admin@guios.local", password="Correcta123", role="administrador")
        cls.software = Software.objects.create(organization=cls.org, name="LibreOffice", version="24.2", license_type="libre")

    def setUp(self):
        self.evaluation = workflow.create_evaluation(self.ana, self.software)
        self.client.force_login(self.ana)

    def url(self, suffix):
        return f"/evaluaciones/{self.evaluation.pk}/{suffix}"

    def assign_all(self, value=3):
        for ev_factor in self.evaluation.factors.all():
            workflow.set_decision_importance(ev_factor, value)

    def answer_all(self, value=4):
        for answer in EvaluationSubfactor.objects.filter(evaluation_factor__evaluation=self.evaluation):
            workflow.answer_subfactor(self.evaluation, answer.pk, value)


class NewEvaluationViewTests(EvaluationViewsBase):
    def test_registers_new_software_and_opens_stage_one(self):
        response = self.client.post("/evaluaciones/nueva/", {"mode": "nuevo", "name": "Odoo", "version": "17", "license_type": "libre"})

        created = Evaluation.objects.filter(software__name="Odoo").get()
        self.assertRedirects(response, f"/evaluaciones/{created.pk}/etapa-1/")
        self.assertEqual(created.factors.count(), 18)

    def test_missing_license_keeps_figma_message_and_creates_nothing(self):
        response = self.client.post("/evaluaciones/nueva/", {"mode": "nuevo", "name": "Odoo"})

        self.assertContains(response, "Elige un tipo de licencia para continuar")
        self.assertFalse(Software.objects.filter(name="Odoo").exists())

    def test_administrator_gets_403(self):
        self.client.force_login(self.admin)

        self.assertEqual(self.client.get("/evaluaciones/nueva/").status_code, 403)


class StageOneViewTests(EvaluationViewsBase):
    def test_lists_18_factors_grouped_by_dimension(self):
        response = self.client.get(self.url("etapa-1/"))

        self.assertContains(response, "Tecnológica · 9 factores")
        self.assertContains(response, "Evaluados 0/18")
        self.assertContains(response, 'name="factor-', count=18 * 5)  # 4 radios + 1 scope select per row

    def test_autosave_returns_row_with_relative_importance(self):
        ev_factor = self.evaluation.factors.get(factor__name="Compatibilidad")
        field = f"factor-{ev_factor.factor_id}-decision_importance"

        response = self.client.post(self.url(f"factor/{ev_factor.factor_id}/"), {field: "4", f"factor-{ev_factor.factor_id}-scope": "externo"}, **HTMX)

        ev_factor.refresh_from_db()
        self.assertEqual((ev_factor.decision_importance, ev_factor.relative_importance), (4, 3))
        self.assertContains(response, "Relevante")
        self.assertContains(response, "Evaluados 1/18")

    def test_autosave_rejects_out_of_range_value(self):
        ev_factor = self.evaluation.factors.first()

        response = self.client.post(self.url(f"factor/{ev_factor.factor_id}/"), {f"factor-{ev_factor.factor_id}-decision_importance": "9"}, **HTMX)

        self.assertEqual(response.status_code, 400)
        ev_factor.refresh_from_db()
        self.assertIsNone(ev_factor.decision_importance)

    def test_other_users_draft_is_forbidden(self):
        self.client.force_login(self.luis)

        self.assertEqual(self.client.get(self.url("etapa-1/")).status_code, 403)

    def test_expired_session_on_autosave_returns_401(self):
        self.client.logout()
        ev_factor = self.evaluation.factors.first()

        response = self.client.post(self.url(f"factor/{ev_factor.factor_id}/"), {}, **HTMX)

        self.assertEqual(response.status_code, 401)

    def test_continue_requires_all_factors(self):
        response = self.client.post(self.url("etapa-1/"), follow=True)

        self.assertContains(response, "Asigna la importancia de los 18 factores para continuar.")

    def test_continue_opens_first_pending_factor(self):
        self.assign_all()

        response = self.client.post(self.url("etapa-1/"))

        first = workflow.factor_progress(self.evaluation)[0]["factor"]
        self.assertRedirects(response, self.url(f"etapa-2/?factor={first.factor_id}"))


class StageTwoAndThreeViewTests(EvaluationViewsBase):
    def setUp(self):
        super().setUp()
        self.assign_all()
        workflow.start_stage_two(self.evaluation)

    def test_answer_updates_live_pm(self):
        answer = EvaluationSubfactor.objects.filter(evaluation_factor__evaluation=self.evaluation, evaluation_factor__factor__name="Compatibilidad").first()

        response = self.client.post(self.url(f"respuesta/{answer.pk}/"), {f"answer-{answer.pk}-value": "4"}, **HTMX)

        self.assertContains(response, "PM parcial · 1 de 8")
        self.assertContains(response, "4,00")

    def test_results_redirect_to_missing_factor(self):
        response = self.client.get(self.url("etapa-3/"), follow=True)

        self.assertContains(response, "faltan 8 subfactores")

    def test_full_flow_finalizes_and_opens_detail(self):
        self.answer_all(4)

        stage3 = self.client.get(self.url("etapa-3/"))
        self.assertContains(stage3, "Adoptar")
        response = self.client.post(self.url("finalizar/"))

        self.evaluation.refresh_from_db()
        self.assertEqual((self.evaluation.status, self.evaluation.recommendation), ("finalizada", "A"))
        self.assertRedirects(response, f"/historial/{self.evaluation.pk}/", fetch_redirect_response=False)

    def test_saving_on_finalized_evaluation_is_forbidden(self):
        self.answer_all(4)
        workflow.finalize(self.evaluation)
        answer = EvaluationSubfactor.objects.filter(evaluation_factor__evaluation=self.evaluation).first()

        response = self.client.post(self.url(f"respuesta/{answer.pk}/"), {f"answer-{answer.pk}-value": "1"}, **HTMX)

        self.assertEqual(response.status_code, 403)
        answer.refresh_from_db()
        self.assertEqual(answer.value, 4)
