"""Read-only queries for screens. Business rules stay in services.py; these only shape data."""
from dataclasses import dataclass, field

from django.db.models import Count

from apps.core.templatetags.ui import RECOMMENDATION_NAMES

from . import workflow
from .models import Evaluation
from .permissions import visible_evaluations


@dataclass
class DashboardSummary:
    finished_count: int = 0
    drafts_count: int = 0
    last: object = None
    resume: object = None
    recent: list = field(default_factory=list)
    by_letter: list = field(default_factory=list)


@dataclass
class ResumeCard:
    """'Continúa donde lo dejaste' card (§7.1)."""

    evaluation: Evaluation
    software: object
    step_label: str
    progress: int
    updated_at: object
    url: str


def recommendation_breakdown(counts, total):
    """Rows for the 'Recomendaciones' panel; the most frequent letter is highlighted."""
    top = max(counts.values(), default=0)
    return [
        {
            "letter": letter,
            "label": label,
            "count": counts.get(letter, 0),
            "percent": round(counts.get(letter, 0) * 100 / total) if total else 0,
            "is_top": top > 0 and counts.get(letter, 0) == top,
        }
        for letter, label in RECOMMENDATION_NAMES.items()
    ]


def _resume_card(draft):
    if draft is None:
        return None
    return ResumeCard(
        evaluation=draft,
        software=draft.software,
        step_label=workflow.resume_label(draft),
        progress=workflow.resume_progress(draft),
        updated_at=draft.updated_at,
        url=workflow.resume_url(draft),
    )


def decisor_dashboard(user):
    """D01 numbers, defined as in the §7.1 table."""
    finished = Evaluation.objects.filter(
        organization_id=user.organization_id, status="finalizada"
    )
    drafts = Evaluation.objects.filter(
        author_id=user.pk, organization_id=user.organization_id, status="borrador"
    )
    finished_count = finished.count()
    counts = dict(
        finished.order_by().values_list("recommendation").annotate(total=Count("id"))
    )
    return DashboardSummary(
        finished_count=finished_count,
        drafts_count=drafts.count(),
        last=finished.filter(author_id=user.pk)
        .select_related("software")
        .order_by("-finished_at")
        .first(),
        resume=_resume_card(drafts.select_related("software").order_by("-updated_at").first()),
        recent=list(finished.select_related("software", "author").order_by("-finished_at")[:4]),
        by_letter=recommendation_breakdown(counts, finished_count),
    )


def history_count(user):
    """History badge: finalized of the organization plus own drafts."""
    return visible_evaluations(user).count()


def history(user, status=None, recommendation=None, query=""):
    """H01 list with the §6.6 filters and search by software name."""
    evaluations = visible_evaluations(user)
    if status in dict(Evaluation.ESTADOS):
        evaluations = evaluations.filter(status=status)
    if recommendation in RECOMMENDATION_NAMES:
        evaluations = evaluations.filter(status="finalizada", recommendation=recommendation)
    query = (query or "").strip()
    if query:
        evaluations = evaluations.filter(software__name__icontains=query)
    return evaluations.order_by("-updated_at")
