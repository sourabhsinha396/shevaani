/**
 * Which currency to price a visitor in, worked out in the browser and offline.
 *
 * **Timezone, not language.** `navigator.language` says what somebody reads, not
 * where they pay from, and an English browser in Mumbai is the common case here
 * rather than the odd one. `Intl.DateTimeFormat().resolvedOptions().timeZone` is
 * set by the operating system from where the machine actually is.
 *
 * **No geolocation API.** No ipapi, no ipinfo, no `cf-ipcountry`. A network call
 * to price a page is a round trip before the first number appears, a dependency
 * that can be down, and a third party told who is reading the pricing page.
 * Timezones are already in the browser and are right often enough for a default
 * that a switcher sits one click away from.
 *
 * **The floor is USD**, and it is what the server renders. The detected value
 * only ever appears after hydration, so there is no mismatch to warn about.
 *
 * None of this decides what anyone is charged. The browser sends a currency
 * code, and the backend re-quotes the price from the pack's USD base - see
 * `backend/app/services/pricing.py`. The worst a tampered value can do is buy at
 * a different price we already publish.
 */

/** Mirrors `SUPPORTED_CURRENCIES` in the backend settings. The API also sends
 *  its own list on `/billing/profile`; this one only orders the switcher. */
export const SUPPORTED_CURRENCIES = ["USD", "INR", "EUR", "GBP", "AUD"] as const;
export type Currency = (typeof SUPPORTED_CURRENCIES)[number];

export const CURRENCY_COOKIE = "shevaani_currency";

/** A$ rather than $ for AUD: both appear in the same switcher, and a menu where
 *  two entries read "$" makes the choice meaningless. */
export const CURRENCY_LABELS: Record<Currency, string> = {
  USD: "$ USD",
  INR: "₹ INR",
  EUR: "€ EUR",
  GBP: "£ GBP",
  AUD: "A$ AUD",
};

export function isSupportedCurrency(value: string | null | undefined): value is Currency {
  return !!value && (SUPPORTED_CURRENCIES as readonly string[]).includes(value);
}

/* Zones for the countries whose currency we actually sell in, and no others.
   Deliberately coarse and deliberately incomplete: a zone we cannot place falls
   through to USD, which is a price we can charge, rather than to a guess we
   would then have to refuse at checkout. */
const ZONE_COUNTRY: Record<string, string> = {
  // India - both spellings are in the wild; Asia/Calcutta is the older alias
  // and still what some Windows installs report.
  "Asia/Kolkata": "IN",
  "Asia/Calcutta": "IN",

  // United Kingdom
  "Europe/London": "GB",
  "Europe/Belfast": "GB",

  // Eurozone, by country so `detectCountry` gets a real answer too
  "Europe/Vienna": "AT",
  "Europe/Brussels": "BE",
  "Europe/Zagreb": "HR",
  "Asia/Nicosia": "CY",
  "Europe/Nicosia": "CY",
  "Europe/Tallinn": "EE",
  "Europe/Helsinki": "FI",
  "Europe/Paris": "FR",
  "Europe/Berlin": "DE",
  "Europe/Busingen": "DE",
  "Europe/Athens": "GR",
  "Europe/Dublin": "IE",
  "Europe/Rome": "IT",
  "Europe/Riga": "LV",
  "Europe/Vilnius": "LT",
  "Europe/Luxembourg": "LU",
  "Europe/Malta": "MT",
  "Europe/Amsterdam": "NL",
  "Europe/Lisbon": "PT",
  "Atlantic/Azores": "PT",
  "Atlantic/Madeira": "PT",
  "Europe/Bratislava": "SK",
  "Europe/Ljubljana": "SI",
  "Europe/Madrid": "ES",
  "Atlantic/Canary": "ES",
  "Europe/Andorra": "AD",
  "Europe/Monaco": "MC",
  "Europe/San_Marino": "SM",
  "Europe/Vatican": "VA",

  // United States. Mapping these buys no currency change - USD is the floor
  // anyway - but it is what lets a US signup record a country.
  "America/New_York": "US",
  "America/Detroit": "US",
  "America/Chicago": "US",
  "America/Denver": "US",
  "America/Phoenix": "US",
  "America/Los_Angeles": "US",
  "America/Anchorage": "US",
  "Pacific/Honolulu": "US",
};

const EUROZONE = new Set([
  "AT", "BE", "HR", "CY", "EE", "FI", "FR", "DE", "GR", "IE",
  "IT", "LV", "LT", "LU", "MT", "NL", "PT", "SK", "SI", "ES",
  // Not members, but they use the euro and nobody there expects otherwise.
  "AD", "MC", "SM", "VA",
]);

const COUNTRY_CURRENCY: Record<string, Currency> = {
  IN: "INR",
  GB: "GBP",
  AU: "AUD",
  NZ: "AUD",
  US: "USD",
};

/** ISO-3166 alpha-2 from an IANA zone, or `null` when we do not map it. */
export function countryFromTimeZone(timeZone: string): string | null {
  if (ZONE_COUNTRY[timeZone]) return ZONE_COUNTRY[timeZone];
  // Every Australia/* zone is Australia, so the prefix is exact rather than a
  // guess - which is not true of, say, America/* or Europe/*.
  if (timeZone.startsWith("Australia/")) return "AU";
  if (timeZone === "Pacific/Auckland") return "NZ";
  return null;
}

export function currencyFromCountry(country: string | null | undefined): Currency | null {
  if (!country) return null;
  const code = country.toUpperCase();
  if (EUROZONE.has(code)) return "EUR";
  return COUNTRY_CURRENCY[code] ?? null;
}

export function currencyFromTimeZone(timeZone: string): Currency | null {
  return currencyFromCountry(countryFromTimeZone(timeZone));
}

/** The browser's own zone, or `""` on a server or a browser without `Intl`. */
export function browserTimeZone(): string {
  if (typeof Intl === "undefined") return "";
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";
  } catch {
    return "";
  }
}

/** What to record on a new account. Not load-bearing - the currency decides the
 *  price and the gateway - so `null` when we cannot place the zone is fine. */
export function detectCountry(): string | null {
  return countryFromTimeZone(browserTimeZone());
}

export function readCurrencyCookie(): Currency | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${CURRENCY_COOKIE}=`));
  const value = match?.split("=")[1] ?? "";
  return isSupportedCurrency(value) ? value : null;
}

export function writeCurrencyCookie(currency: Currency): void {
  if (typeof document === "undefined") return;
  document.cookie = `${CURRENCY_COOKIE}=${currency}; path=/; max-age=31536000; samesite=lax`;
}

/**
 * A saved choice, then the timezone, then USD.
 *
 * The cookie is only written when somebody picks from the switcher, so
 * detection re-runs on every visit for everyone who never touched it - which is
 * what a learner who has moved country would want, and what someone who
 * overrode us explicitly would not.
 */
export function detectCurrency(): Currency {
  const saved = readCurrencyCookie();
  if (saved) return saved;
  return currencyFromTimeZone(browserTimeZone()) ?? "USD";
}
