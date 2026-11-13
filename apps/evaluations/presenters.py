"""Shape workflow data for the evaluation templates. No rules here: math comes from services.py."""
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import groupby

from . import services, workflow
from .models import EvaluationSubfactor

STAGES = [
    (1, "Factores relevantes", "Pasos 1 y 2"),
    (2, "Ponderación", "Pasos 3 y 4"),
    (3, "Resultado", "Pasos 5 y 6"),
]
COMPLIANCE_OPTIONS = [(1, "No cumple"), (2, "No sé"), (3, "Parcial"), (4, "Cumple")]
COMPLIANCE_LABELS = {1: "No cumple", 2: "No sé", 3: "Cumple parcialmente", 4: "Cumple el requisito"}
FODA_ORDER = [("Fortaleza", "Fortalezas", True), ("Debilidad", "Debilidades", False),
              ("Oportunidad", "Oportunidades", True), ("Amenaza", "Amenazas", False)]


def stages(evaluation):
    """Stepper items; reached stages link back so the decisor can review them."""
    return [
        {"number": number, "title": title, "caption": caption,
         "url": workflow.stage_url(evaluation, number) if number <= evaluation.current_step else None}
        for number, title, caption in STAGES
    ]


def _plural(count, word):
    return f"{count} {word}{'' if count == 1 else 'es'}"


# ---------- E1 ----------

def stage1_factors(evaluation):
    return list(
        evaluation.factors.select_related("factor__dimension").order_by("factor__dimension_id", "factor__order")
    )


def stage1_counts(factors):
    evaluated = sum(1 for row in factors if row.decision_importance is not None)
    relevant = sum(1 for row in factors if row.is_relevant)
    return {"evaluated": evaluated, "total": len(factors), "relevant": relevant, "discarded": evaluated - relevant}


def stage1_groups(factors):
    groups = []
    for dimension, rows in groupby(factors, key=lambda row: row.factor.dimension):
        rows = list(rows)
        groups.append({"label": f"{dimension.name} · {_plural(len(rows), 'factor')}", "rows": rows})
    return groups


# ---------- E2 ----------

@dataclass
class FactorView:
    pk: int
    index: int
    count: int
    name: str
    dimension: str
    scope: str
    answered: int
    total: int
    pm: Decimal | None
    url: str
    is_current: bool = False
    foda: str = ""
    meets: bool | None = None
    foda_if_meets: str = ""

    @property
    def missing(self):
        return self.total - self.answered


def weighting(evaluation, factor_id=None):
    """(factor views, current view) for the E2 sidebar; current falls back to the first pending."""
    progress = workflow.factor_progress(evaluation)
    views = []
    for index, item in enumerate(progress, start=1):
        ev_factor = item["factor"]
        views.append(FactorView(
            pk=ev_factor.factor_id, index=index, count=len(progress), name=ev_factor.factor.name,
            dimension=ev_factor.factor.dimension.name, scope=ev_factor.scope.capitalize(),
            answered=item["answered"], total=item["total"], pm=item["pm"],
            url=workflow.stage_url(evaluation, 2, ev_factor.factor_id),
            foda_if_meets=services.clasificar_foda(True, ev_factor.scope),
        ))
        if item["answered"]:
            values = [answer.value for answer in ev_factor.answers.all() if answer.value is not None]
            _, meets = services.resumen_factor(values)
            views[-1].meets = meets
            views[-1].foda = services.clasificar_foda(meets, ev_factor.scope)
    if not views:
        return [], None
    current = next((view for view in views if view.pk == factor_id), None)
    current = current or next((view for view in views if view.missing), views[0])
    current.is_current = True
    return views, current


def current_answers(evaluation, factor_id):
    return EvaluationSubfactor.objects.filter(
        evaluation_factor__evaluation=evaluation, evaluation_factor__factor_id=factor_id
    ).select_related("subfactor")


def overall_progress(views):
    total = sum(view.total for view in views)
    return round(sum(view.answered for view in views) * 100 / total) if total else 0


def last_saved_label(evaluation):
    """'Etapa 2, Compatibilidad 5/8' for the exit modal."""
    label = f"Etapa {evaluation.current_step}"
    if evaluation.current_step == 2:
        _, current = weighting(evaluation)
        if current:
            label += f", {current.name} {current.answered}/{current.total}"
    return label


# ---------- E3 / H02 ----------

@dataclass
class ResultView:
    letter: str
    text: str
    rows: list
    supporting: list
    foda: list
    counts: dict
    relevant_count: int
    discarded_count: int
    problem_count: int = 0
    extra: dict = field(default_factory=dict)


def result_view(evaluation):
    data = workflow.results(evaluation)
    answers = {}
    for answer in EvaluationSubfactor.objects.filter(
        evaluation_factor__evaluation=evaluation, evaluation_factor__is_relevant=True
    ).select_related("subfactor", "evaluation_factor"):
        answers.setdefault(answer.evaluation_factor.factor_id, []).append(
            {"name": answer.subfactor.name, "value": COMPLIANCE_LABELS.get(answer.value, "Sin responder")}
        )
    rows = [
        {"name": row.factor.name, "scope": row.scope, "relative_importance": row.relative_importance,
         "pm": row.pm, "foda": row.foda, "is_problem": row.is_problem, "answers": answers.get(row.factor.pk, [])}
        for row in data["factors"]
    ]
    counts = {key: sum(1 for row in rows if row["foda"] == key) for key, _, _ in FODA_ORDER}
    total_factors = evaluation.factors.count()
    return ResultView(
        letter=data["recommendation"],
        text=data["text"],
        rows=rows,
        supporting=[{"name": row.factor.name, "pm": row.pm, "is_problem": row.is_problem} for row in data["supporting"]],
        foda=[{"label": label, "positive": positive, "factors": [row["name"] for row in rows if row["foda"] == key]}
              for key, label, positive in FODA_ORDER],
        counts=counts,
        relevant_count=len(rows),
        discarded_count=total_factors - len(rows),
        problem_count=data["problem_count"],
    )
