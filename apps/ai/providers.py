"""Pluggable AI suggestion providers.

AI only produces advisory text. It never computes IR, PM, FODA or the A/B/C recommendation:
those stay in apps.evaluations.services so every result remains reproducible (§4).
To add a real provider, implement ``SuggestionProvider`` and call ``register(name, cls)``.
"""
from dataclasses import dataclass, field
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class SuggestionRequest:
    software: str
    factors: list = field(default_factory=list)  # plain dicts: name, scope, ir, pm, foda
    recommendation: str = ""


@dataclass(frozen=True)
class Suggestion:
    text: str


class SuggestionProvider(Protocol):
    def suggest(self, request: SuggestionRequest) -> Suggestion | None: ...


class DisabledProvider:
    """Default when no provider or API key is configured: the feature is simply absent."""

    def suggest(self, request):
        return None


_REGISTRY = {}


def register(name, provider_class):
    _REGISTRY[name] = provider_class


def unregister(name):
    _REGISTRY.pop(name, None)


def get_provider():
    name = settings.AI_PROVIDER
    if name == "disabled" or not settings.AI_API_KEY:
        return DisabledProvider()
    if name not in _REGISTRY:
        raise ImproperlyConfigured(f"AI_PROVIDER '{name}' is not registered in apps.ai.providers.")
    return _REGISTRY[name](
        api_key=settings.AI_API_KEY,
        model=settings.AI_MODEL,
        timeout=settings.AI_TIMEOUT_SECONDS,
    )


def is_enabled():
    return not isinstance(get_provider(), DisabledProvider)
