import json
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from apps.accounts.email_backends import BrevoEmailBackend


@override_settings(BREVO_API_KEY="test-api-key", EMAIL_TIMEOUT=7)
class BrevoEmailBackendTests(SimpleTestCase):
    def make_message(self):
        message = EmailMultiAlternatives(
            subject="Código GUIOS",
            body="Tu código es 123456.",
            from_email="GUIOS PRO <verified@example.com>",
            to=["Ana <ana@example.com>"],
        )
        message.attach_alternative("<p>Tu código es <strong>123456</strong>.</p>", "text/html")
        return message

    @patch("apps.accounts.email_backends.urlopen")
    def test_sends_html_and_text_via_brevo_https_api(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value.status = 201

        sent = BrevoEmailBackend().send_messages([self.make_message()])

        self.assertEqual(sent, 1)
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(request.get_header("Api-key"), "test-api-key")
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 7)
        payload = json.loads(request.data)
        self.assertEqual(payload["sender"], {"email": "verified@example.com", "name": "GUIOS PRO"})
        self.assertEqual(payload["to"], [{"email": "ana@example.com", "name": "Ana"}])
        self.assertEqual(payload["textContent"], "Tu código es 123456.")
        self.assertEqual(payload["htmlContent"], "<p>Tu código es <strong>123456</strong>.</p>")

    @override_settings(BREVO_API_KEY="")
    def test_missing_api_key_fails_explicitly(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "BREVO_API_KEY"):
            BrevoEmailBackend().send_messages([self.make_message()])

    @patch("apps.accounts.email_backends.urlopen")
    def test_api_errors_propagate(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://api.brevo.com/v3/smtp/email",
            401,
            "Unauthorized",
            {},
            BytesIO(b""),
        )

        with self.assertRaises(HTTPError):
            BrevoEmailBackend().send_messages([self.make_message()])

    @patch("apps.accounts.email_backends.urlopen")
    def test_fail_silently_returns_zero_when_provider_fails(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://api.brevo.com/v3/smtp/email",
            401,
            "Unauthorized",
            {},
            BytesIO(b""),
        )

        self.assertEqual(
            BrevoEmailBackend(fail_silently=True).send_messages([self.make_message()]),
            0,
        )

    @patch("apps.accounts.email_backends.urlopen")
    def test_empty_recipient_list_is_not_sent(self, mock_urlopen):
        message = EmailMultiAlternatives(
            subject="Sin destinatario",
            body="Contenido",
            from_email="verified@example.com",
            to=[],
        )

        self.assertEqual(BrevoEmailBackend().send_messages([message]), 0)
        mock_urlopen.assert_not_called()

    @override_settings(
        EMAIL_BACKEND="apps.accounts.email_backends.BrevoEmailBackend",
        DEFAULT_FROM_EMAIL="GUIOS PRO <verified@example.com>",
    )
    @patch(
        "apps.accounts.services.verification_template",
        return_value=("Código GUIOS PRO", "Hola, {nombre}. Tu código es {codigo}."),
    )
    @patch("apps.accounts.email_backends.urlopen")
    def test_verification_email_flows_through_brevo_api(
        self, mock_urlopen, _mock_template
    ):
        mock_urlopen.return_value.__enter__.return_value.status = 201

        from apps.accounts.services import send_verification_email

        send_verification_email("ana@example.com", "123456", "Ana")

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["subject"], "Código GUIOS PRO")
        self.assertIn("Hola, Ana. Tu código es 123456.", payload["textContent"])
        self.assertIn("123456", payload["htmlContent"])


class BrevoMailStatusTests(SimpleTestCase):
    @override_settings(
        EMAIL_BACKEND="apps.accounts.email_backends.BrevoEmailBackend",
        DEFAULT_FROM_EMAIL="GUIOS PRO <verified@example.com>",
    )
    def test_status_describes_https_provider_without_exposing_api_key(self):
        from apps.accounts.mail_status import mail_status

        status = mail_status()

        self.assertEqual(status["mode"], "Brevo API (HTTPS)")
        self.assertEqual(status["server"], "api.brevo.com")
        self.assertEqual(status["user"], "GUIOS PRO <verified@example.com>")
        self.assertTrue(status["is_real"])
        self.assertTrue(status["tls"])
