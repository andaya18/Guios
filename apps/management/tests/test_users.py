from django.test import TestCase

from apps.accounts.models import User

from .helpers import PASSWORD, make_admin, make_decisor, make_organization


class UserListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.unemi = make_organization()
        cls.gad = make_organization("GAD Milagro", "milagro.gob.ec")
        cls.ana = make_decisor(cls.unemi)
        cls.sofia = make_decisor(cls.gad, email="sofia@milagro.gob.ec", first_name="Sofía", last_name="León")
        cls.old = make_decisor(cls.unemi, email="old@unemi.edu.ec", first_name="Pedro", is_active=False)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_active_tab_lists_only_active_users_with_counts(self):
        response = self.client.get("/gestion/usuarios/")
        self.assertEqual(list(response.context["users"]), [self.ana, self.admin, self.sofia])
        self.assertContains(response, "Activos · 3")
        self.assertContains(response, "Desactivados · 1")
        self.assertNotContains(response, "Pendientes")
        self.assertContains(response, "Los usuarios no se eliminan: se desactivan para conservar la autoría de sus evaluaciones.")

    def test_deactivated_tab(self):
        response = self.client.get("/gestion/usuarios/?estado=desactivados")
        self.assertEqual(list(response.context["users"]), [self.old])

    def test_search_by_name_or_email(self):
        by_name = self.client.get("/gestion/usuarios/?q=sofía")
        by_email = self.client.get("/gestion/usuarios/?q=ANA@unemi")
        self.assertEqual(list(by_name.context["users"]), [self.sofia])
        self.assertEqual(list(by_email.context["users"]), [self.ana])

    def test_filters_by_role_and_organization(self):
        by_role = self.client.get("/gestion/usuarios/?rol=administrador")
        by_org = self.client.get(f"/gestion/usuarios/?organizacion={self.gad.pk}")
        self.assertEqual(list(by_role.context["users"]), [self.admin])
        self.assertEqual(list(by_org.context["users"]), [self.sofia])

    def test_administrator_row_shows_role_without_organization(self):
        response = self.client.get("/gestion/usuarios/?rol=administrador")
        self.assertContains(response, '<span class="pill pill--dark">Administrador</span>', html=True)
        self.assertContains(response, "—")


class UserFormTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.organization = make_organization()
        self.client.force_login(self.admin)

    def payload(self, **overrides):
        data = {
            "first_name": "Luis",
            "last_name": "Andrade",
            "email": "landrade@unemi.edu.ec",
            "role": "decisor",
            "organization": self.organization.pk,
            "area": "Dirección TIC",
            "password": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_creates_decisor_with_organization(self):
        response = self.client.post("/gestion/usuarios/nuevo/", self.payload())
        self.assertRedirects(response, "/gestion/usuarios/")
        user = User.objects.get(email="landrade@unemi.edu.ec")
        self.assertEqual((user.role, user.organization), ("decisor", self.organization))
        self.assertTrue(user.check_password(PASSWORD))

    def test_creates_administrator_without_organization(self):
        self.client.post(
            "/gestion/usuarios/nuevo/",
            self.payload(email="admin2@guios.ec", role="administrador"),
        )
        user = User.objects.get(email="admin2@guios.ec")
        self.assertEqual(user.role, "administrador")
        self.assertIsNone(user.organization)

    def test_decisor_requires_organization(self):
        count = User.objects.count()
        response = self.client.post("/gestion/usuarios/nuevo/", self.payload(organization=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Un decisor debe pertenecer a una organización.")
        self.assertEqual(User.objects.count(), count)

    def test_rejects_duplicate_email(self):
        make_decisor(self.organization, email="landrade@unemi.edu.ec")
        count = User.objects.count()
        response = self.client.post("/gestion/usuarios/nuevo/", self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), count)

    def test_edits_user(self):
        user = make_decisor(self.organization)
        response = self.client.post(
            f"/gestion/usuarios/{user.pk}/",
            {
                "first_name": "Ana María",
                "last_name": "Ruiz",
                "email": user.email,
                "role": "decisor",
                "organization": self.organization.pk,
                "area": "",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, "/gestion/usuarios/")
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Ana María")
        self.assertTrue(user.check_password(PASSWORD))

    def test_deactivates_user_without_deleting_it(self):
        user = make_decisor(self.organization)
        count = User.objects.count()
        self.client.post(
            f"/gestion/usuarios/{user.pk}/",
            {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "role": "decisor",
                "organization": self.organization.pk,
                "area": "",
            },
        )
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(User.objects.count(), count)

    def test_edit_form_has_no_delete_action(self):
        user = make_decisor(self.organization)
        response = self.client.get(f"/gestion/usuarios/{user.pk}/")
        self.assertContains(response, "Editar usuario")
        self.assertNotContains(response, "Eliminar")
