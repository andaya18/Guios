from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import CatalogVersion, Dimension, Factor, FactorVersion, Subfactor
from .services import CatalogDataError

# Sección 4.2 de la guía: factor -> (N.º subfactores, IS versión 1, IS versión 2).
TABLA_4_2 = {
    "Compatibilidad": (8, 3, 2),
    "Fiabilidad": (5, 3, 3),
    "Mantenibilidad": (1, 3, 3),
    "Personalización": (6, 3, 2),
    "Prueba": (1, 3, 3),
    "Documentación": (11, 2, 2),
    "Portabilidad": (2, 2, 2),
    "Reusabilidad": (2, 2, 3),
    "Usabilidad": (4, 2, 2),
    "Apoyo de la alta dirección": (1, 3, 3),
    "Formación": (4, 3, 2),
    "Soporte": (6, 3, 3),
    "Actitud hacia el cambio": (2, 2, 2),
    "Bloqueo de proveedores": (1, 2, 3),
    "Casos de estudio de adopción FLOSS": (1, 2, 2),
    "Centralidad de las TI": (2, 2, 2),
    "Tiempo de adopción": (2, 2, 3),
    "Coste total de propiedad (TCO)": (2, 3, 3),
}

CAMBIAN = {
    "Compatibilidad",
    "Personalización",
    "Reusabilidad",
    "Formación",
    "Bloqueo de proveedores",
    "Tiempo de adopción",
}

ALCANCE_EXTERNO = {
    "Compatibilidad",
    "Personalización",
    "Prueba",
    "Fiabilidad",
    "Reusabilidad",
    "Usabilidad",
    "Mantenibilidad",
    "Portabilidad",
    "Documentación",
    "Casos de estudio de adopción FLOSS",
    "Bloqueo de proveedores",
}


class CatalogoCargadoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_catalogo", stdout=StringIO())


class CargaDelCatalogoTests(CatalogoCargadoTestCase):
    def test_cuenta_dimensiones_factores_y_subfactores(self):
        self.assertEqual(Dimension.objects.count(), 3)
        self.assertEqual(Factor.objects.count(), 18)
        self.assertEqual(Subfactor.objects.count(), 61)

    def test_nombres_de_dimensiones(self):
        nombres = list(Dimension.objects.values_list("name", flat=True))
        self.assertEqual(nombres, ["Tecnológica", "Organizacional", "Económica"])

    def test_dimension_de_cada_factor(self):
        cantidades = {d.name: d.factors.count() for d in Dimension.objects.all()}
        self.assertEqual(
            cantidades, {"Tecnológica": 9, "Organizacional": 8, "Económica": 1}
        )

    def test_hay_36_factor_version(self):
        self.assertEqual(FactorVersion.objects.count(), 36)
        for version in CatalogVersion.objects.all():
            self.assertEqual(version.factor_values.count(), 18)

    def test_nombres_de_factores_coinciden_con_la_seccion_4_2(self):
        self.assertEqual(
            set(Factor.objects.values_list("name", flat=True)), set(TABLA_4_2)
        )

    def test_subfactores_por_factor_coinciden_con_la_seccion_4_2(self):
        for factor in Factor.objects.all():
            self.assertEqual(
                factor.subfactors.count(), TABLA_4_2[factor.name][0], factor.name
            )

    def test_orden_de_factores_y_subfactores_es_continuo(self):
        self.assertEqual(
            list(Factor.objects.values_list("order", flat=True)), list(range(1, 19))
        )
        for factor in Factor.objects.all():
            self.assertEqual(
                list(factor.subfactors.values_list("order", flat=True)),
                list(range(1, factor.subfactors.count() + 1)),
            )

    def test_subfactores_sin_citas_ni_texto_vacio(self):
        for texto in Subfactor.objects.values_list("name", flat=True):
            self.assertTrue(texto.strip())
            self.assertNotRegex(texto, r"\[\d")

    def test_actitud_y_apoyo_reciben_los_subfactores_resueltos(self):
        apoyo = Factor.objects.get(name="Apoyo de la alta dirección")
        actitud = Factor.objects.get(name="Actitud hacia el cambio")
        self.assertEqual(
            [s.name for s in apoyo.subfactors.all()],
            ["La alta dirección apoya la adopción exitosa de este software"],
        )
        self.assertIn(
            "El personal de TI de su organización respalda la adopción de este software",
            [s.name for s in actitud.subfactors.all()],
        )


class VersionesDelCatalogoTests(CatalogoCargadoTestCase):
    def test_versiones_uno_y_dos(self):
        v1 = CatalogVersion.objects.get(number=1)
        v2 = CatalogVersion.objects.get(number=2)
        self.assertEqual((v1.name, v1.status), ("Catálogo base de la tesis", "publicada"))
        self.assertEqual((v2.name, v2.status), ("Actualización 2020 a 2025", "activa"))
        self.assertEqual(CatalogVersion.objects.count(), 2)

    def test_importancia_sugerida_coincide_con_la_seccion_4_2(self):
        for fv in FactorVersion.objects.select_related("version", "factor"):
            _, is_v1, is_v2 = TABLA_4_2[fv.factor.name]
            esperado = is_v1 if fv.version.number == 1 else is_v2
            self.assertEqual(fv.suggested_importance, esperado, str(fv))

    def test_exactamente_seis_factores_cambian_de_is(self):
        cambian = {
            nombre for nombre, (_, v1, v2) in TABLA_4_2.items() if v1 != v2
        }
        self.assertEqual(cambian, CAMBIAN)
        en_base = set()
        for factor in Factor.objects.all():
            valores = set(
                FactorVersion.objects.filter(factor=factor).values_list(
                    "suggested_importance", flat=True
                )
            )
            if len(valores) > 1:
                en_base.add(factor.name)
        self.assertEqual(len(en_base), 6)
        self.assertEqual(en_base, CAMBIAN)

    def test_alcance_por_defecto_es_igual_en_ambas_versiones(self):
        for factor in Factor.objects.all():
            alcances = list(
                FactorVersion.objects.filter(factor=factor).values_list(
                    "default_scope", flat=True
                )
            )
            self.assertEqual(len(set(alcances)), 1, factor.name)
            esperado = "externo" if factor.name in ALCANCE_EXTERNO else "interno"
            self.assertEqual(alcances[0], esperado, factor.name)

    def test_soporte_es_interno_por_defecto(self):
        fv = FactorVersion.objects.filter(factor__name="Soporte")
        self.assertEqual(set(fv.values_list("default_scope", flat=True)), {"interno"})

    def test_solo_una_version_activa(self):
        self.assertEqual(CatalogVersion.objects.filter(status="activa").count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CatalogVersion.objects.create(number=3, name="Otra", status="activa")

    def test_una_version_borrador_o_publicada_adicional_es_valida(self):
        CatalogVersion.objects.create(number=3, name="Borrador", status="borrador")
        CatalogVersion.objects.create(number=4, name="Publicada", status="publicada")
        self.assertEqual(CatalogVersion.objects.filter(status="activa").count(), 1)

    def test_par_version_factor_es_unico(self):
        fv = FactorVersion.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            FactorVersion.objects.create(
                version=fv.version,
                factor=fv.factor,
                suggested_importance=2,
                default_scope="interno",
            )


class ComandoCargarCatalogoTests(TestCase):
    def test_es_idempotente(self):
        call_command("cargar_catalogo", stdout=StringIO())
        call_command("cargar_catalogo", stdout=StringIO())
        self.assertEqual(Dimension.objects.count(), 3)
        self.assertEqual(Factor.objects.count(), 18)
        self.assertEqual(Subfactor.objects.count(), 61)
        self.assertEqual(CatalogVersion.objects.count(), 2)
        self.assertEqual(FactorVersion.objects.count(), 36)

    def test_no_pisa_el_estado_de_versiones_existentes(self):
        call_command("cargar_catalogo", stdout=StringIO())
        CatalogVersion.objects.filter(number=2).update(status="publicada")
        CatalogVersion.objects.create(number=3, name="Nueva", status="activa")
        call_command("cargar_catalogo", stdout=StringIO())
        self.assertEqual(CatalogVersion.objects.get(number=2).status, "publicada")
        self.assertEqual(CatalogVersion.objects.filter(status="activa").count(), 1)

    def test_informa_el_resultado(self):
        salida = StringIO()
        call_command("cargar_catalogo", stdout=salida)
        self.assertIn(
            "Catálogo cargado: 3 dimensiones, 18 factores, 61 subfactores, 2 versiones.",
            salida.getvalue(),
        )

    def test_si_la_verificacion_falla_se_revierte_todo(self):
        with patch(
            "apps.catalog.services.verify_catalog",
            side_effect=CatalogDataError("falla simulada"),
        ):
            with self.assertRaisesMessage(Exception, "falla simulada"):
                call_command("cargar_catalogo", stdout=StringIO())
        self.assertEqual(Dimension.objects.count(), 0)
        self.assertEqual(Factor.objects.count(), 0)
        self.assertEqual(Subfactor.objects.count(), 0)
        self.assertEqual(CatalogVersion.objects.count(), 0)
        self.assertEqual(FactorVersion.objects.count(), 0)


class ModelosDelCatalogoTests(CatalogoCargadoTestCase):
    def test_representaciones_en_texto(self):
        self.assertEqual(str(Dimension.objects.first()), "Tecnológica")
        self.assertEqual(str(Factor.objects.first()), "Compatibilidad")
        self.assertEqual(
            str(CatalogVersion.objects.get(number=1)), "v1 · Catálogo base de la tesis"
        )
        fv = FactorVersion.objects.get(version__number=2, factor__name="Compatibilidad")
        self.assertEqual(str(fv), "v2 · Compatibilidad (IS 2)")
        self.assertTrue(str(Subfactor.objects.first()))
