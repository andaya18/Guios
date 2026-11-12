"""Read-only queries for screens. Business rules stay in services.py; these only shape data."""
from dataclasses import dataclass, field

from apps.core.templatetags.ui import RECOMMENDATION_NAMES


@dataclass
class DashboardSummary:
    finished_count: int = 0
    drafts_count: int = 0
    last: object = None
    resume: object = None
    recent: list = field(default_factory=list)
    by_letter: list = field(default_factory=list)


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


def decisor_dashboard(user):
    # Filled with real queries once the evaluation models exist (task T4/T5).
    return DashboardSummary(by_letter=recommendation_breakdown({}, 0))


def history_count(user):
    return 0
