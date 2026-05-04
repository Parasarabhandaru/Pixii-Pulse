"""Foreign exchange rates from open.er-api.com (free, no API key, real HTTP).

Used by analyst._pricing_opportunity to convert local-currency marketplace
prices to USD so cross-marketplace gaps become visible.

Rates are cached for 1 hour in memory so the pipeline isn't billed for FX on
every run. Falls back to recent hardcoded rates if the API is unreachable.
"""
from __future__ import annotations

import time

import requests

_BASE_URL = "https://open.er-api.com/v6/latest/USD"
_CACHE_TTL = 3600  # 1 hour
_TIMEOUT = 8

_cache: dict = {"rates": None, "fetched_at": 0.0, "source": ""}

# Anchor used when the API call fails. Updated occasionally; close enough for the demo.
_FALLBACK_RATES = {
    "USD": 1.0,
    "GBP": 0.79,
    "EUR": 0.93,
    "CAD": 1.36,
    "AUD": 1.51,
    "JPY": 153.0,
    "INR": 83.5,
    "MXN": 17.0,
}


def get_rates() -> dict:
    """Return USD-base rates. e.g. {'GBP': 0.79, 'EUR': 0.93, ...}."""
    now = time.time()
    if _cache["rates"] and (now - _cache["fetched_at"]) < _CACHE_TTL:
        return _cache["rates"]

    try:
        resp = requests.get(_BASE_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        rates = data.get("rates") or {}
        if not rates:
            raise RuntimeError("rates payload empty")
        _cache.update({"rates": rates, "fetched_at": now, "source": "live_api"})
        return rates
    except Exception as exc:
        print(f"[fx] live rate fetch failed ({exc}); using fallback table")
        _cache.update({"rates": _FALLBACK_RATES, "fetched_at": now, "source": "fallback"})
        return _FALLBACK_RATES


def to_usd(amount: float, currency: str) -> float:
    """Convert a local amount to USD using current rates."""
    if amount is None or amount <= 0:
        return 0.0
    code = (currency or "USD").upper()
    if code == "USD":
        return float(amount)
    rates = get_rates()
    rate = rates.get(code)
    if not rate or rate <= 0:
        return float(amount)
    return float(amount) / float(rate)


def rate_source() -> str:
    """For diagnostics / UI captions: 'live_api' or 'fallback'."""
    return _cache.get("source") or "unknown"
