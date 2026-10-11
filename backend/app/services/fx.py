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
MIN_REFRESH_SECONDS = 600
MAX_CACHE_SECONDS = 86400
FETCH_TIMEOUT_SECONDS = 5
CENT = Decimal("0.01")
# Matches the Numeric(18, 6) column, so a rate read back from the database is
# the same rate the expense was converted with.
RATE_PRECISION = Decimal("0.000001")
ZERO_DECIMAL_CURRENCIES = {"JPY", "KRW"}

logger = logging.getLogger(__name__)

# (expires_at unix time, rates). ponytail: per-process cache, each worker fetches
# about once a day; move to Redis only if the provider starts rate-limiting us.
_cached: tuple[float, dict[str, Decimal]] | None = None


class RatesUnavailable(Exception):
    pass


def _fetch_rates() -> tuple[dict[str, Decimal], float]:
    """Rates plus the unix time the provider publishes its next update."""
    with urllib.request.urlopen(RATES_URL, timeout=FETCH_TIMEOUT_SECONDS) as resp:
        payload = json.load(resp, parse_float=Decimal)
    if payload.get("result") != "success":
        raise ValueError("exchange rate provider returned an error")
    rates = {
        code: Decimal(payload["rates"][code]).quantize(RATE_PRECISION)
        for code in SUPPORTED_CURRENCIES
    }
    if any(not rate.is_finite() or rate <= 0 for rate in rates.values()):
        raise ValueError("exchange rate provider returned an invalid rate")
    return rates, float(payload.get("time_next_update_unix", 0))


def usd_rates() -> dict[str, Decimal]:
    """Units of each supported currency per 1 USD."""
    global _cached
    now = time.time()
    if _cached and now < _cached[0]:
        return _cached[1]
    try:
        rates, next_update = _fetch_rates()
        # Keep rates until the provider publishes new ones. A late or missing
        # update time retries in 10 minutes rather than on every request.
        expires = min(max(next_update, now + MIN_REFRESH_SECONDS), now + MAX_CACHE_SECONDS)
        _cached = (expires, rates)
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        if _cached is None:
            raise RatesUnavailable("Exchange rates are unavailable, try again shortly") from exc
        logger.warning("Exchange rate refresh failed, keeping cached rates: %s", exc)
        _cached = (now + MIN_REFRESH_SECONDS, _cached[1])
    return _cached[1]


def rate_for(currency: str) -> Decimal:
    if currency == BASE_CURRENCY:
        return Decimal("1")
    return usd_rates()[currency]


def currency_unit(currency: str) -> Decimal:
    return Decimal("1") if currency in ZERO_DECIMAL_CURRENCIES else CENT


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
