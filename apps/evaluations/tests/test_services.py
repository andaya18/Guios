from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.evaluations import services


def factor(foda, ir):
    return SimpleNamespace(foda=foda, importancia_relativa=ir)


def evaluacion(recomendacion, num_problemas):
    return SimpleNamespace(recomendacion=recomendacion, num_problemas=num_problemas)


class EscalaTests(SimpleTestCase):
    def test_escala_de_importancia(self):
        self.assertEqual(
            services.ESCALA,
            {1: "Irrelevante", 2: "Opcional", 3: "Importante", 4: "Fundamental"},
        )


class MatrizTests(SimpleTestCase):
    ESPERADA = {
        4: {1: 2, 2: 3, 3: 3, 4: 4},
        3: {1: 2, 2: 2, 3: 3, 4: 3},
        2: {1: 1, 2: 2, 3: 2, 4: 3},
        1: {1: 1, 2: 1, 3: 2, 4: 2},
    }

    def test_las_16_celdas_de_la_matriz(self):
        for id_decisor, fila in self.ESPERADA.items():
            for is_sugerida, ir in fila.items():
                with self.subTest(id=id_decisor, is_sugerida=is_sugerida):
                    self.assertEqual(services.MATRIZ[id_decisor][is_sugerida], ir)
                    self.assertEqual(
                        services.importancia_relativa(id_decisor, is_sugerida), ir
                    )

    def test_matriz_tiene_exactamente_16_celdas(self):
        self.assertEqual(sum(len(f) for f in services.MATRIZ.values()), 16)

    def test_ir_id4_is3_es_3(self):
        self.assertEqual(services.importancia_relativa(4, 3), 3)

    def test_ir_id1_is2_es_1_y_se_descarta(self):
        ir = services.importancia_relativa(1, 2)
        self.assertEqual(ir, 1)
        self.assertFalse(services.es_relevante(ir))

    def test_ir_id3_is2_es_2(self):
        ir = services.importancia_relativa(3, 2)
        self.assertEqual(ir, 2)
        self.assertTrue(services.es_relevante(ir))

    def test_irrelevante_con_is3_se_conserva_como_opcional(self):
        ir = services.importancia_relativa(1, 3)
        self.assertEqual(ir, 2)
        self.assertTrue(services.es_relevante(ir))

    def test_es_relevante_solo_si_ir_mayor_que_1(self):
        self.assertFalse(services.es_relevante(1))
        for ir in (2, 3, 4):
            self.assertTrue(services.es_relevante(ir))


class ResumenFactorTests(SimpleTestCase):
    def assertResumen(self, calificaciones, cumple, pm_mostrada):
        pm, resultado = services.resumen_factor(calificaciones)
        self.assertIs(resultado, cumple)
        self.assertEqual(services.formatear_pm(pm), pm_mostrada)

    def test_pm_exacta_en_el_limite(self):
        self.assertResumen([3, 3, 3], True, "3,00")

    def test_justo_por_debajo(self):
        self.assertResumen([4, 3, 3, 3, 3, 3, 3, 1], False, "2,88")

    def test_justo_en_el_limite(self):
        self.assertResumen([4, 3, 3, 3, 3, 3, 3, 2], True, "3,00")

    def test_con_no_se(self):
        self.assertResumen([2, 2, 4, 4], True, "3,00")

    def test_pm_es_decimal_sin_redondear(self):
        pm, _ = services.resumen_factor([4, 3, 3, 3, 3, 3, 3, 1])
        self.assertIsInstance(pm, Decimal)
        self.assertEqual(pm, Decimal("2.875"))

    def test_clasificacion_no_depende_del_numero_redondeado(self):
        # Suma 2999 < 3000: no cumple, aunque la PM se muestre como "3,00".
        pm, cumple = services.resumen_factor([3] * 999 + [2])
        self.assertFalse(cumple)
        self.assertEqual(services.formatear_pm(pm), "3,00")


class FormatearPmTests(SimpleTestCase):
    def test_dos_decimales_con_coma(self):
        self.assertEqual(services.formatear_pm(Decimal("2.875")), "2,88")
        self.assertEqual(services.formatear_pm(Decimal("3")), "3,00")
        self.assertEqual(services.formatear_pm(Decimal("1")), "1,00")
        self.assertEqual(services.formatear_pm(Decimal("4")), "4,00")


class ClasificarFodaTests(SimpleTestCase):
    def test_interno_cumple_es_fortaleza(self):
        self.assertEqual(services.clasificar_foda(True, "interno"), "Fortaleza")

    def test_interno_no_cumple_es_debilidad(self):
        self.assertEqual(services.clasificar_foda(False, "interno"), "Debilidad")

    def test_externo_cumple_es_oportunidad(self):
        self.assertEqual(services.clasificar_foda(True, "externo"), "Oportunidad")

    def test_externo_no_cumple_es_amenaza(self):
        self.assertEqual(services.clasificar_foda(False, "externo"), "Amenaza")


class RecomendarTests(SimpleTestCase):
    def test_a_sin_factores_problematicos(self):
        factores = [factor("Fortaleza", 3), factor("Oportunidad", 2)]
        self.assertEqual(services.recomendar(factores), "A")

    def test_a_sin_factores_relevantes(self):
        self.assertEqual(services.recomendar([]), "A")

    def test_b_debilidad_con_ir_2(self):
        factores = [factor("Fortaleza", 3), factor("Debilidad", 2)]
        self.assertEqual(services.recomendar(factores), "B")

    def test_c_amenaza_con_ir_3(self):
        factores = [factor("Fortaleza", 3), factor("Amenaza", 3)]
        self.assertEqual(services.recomendar(factores), "C")

    def test_c_amenaza_con_ir_4(self):
        self.assertEqual(services.recomendar([factor("Amenaza", 4)]), "C")

    def test_mezcla_b_y_c_gana_c(self):
        factores = [factor("Debilidad", 2), factor("Debilidad", 4)]
        self.assertEqual(services.recomendar(factores), "C")


class TextosRecomendacionTests(SimpleTestCase):
    def test_texto_ra(self):
        self.assertEqual(
            services.RA,
            "Recomendación A: Adoptar. Todos los factores relevantes han sido "
            "identificados como Oportunidades y/o Fortalezas. Esto quiere decir "
            "que la organización cumple satisfactoriamente con la mayoría de "
            "requisitos para adoptar la solución.",
        )

    def test_texto_rb(self):
        self.assertEqual(
            services.RB,
            "Recomendación B: Adoptar con matices. Es posible adoptar. A pesar de "
            "que se han detectado amenazas y/o debilidades, estas corresponden a "
            "factores cuya importancia relativa es opcional; por lo tanto, se "
            "sugiere revisar los criterios que no cumplen con lo mínimo requerido "
            "para adoptar.",
        )

    def test_texto_rc(self):
        self.assertEqual(
            services.RC,
            "Recomendación C: Analizar y posponer la adopción. Se han detectado "
            "debilidades y/o amenazas en factores cuya importancia relativa es "
            "importante o fundamental. Se sugiere analizar estos factores y "
            "posponer la adopción hasta resolverlos.",
        )

    def test_textos_por_letra(self):
        self.assertEqual(
            services.TEXTOS_RECOMENDACION,
            {"A": services.RA, "B": services.RB, "C": services.RC},
        )


class CompararTests(SimpleTestCase):
    def test_clave_comparacion(self):
        self.assertEqual(services.clave_comparacion(evaluacion("A", 0)), (0, 0))
        self.assertEqual(services.clave_comparacion(evaluacion("B", 3)), (1, 3))
        self.assertEqual(services.clave_comparacion(evaluacion("C", 1)), (2, 1))

    def test_empate_dos_b_con_dos_problemas(self):
        uno, dos = evaluacion("B", 2), evaluacion("B", 2)
        ordenadas, mejores = services.comparar([uno, dos])
        self.assertEqual(len(ordenadas), 2)
        self.assertEqual(len(mejores), 2)
        self.assertEqual(
            services.MENSAJE_EMPATE,
            "Las evaluaciones están empatadas: cualquiera de las alternativas "
            "puede adoptarse",
        )

    def test_sin_empate_gana_a_contra_b(self):
        a, b = evaluacion("A", 0), evaluacion("B", 1)
        ordenadas, mejores = services.comparar([b, a])
        self.assertEqual(ordenadas, [a, b])
        self.assertEqual(mejores, [a])

    def test_sin_empate_gana_b_con_1_problema_contra_b_con_3(self):
        uno, tres = evaluacion("B", 1), evaluacion("B", 3)
        ordenadas, mejores = services.comparar([tres, uno])
        self.assertEqual(ordenadas, [uno, tres])
        self.assertEqual(mejores, [uno])

    def test_mejor_recomendacion_pesa_mas_que_menos_problemas(self):
        b_con_5, c_con_0 = evaluacion("B", 5), evaluacion("C", 0)
        ordenadas, mejores = services.comparar([c_con_0, b_con_5])
        self.assertEqual(ordenadas, [b_con_5, c_con_0])
        self.assertEqual(mejores, [b_con_5])
