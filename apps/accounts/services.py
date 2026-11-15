import logging
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Organization, PendingSignup, User, VerificationEmailTemplate

logger = logging.getLogger(__name__)

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "yahoo.com",
    "yahoo.es",
    "icloud.com",
    "proton.me",
    "protonmail.com",
}
MAX_VERIFICATION_ATTEMPTS = 5
VERIFICATION_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)


VERIFICATION_SUBJECT = "Código de verificación de GUIOS PRO"
EMAIL_FAILED_MESSAGE = "No pudimos enviar el código de verificación. Intenta de nuevo en unos minutos."


class VerificationEmailError(Exception):
    """The code could not be delivered; nothing the visitor did wrong."""


def new_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def deliver_code(email, code, name=""):
    """Send the code, turning any SMTP/network failure into VerificationEmailError (logged for the admin)."""
    try:
        send_verification_email(email, code, name)
    except Exception as error:  # SMTP providers raise many different exception types
        logger.exception("No se pudo enviar el código de verificación a %s", email)
        raise VerificationEmailError(EMAIL_FAILED_MESSAGE) from error


DEFAULT_VERIFICATION_BODY = (
    "Hola, {nombre}:\n\n"
    "Tu código de verificación es: {codigo}\n\n"
    "Vence en {minutos} minutos. Si no solicitaste una cuenta en GUIOS PRO, ignora este correo."
)
PLACEHOLDERS = ("{nombre}", "{codigo}", "{minutos}")


def verification_template():
    """(subject, body) edited by the administrator, or the built-in default."""
    stored = VerificationEmailTemplate.objects.first()
    if stored:
        return stored.subject, stored.body
    return VERIFICATION_SUBJECT, DEFAULT_VERIFICATION_BODY


def fill_placeholders(text, name, code):
    """Plain replacement (never str.format) so stray braces in an edited message cannot break sending."""
    values = {"{nombre}": name or "usuario", "{codigo}": code, "{minutos}": str(int(VERIFICATION_TTL.total_seconds() // 60))}
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    return text


def send_verification_email(email, code, name=""):
    """The only place that writes the verification email (signup, resend and the admin test)."""
    subject, body = verification_template()
    text = fill_placeholders(body, name, code)
    html = render_to_string("accounts/email/verification.html", {
        "paragraphs": [line for line in text.split("\n\n") if line.strip()],
        "code": code,
        "minutes": int(VERIFICATION_TTL.total_seconds() // 60),
    })
    message = EmailMultiAlternatives(fill_placeholders(subject, name, code), text, None, [email])
    message.attach_alternative(html, "text/html")
    message.send()


def normalize_email(email):
    return email.strip().lower()


def email_domain(email):
    return normalize_email(email).rsplit("@", 1)[1]


def create_pending_signup(email, first_name, last_name, password):
    normalized_email = normalize_email(email)
    code = new_code()
    pending, _ = PendingSignup.objects.update_or_create(
        email=normalized_email,
        defaults={
            "name": f"{first_name.strip()}|{last_name.strip()}",
            "password_hash": make_password(password),
            "code_hash": make_password(code),
            "expires_at": timezone.now() + VERIFICATION_TTL,
            "attempts": 0,
        },
    )
    try:
        deliver_code(pending.email, code, first_name.strip())
    except VerificationEmailError:
        pending.delete()  # nothing was sent, so the visitor can simply try again
        raise
    return pending


def seconds_until_resend(pending):
    """The code was sent when it started its TTL, so the send time is derived from expires_at."""
    sent_at = pending.expires_at - VERIFICATION_TTL
    remaining = (sent_at + RESEND_COOLDOWN - timezone.now()).total_seconds()
    return max(0, int(remaining) + (remaining % 1 > 0))


def resend_pending_signup_code(pending):
    wait = seconds_until_resend(pending)
    if wait:
        raise ValueError(f"Podrás solicitar un nuevo código en {wait} segundos.")
    code = new_code()
    deliver_code(pending.email, code, pending.name.partition("|")[0])  # only replace the stored code once the new one was sent
    pending.code_hash = make_password(code)
    pending.expires_at = timezone.now() + VERIFICATION_TTL
    pending.attempts = 0
    pending.save(update_fields=["code_hash", "expires_at", "attempts"])


def verify_pending_signup(pending, code):
    if pending.expires_at <= timezone.now():
        raise ValueError("El código expiró. Solicita uno nuevo.")
    if pending.attempts >= MAX_VERIFICATION_ATTEMPTS:
        raise ValueError("Superaste el máximo de intentos. Solicita un código nuevo.")

    # Counted atomically in the database and outside any transaction, so neither concurrent
    # requests nor a wrong-code rollback can skip the limit.
    PendingSignup.objects.filter(pk=pending.pk).update(attempts=F("attempts") + 1)
    pending.refresh_from_db(fields=["attempts"])
    if pending.attempts > MAX_VERIFICATION_ATTEMPTS:
        raise ValueError("Superaste el máximo de intentos. Solicita un código nuevo.")
    if not check_password(code, pending.code_hash):
        remaining = MAX_VERIFICATION_ATTEMPTS - pending.attempts
        if not remaining:
            raise ValueError("Superaste el máximo de intentos. Solicita un código nuevo.")
        raise ValueError(f"Código incorrecto. Intentos restantes: {remaining}.")
    return _create_verified_user(pending)


@transaction.atomic
def _create_verified_user(pending):
    first_name, separator, last_name = pending.name.partition("|")
    if not separator:
        first_name, last_name = pending.name, ""
    user = User.objects.create(
        email=pending.email,
        first_name=first_name,
        last_name=last_name,
        password=pending.password_hash,
        role="decisor",
    )
    pending.delete()
    return user


def active_organization_for_email(email):
    return Organization.objects.filter(domain=email_domain(email), is_active=True).first()
