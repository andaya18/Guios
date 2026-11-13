"""Decisor history screens H01-H03, duplicate and C01 compare."""
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import decisor_required
from apps.core.templatetags.ui import RECOMMENDATION_NAMES, short_date

from . import presenters, selectors, workflow
from .models import Evaluation
from .permissions import get_visible_evaluation, visible_evaluations

PAGE_SIZE = 10
DATE_CHOICES = [("7", "Últimos 7 días"), ("30", "Últimos 30 días"), ("90", "Últimos 90 días")]
STATUS_TABS = [("", "Todas"), ("borrador", "Mis borradores"), ("finalizada", "Finalizadas")]
VERSION_MISMATCH = (
    "Las evaluaciones seleccionadas usan versiones de catálogo distintas, así que no se pueden comparar. "
    "Elige evaluaciones de la misma versión."
)


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@decisor_required
def history_list(request):
    """H01: finalized evaluations of the organization plus own drafts (§6.6)."""
    status = request.GET.get("estado", "")
    filters = {
        "status": status,
        "query": request.GET.get("q", "").strip(),
        "recommendation": request.GET.get("recomendacion", ""),
        "evaluator": _int_or_none(request.GET.get("evaluador")),
        "date": request.GET.get("fecha", ""),
    }
    evaluations = selectors.history(request.user, status or None, filters["recommendation"] or None, filters["query"])
    if filters["evaluator"]:
        evaluations = evaluations.filter(author_id=filters["evaluator"])
    if filters["date"] in dict(DATE_CHOICES):
        evaluations = evaluations.filter(updated_at__gte=timezone.now() - timedelta(days=int(filters["date"])))

    page_obj = Paginator(evaluations, PAGE_SIZE).get_page(request.GET.get("page"))
    for evaluation in page_obj.object_list:
        if not evaluation.is_finalized:
            evaluation.resume_url = workflow.resume_url(evaluation)

    visible = visible_evaluations(request.user)
    counts = {"": visible.count(), "borrador": visible.filter(status="borrador").count(),
              "finalizada": visible.filter(status="finalizada").count()}
    kept = {key: value for key, value in request.GET.items() if key not in ("page", "estado") and value}
    tabs = [
        {"label": label, "count": counts[value], "active": value == status,
         "url": "?" + urlencode({**kept, **({"estado": value} if value else {})})}
        for value, label in STATUS_TABS
    ]
    base_query = {key: value for key, value in request.GET.items() if key != "page" and value}
    return render(request, "history/list.html", {
        "page_obj": page_obj,
        "tabs": tabs,
        "filters": filters,
        "querystring_base": urlencode(base_query) + "&" if base_query else "",
        "recommendation_choices": list(RECOMMENDATION_NAMES.items()),
        "evaluators": User.objects.filter(pk__in=visible.values("author_id")).order_by("first_name"),
        "date_choices": DATE_CHOICES,
    })


@decisor_required
def history_detail(request, pk):
    """H02: read-only results; a draft of the author offers Continuar instead (§6.6)."""
    evaluation = get_visible_evaluation(request.user, pk)
    has_results = evaluation.is_finalized or not workflow.missing_items(evaluation)
    return render(request, "history/detail.html", {
        "evaluation": evaluation,
        "result": presenters.result_view(evaluation) if has_results else None,
        "stage1_rows": presenters.stage1_factors(evaluation),
        "is_own_draft": not evaluation.is_finalized and evaluation.author_id == request.user.pk,
        "resume_url": workflow.resume_url(evaluation),
        "export_url": reverse("history:export", args=[evaluation.pk]),
        "export_label": f"{evaluation.software} · {short_date(evaluation.finished_at)}",
    })


@decisor_required
@require_POST
def duplicate(request, pk):
    """§6.5: new draft for whoever duplicates; the original never changes."""
    original = get_visible_evaluation(request.user, pk)
    copy, warning = workflow.duplicate(original, request.user)
    if warning:
        messages.warning(request, warning)
    return redirect(workflow.stage_url(copy, 1))


@decisor_required
@require_POST
def delete_draft(request, pk):
    """H03 / E4 'Descartar evaluación': only the author's own drafts (§3, §6.6)."""
    evaluation = get_object_or_404(Evaluation, pk=pk, organization_id=request.user.organization_id)
    workflow.delete_draft(evaluation, request.user)
    messages.success(request, f"Se eliminó el borrador de {evaluation.software}.")
    return redirect("history:list")


@decisor_required
def export_pending(request, pk):
    """Replaced by apps.exports once X01 lands (T6)."""
    get_visible_evaluation(request.user, pk)
    raise Http404("La exportación todavía no está disponible.")


@decisor_required
def compare(request):
    """C01: 2 to 4 finalized evaluations of the organization, same catalog version (§4.9)."""
    finished = visible_evaluations(request.user).filter(status="finalizada")
    ids = list(dict.fromkeys(i for i in (_int_or_none(v) for v in request.GET.getlist("ids")) if i))[: presenters.MAX_COMPARED]
    selected = {evaluation.pk: evaluation for evaluation in finished.filter(pk__in=ids)}
    evaluations = [selected[pk] for pk in ids if pk in selected]

    context = {"items": [], "candidates": finished.exclude(pk__in=selected).order_by("-finished_at")}
    if len(evaluations) >= 2 and len({e.catalog_version_id for e in evaluations}) > 1:
        context["version_mismatch"] = VERSION_MISMATCH
        context["items"] = [{"evaluation": e} for e in evaluations]
    elif len(evaluations) >= 2:
        context.update(presenters.compare(evaluations))
    else:
        context["items"] = [{"evaluation": e} for e in evaluations]
    for item in context["items"]:
        others = [str(e.pk) for e in evaluations if e.pk != item["evaluation"].pk]
        item["remove_query"] = urlencode([("ids", pk) for pk in others])
    return render(request, "compare/compare.html", context)
