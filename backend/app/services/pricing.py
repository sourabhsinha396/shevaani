"""One USD price list, quoted into every currency we sell in.

``credit_packs.usd_cents`` is the only price stored. Every other currency is
derived here: convert at a configured rate, apply a purchasing-power multiplier,
then round to a step that reads like a price rather than like a conversion.

That reverses the original design — a ₹ row and a $ row, never converted. Two
hand-maintained price lists were defensible; five are five places to forget, and
past two the arithmetic is easier to trust than the data entry.

Two properties the rest of the billing code leans on:

* **Rates are configuration, not a live feed.** They move when somebody edits a
  setting and redeploys, never mid-session. A price that follows the spot rate
  charges something other than what the buyer read on the pricing page, and
  there is no version of that a buyer reads as honest.
* **The browser sends a currency code and never an amount.** Quotes are
  recomputed server-side at checkout from the same function that produced the
  displayed price, so the worst a tampered request can do is buy at another
  price we publish.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.errors import DomainError

USD = "USD"
INR = "INR"


class UnsupportedCurrency(DomainError):
    status_code = 400
    code = "unsupported_currency"


def supported() -> tuple[str, ...]:
    """Sellable currencies, USD first.

    USD is prepended rather than merely expected in the setting: it is the base
    price and the fallback for every path below, so a deployment that trims the
    list must not be able to remove the one currency that is always quotable.
    """
    codes = [code.upper() for code in settings.supported_currencies]
    return (USD, *[code for code in codes if code != USD])


def is_supported(code: str | None) -> bool:
    return bool(code) and code.upper() in supported()


def coerce(code: str | None) -> str:
    """A currency we can quote, falling back to USD.

    For display paths, where showing a dollar price beats showing an error.
    Checkout goes through :func:`require` instead — there, quietly substituting
    a currency means charging someone in one they did not choose.
    """
    return code.upper() if code and is_supported(code) else USD


def require(code: str | None) -> str:
    if not code or not is_supported(code):
        raise UnsupportedCurrency(f"We do not sell in {code or 'that currency'}.")
    return code.upper()


def quote_minor(usd_cents: int, currency: str) -> int:
    """USD cents in, minor units of ``currency`` out.

    USD passes through untouched rather than round-tripping at a rate of 1.0:
    it is the stored price, and letting a rounding step near it would mean the
    base list could be quietly re-priced by a config change meant for somebody
    else's currency.
    """
    code = require(currency)
    if code == USD:
        return usd_cents

    rate = settings.fx_static_rates.get(code)
    if rate is None:
        # Listed as supported with no rate to convert at. Louder than defaulting
        # to 1.0, which would sell a $9 pack for ₹9.
        raise UnsupportedCurrency(f"No exchange rate is configured for {code}.")

    ppp = settings.ppp_multipliers.get(code, 1.0)
    step = settings.currency_round_steps.get(code, 1)
    major = usd_cents / 100 * rate * ppp
    # The `max` floor keeps a cheap pack from rounding down to zero and becoming
    # free, which is the one rounding bug that costs money rather than pennies.
    rounded = max(step, round(major / step) * step)
    return int(rounded * 100)


def localized(usd_cents: int) -> dict[str, int]:
    """Every supported currency at once.

    Attached to each pack so the browser *picks* a price instead of asking for
    one: switching currency is then a re-render rather than another round trip,
    and no client ever runs the conversion itself.
    """
    return {code: quote_minor(usd_cents, code) for code in supported()}


# --------------------------------------------------------- country → currency

#: Euro members, by ISO-3166 alpha-2. Kept as a set rather than folded into the
#: table below because the interesting fact is membership, not a per-country
#: mapping that happens to repeat twenty times.
_EUROZONE = frozenset(
    {
        "AT", "BE", "HR", "CY", "EE", "FI", "FR", "DE", "GR", "IE",
        "IT", "LV", "LT", "LU", "MT", "NL", "PT", "SK", "SI", "ES",
    }
)

#: Only countries whose own currency we actually price in. Everywhere else
#: resolves to ``None`` and takes the USD floor — quoting a Swiss learner in
#: francs we cannot charge would be worse than quoting them in dollars we can.
_COUNTRY_CURRENCY = {"IN": INR, "GB": "GBP", "AU": "AUD", "NZ": "AUD", "US": USD}


def currency_for_country(country: str | None) -> str | None:
    """ISO-3166 alpha-2 to a currency, or ``None`` if we do not sell in theirs.

    Used as the server-side fallback for an account whose browser did not send a
    currency. The browser's own detection is better — it knows the visitor's
    timezone, while this only knows where they said they were at signup.
    """
    if not country:
        return None
    code = country.upper()
    if code in _EUROZONE:
        return "EUR" if is_supported("EUR") else None
    found = _COUNTRY_CURRENCY.get(code)
    return found if is_supported(found) else None
