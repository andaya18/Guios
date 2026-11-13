"""Decisor evaluation screens D02 and E1-E5. Views stay thin: rules live in workflow/services."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.decorators import decisor_required

from . import presenters, workflow
from .forms import NON_FREE_NOTICE, NewEvaluationForm
from .models import EvaluationFactor, Software
from .permissions import get_editable_draft
from .services import ESCALA

SCALE = sorted(ESCALA.items())


def _stage_context(evaluation, stage, **extra):
    return {
        "evaluation": evaluation,
        "stage": stage,
        "stages": presenters.stages(evaluation),
        "delete_url": reverse("history:delete", args=[evaluation.pk]),
        "finish_url": reverse("evaluations:finish", args=[evaluation.pk]),
        "last_saved_label": presenters.last_saved_label(evaluation),
        **extra,
    }


def _bad_request(error):
    return HttpResponseBadRequest(" ".join(error.messages))


def _redirect_to_missing(request, items):
    for item in items:
        messages.error(request, item["message"])
    return redirect(items[0]["url"])


# ---------- D02 ----------

@decisor_required
def new_evaluation(request):
    organization = request.user.organization
    form = NewEvaluationForm(request.POST or None, organization=organization)
    software = None
    if request.method == "POST":
        if request.POST.get("use_existing"):
            software = get_object_or_404(Software, pk=request.POST["use_existing"], organization=organization)
        elif form.is_valid():
            data = form.cleaned_data
            if data["mode"] == NewEvaluationForm.MODE_EXISTING:
                software = data["software"]
            else:
                software = workflow.register_software(organization, data["name"], data["version"], data["license_type"])
    if software is not None:
        evaluation = workflow.create_evaluation(request.user, software)
        return redirect(workflow.stage_url(evaluation, 1))
    return render(request, "evaluations/new.html", {
        "form": form,
        "non_free_notice": NON_FREE_NOTICE,
        "similar": form.similar_software() if form.is_bound else None,
    })


# ---------- E1 ----------

@decisor_required
def stage1(request, pk):
    evaluation = get_editable_draft(request.user, pk)
    if request.method == "POST":
        try:
            workflow.start_stage_two(evaluation)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect(workflow.stage_url(evaluation, 1))
        return redirect(workflow.resume_url(evaluation))
    factors = presenters.stage1_factors(evaluation)
    return render(request, "evaluations/stage1.html", _stage_context(
        evaluation, 1,
        groups=presenters.stage1_groups(factors),
        counts=presenters.stage1_counts(factors),
        scale=SCALE,
    ))


@decisor_required
@require_POST
def save_factor(request, pk, factor_id):
    """HTMX autosave of one E1 row (§6.4): returns the row plus out-of-band counters."""
    evaluation = get_editable_draft(request.user, pk)
    ev_factor = get_object_or_404(EvaluationFactor.objects.select_related("factor", "evaluation"), evaluation=evaluation, factor_id=factor_id)
    importance = request.POST.get(f"factor-{factor_id}-decision_importance")
    scope = request.POST.get(f"factor-{factor_id}-scope")
    try:
        if importance is not None and str(ev_factor.decision_importance) != importance:
            workflow.set_decision_importance(ev_factor, importance)
        if scope is not None and scope != ev_factor.scope:
            workflow.set_scope(ev_factor, scope)
    except ValidationError as error:
        return _bad_request(error)
    factors = presenters.stage1_factors(evaluation)
    row = next(item for item in factors if item.factor_id == factor_id)
    return render(request, "evaluations/partials/stage1_row.html", {
        "evaluation": evaluation, "row": row, "scale": SCALE, "oob": True,
        "counts": presenters.stage1_counts(factors),
    })


# ---------- E2 ----------

def _factor_id(request):
    try:
        return int(request.GET.get("factor", ""))
    except ValueError:
        return None


@decisor_required
def stage2(request, pk):
    evaluation = get_editable_draft(request.user, pk)
    views, current = presenters.weighting(evaluation, _factor_id(request))
    if evaluation.current_step < 2 or current is None:
        return redirect(workflow.stage_url(evaluation, 1))
    previous = views[current.index - 2] if current.index > 1 else None
    following = views[current.index] if current.index < len(views) else None
    return render(request, "evaluations/stage2.html", _stage_context(
        evaluation, 2,
        factors=views,
        current=current,
        answers=presenters.current_answers(evaluation, current.pk),
        options=presenters.COMPLIANCE_OPTIONS,
        overall_progress=presenters.overall_progress(views),
        previous_url=previous.url if previous else workflow.stage_url(evaluation, 1),
        previous_label="Factor anterior" if previous else "Etapa 1",
        next_url=following.url if following else workflow.stage_url(evaluation, 3),
        next_label="Siguiente factor" if following else "Ver resultado",
    ))


@decisor_required
@require_POST
def save_answer(request, pk, answer_id):
    """HTMX autosave of one subfactor (§6.4): returns the live PM summary of its factor."""
    evaluation = get_editable_draft(request.user, pk)
    try:
        answer = workflow.answer_subfactor(evaluation, answer_id, request.POST.get(f"answer-{answer_id}-value"))
    except ValidationError as error:
        return _bad_request(error)
    _, current = presenters.weighting(evaluation, answer.evaluation_factor.factor_id)
    return render(request, "evaluations/partials/stage2_summary.html", {"current": current, "oob": True})


# ---------- E3 / E5 ----------

@decisor_required
def stage3(request, pk):
    evaluation = get_editable_draft(request.user, pk)
    items = workflow.missing_items(evaluation)
    if items:
        return _redirect_to_missing(request, items)
    if evaluation.current_step < 3:
        workflow.go_to_results(evaluation)
        evaluation.refresh_from_db()
    views, _ = presenters.weighting(evaluation)
    return render(request, "evaluations/stage3.html", _stage_context(
        evaluation, 3,
        result=presenters.result_view(evaluation),
        previous_url=views[-1].url if views else workflow.stage_url(evaluation, 2),
    ))


@decisor_required
@require_POST
def finish(request, pk):
    evaluation = get_editable_draft(request.user, pk)
    try:
        workflow.finalize(evaluation)
    except workflow.IncompleteEvaluation as error:
        return _redirect_to_missing(request, error.items)
    messages.success(request, "Evaluación finalizada. Ya puedes exportarla, duplicarla o compararla.")
    return redirect(evaluation.get_absolute_url())
