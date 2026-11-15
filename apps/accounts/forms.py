from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Organization, User
from .services import PUBLIC_EMAIL_DOMAINS, email_domain, normalize_email

EMAIL_PLACEHOLDER = "nombre@organizacion.edu.ec"
PASSWORD_HELP = "Mín. 8 caracteres, una mayúscula y un número"


def email_input(autocomplete="email"):
    return forms.EmailInput(attrs={"placeholder": EMAIL_PLACEHOLDER, "autocomplete": autocomplete})


def password_input(autocomplete="new-password"):
    return forms.PasswordInput(attrs={"placeholder": "••••••••", "autocomplete": autocomplete})


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="Correo electrónico", widget=email_input())
    password = forms.CharField(label="Contraseña", widget=password_input("current-password"))
    remember = forms.BooleanField(label="Recordarme", required=False)

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Correo o contraseña incorrectos.",
        "inactive": "Tu cuenta no está activa. Contacta al administrador.",
    }

    def clean_username(self):
        return normalize_email(self.cleaned_data["username"])

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.organization_id and not user.organization.is_active:
            raise ValidationError(self.error_messages["inactive"], code="inactive_organization")


class SignupForm(forms.Form):
    first_name = forms.CharField(
        label="Nombre",
        max_length=75,
        widget=forms.TextInput(attrs={"placeholder": "Ingresa tu nombre", "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Apellido",
        max_length=75,
        widget=forms.TextInput(attrs={"placeholder": "Ingresa tu apellido", "autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label="Correo institucional",
        help_text="Utiliza tu correo institucional para asociarte a tu organización.",
        widget=email_input(),
    )
    password = forms.CharField(label="Contraseña", widget=password_input())
    password_confirm = forms.CharField(label="Confirmar contraseña", widget=password_input())

    def clean_email(self):
        email = normalize_email(self.cleaned_data["email"])
        if email_domain(email) in PUBLIC_EMAIL_DOMAINS:
            raise ValidationError("Usa tu correo institucional o de tu empresa.")
        if User.objects.filter(email=email).exists():
            raise ValidationError("Este correo ya tiene una cuenta. Inicia sesión.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        if password and password != cleaned_data.get("password_confirm"):
            self.add_error("password_confirm", "Las contraseñas no coinciden.")
        if password:
            candidate = User(
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password, candidate)
            except ValidationError as error:
                self.add_error("password", error)
        return cleaned_data


class VerificationForm(forms.Form):
    """The screen shows six boxes named ``code``; the view joins them before validating."""

    code = forms.RegexField(
        regex=r"^\d{6}$",
        error_messages={"invalid": "Ingresa los 6 dígitos del código.", "required": "Ingresa los 6 dígitos del código."},
    )

    @classmethod
    def from_boxes(cls, data):
        return cls({"code": "".join(value.strip() for value in data.getlist("code"))})


class OrganizationForm(forms.ModelForm):
    SECTOR_CHOICES = [("", "Seleccionar"), ("publico", "Pública"), ("privado", "Privada")]

    name = forms.CharField(
        label="Nombre de la organización",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Escribe el nombre de tu organización"}),
    )
    sector = forms.ChoiceField(label="Tipo de organización", choices=SECTOR_CHOICES)

    class Meta:
        model = Organization
        fields = ["name", "sector"]


class GuiosPasswordResetForm(PasswordResetForm):
    """Never reveals whether an account exists: Django only emails active users."""

    email = forms.EmailField(label="Correo electrónico", widget=email_input())

    def clean_email(self):
        return normalize_email(self.cleaned_data["email"])

    def get_users(self, email):
        """Active users, including those an administrator created without a password yet (U02).

        Django skips unusable passwords by default; here the link is how those users set their first one.
        """
        return User.objects.filter(email__iexact=email, is_active=True)


class GuiosSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(label="Nueva contraseña", widget=password_input(), strip=False)
    new_password2 = forms.CharField(label="Confirmar", widget=password_input(), strip=False)


class ProfileForm(forms.ModelForm):
    """Editable profile fields; email and organization are fixed by the signup domain (§6.1)."""

    first_name = forms.CharField(label="Nombre", max_length=75)
    last_name = forms.CharField(label="Apellido", max_length=75, required=False)
    area = forms.CharField(
        label="Área o cargo (opcional)",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej. Dirección TIC"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "area"]


class VerificationEmailTemplateForm(forms.Form):
    """Administrator-edited subject and body of the verification email."""

    subject = forms.CharField(label="Asunto", max_length=150)
    body = forms.CharField(label="Mensaje", widget=forms.Textarea(attrs={"rows": 7}))

    def clean_body(self):
        body = self.cleaned_data["body"].replace("\r\n", "\n").strip()
        if "{codigo}" not in body:
            raise ValidationError("El mensaje debe incluir {codigo} para que el usuario reciba su código.")
        return body
