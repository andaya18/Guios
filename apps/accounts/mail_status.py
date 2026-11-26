"""Read-only description of the outgoing mail setup for administrators. Never exposes the password."""
from django.conf import settings

CONSOLE_BACKENDS = {"django.core.mail.backends.console.EmailBackend", "django.core.mail.backends.locmem.EmailBackend"}
BREVO_BACKEND = "apps.accounts.email_backends.BrevoEmailBackend"


def mail_status():
    if settings.EMAIL_BACKEND in CONSOLE_BACKENDS:
        return {
            "mode": "No configurado",
            "is_real": False,
            "detail": "Los códigos de verificación no se están enviando por correo.",
        }
    if settings.EMAIL_BACKEND == BREVO_BACKEND:
        return {
            "mode": "Brevo API (HTTPS)",
            "is_real": True,
            "server": "api.brevo.com",
            "user": settings.DEFAULT_FROM_EMAIL,
            "sender": settings.DEFAULT_FROM_EMAIL,
            "tls": True,
            "detail": "Los códigos se envían mediante la API HTTPS de Brevo.",
        }
    return {
        "mode": "SMTP",
        "is_real": True,
        "server": f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT}",
        "user": settings.EMAIL_HOST_USER or "—",
        "sender": settings.DEFAULT_FROM_EMAIL,
        "tls": settings.EMAIL_USE_TLS,
        "detail": "Los códigos de verificación se envían desde esta cuenta.",
    }
