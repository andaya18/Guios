import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Organization, PendingSignup, User

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


def normalize_email(email):
    return email.strip().lower()


def email_domain(email):
    return normalize_email(email).rsplit("@", 1)[1]


def create_pending_signup(email, first_name, last_name, password):
    normalized_email = normalize_email(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
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
    send_mail(
        "Código de verificación de GUIOS PRO",
        f"Tu código de verificación es: {code}",
        None,
        [pending.email],
    )
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
    code = f"{secrets.randbelow(1_000_000):06d}"
    pending.code_hash = make_password(code)
    pending.expires_at = timezone.now() + VERIFICATION_TTL
    pending.attempts = 0
    pending.save(update_fields=["code_hash", "expires_at", "attempts"])
    send_mail(
        "Código de verificación de GUIOS PRO",
        f"Tu nuevo código de verificación es: {code}",
        None,
        [pending.email],
    )


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
