/**
 * What somebody was trying to book, kept across the trip to the payment provider.
 *
 * The query string cannot do this: the provider returns to a URL the *server*
 * built, which knows about a payment and nothing about what it was for. Session
 * storage rather than local, because an abandoned checkout should not still be
 * waiting to be confirmed tomorrow.
 *
 * It holds no claim on anything. No seat is reserved and no time is held until a
 * booking is actually made, so this is a convenience for the buyer, never a
 * promise to them - which is why the copy around it says so out loud.
 */

export const PENDING_BOOKING_KEY = "shevaani_pending_booking";

/** Lengths a one-to-one can be booked for, in minutes. One for now - add to
 *  this list to reopen the choice on the booking page. The first is also the
 *  fallback for a link that arrives without an explicit duration. */
export const ONE_ON_ONE_DURATIONS = [20];

/** A one-to-one: an hour the learner picked, with no instructor attached yet. */
export interface PendingOneOnOne {
  kind: "one_on_one";
  /** UTC instant, ISO-8601. */
  slot: string;
  duration: number;
}

/** A group discussion: a session that already exists and has a seat to take. */
export interface PendingDiscussion {
  kind: "discussion";
  sessionId: string;
}

export type PendingBooking = PendingOneOnOne | PendingDiscussion;

function parse(raw: string): PendingBooking | null {
  // Read as a loose bag rather than as `Partial<PendingBooking>`: the two
  // members disagree on `kind`, so intersecting them collapses to `never`, and
  // narrowing a union we have not validated yet is backwards anyway.
  const parsed = JSON.parse(raw) as Partial<
    Record<"kind" | "slot" | "sessionId", string> & { duration: number }
  >;

  if (parsed.kind === "discussion") {
    return typeof parsed.sessionId === "string" && parsed.sessionId
      ? { kind: "discussion", sessionId: parsed.sessionId }
      : null;
  }

  // No `kind` means a record written before discussions could be pending. Read
  // as a one-to-one rather than discarded, so a buyer mid-checkout across the
  // deploy still comes back to their slot.
  if (typeof parsed.slot !== "string" || Number.isNaN(Date.parse(parsed.slot))) return null;
  // Past its start there is nothing left to confirm, and offering it would
  // send somebody to a checkout the API will refuse.
  if (Date.parse(parsed.slot) <= Date.now()) return null;
  return {
    kind: "one_on_one",
    slot: parsed.slot,
    duration: Number(parsed.duration) || ONE_ON_ONE_DURATIONS[0],
  };
}

export function readPendingBooking(): PendingBooking | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(PENDING_BOOKING_KEY);
    return raw ? parse(raw) : null;
  } catch {
    return null;
  }
}

export function writePendingBooking(pending: PendingBooking): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.setItem(PENDING_BOOKING_KEY, JSON.stringify(pending));
}

export function clearPendingBooking(): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.removeItem(PENDING_BOOKING_KEY);
}

/** Where to send someone to finish what they started. */
export function checkoutHref(pending: PendingBooking): string {
  if (pending.kind === "discussion") return `/discussions/${pending.sessionId}/checkout`;
  return `/checkout?slot=${encodeURIComponent(pending.slot)}&duration=${pending.duration}`;
}
