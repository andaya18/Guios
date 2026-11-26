import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


def database_config(base_dir: Path, env=None) -> dict:
    env = os.environ if env is None else env
    use_unpooled = env.get("DJANGO_USE_UNPOOLED_DATABASE", "").lower() == "true"
    if use_unpooled:
        database_url = env.get("DATABASE_URL_UNPOOLED")
        if not database_url:
            raise ImproperlyConfigured(
                "DATABASE_URL_UNPOOLED is required when "
                "DJANGO_USE_UNPOOLED_DATABASE=true."
            )
    else:
        database_url = env.get("DATABASE_URL")

    if database_url:
        try:
            parsed = urlsplit(database_url)
            port = parsed.port
        except ValueError as error:
            raise ImproperlyConfigured("DATABASE_URL is not a valid PostgreSQL URL.") from error

        database_name = unquote(parsed.path.lstrip("/"))
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not database_name:
            raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL connection URL.")

        options = dict(parse_qsl(parsed.query))
        options.setdefault("sslmode", env.get("DB_SSLMODE", "require"))
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": database_name,
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname,
            "PORT": port or "",
            "OPTIONS": options,
        }

    return {
        "ENGINE": env.get("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": env.get("DB_NAME", base_dir / "db.sqlite3"),
        "USER": env.get("DB_USER", ""),
        "PASSWORD": env.get("DB_PASSWORD", ""),
        "HOST": env.get("DB_HOST", ""),
        "PORT": env.get("DB_PORT", ""),
        "OPTIONS": {"sslmode": env["DB_SSLMODE"]} if env.get("DB_SSLMODE") else {},
    }
