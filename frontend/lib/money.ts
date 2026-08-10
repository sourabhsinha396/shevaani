/**
 * Minor units in, formatted string out.
 *
 * The API sends paise and cents as integers and never a float, so the only
 * division in the whole money path is this one — at the point of display, after
 * every decision has been made.
 */

/** Locale per currency, so each price is grouped the way its own market writes
 *  it: ₹1,69,900 in India is 1,69,900 and not 169,900. Anything unlisted gets
 *  en-US, which formats a foreign currency correctly even if not natively. */
const LOCALES: Record<string, string> = {
  INR: "en-IN",
  EUR: "de-DE",
  GBP: "en-GB",
  AUD: "en-AU",
  USD: "en-US",
};

export function formatMinor(amountMinor: number, currency: string) {
  const code = currency.toUpperCase();
  return new Intl.NumberFormat(LOCALES[code] ?? "en-US", {
    style: "currency",
    currency: code,
    // Whole-rupee and whole-dollar prices read better without ".00", but a
    // price that genuinely has paise must not be silently rounded away.
    minimumFractionDigits: amountMinor % 100 === 0 ? 0 : 2,
  }).format(amountMinor / 100);
}

/**
 * "₹205 a session" — the unit-price line under a pack.
 *
 * Divides by *sessions*, not credits. A credit is an internal unit and a price
 * per credit is not a price anyone can act on; what a buyer compares between
 * packs is what an hour of teaching ends up costing them. `creditsPerSession`
 * is passed in rather than imported so this module stays pure arithmetic.
 */
export function perSessionLabel(
  amountMinor: number,
  credits: number,
  currency: string,
  creditsPerSession: number,
) {
  const sessions = Math.floor(credits / creditsPerSession);
  if (sessions < 1) return formatMinor(amountMinor, currency);
  return formatMinor(Math.round(amountMinor / sessions), currency);
}
