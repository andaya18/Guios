from django import forms

from apps.accounts.models import Organization, User
from apps.catalog.models import FactorVersion
from apps.evaluations.services import ESCALA


class UserForm(forms.ModelForm):
    """U02 drawer: create (any role) or edit users. Users are never deleted, only deactivated.

    New users get no password here: they receive an email link to create it (Figma U02).
    """

    full_name = forms.CharField(
        label="Nombre completo", max_length=150, error_messages={"required": "Escribe el nombre completo."}
    )
    role = forms.ChoiceField(label="Rol", choices=User.ROLES, widget=forms.RadioSelect)

    class Meta:
        model = User
        fields = ["email", "role", "organization", "is_active"]
        labels = {"email": "Correo electrónico", "organization": "Organización", "is_active": "Activo"}
        widgets = {"email": forms.EmailInput(attrs={"placeholder": "nombre@organizacion.edu.ec"})}
        error_messages = {"email": {"unique": "Este correo ya está registrado"}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = Organization.objects.order_by("name")
        self.fields["organization"].empty_label = "Sin organización"
        self.fields["organization"].required = False
        if self.instance.pk:
            self.initial.setdefault("full_name", self.instance.get_full_name())
        else:
            self.initial.setdefault("is_active", True)

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if not name:
            raise forms.ValidationError("Escribe el nombre completo.")
        return name

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        if role == "decisor" and not cleaned.get("organization"):
            self.add_error("organization", "Un decisor debe pertenecer a una organización.")
        if role == "administrador":
            cleaned["organization"] = None
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        # First word is the first name; the rest goes to last_name, so get_full_name() shows it unchanged.
        first, _, rest = self.cleaned_data["full_name"].partition(" ")
        user.first_name, user.last_name = first, rest
        if user.role == "administrador":
            user.area = ""
        if not user.pk:
            user.set_unusable_password()
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
    authorized_at = forms.DateField(
        label="Fecha de autorización *",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    name = forms.CharField(
        label="Nota de versión",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Ej. Actualización de IS 2020–2025"}),
    )
    confirmed = forms.BooleanField(
        label="Confirmo que estos cambios fueron validados y autorizados metodológicamente",
    )

    def clean_authorized_at(self):
        from django.utils import timezone

        value = self.cleaned_data["authorized_at"]
        if value > timezone.localdate():
            raise forms.ValidationError("La fecha de autorización no puede ser futura.")
        return value
