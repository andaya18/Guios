from unittest.mock import patch
from django.core import mail
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
    """U02 is a right-side drawer over the U01 list (Figma), never a separate page."""

    def setUp(self):
        self.admin = make_admin()
        self.organization = make_organization()
        self.client.force_login(self.admin)

    def payload(self, **overrides):
        data = {
            "full_name": "Luis Andrade",
            "email": "landrade@unemi.edu.ec",
            "role": "decisor",
            "organization": self.organization.pk,
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_new_user_drawer_opens_over_the_list(self):
        make_decisor(self.organization, email="ana@unemi.edu.ec", first_name="Ana", last_name="Ruiz")

        response = self.client.get("/gestion/usuarios/nuevo/")

        self.assertContains(response, 'class="drawer"')
        self.assertContains(response, "Nuevo usuario")
        self.assertContains(response, "ana@unemi.edu.ec")  # the list stays behind the drawer
        for text in ("Nombre completo", "Correo electrónico", "Evalúa software de su organización",
                     "Gestiona usuarios y catálogo. No evalúa.",
                     "Obligatoria para Decisor. Un usuario pertenece a una sola organización.",
                     "Usuario nuevo: se envía al correo un enlace para crear su contraseña.", "Guardar cambios", "Cancelar"):
            self.assertContains(response, text)
        self.assertNotContains(response, 'name="password"')

    def test_edit_drawer_shows_user_data_and_no_delete(self):
        user = make_decisor(self.organization, email="ana@unemi.edu.ec", first_name="Ana", last_name="Ruiz")

        response = self.client.get(f"/gestion/usuarios/{user.pk}/")

        self.assertContains(response, 'class="drawer"')
        self.assertContains(response, "Editar usuario")
        self.assertContains(response, 'value="Ana Ruiz"')
        self.assertNotContains(response, "Usuario nuevo: se envía")
        self.assertNotContains(response, "Eliminar")

    def test_creates_decisor_and_emails_a_link_to_set_the_password(self):
        response = self.client.post("/gestion/usuarios/nuevo/", self.payload(), follow=True)

        user = User.objects.get(email="landrade@unemi.edu.ec")
        self.assertEqual((user.first_name, user.last_name, user.role, user.organization), ("Luis", "Andrade", "decisor", self.organization))
        self.assertFalse(user.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["landrade@unemi.edu.ec"])
        self.assertIn("/recuperar/", mail.outbox[0].body)
        self.assertContains(response, "Usuario landrade@unemi.edu.ec creado. Le enviamos un enlace para crear su contraseña.")

    def test_user_is_created_even_if_the_email_fails(self):
        with patch("apps.management.services.send_mail", side_effect=OSError("SMTP down")):
            response = self.client.post("/gestion/usuarios/nuevo/", self.payload(), follow=True)

        self.assertTrue(User.objects.filter(email="landrade@unemi.edu.ec").exists())
        self.assertContains(response, "no se pudo enviar el enlace para crear la contraseña")

    def test_creates_administrator_without_organization(self):
        self.client.post("/gestion/usuarios/nuevo/", self.payload(email="admin2@guios.ec", role="administrador"))

        user = User.objects.get(email="admin2@guios.ec")
        self.assertEqual((user.role, user.organization), ("administrador", None))

    def test_decisor_requires_organization(self):
        count = User.objects.count()

        response = self.client.post("/gestion/usuarios/nuevo/", self.payload(organization=""))

        self.assertContains(response, "Un decisor debe pertenecer a una organización.")
        self.assertContains(response, 'class="drawer"')
        self.assertEqual(User.objects.count(), count)

    def test_rejects_duplicate_email(self):
        make_decisor(self.organization, email="landrade@unemi.edu.ec")
        count = User.objects.count()

        response = self.client.post("/gestion/usuarios/nuevo/", self.payload())

        self.assertContains(response, "Este correo ya está registrado")
        self.assertEqual(User.objects.count(), count)

    def test_edits_full_name_and_keeps_password(self):
        user = make_decisor(self.organization)

        response = self.client.post(f"/gestion/usuarios/{user.pk}/", self.payload(full_name="Ana María Ruiz", email=user.email))

        self.assertRedirects(response, "/gestion/usuarios/")
        user.refresh_from_db()
        self.assertEqual((user.first_name, user.last_name), ("Ana", "María Ruiz"))
        self.assertTrue(user.check_password(PASSWORD))

    def test_full_name_is_required(self):
        user = make_decisor(self.organization)

        response = self.client.post(f"/gestion/usuarios/{user.pk}/", self.payload(full_name="  ", email=user.email))

        self.assertContains(response, "Escribe el nombre completo.")

    def test_deactivates_user_without_deleting_it(self):
        user = make_decisor(self.organization)
        count = User.objects.count()
        data = self.payload(email=user.email)
        del data["is_active"]

        self.client.post(f"/gestion/usuarios/{user.pk}/", data)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(User.objects.count(), count)
