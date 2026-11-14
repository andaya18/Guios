"""Consultas de lectura del área de administración (listados y conteos)."""
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Count, Q

from apps.accounts.models import Organization, User
from apps.catalog.models import CatalogVersion, Dimension, Factor, Subfactor

from . import services

USER_TABS = {"activos": True, "desactivados": False}
ORGANIZATION_TABS = {"todas": None, "activas": True, "inactivas": False}


def _evaluations_count_by(field, **filters):
    """Conteo de evaluaciones agrupado por `field`.

    El modelo Evaluation llega con la tarea T4; mientras no exista (o no tenga
    el campo), los conteos quedan en cero en lugar de romper la pantalla.
    """
    try:
        model = apps.get_model("evaluations", "Evaluation")
        model._meta.get_field(field)
    except (LookupError, FieldDoesNotExist):
        return {}
    column = f"{field}_id"
    rows = model.objects.filter(**filters).values(column).annotate(total=Count("id"))
    return {row[column]: row["total"] for row in rows}


def evaluations_by_version():
    return _evaluations_count_by("catalog_version")


def evaluations_by_organization():
    return _evaluations_count_by("organization", status="finalizada")


def catalog_counts():
    return {
        "dimensions": Dimension.objects.count(),
        "factors": Factor.objects.count(),
        "subfactors": Subfactor.objects.count(),
    }


def admin_dashboard():
    """Datos de AD01: usuarios, estado del catálogo y organizaciones."""
    users = User.objects.aggregate(
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    organizations = Organization.objects.aggregate(
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        public=Count("id", filter=Q(is_active=True, sector="publico")),
        private=Count("id", filter=Q(is_active=True, sector="privado")),
    )
    draft = services.draft_version()
    return {
        "users_active": users["active"],
        "users_inactive": users["inactive"],
        "organizations_active": organizations["active"],
        "organizations_inactive": organizations["inactive"],
        "organizations_public": organizations["public"],
        "organizations_private": organizations["private"],
        "active_version": services.active_version(),
        "draft": draft,
        "draft_changes": len(services.draft_changes(draft)) if draft else 0,
        **catalog_counts(),
    }


def user_tab_counts():
    return User.objects.aggregate(
        activos=Count("id", filter=Q(is_active=True)),
        desactivados=Count("id", filter=Q(is_active=False)),
    )


def filter_users(*, tab="activos", query="", role="", organization=""):
    users = User.objects.select_related("organization").filter(is_active=USER_TABS.get(tab, True))
    if query:
        users = users.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query)
        )
    if role:
        users = users.filter(role=role)
    if organization.isdigit():
        users = users.filter(organization_id=int(organization))
    return users.order_by("first_name", "last_name", "email")


def organization_tab_counts():
    return Organization.objects.aggregate(
        todas=Count("id"),
        activas=Count("id", filter=Q(is_active=True)),
        inactivas=Count("id", filter=Q(is_active=False)),
    )


def filter_organizations(*, tab="todas", query="", sector=""):
    organizations = Organization.objects.annotate(user_count=Count("users"))
    is_active = ORGANIZATION_TABS.get(tab)
    if is_active is not None:
        organizations = organizations.filter(is_active=is_active)
    if query:
        organizations = organizations.filter(name__icontains=query)
    if sector:
        organizations = organizations.filter(sector=sector)
    evaluations = evaluations_by_organization()
    result = list(organizations.order_by("name"))
    for organization in result:
        organization.evaluation_count = evaluations.get(organization.pk, 0)
    return result


def versions_overview():
    """Versiones para M03 (más reciente primero) con cambios frente a la anterior."""
    evaluations = evaluations_by_version()
    versions = list(CatalogVersion.objects.select_related("published_by").order_by("-number"))
    for version in versions:
        previous = services.previous_version(version)
        version.changed_factors = (
            len({change.factor for change in services.compare_versions(previous, version)})
            if previous else None
        )
        version.previous = previous
        version.evaluation_count = evaluations.get(version.pk, 0)
    return versions
