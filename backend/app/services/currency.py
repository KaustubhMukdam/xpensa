"""
Currency conversion service with 1-hour TTL cache.

Uses the free Open Exchange Rates-compatible API (no key needed for basic USD base).
Falls back to 1.0 if the API is unavailable — so the app doesn't crash.
"""
import httpx
import time
from typing import Optional

# Simple in-memory TTL cache: { base_currency: (rates_dict, fetched_at) }
_cache: dict[str, tuple[dict[str, float], float]] = {}
_CACHE_TTL = 3600  # 1 hour in seconds

# Free API — no key needed, refreshes every 24h (good enough for hackathon)
_API_URL = "https://open.er-api.com/v6/latest/{base}"


async def _fetch_rates(base_currency: str) -> dict[str, float]:
    """Fetch all exchange rates for a given base currency."""
    url = _API_URL.format(base=base_currency.upper())
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = client.get(url)  # type: ignore[assignment]
        # Use sync get to avoid async complexity in a sync FastAPI endpoint
        # For proper async, use await client.get(url)
        raise NotImplementedError  # handled below


async def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """
    Returns the exchange rate to convert 1 unit of from_currency to to_currency.
    Caches rates for 1 hour per base currency.
    Returns 1.0 if currencies are the same or if API fails.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return 1.0

    now = time.time()
    cached = _cache.get(from_currency)
    if cached and (now - cached[1]) < _CACHE_TTL:
        rates = cached[0]
    else:
        rates = await _fetch_rates_async(from_currency)
        _cache[from_currency] = (rates, now)

    rate = rates.get(to_currency)
    if rate is None:
        # Fallback — try to do two-step conversion via USD
        if from_currency != "USD":
            usd_rates = await get_rates_for("USD")
            from_to_usd = usd_rates.get(from_currency)
            to_from_usd = usd_rates.get(to_currency)
            if from_to_usd and to_from_usd:
                return to_from_usd / from_to_usd
        return 1.0  # Last resort fallback

    return rate


async def _fetch_rates_async(base_currency: str) -> dict[str, float]:
    """Async fetch of exchange rates."""
    url = _API_URL.format(base=base_currency.upper())
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            if data.get("result") == "success":
                return data.get("rates", {})
    except Exception:
        pass
    return {}


async def get_rates_for(base_currency: str) -> dict[str, float]:
    """Get cached or fresh rates for a given base currency."""
    now = time.time()
    cached = _cache.get(base_currency)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return cached[0]
    rates = await _fetch_rates_async(base_currency)
    _cache[base_currency] = (rates, now)
    return rates


async def convert_amount(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> tuple[float, float]:
    """
    Returns (converted_amount, exchange_rate_used).
    Rounds to 2 decimal places.
    """
    rate = await get_exchange_rate(from_currency, to_currency)
    converted = round(amount * rate, 2)
    return converted, rate
