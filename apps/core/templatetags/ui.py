from decimal import Decimal

from django import template
from django.utils import timezone
from django.utils.formats import date_format

from apps.evaluations.services import ESCALA, formatear_pm

register = template.Library()

RECOMMENDATION_NAMES = {
    "A": "Adoptar",
    "B": "Adoptar con matices",
    "C": "Analizar y posponer",
}


@register.filter
def startswith(value, prefix):
    return str(value).startswith(str(prefix))


@register.simple_tag
def today_long():
    """'viernes, 9 oct 2026' as shown in the top bar."""
    return date_format(timezone.localdate(), "l, j b Y")


@register.filter
def recommendation_name(letter):
    return RECOMMENDATION_NAMES.get(letter, "")


@register.filter
def short_date(value):
    return date_format(timezone.localtime(value) if hasattr(value, "tzinfo") else value, "d/m/Y") if value else ""


@register.filter
def pm(value):
    """Ponderación media shown with two decimals and a comma ('2,88'), per §4.5."""
    if value is None or value == "":
        return ""
    return formatear_pm(Decimal(str(value)))


@register.filter
def ago_short(value):
    """Compact elapsed time for 'Editado hace 2 h'."""
    if not value:
        return ""
    minutes = int((timezone.now() - value).total_seconds() // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    if minutes < 60 * 24:
        return f"{minutes // 60} h"
    return f"{minutes // (60 * 24)} d"


@register.filter
def importance(value):
    """1..4 -> 'Irrelevante' | 'Opcional' | 'Importante' | 'Fundamental' (§4.1)."""
    return ESCALA.get(value, "")


@register.filter
def scope_label(value):
    return {"interno": "Interno", "externo": "Externo"}.get(value, "")


@register.filter
def recommendation_title(letter):
    """Full name of a recommendation letter (§4.7), e.g. 'Analizar y posponer la adopción'."""
    return {"A": "Adoptar", "B": "Adoptar con matices", "C": "Analizar y posponer la adopción"}.get(letter, "")
