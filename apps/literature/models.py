"""Literature evidence (documents and citations) and the audited computation of suggested importance."""
from django.db import models

from apps.catalog.models import Factor, Subfactor

ORIGINS = [("ia", "IA"), ("respaldo", "Respaldo")]


class Document(models.Model):
    key = models.SlugField(max_length=60, unique=True)
    authors = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=400)
    source = models.CharField(max_length=300, blank=True)
    url = models.URLField(max_length=300, blank=True)
    database = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["authors", "year"]

    def __str__(self):
        return f"{self.authors} ({self.year})"


class Citation(models.Model):
    """One document supporting one subfactor (the counting rule of the thesis)."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="citations")
    subfactor = models.ForeignKey(Subfactor, on_delete=models.PROTECT, related_name="citations")

    class Meta:
        ordering = ["subfactor__factor__order", "subfactor__order"]
        constraints = [models.UniqueConstraint(fields=["document", "subfactor"], name="unique_citation")]

    def __str__(self):
        return f"{self.document} → {self.subfactor}"


class DocumentAssessment(models.Model):
    """Cached AI verdict for one exact version of a document and its citations (content_hash)."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="assessments")
    content_hash = models.CharField(max_length=64)
    model = models.CharField(max_length=80)
    prompt = models.TextField()
    raw_response = models.TextField()
    scores = models.JSONField()  # [{"subfactor_id", "score", "justification"}]
    sources = models.JSONField(default=list)  # [{"title", "uri"}] consulted by the model
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["document", "content_hash", "model"], name="unique_assessment"),
        ]


class ImportanceRun(models.Model):
    """One computation of the 18 IS values for a given corpus hash."""

    corpus_hash = models.CharField(max_length=64, db_index=True)
    origin = models.CharField(max_length=10, choices=ORIGINS)
    model = models.CharField(max_length=80, blank=True)
    expert_importance = models.PositiveSmallIntegerField()
    cuts = models.JSONField(default=list)  # [rq1, rq2, rq3, rq4] as strings
    documents = models.PositiveSmallIntegerField(default=0)
    citations = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.get_origin_display()} · {self.created_at:%Y-%m-%d %H:%M}"


class FactorImportance(models.Model):
    run = models.ForeignKey(ImportanceRun, on_delete=models.CASCADE, related_name="factors")
    factor = models.ForeignKey(Factor, on_delete=models.PROTECT)
    ns = models.PositiveSmallIntegerField()
    tc = models.PositiveSmallIntegerField(null=True, blank=True)
    r = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    il = models.PositiveSmallIntegerField(null=True, blank=True)
    value = models.PositiveSmallIntegerField()
    fallback_value = models.PositiveSmallIntegerField()
    origin = models.CharField(max_length=10, choices=ORIGINS)

    class Meta:
        ordering = ["factor__order"]
        constraints = [models.UniqueConstraint(fields=["run", "factor"], name="unique_run_factor")]

    @property
    def differs_from_fallback(self):
        return self.origin == "ia" and self.value != self.fallback_value
