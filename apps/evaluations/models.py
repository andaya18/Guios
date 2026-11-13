"""Evaluation data (§5, §5.1). Orchestration lives in workflow.py, math in services.py."""
from django.conf import settings
from django.db import models

from apps.accounts.models import Organization
from apps.catalog.models import CatalogVersion, Factor, Subfactor


class Software(models.Model):
    LICENCIAS = [
        ("libre", "Libre o de código abierto"),
        ("propietario", "Propietario"),
        ("otro", "Otro o no sé"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    version = models.CharField(max_length=50, blank=True)
    license_type = models.CharField(max_length=12, choices=LICENCIAS)

    class Meta:
        unique_together = ("organization", "name", "version")
        ordering = ["name", "version"]

    def __str__(self):
        return f"{self.name} {self.version}".strip()


class Evaluation(models.Model):
    ESTADOS = [("borrador", "Borrador"), ("finalizada", "Finalizada")]

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    software = models.ForeignKey(Software, on_delete=models.PROTECT)
    catalog_version = models.ForeignKey(CatalogVersion, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=ESTADOS, default="borrador")
    current_step = models.PositiveSmallIntegerField(default=1)  # etapa 1, 2 o 3
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    recommendation = models.CharField(max_length=1, blank=True)  # "A", "B" o "C"
    duplicated_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.software} · {self.get_status_display()}"

    def get_absolute_url(self):
        return f"/historial/{self.pk}/"

    @property
    def is_finalized(self):
        return self.status == "finalizada"

    def save(self, *args, **kwargs):
        # queryset.update() bypasses this guard: never use it on evaluations (§5.2).
        if self.pk:
            previous = (
                Evaluation.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous == "finalizada":
                raise PermissionError("Una evaluación finalizada no se puede modificar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == "finalizada":
            raise PermissionError("Solo se pueden eliminar borradores.")
        return super().delete(*args, **kwargs)


class EvaluationFactor(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="factors")
    factor = models.ForeignKey(Factor, on_delete=models.PROTECT)
    decision_importance = models.PositiveSmallIntegerField(null=True, blank=True)  # ID 1..4
    suggested_importance = models.PositiveSmallIntegerField()  # copia de la IS usada
    relative_importance = models.PositiveSmallIntegerField(null=True, blank=True)  # IR
    scope = models.CharField(max_length=7)  # "interno" | "externo"
    is_relevant = models.BooleanField(default=False)
    pm = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    foda = models.CharField(max_length=12, blank=True)

    class Meta:
        unique_together = ("evaluation", "factor")
        ordering = ["factor__order"]

    def __str__(self):
        return f"{self.evaluation_id} · {self.factor}"


class EvaluationSubfactor(models.Model):
    evaluation_factor = models.ForeignKey(
        EvaluationFactor, on_delete=models.CASCADE, related_name="answers"
    )
    subfactor = models.ForeignKey(Subfactor, on_delete=models.PROTECT)
    value = models.PositiveSmallIntegerField(null=True, blank=True)  # 1..4

    class Meta:
        unique_together = ("evaluation_factor", "subfactor")
        ordering = ["subfactor__order"]

    def __str__(self):
        return f"{self.subfactor} = {self.value or '-'}"
