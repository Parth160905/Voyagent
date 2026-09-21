"""
Currency conversion using free ECB reference rates from Frankfurter
(no API key needed). If the live call fails, it falls back to rough
built-in rates so the planner never breaks because of FX.
"""

import json
import logging
import ssl
import time
import urllib.request

try:
    import certifi  # fixes SSL certificate errors on some macOS Python installs
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest?base=USD"
# Some APIs block Python's default "Python-urllib" user agent, so send our own.
HEADERS = {"User-Agent": "Voyagent/1.0 (+https://github.com/Parth160905/Voyagent)"}
LIVE_TTL_SECONDS = 6 * 60 * 60   # reuse live rates for 6 hours
RETRY_AFTER_SECONDS = 10 * 60    # after a failure, retry in 10 minutes

# Rough fallback: units of each currency per 1 USD. Only used if the live call fails.
FALLBACK_RATES = {"USD": 1.0, "EUR": 0.88, "GBP": 0.75, "INR": 88.0}

logger = logging.getLogger(__name__)

_cache = {"rates": None, "source": None, "expires": 0.0}


def get_usd_rates():
    """Return (rates, source). rates = units of each currency per 1 USD."""
    now = time.time()
    if _cache["rates"] is not None and now < _cache["expires"]:
        return _cache["rates"], _cache["source"]
    try:
        request = urllib.request.Request(FRANKFURTER_URL, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=5, context=_SSL_CONTEXT) as resp:
            data = json.load(resp)
        rates = {code.upper(): float(value) for code, value in data["rates"].items()}
        rates["USD"] = 1.0
        _cache.update(rates=rates, source="live", expires=now + LIVE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Live FX rates unavailable, using fallback rates: %r", exc)
        _cache.update(rates=dict(FALLBACK_RATES), source="fallback",
                      expires=now + RETRY_AFTER_SECONDS)
    return _cache["rates"], _cache["source"]


def convert(amount, from_ccy, to_ccy):
    """Convert amount between currencies. Raises KeyError for unknown codes."""
    from_ccy, to_ccy = from_ccy.upper(), to_ccy.upper()
    if from_ccy == to_ccy:
        return amount
    rates, _ = get_usd_rates()
    return amount / rates[from_ccy] * rates[to_ccy]