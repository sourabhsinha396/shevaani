import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const IST = "Asia/Kolkata";

/** Everything from the API is UTC; render in the viewer's zone, IST by default. */
export function formatDateTime(iso: string, timeZone: string = IST) {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone,
  }).format(new Date(iso));
}

/** Date only - for facts where the hour is noise ("joined 5 Aug"). */
export function formatDate(iso: string, timeZone: string = IST) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    timeZone,
  }).format(new Date(iso));
}

export function formatTime(iso: string, timeZone: string = IST) {
  return new Intl.DateTimeFormat("en-IN", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone,
  }).format(new Date(iso));
}

export function formatDayLabel(iso: string, timeZone: string = IST) {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone,
  }).format(new Date(iso));
}

export function durationMinutes(startIso: string, endIso: string) {
  return Math.round(
    (new Date(endIso).getTime() - new Date(startIso).getTime()) / 60000,
  );
}

/**
 * Seat count as shown to learners, padded by up to 2.
 *
 * Every learner-facing surface goes through this, so the card, the seat meter,
 * the detail page and checkout can never quote different numbers for the same
 * session. Admin screens deliberately do *not* - whoever runs the session needs
 * the real figure to decide whether it goes ahead.
 *
 * Two properties matter more than the padding itself, because breaking either
 * is visible to a learner and reads as the site making numbers up:
 *
 *   - it never decreases as seats fill. A plain `+2 until near the top` drops
 *     from 5/6 to 4/6 the moment the fourth seat sells, so somebody watching
 *     the page sees the room empty out as it fills.
 *   - it never reaches `maxSeats` unless the session is genuinely full, so the
 *     card never says "last seat" about a room with three going spare.
 */
export function increasedSeatsTaken(seatsTaken: number, maxSeats: number) {
  if (seatsTaken >= maxSeats) return maxSeats;
  return Math.min(seatsTaken + 2, maxSeats - 1);
}

/** The other half of the same figure. Deriving it rather than reading
 *  `seats_left` is what stops a card showing "5 of 6 taken" beside "2 left". */
export function increasedSeatsLeft(seatsTaken: number, maxSeats: number) {
  return maxSeats - increasedSeatsTaken(seatsTaken, maxSeats);
}

export function relativeToNow(iso: string) {
  const diffMs = new Date(iso).getTime() - Date.now();
  const minutes = Math.round(diffMs / 60000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  if (Math.abs(minutes) < 60) return rtf.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return rtf.format(hours, "hour");
  return rtf.format(Math.round(hours / 24), "day");
}
