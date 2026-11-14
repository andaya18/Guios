"""Administrator screen for the AI-computed suggested importance (catalog tab)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.ai.verification import VALID_MIN_SCORE
from apps.management.permissions import AdministratorRequiredMixin
from apps.management.selectors import catalog_counts
from apps.management.views import catalog_url

from . import services
from .forms import DocumentForm
from .models import Citation, Document

PAGE = "management:suggested_importance"


def _citation_entry(citation, verdict):
    """The validity threshold lives in VALID_MIN_SCORE; the template only shows the result."""
    return {"citation": citation, "verdict": verdict, "is_valid": bool(verdict) and verdict["score"] >= VALID_MIN_SCORE}


class SuggestedImportanceView(AdministratorRequiredMixin, View):
    def get(self, request):
        return self.render_page(request, DocumentForm())

    def render_page(self, request, form):
        run = services.compute()  # recalculates automatically when documents or citations changed
        assessments = services.latest_assessments()
        documents = []
        for document in Document.objects.prefetch_related("citations__subfactor__factor"):
            assessment = assessments.get(document.pk)
            verdicts = {item["subfactor_id"]: item for item in (assessment.scores if assessment else [])}
            documents.append({
                "document": document,
                "assessment": assessment,
                "citations": [_citation_entry(c, verdicts.get(c.subfactor_id)) for c in document.citations.all()],
            })
        return render(request, "management/catalog/suggested_importance.html", {
            "run": run,
            "rows": run.factors.select_related("factor"),
            "documents": documents,
            "form": form,
            "valid_min_score": VALID_MIN_SCORE,
            "section": "importance",
            "catalog_url": catalog_url(),
            **catalog_counts(),
        })


class RecalculateView(AdministratorRequiredMixin, View):
    def post(self, request):
        run = services.compute(force=True)
        if run.origin == "ia":
            messages.success(request, "Importancia sugerida recalculada con IA.")
        else:
            messages.warning(request, f"La IA no respondió ({run.error}); se muestran los valores de respaldo.")
        return redirect(PAGE)


class DocumentCreateView(SuggestedImportanceView):
    def get(self, request):
        return redirect(PAGE)

    def post(self, request):
        form = DocumentForm(request.POST)
        if not form.is_valid():
            return self.render_page(request, form)
        data = {key: form.cleaned_data[key] for key in DocumentForm.Meta.fields}
        document = services.create_document(data, form.cleaned_data["subfactors"])
        messages.success(request, f"Documento {document} agregado. La importancia sugerida se recalcula con él.")
        return redirect(PAGE)


class DocumentDeleteView(AdministratorRequiredMixin, View):
    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        document.delete()
        messages.success(request, f"Documento {document} eliminado con sus citas.")
        return redirect(PAGE)


class CitationDeleteView(AdministratorRequiredMixin, View):
    def post(self, request, pk):
        citation = get_object_or_404(Citation.objects.select_related("document", "subfactor"), pk=pk)
        citation.delete()
        messages.success(request, f"Cita eliminada: {citation.document} → {citation.subfactor.name}.")
        return redirect(PAGE)


class DraftFromRunView(AdministratorRequiredMixin, View):
    def post(self, request):
        try:
            draft = services.apply_to_draft(services.compute())
        except services.DraftNotAllowed as error:
            messages.error(request, str(error))
            return redirect(PAGE)
        messages.success(request, f"Borrador v{draft.number} creado con la importancia sugerida por la IA. Revísalo y publícalo con su sustento.")
        return redirect("management:catalog_editor", draft.number)
