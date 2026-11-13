from django.test import TestCase

from apps.accounts.models import Organization

from .helpers import make_admin, make_decisor, make_organization


class OrganizationListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.unemi = make_organization()
        cls.agro = make_organization("Agroexport S.A.", "agro.com", sector="privado")
        cls.xyz = make_organization("Consultora XYZ", "xyz.com", sector="privado", is_active=False)
        make_decisor(cls.unemi)
        make_decisor(cls.unemi, email="luis@unemi.edu.ec")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_lists_all_with_tab_counts_and_user_count(self):
        response = self.client.get("/gestion/organizaciones/")
        organizations = list(response.context["organizations"])
        self.assertEqual(organizations, [self.agro, self.xyz, self.unemi])
        self.assertEqual(organizations[2].user_count, 2)
        self.assertContains(response, "Todas · 3")
        self.assertContains(response, "Activas · 2")
        self.assertContains(response, "Inactivas · 1")
        self.assertContains(response, "Una organización con evaluaciones no se elimina: se desactiva y sus usuarios ya no pueden crear evaluaciones nuevas.")

    def test_tabs_search_and_sector_filter(self):
        inactive = self.client.get("/gestion/organizaciones/?estado=inactivas")
        search = self.client.get("/gestion/organizaciones/?q=agro")
        sector = self.client.get("/gestion/organizaciones/?sector=publico")
        self.assertEqual(list(inactive.context["organizations"]), [self.xyz])
        self.assertEqual(list(search.context["organizations"]), [self.agro])
        self.assertEqual(list(sector.context["organizations"]), [self.unemi])

    def test_inactive_row_offers_reactivation(self):
        response = self.client.get("/gestion/organizaciones/?estado=inactivas")
        self.assertContains(response, "Reactivar")


class OrganizationFormTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.client.force_login(self.admin)

    def test_creates_organization(self):
        response = self.client.post(
            "/gestion/organizaciones/nueva/",
            {"name": "Hospital León Becerra", "domain": "hlb.gob.ec", "sector": "publico", "is_active": "on"},
        )
        self.assertRedirects(response, "/gestion/organizaciones/")
        organization = Organization.objects.get(domain="hlb.gob.ec")
        self.assertEqual((organization.name, organization.sector, organization.is_active), ("Hospital León Becerra", "publico", True))

    def test_create_modal_copy(self):
        response = self.client.get("/gestion/organizaciones/nueva/")
        self.assertContains(response, "Nueva organización")
        self.assertContains(response, "Activa · visible en el registro de usuarios")
        self.assertContains(response, "Crear organización")

    def test_edits_name_and_sector(self):
        organization = make_organization()
        self.client.post(
            f"/gestion/organizaciones/{organization.pk}/",
            {"name": "UNEMI – Dirección TIC", "domain": "unemi.edu.ec", "sector": "privado", "is_active": "on"},
        )
        organization.refresh_from_db()
        self.assertEqual((organization.name, organization.sector), ("UNEMI – Dirección TIC", "privado"))

    def test_domain_is_locked_once_it_has_users(self):
        organization = make_organization()
        make_decisor(organization)
        response = self.client.post(
            f"/gestion/organizaciones/{organization.pk}/",
            {"name": "UNEMI", "domain": "otro.edu.ec", "sector": "publico", "is_active": "on"},
        )
        self.assertRedirects(response, "/gestion/organizaciones/")
        organization.refresh_from_db()
        self.assertEqual(organization.domain, "unemi.edu.ec")
        edit = self.client.get(f"/gestion/organizaciones/{organization.pk}/")
        self.assertTrue(edit.context["form"].fields["domain"].disabled)

    def test_domain_is_editable_without_users(self):
        organization = make_organization()
        self.client.post(
            f"/gestion/organizaciones/{organization.pk}/",
            {"name": "UNEMI", "domain": "nuevo.edu.ec", "sector": "publico", "is_active": "on"},
        )
        organization.refresh_from_db()
        self.assertEqual(organization.domain, "nuevo.edu.ec")

    def test_deactivates_and_reactivates(self):
        organization = make_organization()
        self.client.post(
            f"/gestion/organizaciones/{organization.pk}/",
            {"name": "UNEMI", "domain": "unemi.edu.ec", "sector": "publico"},
        )
        organization.refresh_from_db()
        self.assertFalse(organization.is_active)
        response = self.client.post(f"/gestion/organizaciones/{organization.pk}/reactivar/")
        self.assertRedirects(response, "/gestion/organizaciones/")
        organization.refresh_from_db()
        self.assertTrue(organization.is_active)
        self.assertEqual(Organization.objects.count(), 1)
