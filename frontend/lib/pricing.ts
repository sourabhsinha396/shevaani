/**
 * Marketing copy for the credit packs — and deliberately no prices.
 *
 * There used to be a hardcoded ₹ and $ list here, kept in step with
 * `backend/app/cli.py` by hand. Two lists was already one too many; five would
 * have guaranteed drift, and a pricing page that quotes a number checkout then
 * refuses is worse than one that takes a moment to load. Prices now come from
 * `GET /billing/packs`, which is public precisely so this page can use it.
 *
 * What stays here is the part the backend has no business knowing: the blurb,
 * the feature list, and which pack gets the badge. Joined to the API rows on
 * `slug`, so a pack seeded without an entry here still renders — just bare.
 */
import type { CreditPack } from "@/lib/types";

/**
 * What one session costs, group or one-to-one.
 *
 * Mirrors `SESSION_PRICE_CREDITS` in the backend settings, which is the value
 * that actually gets charged. This copy exists so the pages can do the
 * credits→sessions arithmetic without a round trip; if the setting moves, this
 * has to move with it. An individual session can override its own price, so
 * anywhere a real session is on screen, prefer its `price_credits`.
 */
export const CREDITS_PER_SESSION = 2;

/** "5 credits" → "2 sessions". Rounds down: a spare credit buys nothing. */
export function sessionsFrom(credits: number): number {
  return Math.floor(credits / CREDITS_PER_SESSION);
}

/**
 * "4 sessions" — the unit every buying and booking screen speaks in.
 *
 * Credits are the ledger's unit and stay in the ledger. Nobody arrives wanting
 * credits; they want to talk to someone for an hour, and a balance quoted in a
 * currency they have to convert in their head is a balance they misread. Admin
 * screens and the legal pages still say credits, because there the mechanic
 * *is* the subject.
 */
export function sessionLabel(sessions: number): string {
  return `${sessions} session${sessions === 1 ? "" : "s"}`;
}

/** A balance, in the unit it is shown in. */
export function sessionBalanceLabel(credits: number): string {
  return sessionLabel(sessionsFrom(credits));
}

/**
 * What a session costs, in the unit the buying screens speak in. `"Free"` at zero.
 *
 * Rounds *up*, unlike `sessionsFrom`. Rounding down is right for a balance — a
 * spare credit buys nothing — but a price rounded down reads as free: a session
 * priced at one credit would render "0 sessions" next to a Book button that then
 * charges for it. Admin can set an odd `price_credits` (the new-session form
 * still defaults to 1), so this is reachable, not theoretical.
 */
export function sessionPriceLabel(credits: number): string {
  if (credits <= 0) return "Free";
  return sessionLabel(Math.ceil(credits / CREDITS_PER_SESSION));
}

/**
 * A signed ledger movement, in sessions: `+4`, `-1`.
 *
 * Halves are shown as halves rather than rounded away. Every pack and every
 * session price is an even number of credits, so this should not come up — but
 * an admin grant of an odd number would otherwise display as a whole session
 * that is not on the balance, and a ledger that does not add up is worse than
 * one that shows a `0.5`.
 */
export function sessionDeltaLabel(credits: number): string {
  const sessions = credits / CREDITS_PER_SESSION;
  const text = Number.isInteger(sessions) ? String(sessions) : sessions.toFixed(1);
  return sessions > 0 ? `+${text}` : text;
}

export type PackCopy = {
  blurb: string;
  features: string[];
  highlight?: boolean;
};

/* Counted in sessions, not credits, because that is the unit somebody is
   actually buying. Every pack's credit count is a multiple of
   CREDITS_PER_SESSION — see the note on `_PACKS` in the backend CLI — so none
   of these numbers leaves a remainder a learner can never spend. */
export const PACK_COPY: Record<string, PackCopy> = {
  starter: {
    blurb: "One discussion, to find your level before committing.",
    features: [
      "1 session",
      "group discussion or 1:1",
      "perfomance summary",
      "Cancelation or reschedule is not supported",
    ],
  },
  regular: {
    blurb: "A month of weekly practice — where fluency actually starts to move.",
    features: [
      "4 sessions",
      "Use for group discussions or 1:1",
      "We try to match you with better speakers",
      "Cancel or reschedule up to 12h before",
      "Progress summary",
    ],
    highlight: true,
  },
  intensive: {
    blurb: "A season of it, with room for one-to-ones.",
    features: [
      "12 sessions",
      "Use for group discussions or 1:1",
      "We try to match you with better speakers",
      "Progress summary",
    ],
  },
};

export function copyFor(slug: string): PackCopy {
  return PACK_COPY[slug] ?? { blurb: "", features: [] };
}

/**
 * The pack's price in `currency`, in minor units.
 *
 * Falls back to USD rather than to zero or a dash: a pack quoted in a currency
 * the browser knows about but this deployment has dropped should still show a
 * price somebody can pay, which is exactly what checkout will fall back to too.
 */
export function priceFor(pack: CreditPack, currency: string): { minor: number; currency: string } {
  const code = currency.toUpperCase();
  if (pack.prices?.[code] !== undefined) return { minor: pack.prices[code], currency: code };
  return { minor: pack.prices?.USD ?? pack.usd_cents, currency: "USD" };
}
