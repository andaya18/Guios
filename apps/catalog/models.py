from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class CatalogVersion(models.Model):
    ESTADOS = [("borrador", "Borrador"), ("activa", "Activa"), ("publicada", "Publicada")]

    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=ESTADOS, default="borrador")
    justification = models.TextField(blank=True)
    authorized_by = models.CharField(max_length=150, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

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
