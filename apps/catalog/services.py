import json
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from .models import CatalogVersion, Dimension, Factor, FactorVersion, Subfactor

DATA_DIR = Path(__file__).resolve().parent / "data"

EXPECTED_DIMENSIONS = 3
EXPECTED_FACTORS = 18
EXPECTED_SUBFACTORS = 61
EXPECTED_FACTOR_VERSIONS = 36
EXPECTED_CHANGED_IMPORTANCE = 6

VALID_SCOPES = {value for value, _ in FactorVersion.ALCANCES}
VALID_STATUSES = {value for value, _ in CatalogVersion.ESTADOS}


class CatalogDataError(Exception):
    """El catálogo cargado no cumple las verificaciones de la sección 5.3."""


def read_json(filename, data_dir=DATA_DIR):
    with open(Path(data_dir) / filename, encoding="utf-8") as handle:
        return json.load(handle)


def _validate_importance(factor_names, versions):
    for version in versions:
        importances = version["suggested_importance"]
        if set(importances) != set(factor_names):
            raise CatalogDataError(
                f"La versión {version['number']} no define la IS de los 18 factores."
            )
        if any(not 1 <= value <= 4 for value in importances.values()):
            raise CatalogDataError(
                f"La versión {version['number']} tiene una IS fuera del rango 1 a 4."
            )
        if version["status"] not in VALID_STATUSES:
            raise CatalogDataError(f"Estado inválido en la versión {version['number']}.")


def _load_structure(catalog):
    factors = []
    subfactor_count = 0
    factor_order = 0
    for dimension_data in catalog["dimensions"]:
        dimension, _ = Dimension.objects.get_or_create(name=dimension_data["name"])
        for factor_data in dimension_data["factors"]:
            factor_order += 1
            if factor_data["default_scope"] not in VALID_SCOPES:
                raise CatalogDataError(
                    f"Alcance inválido en el factor {factor_data['name']}."
                )
            factor, _ = Factor.objects.update_or_create(
                dimension=dimension,
                name=factor_data["name"],
                defaults={"order": factor_order},
            )
            factors.append((factor, factor_data["default_scope"]))
            for position, text in enumerate(factor_data["subfactors"], start=1):
                Subfactor.objects.update_or_create(
                    factor=factor, order=position, defaults={"name": text}
                )
                subfactor_count += 1
    return factors, subfactor_count


def _load_versions(versions, factors):
    """Crea cada versión y sus FactorVersion una sola vez.

    Las versiones ya existentes no se tocan: pueden haber sido publicadas o
    editadas desde el panel, y solo una puede estar activa.
    """
    now = timezone.now()
    for version_data in versions:
        version, created = CatalogVersion.objects.get_or_create(
            number=version_data["number"],
            defaults={
                "name": version_data["name"],
                "status": version_data["status"],
                "justification": version_data["justification"],
                "published_at": now,
            },
        )
        for factor, default_scope in factors:
            FactorVersion.objects.get_or_create(
                version=version,
                factor=factor,
                defaults={
                    "suggested_importance": version_data["suggested_importance"][factor.name],
                    "default_scope": default_scope,
                },
            )


def verify_catalog(numbers, factor_count, subfactor_count, dimension_count):
    """Verificaciones finales de la sección 5.3."""
    factor_versions = FactorVersion.objects.filter(version__number__in=numbers)
    importance = {}
    for number, factor_id, value in factor_versions.values_list(
        "version__number", "factor_id", "suggested_importance"
    ):
        importance.setdefault(factor_id, {})[number] = value
    changed = sum(1 for values in importance.values() if len(set(values.values())) > 1)

    checks = [
        ("dimensiones", dimension_count, EXPECTED_DIMENSIONS),
        ("factores", factor_count, EXPECTED_FACTORS),
        ("subfactores", subfactor_count, EXPECTED_SUBFACTORS),
        ("FactorVersion", factor_versions.count(), EXPECTED_FACTOR_VERSIONS),
        ("factores con IS distinta", changed, EXPECTED_CHANGED_IMPORTANCE),
        (
            "versiones activas",
            CatalogVersion.objects.filter(status="activa").count(),
            1,
        ),
    ]
    for label, found, expected in checks:
        if found != expected:
            raise CatalogDataError(f"{label}: se esperaban {expected} y hay {found}.")


@transaction.atomic
def load_catalog(data_dir=DATA_DIR):
    """Carga el catálogo inicial (§5.3). Es idempotente y atómica."""
    catalog = read_json("catalogo.json", data_dir)
    versions = read_json("versiones.json", data_dir)["versions"]
    _validate_importance(
        [factor["name"] for dim in catalog["dimensions"] for factor in dim["factors"]],
        versions,
    )
    factors, subfactor_count = _load_structure(catalog)
    _load_versions(versions, factors)
    verify_catalog(
        [version["number"] for version in versions],
        factor_count=len(factors),
        subfactor_count=subfactor_count,
        dimension_count=len(catalog["dimensions"]),
    )
    return {
        "dimensions": len(catalog["dimensions"]),
        "factors": len(factors),
        "subfactors": subfactor_count,
        "versions": len(versions),
    }
