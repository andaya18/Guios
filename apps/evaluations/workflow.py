"""Evaluation flow (§6.3-§6.5): ORM orchestration only; every calculation comes from services.py."""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.catalog.models import CatalogVersion, Factor, FactorVersion, Subfactor

from . import services
from .models import Evaluation, EvaluationFactor, EvaluationSubfactor, Software

STAGE_NAMES = {1: "Factores relevantes", 2: "Ponderación", 3: "Resultado"}
STAGE_COUNT = len(STAGE_NAMES)
NO_RELEVANT_MESSAGE = "Debes marcar al menos un factor como relevante para continuar."
FINALIZED_MESSAGE = "Una evaluación finalizada no se puede modificar."
VALID_SCOPES = {value for value, _ in FactorVersion.ALCANCES}
VALID_LICENSES = {value for value, _ in Software.LICENCIAS}
STORED_PM = Decimal("0.0001")


class IncompleteEvaluation(ValidationError):
    """Raised when §4.8 fails; `items` keeps the {"message", "url"} list for the screen."""

    def __init__(self, items):
        self.items = items
        super().__init__([item["message"] for item in items], code="incomplete")


@dataclass
class FactorResult:
    evaluation_factor: EvaluationFactor
    factor: Factor
    scope: str
    relative_importance: int
    pm: Decimal | None
    cumple: bool | None
    foda: str

    @property
    def importancia_relativa(self):
        """Name services.recomendar expects."""
        return self.relative_importance

    @property
    def is_problem(self):
        return self.cumple is False


# URLs (§7) are plain strings until the evaluation views define named routes.


def stage_url(evaluation, step, factor_id=None):
    url = f"/evaluaciones/{evaluation.pk}/etapa-{step}/"
    return f"{url}?factor={factor_id}" if factor_id else url


def _scale_value(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = None
    if number is None or isinstance(value, bool) or not 1 <= number <= 4:
        raise ValidationError("El valor debe estar entre 1 y 4.", code="out_of_range")
    return number


def _ensure_draft(evaluation):
    """Locks the row and reads the stored status, so neither a stale instance nor a concurrent
    finalize lets a write land on a finalized evaluation. Call inside transaction.atomic()."""
    stored = (
        Evaluation.objects.select_for_update()
        .filter(pk=evaluation.pk)
        .values_list("status", flat=True)
        .first()
    )
    if stored != "borrador":
        raise PermissionDenied(FINALIZED_MESSAGE)


def _touch(evaluation, step):
    evaluation.current_step = step
    evaluation.save(update_fields=["current_step", "updated_at"])


def _plural(count, singular, plural):
    return (singular if count == 1 else plural).format(n=count)


def active_version():
    return CatalogVersion.objects.get(status="activa")


def register_software(organization, name, version, license_type):
    name, version = (name or "").strip(), (version or "").strip()
    if not name:
        raise ValidationError("El nombre del software es obligatorio.", code="required")
    if license_type not in VALID_LICENSES:
        raise ValidationError("Elige un tipo de licencia válido.", code="invalid_license")
    software, _ = Software.objects.get_or_create(
        organization=organization,
        name=name,
        version=version,
        defaults={"license_type": license_type},
    )
    return software


@transaction.atomic
def create_evaluation(user, software):
    if user.organization_id is None or user.organization_id != software.organization_id:
        raise PermissionDenied("El software no pertenece a tu organización.")
    version = active_version()
    evaluation = Evaluation.objects.create(
        organization_id=user.organization_id,
        author=user,
        software=software,
        catalog_version=version,
    )
    EvaluationFactor.objects.bulk_create(
        EvaluationFactor(
            evaluation=evaluation,
            factor_id=value.factor_id,
            suggested_importance=value.suggested_importance,
            scope=value.default_scope,
        )
        for value in version.factor_values.all()
    )
    return evaluation


@transaction.atomic
def set_decision_importance(ev_factor, value):
    evaluation = ev_factor.evaluation
    _ensure_draft(evaluation)
    value = _scale_value(value)
    relative = services.importancia_relativa(value, ev_factor.suggested_importance)
    ev_factor.decision_importance = value
    ev_factor.relative_importance = relative
    ev_factor.is_relevant = services.es_relevante(relative)
    ev_factor.save(update_fields=["decision_importance", "relative_importance", "is_relevant"])
    # Editing E1 reopens stage 1: newly relevant factors need their answer rows (§6.3).
    _touch(evaluation, 1)
    return ev_factor


@transaction.atomic
def set_scope(ev_factor, scope):
    evaluation = ev_factor.evaluation
    _ensure_draft(evaluation)
    if scope not in VALID_SCOPES:
        raise ValidationError("El alcance debe ser interno o externo.", code="invalid_scope")
    ev_factor.scope = scope
    ev_factor.save(update_fields=["scope"])
    _touch(evaluation, 1)
    return ev_factor


@transaction.atomic
def start_stage_two(evaluation):
    _ensure_draft(evaluation)
    factors = list(evaluation.factors.all())
    if any(ev_factor.decision_importance is None for ev_factor in factors):
        raise ValidationError(
            f"Asigna la importancia de los {len(factors)} factores para continuar.",
            code="missing_importance",
        )
    relevant = {ev_factor.factor_id: ev_factor for ev_factor in factors if ev_factor.is_relevant}
    if not relevant:
        raise ValidationError(NO_RELEVANT_MESSAGE, code="no_relevant")
    existing = set(
        EvaluationSubfactor.objects.filter(
            evaluation_factor__in=relevant.values()
        ).values_list("subfactor_id", flat=True)
    )
    EvaluationSubfactor.objects.bulk_create(
        EvaluationSubfactor(evaluation_factor=relevant[subfactor.factor_id], subfactor=subfactor)
        for subfactor in Subfactor.objects.filter(factor_id__in=relevant)
        if subfactor.pk not in existing
    )
    _touch(evaluation, 2)


@transaction.atomic
def answer_subfactor(evaluation, answer_id, value):
    _ensure_draft(evaluation)
    value = _scale_value(value)
    answer = EvaluationSubfactor.objects.get(
        pk=answer_id, evaluation_factor__evaluation=evaluation
    )
    answer.value = value
    answer.save(update_fields=["value"])
    _touch(evaluation, 2)
    return answer


def _subfactor_totals(factor_ids):
    rows = (
        Subfactor.objects.filter(factor_id__in=factor_ids)
        .order_by()
        .values_list("factor_id")
        .annotate(total=Count("id"))
    )
    return dict(rows)


def _relevant_factors(evaluation):
    """(evaluation_factor, answered values, catalog subfactor total) per relevant factor."""
    factors = list(
        evaluation.factors.filter(is_relevant=True)
        .select_related("factor")
        .prefetch_related("answers")
    )
    totals = _subfactor_totals([ev_factor.factor_id for ev_factor in factors])
    return [
        (
            ev_factor,
            [answer.value for answer in ev_factor.answers.all() if answer.value is not None],
            totals.get(ev_factor.factor_id, 0),
        )
        for ev_factor in factors
    ]


def _pending_factor(evaluation):
    """First relevant factor with unanswered subfactors (§7.1), or None."""
    for ev_factor, values, total in _relevant_factors(evaluation):
        if len(values) < total:
            return ev_factor, values, total
    return None


def factor_progress(evaluation):
    return [
        {
            "factor": ev_factor,
            "answered": len(values),
            "total": total,
            "pm": services.resumen_factor(values)[0] if values else None,
        }
        for ev_factor, values, total in _relevant_factors(evaluation)
    ]


def missing_items(evaluation):
    """What still blocks finishing (§4.8), each with a link to complete it."""
    items = []
    factors = list(evaluation.factors.all())
    unassigned = sum(1 for ev_factor in factors if ev_factor.decision_importance is None)
    if unassigned:
        message = _plural(
            unassigned,
            "Etapa 1: falta {n} factor por asignar importancia",
            "Etapa 1: faltan {n} factores por asignar importancia",
        )
        items.append({"message": message, "url": stage_url(evaluation, 1)})
    elif not any(ev_factor.is_relevant for ev_factor in factors):
        items.append({"message": NO_RELEVANT_MESSAGE, "url": stage_url(evaluation, 1)})
    for ev_factor, values, total in _relevant_factors(evaluation):
        missing = total - len(values)
        if missing:
            count = _plural(missing, "falta {n} subfactor", "faltan {n} subfactores")
            items.append(
                {
                    "message": f"{ev_factor.factor.name}: {count}",
                    "url": stage_url(evaluation, 2, ev_factor.factor_id),
                }
            )
    return items


@transaction.atomic
def go_to_results(evaluation):
    _ensure_draft(evaluation)
    items = missing_items(evaluation)
    if items:
        raise IncompleteEvaluation(items)
    _touch(evaluation, 3)


def _computed_rows(evaluation):
    rows = []
    for ev_factor, values, total in _relevant_factors(evaluation):
        pm = cumple = None
        foda = ""
        if values and len(values) == total:
            pm, cumple = services.resumen_factor(values)
            foda = services.clasificar_foda(cumple, ev_factor.scope)
        rows.append(
            FactorResult(
                ev_factor, ev_factor.factor, ev_factor.scope,
                ev_factor.relative_importance, pm, cumple, foda,
            )
        )
    return rows


def _saved_rows(evaluation):
    return [
        FactorResult(
            ev_factor,
            ev_factor.factor,
            ev_factor.scope,
            ev_factor.relative_importance,
            ev_factor.pm,
            ev_factor.foda == services.clasificar_foda(True, ev_factor.scope),
            ev_factor.foda,
        )
        for ev_factor in evaluation.factors.filter(is_relevant=True).select_related("factor")
    ]


def results(evaluation):
    """E3 data: computed live for drafts, read from stored values once finalized."""
    if evaluation.is_finalized:
        rows = _saved_rows(evaluation)
        letter = evaluation.recommendation
    else:
        rows = _computed_rows(evaluation)
        complete = bool(rows) and all(row.foda for row in rows)
        letter = services.recomendar(rows) if complete else ""
    problems = [row for row in rows if row.is_problem]
    return {
        "factors": rows,
        "recommendation": letter,
        "text": services.TEXTOS_RECOMENDACION.get(letter, ""),
        # §4.7: the problematic factors support B/C; with A every relevant factor does.
        "supporting": rows if letter == "A" else problems,
        "problem_count": len(problems),
    }


@transaction.atomic
def finalize(evaluation):
    _ensure_draft(evaluation)
    locked = Evaluation.objects.get(pk=evaluation.pk)
    items = missing_items(locked)
    if items:
        raise IncompleteEvaluation(items)
    result = results(locked)
    for row in result["factors"]:
        ev_factor = row.evaluation_factor
        ev_factor.pm = row.pm.quantize(STORED_PM, rounding=ROUND_HALF_UP)
        ev_factor.foda = row.foda
        ev_factor.save(update_fields=["pm", "foda"])
    locked.factors.filter(is_relevant=False).update(pm=None, foda="")
    locked.status = "finalizada"
    locked.recommendation = result["recommendation"]
    locked.finished_at = timezone.now()
    locked.current_step = 3
    locked.save()
    evaluation.refresh_from_db()
    return evaluation


@transaction.atomic
def duplicate(evaluation, user):
    """New draft for `user` with the same IDs, scopes and answers on the active version (§6.5)."""
    if user.organization_id is None or user.organization_id != evaluation.organization_id:
        raise PermissionDenied("La evaluación no pertenece a tu organización.")
    if not evaluation.is_finalized:
        raise ValidationError("Solo se pueden duplicar evaluaciones finalizadas.", code="draft")
    version = active_version()
    same_version = version.pk == evaluation.catalog_version_id
    suggested = dict(version.factor_values.values_list("factor_id", "suggested_importance"))
    copy = Evaluation.objects.create(
        organization_id=evaluation.organization_id,
        author=user,
        software_id=evaluation.software_id,
        catalog_version=version,
        duplicated_from=evaluation,
    )
    for original in evaluation.factors.prefetch_related("answers"):
        importance = suggested[original.factor_id]
        relative = (
            services.importancia_relativa(original.decision_importance, importance)
            if original.decision_importance
            else None
        )
        ev_factor = EvaluationFactor.objects.create(
            evaluation=copy,
            factor_id=original.factor_id,
            decision_importance=original.decision_importance,
            suggested_importance=importance,
            relative_importance=relative,
            scope=original.scope,
            is_relevant=relative is not None and services.es_relevante(relative),
        )
        EvaluationSubfactor.objects.bulk_create(
            EvaluationSubfactor(
                evaluation_factor=ev_factor, subfactor_id=answer.subfactor_id, value=answer.value
            )
            for answer in original.answers.all()
        )
    warning = None
    if not same_version:
        warning = (
            f"Esta evaluación usa el catálogo versión {version.number}, distinto al de la original"
        )
    return copy, warning


@transaction.atomic
def delete_draft(evaluation, user):
    if evaluation.author_id != user.pk:
        raise PermissionDenied("Solo puedes eliminar tus propios borradores.")
    _ensure_draft(evaluation)
    evaluation.delete()


def resume_label(evaluation):
    """'Etapa 2 de 3 · Ponderación · Factor: Compatibilidad (5 de 8 subfactores)' (§7.1)."""
    step = evaluation.current_step
    label = f"Etapa {step} de {STAGE_COUNT} · {STAGE_NAMES[step]}"
    if step == 1:
        factors = list(evaluation.factors.all())
        assigned = sum(1 for ev_factor in factors if ev_factor.decision_importance is not None)
        return f"{label} · {assigned} de {len(factors)} factores"
    if step == 2:
        pending = _pending_factor(evaluation)
        if pending:
            ev_factor, values, total = pending
            return f"{label} · Factor: {ev_factor.factor.name} ({len(values)} de {total} subfactores)"
    return label


def resume_progress(evaluation):
    """Percent = ((step - 1) + fraction of the current stage) / 3 * 100."""
    step = evaluation.current_step
    fraction = 0
    if step == 1:
        factors = list(evaluation.factors.all())
        assigned = sum(1 for ev_factor in factors if ev_factor.decision_importance is not None)
        fraction = assigned / len(factors) if factors else 0
    elif step == 2:
        rows = _relevant_factors(evaluation)
        total = sum(total for _, _, total in rows)
        fraction = sum(len(values) for _, values, _ in rows) / total if total else 0
    return round(((step - 1) + fraction) / STAGE_COUNT * 100)


def resume_url(evaluation):
    """Link to the current stage; stage 2 opens the first factor still pending."""
    step = evaluation.current_step
    if step == 2:
        pending = _pending_factor(evaluation)
        if pending:
            return stage_url(evaluation, 2, pending[0].factor_id)
    return stage_url(evaluation, step)
