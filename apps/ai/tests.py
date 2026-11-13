from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from apps.ai import providers


class FakeProvider:
    def __init__(self, api_key, model, timeout):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def suggest(self, request):
        return providers.Suggestion(text=f"{request.software}: ok")


class ProviderSelectionTests(SimpleTestCase):
    def test_disabled_by_default_returns_no_suggestion(self):
        provider = providers.get_provider()

        self.assertFalse(providers.is_enabled())
        self.assertIsNone(provider.suggest(providers.SuggestionRequest(software="X", factors=[])))

    @override_settings(AI_PROVIDER="fake", AI_API_KEY="")
    def test_provider_without_key_stays_disabled(self):
        self.assertIsInstance(providers.get_provider(), providers.DisabledProvider)

    @override_settings(AI_PROVIDER="desconocido", AI_API_KEY="k")
    def test_unknown_provider_is_a_configuration_error(self):
        with self.assertRaises(ImproperlyConfigured):
            providers.get_provider()

    @override_settings(AI_PROVIDER="fake", AI_API_KEY="secret", AI_MODEL="m1", AI_TIMEOUT_SECONDS=5)
    def test_registered_provider_receives_settings(self):
        providers.register("fake", FakeProvider)
        try:
            provider = providers.get_provider()
            self.assertTrue(providers.is_enabled())
            self.assertEqual((provider.api_key, provider.model, provider.timeout), ("secret", "m1", 5))
            self.assertEqual(provider.suggest(providers.SuggestionRequest(software="Odoo", factors=[])).text, "Odoo: ok")
        finally:
            providers.unregister("fake")
