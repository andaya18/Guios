"""Provider-agnostic contract for verifying literature citations with an AI model.

A verifier reads one document and the subfactors it is cited for, searches the web, and scores
each citation with the rubric below. It never computes IL or IS: apps.evaluations.services does.
"""
from dataclasses import dataclass, field
from typing import Protocol

from django.conf import settings

RUBRIC_VERSION = "2026-11-rubrica-4-leer-primero"
VALID_MIN_SCORE = 2  # citations scored 2 or 3 count for TC
SCORES = (0, 1, 2, 3)
MAX_JUSTIFICATION = 400
MAX_SCORE = max(SCORES)


def is_valid_score(score):
    """Single definition of a citation that counts for TC."""
    return score >= VALID_MIN_SCORE

RUBRIC = """Rúbrica de relevancia de cada cita (puntaje entero de 0 a 3):
3 = El documento existe, se publicó entre 2020 y 2025, tiene revisión por pares, trata la adopción
    organizacional de software y aborda de forma explícita el subfactor indicado.
2 = Igual que 3, pero menciona el factor o un subfactor equivalente y no exactamente el indicado.
1 = El documento existe, pero no cumple algún criterio de inclusión (fuera de 2020-2025, sin revisión
    por pares, o no trata la adopción organizacional de software ni el factor).
0 = No se pudo encontrar el documento con los datos dados, o los datos no coinciden (título, DOI o año).
Criterios de exclusión: publicaciones sin revisión por pares, entradas de blog y trabajos que no traten
la adopción organizacional de software."""


class AIUnavailable(Exception):
    """The AI could not produce a usable answer; callers fall back without saving anything invalid."""

    KINDS = ("disabled", "timeout", "quota", "auth", "network", "invalid_response")

    def __init__(self, kind, detail=""):
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}" if detail else kind)


@dataclass(frozen=True)
class CitationScore:
    subfactor_id: int
    score: int
    justification: str

    @property
    def is_valid(self):
        return is_valid_score(self.score)


@dataclass(frozen=True)
class DocumentVerdict:
    model: str
    prompt: str
    raw_response: str
    scores: tuple
    sources: tuple = field(default_factory=tuple)  # ({"title": ..., "uri": ...}, ...)


class CitationVerifier(Protocol):
    model: str

    def verify(self, document: dict, citations: list) -> DocumentVerdict:
        """document: plain dict; citations: [{"subfactor_id", "factor", "subfactor"}]. Raises AIUnavailable."""


def validate_scores(payload, citations):
    """Strict check of the model's JSON: every citation exactly once, integer score 0-3, short justification."""
    if not isinstance(payload, dict) or not isinstance(payload.get("citas"), list):
        raise AIUnavailable("invalid_response", "falta la lista 'citas'")
    expected = {citation["subfactor_id"] for citation in citations}
    scores = {}
    for item in payload["citas"]:
        if not isinstance(item, dict):
            raise AIUnavailable("invalid_response", "cada cita debe ser un objeto")
        subfactor_id, score, text = item.get("subfactor_id"), item.get("puntaje"), item.get("justificacion")
        if isinstance(score, bool) or not isinstance(score, int) or score not in SCORES:
            raise AIUnavailable("invalid_response", f"puntaje fuera de rango: {score!r}")
        if not isinstance(text, str) or not text.strip():
            raise AIUnavailable("invalid_response", "justificación vacía")
        if subfactor_id not in expected or subfactor_id in scores:
            raise AIUnavailable("invalid_response", f"subfactor inesperado o repetido: {subfactor_id!r}")
        scores[subfactor_id] = CitationScore(subfactor_id, score, text.strip()[:MAX_JUSTIFICATION])
    if set(scores) != expected:
        raise AIUnavailable("invalid_response", "faltan citas en la respuesta")
    return tuple(scores[key] for key in sorted(scores))


_REGISTRY = {}


def register(name, factory):
    _REGISTRY[name] = factory


def get_verifier():
    """Configured verifier, or None when AI is disabled or has no key (the caller uses the fallback)."""
    name = settings.AI_PROVIDER
    if name == "disabled" or not settings.AI_API_KEY:
        return None
    if name not in _REGISTRY:
        from . import gemini  # noqa: F401  registers the built-in provider

    factory = _REGISTRY.get(name)
    if factory is None:
        raise AIUnavailable("disabled", f"proveedor de IA desconocido: {name}")
    return factory()
