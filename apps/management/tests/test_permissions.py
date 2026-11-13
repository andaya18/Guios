from django.test import TestCase

from .helpers import make_admin, make_decisor, make_organization

MANAGEMENT_URLS = [
    "/gestion/",
    "/gestion/usuarios/",
    "/gestion/usuarios/nuevo/",
    "/gestion/organizaciones/",
    "/gestion/organizaciones/nueva/",
    "/gestion/catalogo/",
    "/gestion/catalogo/comparar/?a=1&b=2",
]


class ManagementAccessTests(TestCase):
    def setUp(self):
        self.organization = make_organization()
        self.decisor = make_decisor(self.organization)
        self.admin = make_admin()

    def test_anonymous_visitor_is_sent_to_login(self):
        for url in MANAGEMENT_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith("/acceso/"))

    def test_decisor_gets_403_on_every_management_page(self):
        self.client.force_login(self.decisor)
        for url in MANAGEMENT_URLS + [
            f"/gestion/usuarios/{self.decisor.pk}/",
            f"/gestion/organizaciones/{self.organization.pk}/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_decisor_cannot_post_changes(self):
        self.client.force_login(self.decisor)
        response = self.client.post(
            f"/gestion/organizaciones/{self.organization.pk}/",
            {"name": "Otra", "sector": "privado"},
        )
        self.assertEqual(response.status_code, 403)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "UNEMI")

    def test_administrator_can_open_management_pages(self):
        self.client.force_login(self.admin)
        for url in ["/gestion/", "/gestion/usuarios/", "/gestion/organizaciones/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
