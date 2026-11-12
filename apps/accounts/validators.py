import re

from django.core.exceptions import ValidationError


class UppercaseDigitValidator:
    """Requires at least one uppercase letter and one digit, as stated in the signup screen."""

    message = "La contraseña debe tener al menos una mayúscula y un número."

    def validate(self, password, user=None):
        if not (re.search(r"[A-ZÁÉÍÓÚÑ]", password) and re.search(r"\d", password)):
            raise ValidationError(self.message, code="password_missing_uppercase_or_digit")

    def get_help_text(self):
        return self.message
