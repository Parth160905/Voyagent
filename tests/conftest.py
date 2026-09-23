import os

import pytest

# Dummy keys so modules that read env vars at import time don't crash in CI.
# Set before anything imports dotenv, so local .env keys are never used in tests.
for key in [
    "DUFFEL_API_KEY", "DUFFEL_ACCESS_TOKEN", "GOOGLE_PLACES_API_KEY",
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
]:
    os.environ.setdefault(key, "test-key")


class NetworkBlocked(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if any test tries to hit a real API."""
    def blocked(*args, **kwargs):
        raise NetworkBlocked("Tests must not make real network calls")

    import httpx
    import requests

    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)
