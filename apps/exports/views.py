from django.http import Http404, HttpResponse, HttpResponseBadRequest

from apps.core.decorators import decisor_required
from apps.evaluations.permissions import get_visible_evaluation

from . import services

CONTENT_TYPES = {"pdf": "application/pdf", "csv": "text/csv; charset=utf-8"}


@decisor_required
def export_evaluation(request, pk):
    """X01: PDF or CSV of a finalized evaluation of the user's organization (§6.8)."""
    fmt = request.GET.get("formato", "pdf")
    if fmt not in CONTENT_TYPES:
        return HttpResponseBadRequest("Formato no válido: usa pdf o csv.")
    evaluation = get_visible_evaluation(request.user, pk)
    if not evaluation.is_finalized:
        raise Http404("Solo se pueden exportar evaluaciones finalizadas.")
    if fmt == "csv":
        content = services.build_csv(evaluation)
    else:
        content = services.build_pdf(evaluation, request.GET.getlist("incluir"))
    response = HttpResponse(content, content_type=CONTENT_TYPES[fmt])
    response["Content-Disposition"] = f'attachment; filename="{services.export_filename(evaluation, fmt)}"'
    return response
