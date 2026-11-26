import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the configured test administrator and decisor without changing existing users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that the test accounts should be provisioned.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Vuelve a ejecutar el comando con --confirm.")

        admin_email = os.getenv("GUIOS_TEST_ADMIN_EMAIL", "").strip().lower()
        decisor_email = os.getenv("GUIOS_TEST_DECISOR_EMAIL", "").strip().lower()
        admin_password = os.getenv("GUIOS_TEST_ADMIN_PASSWORD", "")
        decisor_password = os.getenv("GUIOS_TEST_DECISOR_PASSWORD", "")
        admin_first_name = os.getenv("GUIOS_TEST_ADMIN_FIRST_NAME", "Administrador")
        decisor_first_name = os.getenv("GUIOS_TEST_DECISOR_FIRST_NAME", "Decisor")
        required = {
            "GUIOS_TEST_ADMIN_EMAIL": admin_email,
            "GUIOS_TEST_DECISOR_EMAIL": decisor_email,
            "GUIOS_TEST_ADMIN_PASSWORD": admin_password,
            "GUIOS_TEST_DECISOR_PASSWORD": decisor_password,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise CommandError(f"Faltan variables requeridas: {', '.join(missing)}.")
        if admin_email == decisor_email:
            raise CommandError("El administrador y el decisor deben tener correos distintos.")

        self._validate_email(admin_email, "administrador")
        self._validate_email(decisor_email, "decisor")

        admin = User.objects.filter(email=admin_email).first()
        decisor = User.objects.filter(email=decisor_email).first()
        self._validate_existing_user(
            admin,
            admin_password,
            "administrador",
            role="administrador",
            is_staff=True,
            is_superuser=True,
        )
        self._validate_existing_user(
            decisor,
            decisor_password,
            "decisor",
            role="decisor",
            is_staff=False,
            is_superuser=False,
        )

        if admin is None:
            self._validate_password(admin_password, admin_email, admin_first_name)
            User.objects.create_superuser(
                email=admin_email,
                password=admin_password,
                first_name=admin_first_name,
                role="administrador",
            )
            self.stdout.write("Administrador de prueba creado.")
        else:
            self.stdout.write("El administrador de prueba ya existía; no se modificó.")

        if decisor is None:
            self._validate_password(decisor_password, decisor_email, decisor_first_name)
            User.objects.create_user(
                email=decisor_email,
                password=decisor_password,
                first_name=decisor_first_name,
                role="decisor",
            )
            self.stdout.write("Decisor de prueba creado.")
        else:
            self.stdout.write("El decisor de prueba ya existía; no se modificó.")

    @staticmethod
    def _validate_email(email, label):
        try:
            validate_email(email)
        except ValidationError as error:
            raise CommandError(f"El correo del {label} no es válido.") from error

    @staticmethod
    def _validate_password(password, email, first_name):
        user = User(email=email, first_name=first_name)
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError("\n".join(error.messages)) from error

    @staticmethod
    def _validate_existing_user(user, password, label, **expected_fields):
        if user is None:
            return
        if any(getattr(user, field) != value for field, value in expected_fields.items()):
            raise CommandError(
                f"El correo configurado para el {label} ya pertenece a una cuenta "
                "con otro rol o permisos; no se modificó."
            )
        if not user.is_active or not user.check_password(password):
            raise CommandError(
                f"El {label} ya existe, pero no coincide con la contraseña configurada; "
                "no se modificó."
            )
