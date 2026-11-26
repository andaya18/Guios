import json
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class BrevoEmailBackend(BaseEmailBackend):
    api_url = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = settings.BREVO_API_KEY

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            error = ImproperlyConfigured("BREVO_API_KEY must be configured to send email.")
            if self.fail_silently:
                return 0
            raise error

        sent = 0
        for message in email_messages:
            if self._send_message(message):
                sent += 1
        return sent

    def _send_message(self, message):
        recipients = [_address_payload(address) for address in message.to]
        if not recipients:
            return False

        sender_name, sender_email = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        if not sender_email:
            raise ImproperlyConfigured("DEFAULT_FROM_EMAIL must contain a valid sender address.")
        sender = {"email": sender_email}
        if sender_name:
            sender["name"] = sender_name

        payload = {
            "sender": sender,
            "to": recipients,
            "subject": message.subject,
            "textContent": message.body,
        }
        html_content = next(
            (content for content, mimetype in message.alternatives if mimetype == "text/html"),
            None,
        )
        if html_content:
            payload["htmlContent"] = html_content

        cc = [_address_payload(address) for address in message.cc]
        bcc = [_address_payload(address) for address in message.bcc]
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc

        reply_to = [_address_payload(address) for address in message.reply_to]
        if reply_to:
            payload["replyTo"] = reply_to[0]

        request = Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "api-key": self.api_key,
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
                return 200 <= response.status < 300
        except (HTTPError, URLError, TimeoutError):
            if self.fail_silently:
                return False
            raise


def _address_payload(address):
    name, email = parseaddr(address)
    if not email:
        raise ImproperlyConfigured("Email recipients must contain valid addresses.")
    recipient = {"email": email}
    if name:
        recipient["name"] = name
    return recipient
