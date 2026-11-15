from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Organization, PendingSignup, User


class LoginTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Universidad GUIOS",
            domain="guios.edu.ec",
            sector="publico",
        )
        self.user = User.objects.create_user(
            email="ana@guios.edu.ec",
            password="Correcta123!",
            first_name="Ana",
            organization=self.organization,
        )

    def test_login_redirects_decisor_to_dashboard(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "ana@guios.edu.ec", "password": "Correcta123!"},
        )
        self.assertRedirects(response, "/")

    def test_inactive_organization_cannot_login(self):
        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "ana@guios.edu.ec", "password": "Correcta123!"},
        )
        self.assertContains(response, "Tu cuenta no está activa")


class SignupScreenTests(TestCase):
    def test_signup_first_step_uses_separate_name_fields(self):
        response = self.client.get(reverse("accounts:signup"))

        self.assertContains(response, "Nombre")
        self.assertContains(response, "Apellido")
        self.assertContains(response, "Ingresa tu nombre")
        self.assertContains(response, "Ingresa tu apellido")

    @patch("apps.accounts.services.send_mail")
    def test_signup_first_step_shows_progress_and_sends_code(self, send_mail):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Luis",
                "last_name": "Pérez",
                "email": "luis@empresa.edu.ec",
                "password": "Correcta123!",
                "password_confirm": "Correcta123!",
            },
        )
        self.assertRedirects(response, reverse("accounts:signup_verify"))
        self.assertTrue(PendingSignup.objects.filter(email="luis@empresa.edu.ec").exists())
        send_mail.assert_called_once()

    def test_organization_step_shows_read_only_domain(self):
        user = User.objects.create(
            email="ana@empresa.edu.ec",
            first_name="Ana",
            password="not-used",
        )
        session = self.client.session
        session["pending_user_id"] = user.pk
        session.save()

        response = self.client.get(reverse("accounts:signup_organization"))

        self.assertContains(response, 'value="empresa.edu.ec"')
        self.assertContains(response, "readonly")


SIGNUP_DATA = {
    "first_name": "Gabriela",
    "last_name": "Andagoya",
    "email": "gabriela@unemi.edu.ec",
    "password": "Correcta123",
    "password_confirm": "Correcta123",
}


class PasswordPolicyTests(TestCase):
    @patch("apps.accounts.services.send_mail")
    def test_signup_rejects_password_without_uppercase_and_digit(self, send_mail):
        data = {**SIGNUP_DATA, "password": "sinmayusculas", "password_confirm": "sinmayusculas"}

        response = self.client.post(reverse("accounts:signup"), data)

        self.assertContains(response, "La contraseña debe tener al menos una mayúscula y un número.")
        self.assertFalse(PendingSignup.objects.exists())
        send_mail.assert_not_called()

    @patch("apps.accounts.services.send_mail")
    def test_signup_rejects_short_password(self, send_mail):
        data = {**SIGNUP_DATA, "password": "Ab1", "password_confirm": "Ab1"}

        response = self.client.post(reverse("accounts:signup"), data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PendingSignup.objects.exists())


class VerificationTests(TestCase):
    def setUp(self):
        with patch("apps.accounts.services.send_mail"):
            self.client.post(reverse("accounts:signup"), SIGNUP_DATA)
        self.pending = PendingSignup.objects.get()

    def post_code(self, code):
        return self.client.post(reverse("accounts:signup_verify"), {"code": list(code)})

    def test_wrong_code_counts_attempts(self):
        response = self.post_code("000000")

        self.pending.refresh_from_db()
        self.assertEqual(self.pending.attempts, 1)
        self.assertContains(response, "Código incorrecto. Intentos restantes: 4.")

    def test_five_wrong_codes_block_verification(self):
        for _ in range(5):
            self.post_code("000000")

        response = self.post_code("000000")

        self.assertContains(response, "Superaste el máximo de intentos. Solicita un código nuevo.")
        self.assertFalse(User.objects.filter(email=SIGNUP_DATA["email"]).exists())

    @patch("apps.accounts.services.secrets.randbelow", return_value=123456)
    def test_six_digit_boxes_are_joined_into_one_code(self, _randbelow):
        with patch("apps.accounts.services.send_mail"):
            self.client.post(reverse("accounts:signup"), SIGNUP_DATA)

        response = self.post_code("123456")

        self.assertRedirects(response, reverse("accounts:signup_organization"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(email=SIGNUP_DATA["email"]).exists())

    @patch("apps.accounts.services.send_mail")
    def test_resend_is_rejected_within_60_seconds(self, send_mail):
        response = self.client.post(reverse("accounts:signup_verify"), {"resend": "1"}, follow=True)

        self.assertContains(response, "Podrás solicitar un nuevo código en")
        send_mail.assert_not_called()

    def test_verify_screen_matches_figma_modal(self):
        response = self.client.get(reverse("accounts:signup_verify"))

        for text in (
            "Verifica tu correo",
            "Hemos enviado un código de verificación a tu correo institucional.",
            "gabriela@unemi.edu.ec",
            "Código de verificación",
            "Verificar correo",
            "¿No recibiste el código?",
            "Reenviar código",
        ):
            self.assertContains(response, text)
        self.assertContains(response, 'name="code"', count=6)


class AuthScreensCopyTests(TestCase):
    def test_login_copy_matches_figma(self):
        response = self.client.get(reverse("accounts:login"))

        for text in (
            "Comienza a evaluar software con un proceso claro y estructurado.",
            "18 factores y 61 subfactores de la guía GUIOS",
            "Avance guardado automáticamente",
            "Historial, comparación y exportación",
            "Ingresa con tu correo registrado.",
            "Correo electrónico",
            "Recordarme",
            "¿Olvidaste tu contraseña?",
            "¿No tienes cuenta?",
            "Crear cuenta",
        ):
            self.assertContains(response, text)

    def test_signup_copy_matches_figma(self):
        response = self.client.get(reverse("accounts:signup"))

        for text in (
            "Decide la adopción de software con evidencia, no con intuición.",
            "Usa tu correo institucional y comienza tus evaluaciones",
            "Analiza factores y subfactores relevantes",
            "Obtén resultados que respalden tu decisión",
            "¡Empieza a tomar decisiones con evidencia!",
            "Correo institucional",
            "Utiliza tu correo institucional para asociarte a tu organización.",
            "Mín. 8 caracteres, una mayúscula y un número",
            "¿Ya tienes cuenta?",
        ):
            self.assertContains(response, text)

    def test_organization_step_copy_matches_figma(self):
        user = User.objects.create(email="ana@empresa.com", first_name="Ana", password="x")
        session = self.client.session
        session["pending_user_id"] = user.pk
        session.save()

        response = self.client.get(reverse("accounts:signup_organization"))

        for text in (
            "Registra tu organización",
            "No encontramos una organización asociada a tu dominio.",
            "Registra los datos de tu organización para continuar.",
            "Dominio institucional",
            "Detectado automáticamente a partir de tu correo. No se puede modificar.",
            "Escribe el nombre de tu organización",
            "Tipo de organización",
            "Seleccionar",
            "Pública",
            "Privada",
            "Continuar",
        ):
            self.assertContains(response, text)

    def test_recover_copy_matches_figma(self):
        response = self.client.get(reverse("accounts:password_reset"))

        for text in (
            "Recupera el acceso sin perder tus evaluaciones.",
            "Volver a iniciar sesión",
            "Te enviaremos un enlace para crear una nueva contraseña.",
            "Enviar enlace",
        ):
            self.assertContains(response, text)


class RememberMeTests(LoginTests):
    def test_without_remember_session_ends_with_browser(self):
        self.client.post(
            reverse("accounts:login"),
            {"username": "ana@guios.edu.ec", "password": "Correcta123!"},
        )
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_session_expires_after_30_minutes_of_inactivity(self):
        from django.conf import settings

        self.client.post(
            reverse("accounts:login"),
            {"username": "ana@guios.edu.ec", "password": "Correcta123!"},
        )
        self.assertEqual(self.client.session.get_expiry_age(), 30 * 60)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_with_remember_session_lasts_14_days(self):
        self.client.post(
            reverse("accounts:login"),
            {"username": "ana@guios.edu.ec", "password": "Correcta123!", "remember": "on"},
        )
        self.assertEqual(self.client.session.get_expiry_age(), 14 * 24 * 60 * 60)

    def test_with_remember_session_persists(self):
        self.client.post(
            reverse("accounts:login"),
            {"username": "ana@guios.edu.ec", "password": "Correcta123!", "remember": "on"},
        )
        self.assertFalse(self.client.session.get_expire_at_browser_close())


class PasswordResetTests(TestCase):
    def test_unknown_email_does_not_reveal_accounts(self):
        response = self.client.post(reverse("accounts:password_reset"), {"email": "nadie@empresa.com"})

        self.assertRedirects(response, reverse("accounts:password_reset_done"))

    def test_done_screen_shows_figma_notice(self):
        response = self.client.get(reverse("accounts:password_reset_done"))

        self.assertContains(
            response,
            "Si el correo está registrado recibirás el enlace en unos minutos. El enlace vence en 30 min.",
        )

    def test_reset_link_expires_in_30_minutes(self):
        from django.conf import settings

        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 30 * 60)

    def test_confirm_logs_user_in_after_saving(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        user = User.objects.create_user(email="ana@guios.edu.ec", password="Vieja1234", first_name="Ana")
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        url = reverse("accounts:password_reset_confirm", args=[uid, token])
        form_url = self.client.get(url, follow=True).redirect_chain[-1][0]

        response = self.client.get(form_url)
        self.assertContains(response, "Guardar y entrar")
        self.client.post(form_url, {"new_password1": "Nueva12345", "new_password2": "Nueva12345"})

        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)



class ProfileTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        self.user = User.objects.create_user(
            email="maria@unemi.edu.ec", password="Correcta123", first_name="María", last_name="Pérez",
            organization=self.organization,
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()

        self.assertRedirects(self.client.get("/cuenta/configuracion/"), "/acceso/?next=/cuenta/configuracion/", fetch_redirect_response=False)

    def test_page_matches_figma_copy(self):
        response = self.client.get("/cuenta/configuracion/")

        for text in ("Configuración", "Administra tu perfil y las preferencias de la aplicación.", "Preferencias",
                     "Apariencia", "Claro", "Oscuro", "Información personal", "Correo institucional",
                     "El correo identifica tu cuenta y tu organización; no se puede modificar.", "Organización",
                     "unemi.edu.ec", "Pública", "Tu organización se asigna según el dominio de tu correo y no se cambia aquí.",
                     "Guardar cambios", "Cancelar"):
            self.assertContains(response, text)

    def test_saves_name_and_area_but_never_email(self):
        response = self.client.post("/cuenta/configuracion/", {
            "first_name": "Mariela", "last_name": "Paz", "area": "Dirección TIC", "email": "otro@gmail.com",
        })

        self.assertRedirects(response, "/cuenta/configuracion/")
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name, self.user.area, self.user.email),
                         ("Mariela", "Paz", "Dirección TIC", "maria@unemi.edu.ec"))

    def test_name_is_required(self):
        response = self.client.post("/cuenta/configuracion/", {"first_name": "", "last_name": "Paz"})

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "María")


class AdminMailSettingsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@guios.local", password="Correcta123", first_name="Carlos", role="administrador")
        self.client.force_login(self.admin)

    def test_admin_sees_mail_status_without_password(self):
        from django.test import override_settings

        with override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="smtp.gmail.com",
                               EMAIL_PORT=587, EMAIL_HOST_USER="codigos@unemi.edu.ec", EMAIL_HOST_PASSWORD="super-secreta"):
            response = self.client.get("/cuenta/configuracion/")

        self.assertContains(response, "Correo de verificación")
        self.assertContains(response, "smtp.gmail.com:587")
        self.assertContains(response, "codigos@unemi.edu.ec")
        self.assertNotContains(response, "super-secreta")
        self.assertNotContains(response, "Tu organización se asigna")

    def test_without_smtp_the_panel_shows_status_without_development_texts(self):
        from django.test import override_settings

        with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            response = self.client.get("/cuenta/configuracion/")

        self.assertContains(response, "No configurado")
        for text in ("Modo desarrollo", "terminal", ".env", "Consola", "EMAIL_HOST_PASSWORD"):
            self.assertNotContains(response, text)

    def test_send_test_email_to_admin(self):
        from django.core import mail

        with patch("apps.accounts.views.mail_status", return_value={"is_real": True}):
            response = self.client.post("/cuenta/configuracion/correo-de-prueba/", follow=True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@guios.local"])
        self.assertContains(response, "Correo de prueba enviado a admin@guios.local. Revisa también la carpeta de spam.")

    def test_decisor_cannot_send_test_email(self):
        decisor = User.objects.create_user(email="ana@x.edu.ec", password="Correcta123", first_name="Ana")
        self.client.force_login(decisor)

        self.assertEqual(self.client.post("/cuenta/configuracion/correo-de-prueba/").status_code, 403)


class DjangoAdminUserTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(email="gabriela@unemi.edu.ec", password="Correcta123")
        self.client.force_login(self.superuser)

    def test_change_page_has_email_and_name_but_no_username(self):
        response = self.client.get(f"/admin/accounts/user/{self.superuser.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="first_name"')
        self.assertNotContains(response, 'name="username"')

    def test_add_page_and_search_work(self):
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 200)
        self.assertEqual(self.client.get("/admin/accounts/user/?q=gabriela").status_code, 200)

    def test_admin_can_set_name_from_change_page(self):
        url = f"/admin/accounts/user/{self.superuser.pk}/change/"
        data = {
            "email": "gabriela@unemi.edu.ec", "first_name": "Gabriela", "last_name": "Andagoya",
            "role": "administrador", "area": "", "is_active": "on", "is_staff": "on", "is_superuser": "on",
            "last_login_0": "", "last_login_1": "", "date_joined_0": "2026-11-14", "date_joined_1": "10:00:00",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        self.superuser.refresh_from_db()
        self.assertEqual(self.superuser.get_full_name(), "Gabriela Andagoya")

    def test_add_user_creates_account_with_email(self):
        response = self.client.post("/admin/accounts/user/add/", {
            "email": "nuevo@unemi.edu.ec", "password1": "Segura2026x", "password2": "Segura2026x",
            "role": "administrador",
        })

        self.assertEqual(response.status_code, 302, response.content.decode()[:800])
        self.assertTrue(User.objects.get(email="nuevo@unemi.edu.ec").check_password("Segura2026x"))


class VerificationEmailPathTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@guios.local", password="Correcta123", first_name="Carlos", role="administrador")
        self.client.force_login(self.admin)

    def test_test_email_uses_the_real_verification_template(self):
        from django.core import mail

        self.client.post("/cuenta/configuracion/correo-de-prueba/", {"recipient": "gabriela@unemi.edu.ec"})

        self.assertEqual(mail.outbox[0].to, ["gabriela@unemi.edu.ec"])
        self.assertEqual(mail.outbox[0].subject, "Código de verificación de GUIOS PRO")
        self.assertRegex(mail.outbox[0].body, r"Tu código de verificación es: \d{6}")

    def test_signup_and_test_email_share_the_same_message(self):
        from django.core import mail

        with patch("apps.accounts.services.secrets.randbelow", return_value=123456):
            self.client.post("/registro/", SIGNUP_DATA)

        self.assertEqual(mail.outbox[0].subject, "Código de verificación de GUIOS PRO")
        self.assertIn("Tu código de verificación es: 123456", mail.outbox[0].body)

    def test_recipient_defaults_to_admin_email(self):
        from django.core import mail

        self.client.post("/cuenta/configuracion/correo-de-prueba/")

        self.assertEqual(mail.outbox[0].to, ["admin@guios.local"])

    def test_invalid_recipient_is_rejected(self):
        from django.core import mail

        response = self.client.post("/cuenta/configuracion/correo-de-prueba/", {"recipient": "no-es-correo"}, follow=True)

        self.assertContains(response, "Escribe un correo válido para la prueba.")
        self.assertEqual(len(mail.outbox), 0)

    def test_without_smtp_the_test_mail_reports_it_was_not_sent(self):
        from django.test import override_settings

        with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            response = self.client.post("/cuenta/configuracion/correo-de-prueba/", follow=True)

        self.assertContains(response, "No hay un servidor de correo configurado: el correo de prueba no se envió.")

    def test_smtp_failure_is_reported(self):
        with patch("apps.accounts.views.send_verification_email", side_effect=OSError("Connection refused")):
            response = self.client.post("/cuenta/configuracion/correo-de-prueba/", follow=True)

        self.assertContains(response, "No se pudo enviar el correo de prueba: Connection refused")


class AvatarInitialsTests(TestCase):
    def test_initials_from_full_name_or_email(self):
        from apps.core.templatetags.ui import initials

        self.assertEqual(initials(User(first_name="Gabriela", last_name="Andagoya", email="g@x.ec")), "GA")
        self.assertEqual(initials(User(first_name="maría", email="m@x.ec")), "M")
        self.assertEqual(initials(User(email="gabrielaadmin@gmail.com")), "G")

    def test_sidebar_shows_initials(self):
        org = Organization.objects.create(name="UNEMI", domain="unemi.edu.ec", sector="publico")
        user = User.objects.create_user(email="g@unemi.edu.ec", password="Correcta123", first_name="Gabriela", last_name="Andagoya", organization=org)
        self.client.force_login(user)

        self.assertContains(self.client.get("/"), '<span class="avatar" aria-hidden="true">GA</span>', html=False)


class EmailFailureTests(TestCase):
    """If SMTP fails, the visitor sees a clear message instead of a server error (§4.8 usability)."""

    def test_signup_shows_error_and_can_retry_when_mail_fails(self):
        with patch("apps.accounts.services.send_mail", side_effect=OSError("SMTP down")):
            response = self.client.post(reverse("accounts:signup"), SIGNUP_DATA)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pudimos enviar el código de verificación. Intenta de nuevo en unos minutos.")
        self.assertFalse(PendingSignup.objects.exists())

        with patch("apps.accounts.services.send_mail"):
            retry = self.client.post(reverse("accounts:signup"), SIGNUP_DATA)
        self.assertRedirects(retry, reverse("accounts:signup_verify"), fetch_redirect_response=False)

    def test_resend_failure_keeps_previous_code_valid(self):
        from datetime import timedelta

        from django.utils import timezone

        with patch("apps.accounts.services.send_mail"):
            self.client.post(reverse("accounts:signup"), SIGNUP_DATA)
        pending = PendingSignup.objects.get()
        PendingSignup.objects.filter(pk=pending.pk).update(expires_at=timezone.now() + timedelta(minutes=8))
        before = PendingSignup.objects.get()

        with patch("apps.accounts.services.send_mail", side_effect=OSError("SMTP down")):
            response = self.client.post(reverse("accounts:signup_verify"), {"resend": "1"}, follow=True)

        self.assertContains(response, "No pudimos enviar el código de verificación. Intenta de nuevo en unos minutos.")
        after = PendingSignup.objects.get()
        self.assertEqual((after.code_hash, after.expires_at), (before.code_hash, before.expires_at))
