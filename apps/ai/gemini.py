"""Gemini citation verifier: reads each document on the web + strict JSON output, stdlib HTTP only.

Configuration (environment variables): AI_PROVIDER=gemini, AI_API_KEY, AI_MODEL, AI_TEMPERATURE,
AI_TIMEOUT_SECONDS, AI_GROUNDING. The key travels in the x-goog-api-key header, never in the URL or logs.

AI_GROUNDING="url" (default) reads the document's own DOI/link page with the urlContext tool, which the
free tier allows. AI_GROUNDING="search" uses Google Search grounding, which needs a billed project.
"""
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .verification import RUBRIC, AIUnavailable, DocumentVerdict, register, validate_scores

DEFAULT_MODEL = "gemini-3-flash-preview"  # Gemini 3+ is required to combine web tools with JSON output
GROUNDING_TOOLS = {"url": "urlContext", "search": "googleSearch"}
URL_SUCCESS = "URL_RETRIEVAL_STATUS_SUCCESS"
DOI_PREFIX = "https://doi.org/"
# Without this, long prompts get answered from memory and come back with no pages read (seen with real calls).
READ_FIRST = (
    "Antes de responder, usa la herramienta de lectura de URL para abrir TODAS las páginas indicadas; "
    "no respondas de memoria."
)
# Open scholarly records of a DOI: publishers often block automated reads of the article page.
OPEN_METADATA = (
    "https://api.openalex.org/works/doi:{doi}",
    "https://api.crossref.org/works/{doi}",
    "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,year,venue,abstract,publicationTypes",
)


def reading_urls(url):
    """Pages the model reads for a document: the link itself plus open metadata records for a DOI."""
    if url.startswith(DOI_PREFIX):
        doi = url[len(DOI_PREFIX):]
        return [url] + [template.format(doi=doi) for template in OPEN_METADATA]
    return [url]
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "citas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subfactor_id": {"type": "integer"},
                    "puntaje": {"type": "integer", "enum": [0, 1, 2, 3]},
                    "justificacion": {"type": "string", "description": "Una o dos frases."},
                },
                "required": ["subfactor_id", "puntaje", "justificacion"],
            },
        }
    },
    "required": ["citas"],
}


def build_prompt(document, citations, grounding="url"):
    """Deterministic prompt: same document, citations and grounding always give the same text."""
    if grounding == "url":
        pages = " ".join(reading_urls(document.get("url", "")))
        action = (
            f"Lee estas páginas del documento (artículo y registros académicos abiertos): {pages} . "
            "Con lo que puedas leer, evalúa si el documento respalda cada subfactor listado."
        )
    else:
        action = "Busca en internet el documento indicado y evalúa si respalda cada subfactor listado."
    lines = [
        *([READ_FIRST, ""] if grounding == "url" else []),
        "Eres un revisor de literatura científica sobre adopción de software libre (FLOSS).",
        action,
        "",
        RUBRIC,
        "",
        "Documento:",
        f"- Autores: {document['authors']}",
        f"- Año: {document['year']}",
        f"- Título: {document['title']}",
        f"- Fuente: {document.get('source', '')}",
        f"- DOI o enlace: {document.get('url', '')}",
        "",
        "Citas a evaluar (una por subfactor):",
    ]
    for citation in sorted(citations, key=lambda item: item["subfactor_id"]):
        lines.append(f"- subfactor_id {citation['subfactor_id']} · factor «{citation['factor']}» · subfactor «{citation['subfactor']}»")
    lines += [
        "",
        "Responde solo con JSON que cumpla el esquema: una entrada por cada subfactor_id listado, con",
        "puntaje entero de 0 a 3 según la rúbrica y una justificación breve en español.",
    ]
    return "\n".join(lines)


def _sources(candidate):
    """Pages the model actually read (urlContext) plus search results (googleSearch)."""
    read = [
        {"title": "Página leída", "uri": item.get("retrievedUrl", "")}
        for item in (candidate.get("urlContextMetadata") or {}).get("urlMetadata") or []
        if isinstance(item, dict) and item.get("urlRetrievalStatus") == URL_SUCCESS
    ]
    found = [
        {"title": chunk["web"].get("title", ""), "uri": chunk["web"].get("uri", "")}
        for chunk in (candidate.get("groundingMetadata") or {}).get("groundingChunks") or []
        if isinstance(chunk, dict) and chunk.get("web")
    ]
    return tuple(read + found)


class GeminiVerifier:
    def __init__(self, api_key, model, temperature, timeout, grounding="url"):
        self._api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.temperature = temperature
        self.timeout = timeout
        self.grounding = grounding if grounding in GROUNDING_TOOLS else "url"

    def _post(self, body):
        request = Request(
            ENDPOINT.format(model=self.model),
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as error:
            if error.code == 429:
                raise AIUnavailable("quota", "límite de la API alcanzado") from None
            if error.code in (401, 403):
                raise AIUnavailable("auth", "clave de API inválida o sin permisos") from None
            raise AIUnavailable("network", f"HTTP {error.code}") from None
        except (socket.timeout, TimeoutError):
            raise AIUnavailable("timeout", f"sin respuesta en {self.timeout} s") from None
        except URLError as error:
            raise AIUnavailable("network", str(error.reason)) from None

    def verify(self, document, citations):
        if self.grounding == "url" and not document.get("url"):
            raise AIUnavailable("network", "el documento no tiene DOI ni enlace para leerlo")
        prompt = build_prompt(document, citations, self.grounding)
        raw = self._post({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{GROUNDING_TOOLS[self.grounding]: {}}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
                "responseJsonSchema": RESPONSE_SCHEMA,
            },
        })
        try:
            candidate = json.loads(raw)["candidates"][0]
            text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
            payload = json.loads(text)
        except (ValueError, KeyError, IndexError, TypeError):
            raise AIUnavailable("invalid_response", "la respuesta no es JSON válido") from None
        sources = _sources(candidate)
        if not sources:
            # The rubric needs evidence from the web; an answer that read nothing is not trusted.
            raise AIUnavailable("network", "no se pudo leer el documento en la web")
        return DocumentVerdict(
            model=self.model,
            prompt=prompt,
            raw_response=text,
            scores=validate_scores(payload, citations),
            sources=sources,
        )


register("gemini", lambda: GeminiVerifier(
    api_key=settings.AI_API_KEY,
    model=settings.AI_MODEL,
    temperature=settings.AI_TEMPERATURE,
    timeout=settings.AI_TIMEOUT_SECONDS,
    grounding=settings.AI_GROUNDING,
))
