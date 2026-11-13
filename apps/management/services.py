"""Reglas del catálogo metodológico para el administrador (§5.2, §6.9).

Las vistas solo llaman a estas funciones. Los factores y subfactores nunca se
agregan ni se quitan aquí: una versión solo cambia la importancia sugerida y el
alcance por defecto de cada factor.
"""
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.catalog.models import CatalogVersion, Factor, FactorVersion
from apps.evaluations.services import ESCALA

SCOPES = dict(FactorVersion.ALCANCES)


class CatalogRuleError(Exception):
    """Una operación viola las reglas del catálogo."""


@dataclass(frozen=True)
class Change:
    factor: Factor
    field: str
    before: str
    after: str


def importance_label(value):
    return f"{ESCALA[value]} ({value})"


def compare_versions(base, other):
    """Diferencias de IS y alcance, factor por factor, de `other` respecto de `base`."""
    base_values = {fv.factor_id: fv for fv in base.factor_values.all()}
    changes = []
    for value in other.factor_values.select_related("factor").order_by("factor__order"):
        previous = base_values.get(value.factor_id)
        if previous is None:
            continue
        if previous.suggested_importance != value.suggested_importance:
            changes.append(Change(
                value.factor,
                "Importancia sugerida",
                importance_label(previous.suggested_importance),
                importance_label(value.suggested_importance),
            ))
        if previous.default_scope != value.default_scope:
            changes.append(Change(
                value.factor,
                "Alcance por defecto",
                SCOPES[previous.default_scope],
                SCOPES[value.default_scope],
            ))
    return changes


def active_version():
    return CatalogVersion.objects.filter(status="activa").first()


def draft_version():
    return CatalogVersion.objects.filter(status="borrador").first()


def previous_version(version):
    return CatalogVersion.objects.filter(number__lt=version.number).exclude(status="borrador").order_by("-number").first()


def draft_changes(draft=None):
    """Cambios del borrador frente a la versión activa; lista vacía si no hay borrador."""
    draft = draft or draft_version()
    active = active_version()
    if draft is None or active is None:
        return []
    return compare_versions(active, draft)


@transaction.atomic
def create_draft():
    """Crea una versión en borrador copiando la activa. Solo hay un borrador a la vez."""
    existing = CatalogVersion.objects.select_for_update().filter(status="borrador").first()
    if existing:
        return existing
    active = active_version()
    if active is None:
        raise CatalogRuleError("No hay una versión activa para copiar.")
    number = (CatalogVersion.objects.aggregate(Max("number"))["number__max"] or 0) + 1
    draft = CatalogVersion.objects.create(number=number, name="Borrador", status="borrador")
    FactorVersion.objects.bulk_create(
        FactorVersion(
            version=draft,
            factor_id=value.factor_id,
            suggested_importance=value.suggested_importance,
            default_scope=value.default_scope,
        )
        for value in active.factor_values.all()
    )
    return draft


def update_draft_factor(version, factor, suggested_importance, default_scope):
    """Edita la IS (1 a 4) y el alcance por defecto de un factor de un borrador."""
    if version.status != "borrador":
        raise CatalogRuleError("Solo se puede editar una versión en borrador.")
    if suggested_importance not in ESCALA:
        raise CatalogRuleError("La importancia sugerida va de 1 a 4.")
    if default_scope not in SCOPES:
        raise CatalogRuleError("El alcance debe ser Interno o Externo.")
    value = FactorVersion.objects.get(version=version, factor=factor)
    value.suggested_importance = suggested_importance
    value.default_scope = default_scope
    value.save(update_fields=["suggested_importance", "default_scope"])
    return value


@transaction.atomic
def publish_version(version, *, justification, authorized_by, name):
    """Publica un borrador: la activa pasa a publicada y el borrador queda activo.

    Las evaluaciones existentes conservan la versión con la que se hicieron.
    """
    version = CatalogVersion.objects.select_for_update().get(pk=version.pk)
    if version.status != "borrador":
        raise CatalogRuleError("Solo se puede publicar una versión en borrador.")
    if not justification.strip() or not authorized_by.strip():
        raise CatalogRuleError("El sustento y el nombre de quien autoriza son obligatorios.")
    _demote_active()
    version.status = "activa"
    version.justification = justification.strip()
    version.authorized_by = authorized_by.strip()
    version.name = name.strip() or version.name
    version.published_at = timezone.now()
    version.save(update_fields=["status", "justification", "authorized_by", "name", "published_at"])
    return version


@transaction.atomic
def set_active_version(version):
    """Marca como activa una versión publicada; la activa anterior pasa a publicada."""
    version = CatalogVersion.objects.select_for_update().get(pk=version.pk)
    if version.status == "activa":
        return version
    if version.status != "publicada":
        raise CatalogRuleError("Solo se puede activar una versión publicada.")
    _demote_active()
    version.status = "activa"
    version.save(update_fields=["status"])
    return version


def _demote_active():
    for current in CatalogVersion.objects.select_for_update().filter(status="activa"):
        current.status = "publicada"
        current.save(update_fields=["status"])
