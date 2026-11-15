import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

from guios.env import load_env_file  # noqa: E402  (needs BASE_DIR)

# Local, git-ignored settings (see .env.example). Real environment variables take priority.
load_env_file(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.evaluations",
    "apps.exports",
    "apps.management",
    "apps.ai",
    "apps.literature",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "guios.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.shell",
            ],
        },
    }
]

WSGI_APPLICATION = "guios.wsgi.application"
ASGI_APPLICATION = "guios.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
        # Hosted PostgreSQL (Neon, Render) requires TLS: set DB_SSLMODE=require there.
        "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE")} if os.getenv("DB_SSLMODE") else {},
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "apps.accounts.validators.UppercaseDigitValidator"},
]
PASSWORD_RESET_TIMEOUT = 30 * 60

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Guayaquil"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static", BASE_DIR / "img"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # filled by collectstatic on deploy (git-ignored)

# Full URLs allowed to POST forms, e.g. https://guios-pro.onrender.com (comma separated).
CSRF_TRUSTED_ORIGINS = [origin for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin]

if not DEBUG:
    # Production: WhiteNoise serves compressed, cache-busted static files without a separate web server.
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
    # Render terminates HTTPS at its proxy and forwards the original scheme in this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/acceso/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/acceso/"

# A session ends after 30 minutes without activity (G02); "Recordarme" extends it.
SESSION_COOKIE_AGE = 30 * 60
SESSION_SAVE_EVERY_REQUEST = True
REMEMBER_ME_AGE = 14 * 24 * 60 * 60

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@guios.local")
# Only used with EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend (production).
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = 10

# Optional AI suggestions (apps.ai). Without a key the feature stays disabled.
AI_PROVIDER = os.getenv("AI_PROVIDER", "disabled")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")
AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "90"))
# Gemini 3 recommends 1.0; 0 was requested for repeatability, which the hash cache guarantees anyway.
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0"))
# "url": read each document's DOI page (free tier). "search": Google Search grounding (needs billing).
AI_GROUNDING = os.getenv("AI_GROUNDING", "url")

# Tests never reach the real AI provider (no quota spent, no network, deterministic runs).
if len(sys.argv) > 1 and sys.argv[1] == "test":
    AI_PROVIDER, AI_API_KEY = "disabled", ""

# Expert importance (IE) used with the literature importance (IL); fixed at 3 by the thesis.
LITERATURE_EXPERT_IMPORTANCE = int(os.getenv("LITERATURE_EXPERT_IMPORTANCE", "3"))
