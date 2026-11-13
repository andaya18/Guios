from django import forms

from .models import Software

FREE_LICENSE = "libre"
NON_FREE_NOTICE = (
    "La metodología GUIOS fue validada para software libre; "
    "en otros tipos de software los resultados son orientativos"
)


class NewEvaluationForm(forms.Form):
    """D02: pick a registered software of the organization or register a new one (§6.3)."""

    MODE_EXISTING = "existente"
    MODE_NEW = "nuevo"

    mode = forms.ChoiceField(
        choices=[(MODE_EXISTING, "Elegir uno registrado"), (MODE_NEW, "Registrar nuevo")],
        initial=MODE_NEW,
        widget=forms.RadioSelect,
    )
    software = forms.ModelChoiceField(
        label="Software registrado *",
        queryset=Software.objects.none(),
        required=False,
        empty_label="Selecciona...",
    )
    name = forms.CharField(
        label="Nombre del software *",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej. LibreOffice"}),
    )
    version = forms.CharField(
        label="Versión",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej. 24.2"}),
    )
    license_type = forms.ChoiceField(
        label="Tipo de licencia *",
        choices=[("", "Selecciona...")] + Software.LICENCIAS,
        required=False,
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["software"].queryset = Software.objects.filter(organization=organization).order_by("name", "version")

    def clean(self):
        data = super().clean()
        if data.get("mode") == self.MODE_EXISTING:
            if not data.get("software"):
                self.add_error("software", "Elige un software registrado para continuar")
            return data
        if not data.get("name", "").strip():
            self.add_error("name", "Escribe el nombre del software para continuar")
        if not data.get("license_type"):
            self.add_error("license_type", "Elige un tipo de licencia para continuar")
        return data

    def similar_software(self):
        """Registered software with the same name but another version, to suggest reusing it."""
        name = (self.data.get("name") or "").strip()
        if not name:
            return None
        version = (self.data.get("version") or "").strip()
        return (
            Software.objects.filter(organization=self.organization, name__iexact=name)
            .exclude(version=version)
            .first()
        )
