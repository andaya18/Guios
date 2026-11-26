from pathlib import Path
from unittest import TestCase

from django.core.exceptions import ImproperlyConfigured

from guios.database import database_config


class DatabaseConfigTests(TestCase):
    def test_neon_url_configures_postgresql_and_tls(self):
        config = database_config(
            Path("."),
            {
                "DATABASE_URL": (
                    "postgresql://guios%40example.com:p%40ss@ep.example.neon.tech:5432/guios"
                    "?channel_binding=require"
                )
            },
        )

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "guios")
        self.assertEqual(config["USER"], "guios@example.com")
        self.assertEqual(config["PASSWORD"], "p@ss")
        self.assertEqual(config["HOST"], "ep.example.neon.tech")
        self.assertEqual(
            config["OPTIONS"],
            {"channel_binding": "require", "sslmode": "require"},
        )

    def test_unpooled_url_is_selected_only_for_migrations(self):
        config = database_config(
            Path("."),
            {
                "DATABASE_URL": "postgresql://user:pass@pooled.example.neon.tech/app",
                "DATABASE_URL_UNPOOLED": "postgresql://user:pass@direct.example.neon.tech/app",
                "DJANGO_USE_UNPOOLED_DATABASE": "true",
            },
        )

        self.assertEqual(config["HOST"], "direct.example.neon.tech")

    def test_unpooled_mode_requires_direct_url(self):
        with self.assertRaisesRegex(
            ImproperlyConfigured,
            "DATABASE_URL_UNPOOLED is required",
        ):
            database_config(Path("."), {"DJANGO_USE_UNPOOLED_DATABASE": "true"})

    def test_legacy_database_settings_remain_supported(self):
        config = database_config(
            Path("project"),
            {"DB_ENGINE": "django.db.backends.sqlite3"},
        )

        self.assertEqual(config["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(config["NAME"], Path("project") / "db.sqlite3")

    def test_invalid_database_url_fails_explicitly(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "PostgreSQL connection URL"):
            database_config(Path("."), {"DATABASE_URL": "sqlite:///local.db"})
