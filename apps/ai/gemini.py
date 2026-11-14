"""Gemini citation verifier: Google Search grounding + strict JSON output, stdlib HTTP only.

Configuration (environment variables): AI_PROVIDER=gemini, AI_API_KEY, AI_MODEL, AI_TEMPERATURE,
AI_TIMEOUT_SECONDS. The key travels in the x-goog-api-key header, never in the URL or the logs.
"""
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .verification import RUBRIC, AIUnavailable, DocumentVerdict, register, validate_scores

DEFAULT_MODEL = "gemini-3-flash-preview"  # Gemini 3+ is required to combine search with JSON output
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


def build_prompt(document, citations):
    """Deterministic prompt: same document and citations always give the same text."""
    lines = [
        "Eres un revisor de literatura científica sobre adopción de software libre (FLOSS).",
        "Busca en internet el documento indicado y evalúa si respalda cada subfactor listado.",
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


class GeminiVerifier:
    def __init__(self, api_key, model, temperature, timeout):
        self._api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.temperature = temperature
        self.timeout = timeout

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
        prompt = build_prompt(document, citations)
        raw = self._post({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"googleSearch": {}}],
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
        chunks = (candidate.get("groundingMetadata") or {}).get("groundingChunks") or []
        sources = tuple(
            {"title": chunk["web"].get("title", ""), "uri": chunk["web"].get("uri", "")}
            for chunk in chunks if isinstance(chunk, dict) and chunk.get("web")
        )
        if not sources:
            # The rubric needs evidence from the web; an answer without search is not trusted.
            raise AIUnavailable("network", "la búsqueda web no devolvió fuentes")
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
))
