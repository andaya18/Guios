from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.ai.verification import AIUnavailable, CitationScore, DocumentVerdict
from apps.catalog.models import Factor
from apps.literature import services
from apps.literature.models import Citation, Document, FactorImportance, ImportanceRun

# Thesis-update values (doc/sugerida.pdf, Table 17) the full dataset must reproduce when every citation is valid.
UPDATE_IS = {
    "Compatibilidad": 2, "Fiabilidad": 3, "Mantenibilidad": 3, "Personalización": 2, "Prueba": 3,
    "Documentación": 2, "Portabilidad": 2, "Reusabilidad": 3, "Usabilidad": 2, "Apoyo de la alta dirección": 3,
    "Formación": 2, "Soporte": 3, "Actitud hacia el cambio": 2, "Bloqueo de proveedores": 3,
    "Casos de estudio de adopción FLOSS": 2, "Centralidad de las TI": 2, "Tiempo de adopción": 3,
    "Coste total de propiedad (TCO)": 3,
}


class FakeVerifier:
    """Scores every citation with `score`, records each call, optionally fails."""

    model = "fake-model"

    def __init__(self, score=3, fail=None, scores_by_document=None):
        self.score, self.fail, self.scores_by_document = score, fail, scores_by_document or {}
        self.calls = []

    def verify(self, document, citations):
        self.calls.append(document["key"])
        if self.fail:
            raise AIUnavailable(self.fail, "simulated")
        score = self.scores_by_document.get(document["key"], self.score)
        return DocumentVerdict(
            model=self.model,
            prompt=f"prompt {document['key']}",
            raw_response='{"citas": []}',
            scores=tuple(CitationScore(c["subfactor_id"], score, "Justificación breve.") for c in citations),
            sources=({"title": "Fuente", "uri": "https://example.org"},),
        )


def values(run):
    return {row.factor.name: row.value for row in run.factors.select_related("factor")}


class LiteratureComputeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", verbosity=0)
        call_command("cargar_literatura", verbosity=0)

    def compute(self, verifier):
        return services.compute(verifier=verifier)

    def test_loader_creates_table_14(self):
        self.assertEqual((Document.objects.count(), Citation.objects.count()), (13, 71))

    def test_loader_is_idempotent(self):
        call_command("cargar_literatura", verbosity=0)

        self.assertEqual((Document.objects.count(), Citation.objects.count()), (13, 71))

    def test_ai_result_reproduces_table_17_and_keeps_trace(self):
        run = self.compute(FakeVerifier(score=3))

        self.assertEqual(run.origin, "ia")
        self.assertEqual(values(run), UPDATE_IS)
        soporte = run.factors.get(factor__name="Soporte")
        self.assertEqual((soporte.ns, soporte.tc, soporte.il, soporte.origin), (6, 8, 3, "ia"))
        assessment = Document.objects.get(key="butler-2022").assessments.get()
        self.assertEqual(assessment.model, "fake-model")
        self.assertEqual(assessment.sources, [{"title": "Fuente", "uri": "https://example.org"}])
        self.assertTrue(assessment.prompt and assessment.raw_response and assessment.created_at)

    def test_repeating_without_changes_is_identical_and_makes_no_calls(self):
        first = self.compute(FakeVerifier())
        verifier = FakeVerifier()

        second = self.compute(verifier)

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(values(second), values(first))
        self.assertEqual(verifier.calls, [])

    def test_deleting_a_document_changes_hash_and_recalculates_without_new_calls(self):
        first = self.compute(FakeVerifier())
        Document.objects.get(key="sanchez-2020").delete()
        verifier = FakeVerifier()

        second = self.compute(verifier)

        self.assertNotEqual(second.corpus_hash, first.corpus_hash)
        self.assertEqual(verifier.calls, [])
        self.assertEqual(second.factors.get(factor__name="Bloqueo de proveedores").tc, 3)
        self.assertEqual(second.factors.get(factor__name="Soporte").tc, 5)

    def test_deleting_a_citation_reverifies_only_that_document(self):
        self.compute(FakeVerifier())
        compat = Factor.objects.get(name="Compatibilidad")
        Citation.objects.get(document__key="bostan-2024", subfactor__factor=compat).delete()
        verifier = FakeVerifier()

        run = self.compute(verifier)

        self.assertEqual(verifier.calls, ["bostan-2024"])
        self.assertEqual(run.factors.get(factor=compat).tc, 9)

    def test_adding_a_citation_recalculates_automatically(self):
        first = self.compute(FakeVerifier())
        casos = Factor.objects.get(name="Casos de estudio de adopción FLOSS")
        Citation.objects.create(document=Document.objects.get(key="li-2022"), subfactor=casos.subfactors.first())
        verifier = FakeVerifier()

        run = self.compute(verifier)

        self.assertNotEqual(run.pk, first.pk)
        self.assertEqual(verifier.calls, ["li-2022"])
        self.assertEqual(run.factors.get(factor=casos).tc, 1)

    def test_invalid_scores_do_not_count_for_tc(self):
        run = self.compute(FakeVerifier(score=3, scores_by_document={"butler-2022": 1}))

        self.assertEqual(run.factors.get(factor__name="Mantenibilidad").tc, 2)

    def test_ai_failure_uses_fallback_and_saves_nothing_invalid(self):
        for kind in ("timeout", "quota", "auth", "network", "invalid_response"):
            with self.subTest(kind=kind):
                run = self.compute(FakeVerifier(fail=kind))

                self.assertEqual(run.origin, "respaldo")
                self.assertIn(kind, run.error)
                self.assertEqual(values(run), UPDATE_IS)
                self.assertTrue(all(row.il is None and row.origin == "respaldo" for row in run.factors.all()))
        self.assertFalse(Document.objects.filter(assessments__isnull=False).exists())

    @override_settings(AI_PROVIDER="disabled", AI_API_KEY="")
    def test_without_key_uses_fallback(self):
        run = services.compute()

        self.assertEqual((run.origin, run.error), ("respaldo", "disabled"))

    def test_fallback_is_replaced_by_ai_when_available_again(self):
        fallback = self.compute(FakeVerifier(fail="quota"))

        run = self.compute(FakeVerifier())

        self.assertEqual(run.corpus_hash, fallback.corpus_hash)
        self.assertEqual(run.origin, "ia")
        self.assertEqual(services.current_run().pk, run.pk)

    def test_fallback_is_reused_while_ai_stays_unavailable(self):
        first = self.compute(FakeVerifier(fail="timeout"))

        second = self.compute(FakeVerifier(fail="timeout"))

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(ImportanceRun.objects.count(), 1)

    def test_discrepancy_with_fallback_is_recorded(self):
        run = self.compute(FakeVerifier(score=3, scores_by_document={"li-2022": 0, "linaker-2022": 0}))

        rows = {row.factor.name: row for row in run.factors.select_related("factor")}
        differing = [name for name, row in rows.items() if row.differs_from_fallback]
        self.assertTrue(differing)
        for name in differing:
            self.assertEqual(rows[name].fallback_value, UPDATE_IS[name])
            self.assertNotEqual(rows[name].value, rows[name].fallback_value)

    def test_partial_failure_keeps_verified_documents_for_next_run(self):
        self.compute(FakeVerifier(fail="timeout"))
        self.compute(FakeVerifier(scores_by_document={}))
        verifier = FakeVerifier()

        services.compute(verifier=verifier, force=True)

        self.assertEqual(verifier.calls, [])
        self.assertEqual(FactorImportance.objects.filter(run=services.current_run()).count(), 18)
