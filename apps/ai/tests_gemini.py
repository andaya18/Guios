import io
import json
import socket
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase, override_settings

from apps.ai import gemini
from apps.ai.verification import AIUnavailable, get_verifier

DOCUMENT = {"key": "li-2022", "authors": "Li et al.", "year": 2022, "title": "Exploring factors", "source": "JSS", "url": "https://doi.org/x"}
CITATIONS = [
    {"subfactor_id": 7, "factor": "Compatibilidad", "subfactor": "El software usa formatos estándar"},
    {"subfactor_id": 9, "factor": "Prueba", "subfactor": "El software es fácil de instalar y de probar"},
]


DEFAULT_CHUNKS = [{"web": {"uri": "https://doi.org/x", "title": "doi.org"}}]


def api_body(payload_text, chunks=None):
    return json.dumps({"candidates": [{
        "content": {"parts": [{"text": payload_text}]},
        "groundingMetadata": {"groundingChunks": DEFAULT_CHUNKS if chunks is None else chunks},
    }]}).encode()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


GOOD = json.dumps({"citas": [
    {"subfactor_id": 9, "puntaje": 2, "justificacion": "Menciona la instalación."},
    {"subfactor_id": 7, "puntaje": 3, "justificacion": "Trata formatos estándar."},
]})


@override_settings(AI_PROVIDER="gemini", AI_API_KEY="test-key", AI_MODEL="gemini-test", AI_TEMPERATURE=0.0, AI_TIMEOUT_SECONDS=5)
class GeminiVerifierTests(SimpleTestCase):
    def verify(self, body=None, error=None):
        with patch("apps.ai.gemini.urlopen") as urlopen:
            if error:
                urlopen.side_effect = error
            else:
                urlopen.return_value = FakeResponse(body)
            result = get_verifier().verify(DOCUMENT, CITATIONS)
            return result, urlopen.call_args

    def test_valid_answer_is_parsed_with_sources(self):
        verdict, call = self.verify(api_body(GOOD))

        self.assertEqual([(s.subfactor_id, s.score) for s in verdict.scores], [(7, 3), (9, 2)])
        self.assertEqual(verdict.sources, ({"title": "doi.org", "uri": "https://doi.org/x"},))
        self.assertEqual(verdict.model, "gemini-test")
        request = call.args[0]
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")
        self.assertNotIn("test-key", request.full_url)
        sent = json.loads(request.data)
        self.assertEqual(sent["tools"], [{"googleSearch": {}}])
        self.assertEqual(sent["generationConfig"]["temperature"], 0.0)
        self.assertEqual(sent["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("Rúbrica", sent["contents"][0]["parts"][0]["text"])
        self.assertEqual(call.kwargs["timeout"], 5)

    def test_prompt_is_identical_for_identical_input(self):
        first, _ = self.verify(api_body(GOOD))
        second, _ = self.verify(api_body(GOOD))

        self.assertEqual(first.prompt, second.prompt)

    def test_errors_are_mapped(self):
        cases = [
            (HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b"{}")), "quota"),
            (HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b"{}")), "auth"),
            (HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b"{}")), "auth"),
            (HTTPError("u", 500, "Server Error", {}, io.BytesIO(b"{}")), "network"),
            (socket.timeout("timed out"), "timeout"),
            (URLError("down"), "network"),
        ]
        for error, kind in cases:
            with self.subTest(kind=kind), self.assertRaises(AIUnavailable) as raised:
                self.verify(error=error)
            self.assertEqual(raised.exception.kind, kind)

    def test_invalid_answers_are_rejected(self):
        bad_payloads = [
            "no es json",
            json.dumps({"citas": [{"subfactor_id": 7, "puntaje": 5, "justificacion": "x"}, {"subfactor_id": 9, "puntaje": 2, "justificacion": "y"}]}),
            json.dumps({"citas": [{"subfactor_id": 7, "puntaje": 3, "justificacion": "x"}]}),
            json.dumps({"citas": [{"subfactor_id": 7, "puntaje": "3", "justificacion": "x"}, {"subfactor_id": 9, "puntaje": 2, "justificacion": "y"}]}),
            json.dumps({"citas": [{"subfactor_id": 7, "puntaje": 3, "justificacion": ""}, {"subfactor_id": 9, "puntaje": 2, "justificacion": "y"}]}),
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload[:30]), self.assertRaises(AIUnavailable) as raised:
                self.verify(api_body(payload))
            self.assertEqual(raised.exception.kind, "invalid_response")

    def test_answer_without_web_search_is_a_search_failure(self):
        with self.assertRaises(AIUnavailable) as raised:
            self.verify(api_body(GOOD, chunks=[]))

        self.assertEqual(raised.exception.kind, "network")

    def test_blocked_or_empty_candidates_are_invalid(self):
        with self.assertRaises(AIUnavailable) as raised:
            self.verify(json.dumps({"candidates": []}).encode())

        self.assertEqual(raised.exception.kind, "invalid_response")


class ProviderSelectionTests(SimpleTestCase):
    @override_settings(AI_PROVIDER="gemini", AI_API_KEY="")
    def test_without_key_there_is_no_verifier(self):
        self.assertIsNone(get_verifier())

    @override_settings(AI_PROVIDER="otro", AI_API_KEY="k")
    def test_unknown_provider_is_reported(self):
        with self.assertRaises(AIUnavailable):
            get_verifier()

    @override_settings(AI_PROVIDER="gemini", AI_API_KEY="k", AI_MODEL="")
    def test_default_model_is_used_when_unset(self):
        self.assertEqual(get_verifier().model, gemini.DEFAULT_MODEL)
