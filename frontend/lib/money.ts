/**
 * Minor units in, formatted string out.
 *
 * The API sends paise and cents as integers and never a float, so the only
 * division in the whole money path is this one — at the point of display, after
 * every decision has been made.
 */
export function formatMinor(amountMinor: number, currency: string) {
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency,
    // Whole-rupee and whole-dollar prices read better without ".00", but a
    // price that genuinely has paise must not be silently rounded away.
    minimumFractionDigits: amountMinor % 100 === 0 ? 0 : 2,
  }).format(amountMinor / 100);
}

/** "₹100 a session" — the per-credit line under a pack. */
export function perCreditLabel(amountMinor: number, credits: number, currency: string) {
  return formatMinor(Math.round(amountMinor / credits), currency);
}
