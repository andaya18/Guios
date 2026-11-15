from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db import models


class CatalogVersion(models.Model):
    ESTADOS = [("borrador", "Borrador"), ("activa", "Activa"), ("publicada", "Publicada")]

    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=ESTADOS, default="borrador")
    justification = models.TextField(blank=True)
    authorized_by = models.CharField(max_length=150, blank=True)
    # Date the methodological authority approved the change; may precede the publication (M02).
    authorized_at = models.DateField(null=True, blank=True)
    # AI computation this version's IS came from; empty for versions loaded from the thesis/teacher tables.
    importance_run = models.ForeignKey(
        "literature.ImportanceRun", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    # Quién publicó la versión; vacío en las creadas por cargar_catalogo (se muestra como "Sistema").
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["status"],
                condition=models.Q(status="activa"),
                name="catalog_single_active_version",
            ),
        ]

    def __str__(self):
        return f"v{self.number} · {self.name}"


class Dimension(models.Model):
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Factor(models.Model):
    dimension = models.ForeignKey(Dimension, on_delete=models.PROTECT, related_name="factors")
    name = models.CharField(max_length=150)
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class Subfactor(models.Model):
    factor = models.ForeignKey(Factor, on_delete=models.PROTECT, related_name="subfactors")
    name = models.CharField(max_length=300)
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["factor__order", "order"]

    def __str__(self):
        return self.name


class FactorVersion(models.Model):
    ALCANCES = [("interno", "Interno"), ("externo", "Externo")]

    version = models.ForeignKey(
        CatalogVersion, on_delete=models.CASCADE, related_name="factor_values"
    )
    factor = models.ForeignKey(Factor, on_delete=models.PROTECT)
    suggested_importance = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    default_scope = models.CharField(max_length=7, choices=ALCANCES)

    class Meta:
        unique_together = ("version", "factor")
        ordering = ["version__number", "factor__order"]

    def __str__(self):
        return f"v{self.version.number} · {self.factor} (IS {self.suggested_importance})"
