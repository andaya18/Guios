from django import forms

from apps.catalog.models import Subfactor

from .models import Document


class SubfactorChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, subfactor):
        return f"{subfactor.factor.name} · {subfactor.order}. {subfactor.name}"


class DocumentForm(forms.ModelForm):
    subfactors = SubfactorChoiceField(
        label="Subfactores que respalda",
        queryset=Subfactor.objects.select_related("factor").order_by("factor__order", "order"),
        widget=forms.SelectMultiple(attrs={"size": 8}),
        help_text="Cada subfactor elegido cuenta como una cita (convención de la tesis).",
    )

    class Meta:
        model = Document
        fields = ["authors", "year", "title", "source", "url", "database"]
        labels = {"authors": "Autores", "year": "Año", "title": "Título", "source": "Revista o fuente",
                  "url": "DOI o enlace", "database": "Base de datos"}
