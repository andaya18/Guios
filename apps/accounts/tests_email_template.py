from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Organization, User, VerificationEmailTemplate
from apps.accounts.services import send_verification_email

URL = "/cuenta/configuracion/mensaje-codigo/"
SIGNUP = {
    "first_name": "Gabriela", "last_name": "Andagoya", "email": "gabriela@unemi.edu.ec",
    "password": "Segura2026x", "password_confirm": "Segura2026x",
}


class VerificationEmailTemplateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@guios.local", password="Correcta123", first_name="Carlos", role="administrador")
        self.client.force_login(self.admin)

    def test_default_message_when_nothing_was_customized(self):
        send_verification_email("ana@unemi.edu.ec", "123456", "Ana")

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Código de verificación de GUIOS PRO")
        self.assertIn("Hola, Ana", message.body)
        self.assertIn("123456", message.body)
        self.assertIn("10 minutos", message.body)

    def test_email_has_branded_html_with_the_code(self):
        send_verification_email("ana@unemi.edu.ec", "123456", "Ana")

        html, mimetype = mail.outbox[0].alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("GUIOS PRO", html)
        self.assertIn("123456", html)

    def test_admin_customizes_subject_and_body_used_at_signup(self):
        response = self.client.post(URL, {
            "subject": "Tu código para GUIOS PRO",
            "body": "Bienvenida {nombre}.\nUsa {codigo}; vence en {minutos} minutos.",
        }, follow=True)

        self.assertContains(response, "Mensaje del código de verificación guardado.")
        with patch("apps.accounts.services.secrets.randbelow", return_value=654321):
            self.client.post(reverse("accounts:signup"), SIGNUP)
        message = mail.outbox[-1]
        self.assertEqual(message.subject, "Tu código para GUIOS PRO")
        self.assertEqual(message.body, "Bienvenida Gabriela.\nUsa 654321; vence en 10 minutos.")
        self.assertEqual(VerificationEmailTemplate.objects.get().updated_by, self.admin)

    def test_body_without_code_placeholder_is_rejected(self):
        response = self.client.post(URL, {"subject": "Asunto", "body": "Hola {nombre}, bienvenido."}, follow=True)

        self.assertContains(response, "El mensaje debe incluir {codigo} para que el usuario reciba su código.")
        self.assertFalse(VerificationEmailTemplate.objects.exists())

    def test_stray_braces_do_not_break_sending(self):
        self.client.post(URL, {"subject": "Código {", "body": "Código: {codigo} } {otra}"})

        send_verification_email("ana@unemi.edu.ec", "111222", "Ana")

        self.assertEqual(mail.outbox[-1].body, "Código: 111222 } {otra}")

    def test_html_escapes_the_admin_message(self):
        self.client.post(URL, {"subject": "Código", "body": "<script>x</script> {codigo}"})

        send_verification_email("ana@unemi.edu.ec", "111222", "Ana")

        html = mail.outbox[-1].alternatives[0][0]
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_restore_default_message(self):
        self.client.post(URL, {"subject": "Otro", "body": "Código {codigo}"})

        self.client.post(URL, {"restore": "1"})

        send_verification_email("ana@unemi.edu.ec", "123456", "Ana")
        self.assertEqual(mail.outbox[-1].subject, "Código de verificación de GUIOS PRO")

    def test_settings_page_shows_editor_with_current_values_and_placeholders(self):
        response = self.client.get("/cuenta/configuracion/")

        for text in ("Mensaje del código de verificación", 'name="subject"', 'name="body"',
                     "{nombre}", "{codigo}", "{minutos}", "Guardar mensaje", "Restaurar predeterminado"):
            self.assertContains(response, text)

    def test_decisor_cannot_edit_the_message(self):
        organization = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        decisor = User.objects.create_user(email="ana@unemi.edu.ec", password="Correcta123", first_name="Ana", organization=organization)
        self.client.force_login(decisor)

        self.assertEqual(self.client.post(URL, {"subject": "x", "body": "{codigo}"}).status_code, 403)
        self.assertNotContains(self.client.get("/cuenta/configuracion/"), "Mensaje del código de verificación")
