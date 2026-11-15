"""Suggested importance computed from AI-verified literature (doc/sugerida.pdf).

Flow: hash the corpus -> reuse a stored AI run if the hash is unchanged -> otherwise verify only the
documents without a cached verdict -> count valid citations (TC) -> thesis formulas -> store the run.
Any AI failure produces a fallback run from respaldo_is.json; nothing invalid is ever stored.
"""
import hashlib
import json
import logging
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.ai.verification import RUBRIC_VERSION, AIUnavailable, get_verifier, is_valid_score
from apps.catalog.models import Factor, Subfactor
from apps.evaluations import services as formulas

from .models import Citation, Document, DocumentAssessment, FactorImportance, ImportanceRun

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent / "data"
LITERATURE_FILE = DATA_DIR / "literatura_2020_2025.json"
FALLBACK_FILE = DATA_DIR / "respaldo_is.json"
R_PRECISION = Decimal("0.0001")


def _sha256(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


# ---------- data loading ----------

@transaction.atomic
def load_literature(path=LITERATURE_FILE):
    """Idempotent import of Table 14. Never deletes documents or citations added by an administrator."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    documents = {}
    for item in data["documents"]:
        fields = {key: item[key] for key in ("authors", "year", "title", "source", "url", "database")}
        documents[item["key"]], _ = Document.objects.update_or_create(key=item["key"], defaults=fields)
    for item in data["citations"]:
        subfactor = Subfactor.objects.get(factor__name=item["factor"], order=item["subfactor_order"])
        Citation.objects.get_or_create(document=documents[item["document"]], subfactor=subfactor)
    return len(documents), len(data["citations"])


def fallback_values():
    """Teacher-provided IS kept apart from AI results (Table 17)."""
    return json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))["values"]


# ---------- hashing ----------

def _document_payload(document):
    citations = sorted(
        (citation.subfactor.factor.name, citation.subfactor.order, citation.subfactor.pk, citation.subfactor.name)
        for citation in document.citations.all()
    )
    return {
        "key": document.key, "authors": document.authors, "year": document.year, "title": document.title,
        "source": document.source, "url": document.url,
        "citations": [{"factor": f, "order": o, "subfactor_id": i, "subfactor": n} for f, o, i, n in citations],
    }


def document_hash(document):
    return _sha256({"document": _document_payload(document), "rubric": RUBRIC_VERSION})


def _documents():
    return list(Document.objects.prefetch_related("citations__subfactor__factor").order_by("key"))


def corpus_hash(documents=None):
    documents = _documents() if documents is None else documents
    return _sha256({
        "documents": sorted(document_hash(document) for document in documents),
        "expert_importance": settings.LITERATURE_EXPERT_IMPORTANCE,
        "rubric": RUBRIC_VERSION,
    })


# ---------- computation ----------

def current_run():
    """Latest stored run for the current corpus, preferring an AI run over a fallback one."""
    runs = ImportanceRun.objects.filter(corpus_hash=corpus_hash())
    return runs.filter(origin="ia").first() or runs.first()


def _assessment_for(document, verifier):
    content_hash = document_hash(document)
    cached = DocumentAssessment.objects.filter(document=document, content_hash=content_hash, model=verifier.model).first()
    if cached:
        return cached
    payload = _document_payload(document)
    citations = [{"subfactor_id": c["subfactor_id"], "factor": c["factor"], "subfactor": c["subfactor"]} for c in payload["citations"]]
    verdict = verifier.verify(payload, citations)  # raises AIUnavailable; nothing is stored then
    return DocumentAssessment.objects.create(
        document=document,
        content_hash=content_hash,
        model=verdict.model,
        prompt=verdict.prompt,
        raw_response=verdict.raw_response,
        scores=[{"subfactor_id": s.subfactor_id, "score": s.score, "justification": s.justification} for s in verdict.scores],
        sources=[dict(source) for source in verdict.sources],
    )


def _valid_citations_per_factor(documents, assessments):
    counts = {}
    for document in documents:
        if document.pk not in assessments:
            continue
        valid = {item["subfactor_id"] for item in assessments[document.pk].scores if is_valid_score(item["score"])}
        for citation in document.citations.all():
            if citation.subfactor_id in valid:
                counts[citation.subfactor.factor_id] = counts.get(citation.subfactor.factor_id, 0) + 1
    return counts


def _factors_with_ns():
    return [(factor, factor.subfactors.count()) for factor in Factor.objects.prefetch_related("subfactors").order_by("order")]


@transaction.atomic
def _save_run(hash_, origin, rows, documents, model="", cuts=(), error=""):
    run = ImportanceRun.objects.create(
        corpus_hash=hash_, origin=origin, model=model, expert_importance=settings.LITERATURE_EXPERT_IMPORTANCE,
        cuts=[str(cut) for cut in cuts], documents=len(documents),
        citations=sum(len(document.citations.all()) for document in documents), error=error[:300],
    )
    FactorImportance.objects.bulk_create(FactorImportance(run=run, **row) for row in rows)
    return run


def _fallback_run(hash_, documents, error):
    fallback = fallback_values()
    logger.warning("Importancia sugerida: se usa el respaldo (%s).", error)
    rows = [
        {"factor": factor, "ns": ns, "value": fallback[factor.name], "fallback_value": fallback[factor.name], "origin": "respaldo"}
        for factor, ns in _factors_with_ns()
    ]
    return _save_run(hash_, "respaldo", rows, documents, error=error)


def compute(verifier=None, force=False):
    """Return the IS run for the current corpus, calling the AI only for what changed (S3, S5, S6, S8)."""
    documents = _documents()
    hash_ = corpus_hash(documents)
    existing = ImportanceRun.objects.filter(corpus_hash=hash_)
    stored_ai = existing.filter(origin="ia").first()
    if stored_ai and not force:
        return stored_ai

    try:
        verifier = verifier or get_verifier()
    except AIUnavailable as error:
        verifier, reason = None, str(error)
    else:
        reason = "disabled"
    if verifier is None:
        return existing.filter(origin="respaldo").first() or _fallback_run(hash_, documents, reason)

    try:
        # A document without citations adds nothing to TC, so it is never sent to the AI.
        assessments = {
            document.pk: _assessment_for(document, verifier) for document in documents if document.citations.all()
        }
    except AIUnavailable as error:
        return existing.filter(origin="respaldo", error=str(error)[:300]).first() or _fallback_run(hash_, documents, str(error))

    valid = _valid_citations_per_factor(documents, assessments)
    factors = _factors_with_ns()
    by_name = formulas.calcular_importancia_sugerida(
        {factor.name: (ns, valid.get(factor.pk, 0)) for factor, ns in factors},
        importancia_experto=settings.LITERATURE_EXPERT_IMPORTANCE,
    )
    cuts = formulas.cortes_cuartiles([row["r"] for row in by_name.values()])
    fallback = fallback_values()
    rows = [
        {"factor": factor, "ns": ns, "tc": by_name[factor.name]["tc"], "r": by_name[factor.name]["r"].quantize(R_PRECISION),
         "il": by_name[factor.name]["il"], "value": by_name[factor.name]["is"], "fallback_value": fallback[factor.name], "origin": "ia"}
        for factor, ns in factors
    ]
    run = _save_run(hash_, "ia", rows, documents, model=verifier.model, cuts=cuts)
    differing = [row["factor"].name for row in rows if row["value"] != row["fallback_value"]]
    if differing:
        logger.info("Importancia sugerida por IA distinta del respaldo en: %s", ", ".join(differing))
    return run


# ---------- screen helpers ----------

class DraftNotAllowed(Exception):
    pass


def latest_assessments():
    """Most recent stored verdict per document, keyed by document id (for the trace on screen)."""
    latest = {}
    for assessment in DocumentAssessment.objects.order_by("document_id", "-created_at"):
        latest.setdefault(assessment.document_id, assessment)
    return latest


def unique_key(authors, year):
    """'perez-2024' from 'Pérez et al.' + 2024, with -b, -c... when taken."""
    from django.utils.text import slugify

    surname = slugify(authors.replace(" et al.", "").split(" y ")[0].split(",")[0]).split("-")[0] or "documento"
    base = f"{surname}-{year}"
    key, suffix = base, ord("b")
    while Document.objects.filter(key=key).exists():
        key, suffix = f"{base}-{chr(suffix)}", suffix + 1
    return key


@transaction.atomic
def create_document(data, subfactors):
    document = Document.objects.create(key=unique_key(data["authors"], data["year"]), **data)
    Citation.objects.bulk_create(Citation(document=document, subfactor=subfactor) for subfactor in subfactors)
    return document


@transaction.atomic
def apply_to_draft(run):
    """Copy AI-computed IS into the catalog draft; publishing still needs justification and authorization (M02)."""
    from apps.catalog.models import FactorVersion
    from apps.management import services as catalog

    if run.origin != "ia":
        raise DraftNotAllowed("Solo se puede crear un borrador con valores calculados por la IA.")
    draft = catalog.create_draft()
    scopes = dict(FactorVersion.objects.filter(version=draft).values_list("factor_id", "default_scope"))
    for row in run.factors.select_related("factor"):
        catalog.update_draft_factor(draft, row.factor, row.value, scopes[row.factor_id])
    draft.importance_run = run
    draft.save(update_fields=["importance_run"])
    return draft
