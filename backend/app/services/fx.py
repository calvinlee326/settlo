import json
import logging
import time
import urllib.request
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, get_args

Currency = Literal["USD", "TWD", "JPY", "CNY", "KRW", "THB", "EUR"]
SUPPORTED_CURRENCIES: tuple[str, ...] = get_args(Currency)
BASE_CURRENCY = "USD"
RATES_URL = "https://open.er-api.com/v6/latest/USD"
CACHE_TTL_SECONDS = 3600
FETCH_TIMEOUT_SECONDS = 5
CENT = Decimal("0.01")

logger = logging.getLogger(__name__)

# ponytail: per-process cache, each worker fetches once an hour; move to Redis
# only if the provider starts rate-limiting us.
_cached: tuple[float, dict[str, Decimal]] | None = None


class RatesUnavailable(Exception):
    pass


def _fetch_rates() -> dict[str, Decimal]:
    with urllib.request.urlopen(RATES_URL, timeout=FETCH_TIMEOUT_SECONDS) as resp:
        payload = json.load(resp, parse_float=Decimal)
    if payload.get("result") != "success":
        raise ValueError("exchange rate provider returned an error")
    rates = {code: Decimal(payload["rates"][code]) for code in SUPPORTED_CURRENCIES}
    if any(not rate.is_finite() or rate <= 0 for rate in rates.values()):
        raise ValueError("exchange rate provider returned an invalid rate")
    return rates


def usd_rates() -> dict[str, Decimal]:
    """Units of each supported currency per 1 USD."""
    global _cached
    now = time.monotonic()
    if _cached and now - _cached[0] < CACHE_TTL_SECONDS:
        return _cached[1]
    try:
        _cached = (now, _fetch_rates())
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        if _cached is None:
            raise RatesUnavailable("Exchange rates are unavailable, try again shortly") from exc
        logger.warning("Exchange rate refresh failed, keeping cached rates: %s", exc)
        _cached = (now, _cached[1])
    return _cached[1]


def rate_for(currency: str) -> Decimal:
    if currency == BASE_CURRENCY:
        return Decimal("1")
    return usd_rates()[currency]


def to_usd(amount: Decimal, rate: Decimal) -> Decimal:
    return (amount / rate).quantize(CENT, ROUND_HALF_UP)


def shares_to_usd(amounts: list[Decimal], rate: Decimal) -> list[Decimal]:
    """Convert shares by rounding the running total, so they always add up to
    to_usd(sum(amounts)) and group balances stay exact to the cent."""
    shares, running, converted = [], Decimal("0"), Decimal("0")
    for amount in amounts:
        running += amount
        total = to_usd(running, rate)
        shares.append(total - converted)
        converted = total
    return shares
