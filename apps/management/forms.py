from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.accounts.models import Organization, User
from apps.catalog.models import FactorVersion
from apps.evaluations.services import ESCALA


class UserForm(forms.ModelForm):
    """U02: crear (con cualquier rol) y editar usuarios. Nunca se eliminan."""

    password = forms.CharField(
        label="Contraseña temporal",
        widget=forms.PasswordInput(attrs={"placeholder": "Mínimo 8 caracteres", "autocomplete": "new-password"}),
        help_text="El usuario podrá cambiarla desde Recuperar contraseña.",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role", "organization", "area", "is_active"]
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
            "role": "Rol",
            "organization": "Organización",
            "area": "Área",
            "is_active": "Activo · puede iniciar sesión",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "Ingresa el nombre"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Ingresa el apellido"}),
            "email": forms.EmailInput(attrs={"placeholder": "nombre@organizacion.edu.ec"}),
            "area": forms.TextInput(attrs={"placeholder": "Ej. Dirección TIC"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name"):
            self.fields[name].required = True
        self.fields["organization"].queryset = Organization.objects.order_by("name")
        self.fields["organization"].empty_label = "Sin organización"
        if self.instance.pk:
            del self.fields["password"]
        else:
            del self.fields["is_active"]

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        if role == "decisor" and not cleaned.get("organization"):
            self.add_error("organization", "Un decisor debe pertenecer a una organización.")
        if role == "administrador":
            cleaned["organization"] = None
            cleaned["area"] = ""
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if "password" in self.cleaned_data:
            user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class OrganizationForm(forms.ModelForm):
    """O02: nombre, sector y estado. El dominio se bloquea cuando ya tiene usuarios (§6.9)."""

    class Meta:
        model = Organization
        fields = ["name", "domain", "sector", "is_active"]
        labels = {"name": "Nombre *", "domain": "Dominio de correo *", "sector": "Sector *", "is_active": "Estado"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Nombre de la organización"}),
            "domain": forms.TextInput(attrs={"placeholder": "organizacion.edu.ec"}),
            "sector": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sector"].choices = Organization.SECTORS
        if not self.instance.pk:
            self.initial.setdefault("is_active", True)
            self.initial.setdefault("sector", "publico")
        elif self.instance.users.exists():
            self.fields["domain"].disabled = True
            self.fields["domain"].help_text = "No se puede cambiar: la organización ya tiene usuarios."

    def clean_domain(self):
        return self.cleaned_data["domain"].strip().lower().lstrip("@")


class FactorValuesForm(forms.Form):
    """M01: solo la IS (1 a 4) y el alcance por defecto (Interno o Externo)."""

    suggested_importance = forms.TypedChoiceField(
        label="Importancia sugerida",
        coerce=int,
        choices=[(value, f"{value} {label}") for value, label in ESCALA.items()],
        widget=forms.RadioSelect,
    )
    default_scope = forms.ChoiceField(
        label="Alcance por defecto",
        choices=FactorVersion.ALCANCES,
        widget=forms.RadioSelect,
    )


class PublishForm(forms.Form):
    """M02: sustento y autorización obligatorios antes de publicar."""

    justification = forms.CharField(
        label="Sustento metodológico *",
        max_length=500,
        widget=forms.TextInput(attrs={"placeholder": "Ej. Revisión bibliográfica 2020–2025 (Tarea N.° 1, Tabla 17)"}),
    )
    authorized_by = forms.CharField(
        label="Autorizado por *",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Nombre de quien autoriza"}),
    )
    name = forms.CharField(
        label="Nota de versión",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Ej. Actualización de IS 2020–2025"}),
    )
    confirmed = forms.BooleanField(
        label="Confirmo que estos cambios fueron validados y autorizados metodológicamente",
    )
