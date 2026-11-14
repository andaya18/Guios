from django.test import TestCase

from apps.catalog.models import CatalogVersion, Factor, FactorVersion
from apps.catalog.services import load_catalog
from apps.management import services
from apps.management.services import CatalogRuleError


def values_of(number):
    return list(
        FactorVersion.objects.filter(version__number=number)
        .order_by("factor__order")
        .values_list("factor_id", "suggested_importance", "default_scope")
    )


class CompareVersionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_catalog()

    def test_v1_and_v2_differ_in_six_factors(self):
        v1, v2 = CatalogVersion.objects.get(number=1), CatalogVersion.objects.get(number=2)
        changes = services.compare_versions(v1, v2)
        self.assertEqual(len(changes), 6)
        self.assertTrue(all(change.field == "Importancia sugerida" for change in changes))
        self.assertEqual(len({change.factor for change in changes}), 6)

    def test_change_reports_labels_before_and_after(self):
        v1, v2 = CatalogVersion.objects.get(number=1), CatalogVersion.objects.get(number=2)
        change = services.compare_versions(v1, v2)[0]
        before = FactorVersion.objects.get(version=v1, factor=change.factor).suggested_importance
        self.assertRegex(change.before, rf"^(Irrelevante|Opcional|Importante|Fundamental) \({before}\)$")

    def test_scope_changes_are_reported(self):
        draft = services.create_draft()
        factor = Factor.objects.get(order=1)
        current = FactorVersion.objects.get(version=draft, factor=factor)
        other = "externo" if current.default_scope == "interno" else "interno"
        services.update_draft_factor(draft, factor, current.suggested_importance, other)
        changes = services.compare_versions(CatalogVersion.objects.get(number=2), draft)
        self.assertEqual([(c.factor, c.field) for c in changes], [(factor, "Alcance por defecto")])


class DraftVersionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_catalog()

    def test_create_draft_copies_the_active_version(self):
        draft = services.create_draft()
        self.assertEqual((draft.number, draft.status), (3, "borrador"))
        self.assertEqual(
            [row[1:] for row in values_of(3)],
            [row[1:] for row in values_of(2)],
        )

    def test_only_one_draft_at_a_time(self):
        first = services.create_draft()
        second = services.create_draft()
        self.assertEqual(first, second)
        self.assertEqual(CatalogVersion.objects.filter(status="borrador").count(), 1)

    def test_update_draft_factor(self):
        draft = services.create_draft()
        factor = Factor.objects.get(order=3)
        services.update_draft_factor(draft, factor, 4, "externo")
        value = FactorVersion.objects.get(version=draft, factor=factor)
        self.assertEqual((value.suggested_importance, value.default_scope), (4, "externo"))

    def test_published_versions_cannot_be_edited(self):
        active = CatalogVersion.objects.get(number=2)
        before = values_of(2)
        with self.assertRaisesMessage(CatalogRuleError, "Solo se puede editar una versión en borrador."):
            services.update_draft_factor(active, Factor.objects.get(order=1), 1, "interno")
        self.assertEqual(values_of(2), before)

    def test_rejects_importance_out_of_range_and_unknown_scope(self):
        draft = services.create_draft()
        factor = Factor.objects.get(order=1)
        before = values_of(3)
        for importance, scope in [(0, "interno"), (5, "interno"), (2, "ambos")]:
            with self.subTest(importance=importance, scope=scope):
                with self.assertRaises(CatalogRuleError):
                    services.update_draft_factor(draft, factor, importance, scope)
        self.assertEqual(values_of(3), before)


class PublishVersionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_catalog()

    def test_publish_promotes_draft_and_keeps_previous_published(self):
        draft = services.create_draft()
        v2_before = values_of(2)
        services.publish_version(draft, justification="Revisión 2026", authorized_by="PhD. V. Rea", name="Actualización 2026")
        draft.refresh_from_db()
        v2 = CatalogVersion.objects.get(number=2)
        self.assertEqual(draft.status, "activa")
        self.assertIsNotNone(draft.published_at)
        self.assertEqual((draft.justification, draft.authorized_by, draft.name), ("Revisión 2026", "PhD. V. Rea", "Actualización 2026"))
        self.assertEqual(v2.status, "publicada")
        self.assertEqual(CatalogVersion.objects.filter(status="activa").count(), 1)
        self.assertEqual(values_of(2), v2_before)

    def test_publish_records_who_published(self):
        from apps.management.tests.helpers import make_admin

        admin = make_admin()
        draft = services.create_draft()
        services.publish_version(draft, justification="Sustento", authorized_by="PhD. V. Rea", name="x", published_by=admin)
        draft.refresh_from_db()
        self.assertEqual(draft.published_by, admin)

    def test_only_drafts_can_be_published(self):
        v1 = CatalogVersion.objects.get(number=1)
        with self.assertRaisesMessage(CatalogRuleError, "Solo se puede publicar una versión en borrador."):
            services.publish_version(v1, justification="x", authorized_by="y", name="z")
        self.assertEqual(CatalogVersion.objects.get(number=2).status, "activa")

    def test_publish_requires_justification_and_authorizer(self):
        draft = services.create_draft()
        with self.assertRaises(CatalogRuleError):
            services.publish_version(draft, justification=" ", authorized_by="PhD. V. Rea", name="x")
        with self.assertRaises(CatalogRuleError):
            services.publish_version(draft, justification="Sustento", authorized_by="", name="x")
        draft.refresh_from_db()
        self.assertEqual(draft.status, "borrador")


class SetActiveVersionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_catalog()

    def test_any_published_version_can_become_active(self):
        services.set_active_version(CatalogVersion.objects.get(number=1))
        statuses = dict(CatalogVersion.objects.values_list("number", "status"))
        self.assertEqual(statuses, {1: "activa", 2: "publicada"})

    def test_draft_cannot_become_active(self):
        draft = services.create_draft()
        with self.assertRaisesMessage(CatalogRuleError, "Solo se puede activar una versión publicada."):
            services.set_active_version(draft)
        self.assertEqual(CatalogVersion.objects.get(number=2).status, "activa")
