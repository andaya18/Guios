from datetime import timedelta

from django import template
from django.utils import timezone
from django.utils.formats import date_format

register = template.Library()

STATUS_PILLS = {"activa": "draft", "publicada": "neutral", "borrador": "dark"}


@register.filter
def last_access(value):
    """'hoy', 'ayer' o la fecha, como en la columna Último acceso de U01."""
    if not value:
        return "Nunca"
    day = timezone.localtime(value).date()
    today = timezone.localdate()
    if day == today:
        return "hoy"
    if day == today - timedelta(days=1):
        return "ayer"
    return date_format(day, "d/m/Y")


@register.filter
def version_pill(status):
    return STATUS_PILLS.get(status, "neutral")
