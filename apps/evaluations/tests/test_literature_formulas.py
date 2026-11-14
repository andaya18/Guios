"""Suggested importance from literature citations (doc/sugerida.pdf, Tables 12-17)."""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.evaluations import services

FACTORS = [
    "Compatibilidad", "Fiabilidad", "Mantenibilidad", "Personalización", "Prueba", "Documentación",
    "Portabilidad", "Reusabilidad", "Usabilidad", "Apoyo de la alta dirección", "Formación", "Soporte",
    "Actitud hacia el cambio", "Bloqueo de proveedores", "Casos de estudio de adopción FLOSS",
    "Centralidad de las TI", "Tiempo de adopción", "Coste total de propiedad (TCO)",
]
NS = [8, 5, 1, 6, 1, 11, 2, 2, 4, 1, 4, 6, 2, 1, 1, 2, 2, 2]

# Table 13 (thesis 2008-2019): TC, IL, IS.
THESIS_TC = [33, 19, 4, 30, 4, 20, 4, 5, 14, 5, 27, 43, 3, 3, 1, 2, 2, 24]
THESIS_IL = [3, 3, 3, 4, 3, 1, 2, 2, 2, 4, 4, 4, 1, 2, 1, 1, 1, 4]
THESIS_IS = [3, 3, 3, 3, 3, 2, 2, 2, 2, 3, 3, 3, 2, 2, 2, 2, 2, 3]

# Tables 15 and 17 (update 2020-2025): TC, IL, IS.
UPDATE_TC = [10, 7, 3, 4, 2, 9, 2, 4, 2, 2, 4, 8, 2, 4, 0, 1, 4, 3]
UPDATE_IL = [2, 3, 4, 1, 3, 1, 2, 3, 1, 3, 2, 3, 2, 4, 1, 1, 3, 3]
UPDATE_IS = [2, 3, 3, 2, 3, 2, 2, 3, 2, 3, 2, 3, 2, 3, 2, 2, 3, 3]


def counts(tc):
    return {name: (ns, cites) for name, ns, cites in zip(FACTORS, NS, tc)}


class QuartileTests(SimpleTestCase):
    def test_thesis_cuts_match_quartile_inc(self):
        ratios = [Decimal(c) / Decimal(n) for c, n in zip(THESIS_TC, NS)]

        cuts = services.cortes_cuartiles(ratios)

        self.assertEqual([round(c, 2) for c in cuts], [Decimal("1.86"), Decimal("3.65"), Decimal("4.78"), Decimal("12.00")])

    def test_update_cuts_match_table_16(self):
        ratios = [Decimal(c) / Decimal(n) for c, n in zip(UPDATE_TC, NS)]

        cuts = services.cortes_cuartiles(ratios)

        self.assertEqual([round(c, 2) for c in cuts], [Decimal("0.86"), Decimal("1.29"), Decimal("2.00"), Decimal("4.00")])

    def test_value_equal_to_a_cut_goes_to_lower_quartile(self):
        cuts = (Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"))

        self.assertEqual(services.importancia_literatura(Decimal("2"), cuts), 2)
        self.assertEqual(services.importancia_literatura(Decimal("2.0001"), cuts), 3)
        self.assertEqual(services.importancia_literatura(Decimal("1"), cuts), 1)

    def test_needs_at_least_two_factors(self):
        with self.assertRaises(ValueError):
            services.cortes_cuartiles([Decimal("1")])


class SuggestedImportanceTests(SimpleTestCase):
    def test_expert_importance_crosses_the_matrix(self):
        self.assertEqual([services.importancia_sugerida(3, il) for il in (1, 2, 3, 4)], [2, 2, 3, 3])
        self.assertEqual(services.importancia_sugerida(4, 4), 4)

    def test_rejects_values_outside_scale(self):
        with self.assertRaises(ValueError):
            services.importancia_sugerida(3, 5)

    def test_thesis_table_13_is_reproduced(self):
        rows = services.calcular_importancia_sugerida(counts(THESIS_TC), importancia_experto=3)

        self.assertEqual([rows[name]["il"] for name in FACTORS], THESIS_IL)
        self.assertEqual([rows[name]["is"] for name in FACTORS], THESIS_IS)
        self.assertEqual(rows["Soporte"]["r"].quantize(Decimal("0.01")), Decimal("7.17"))

    def test_update_table_17_is_reproduced(self):
        rows = services.calcular_importancia_sugerida(counts(UPDATE_TC), importancia_experto=3)

        self.assertEqual([rows[name]["il"] for name in FACTORS], UPDATE_IL)
        self.assertEqual([rows[name]["is"] for name in FACTORS], UPDATE_IS)

    def test_result_is_identical_on_repeated_runs(self):
        first = services.calcular_importancia_sugerida(counts(UPDATE_TC), importancia_experto=3)

        self.assertEqual(first, services.calcular_importancia_sugerida(counts(UPDATE_TC), importancia_experto=3))
