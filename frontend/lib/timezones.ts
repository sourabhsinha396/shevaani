/**
 * The zones a learner can read the booking calendar in.
 *
 * Five, not four hundred. They are the same five markets checkout sells to (see
 * `lib/currency.ts`), which is not a coincidence: someone paying in pounds is
 * almost always reading times in London, and a picker with every IANA zone in it
 * is a search box where a two-word answer would do.
 *
 * **Detection, then India.** The core team is in IST and the booking window is
 * defined in it, so an unplaceable browser gets Asia/Kolkata rather than UTC -
 * a zone somebody actually teaches in beats a zone nobody lives in.
 *
 * None of this changes what is bookable. The API sends UTC instants; a zone only
 * decides how they are printed and which calendar day they fall on.
 */

export const BOOKING_TIMEZONE = "Asia/Kolkata";

export interface BookingZone {
  id: string;
  /** What the picker shows. Not the IANA id - nobody thinks in "Europe/Berlin". */
  label: string;
}

export const BOOKING_ZONES: readonly BookingZone[] = [
  { id: "Asia/Kolkata", label: "India - IST" },
  { id: "Europe/London", label: "United Kingdom - London" },
  { id: "Europe/Berlin", label: "Europe - Central European Time" },
  { id: "America/New_York", label: "United States - Eastern" },
  { id: "Australia/Sydney", label: "Australia - Sydney" },
] as const;

export const TIMEZONE_COOKIE = "shevaani_timezone";

export function isBookingZone(value: string | null | undefined): boolean {
  return !!value && BOOKING_ZONES.some((zone) => zone.id === value);
}

/** Older alias still reported by some Windows installs, and by this machine. */
const ALIASES: Record<string, string> = {
  "Asia/Calcutta": "Asia/Kolkata",
  "Europe/Belfast": "Europe/London",
  "Europe/Dublin": "Europe/London",
};

/* Zones that are unambiguously one of the five, spelled out where a prefix would
   get it wrong. Everything else falls through to the continent rules below. */
const EXACT: Record<string, string> = {
  "Europe/Lisbon": "Europe/London",
  "Atlantic/Azores": "Europe/London",
  "Atlantic/Canary": "Europe/London",
  "Pacific/Auckland": "Australia/Sydney",
};

/**
 * The closest of the five to a browser's own zone.
 *
 * Coarse on purpose. Someone in Los Angeles is shown New York, which is three
 * hours out - but it is three hours out in a zone they can reason about, and the
 * picker is right there. Guessing precisely is not on the table with five
 * options; the job is to open on a plausible one instead of always on IST.
 */
export function nearestBookingZone(timeZone: string): string {
  if (!timeZone) return BOOKING_TIMEZONE;

  const resolved = ALIASES[timeZone] ?? timeZone;
  if (isBookingZone(resolved)) return resolved;
  if (EXACT[resolved]) return EXACT[resolved];

  if (resolved.startsWith("Australia/") || resolved.startsWith("Pacific/")) {
    return "Australia/Sydney";
  }
  if (resolved.startsWith("Europe/") || resolved.startsWith("Africa/")) {
    return "Europe/Berlin";
  }
  if (resolved.startsWith("America/") || resolved.startsWith("Atlantic/")) {
    return "America/New_York";
  }
  // Asia, Indian/*, and anything unrecognised. IST is where the instructors are.
  return BOOKING_TIMEZONE;
}

/** The browser's own zone, or `""` on the server. */
export function browserTimeZone(): string {
  if (typeof Intl === "undefined") return "";
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";
  } catch {
    return "";
  }
}

export function readTimezoneCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${TIMEZONE_COOKIE}=`));
  const value = match?.split("=")[1] ?? "";
  return isBookingZone(value) ? value : null;
}

export function writeTimezoneCookie(timeZone: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${TIMEZONE_COOKIE}=${timeZone}; path=/; max-age=31536000; samesite=lax`;
}

/**
 * A saved choice, then the browser, then India.
 *
 * Only an explicit pick is written to the cookie, so detection re-runs for
 * everybody who never touched the switcher - which is what somebody who has
 * flown somewhere would want, and what somebody who overrode us would not.
 */
export function detectBookingZone(): string {
  return readTimezoneCookie() ?? nearestBookingZone(browserTimeZone());
}

/** `2026-08-11` - the calendar date an instant falls on *in this zone*.
 *
 *  Load-bearing: 07:00 IST is the previous evening in New York, so slots have to
 *  be regrouped by the reader's date or the calendar shows Tuesday's 9pm under
 *  Wednesday. `en-CA` is the shortest route to ISO order out of `Intl`. */
export function zonedDateKey(instant: Date | string, timeZone: string): string {
  const date = typeof instant === "string" ? new Date(instant) : instant;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

/* [standard, daylight] for each of the five. Written out rather than taken from
   `Intl`, which returns "GMT+5:30" for Kolkata and "GMT+1" for Berlin under
   every locale a British-English site would reasonably ask in - accurate, and
   not what anybody calls the time where they live. */
const ABBREVIATIONS: Record<string, [string, string]> = {
  "Asia/Kolkata": ["IST", "IST"],
  "Europe/London": ["GMT", "BST"],
  "Europe/Berlin": ["CET", "CEST"],
  "America/New_York": ["EST", "EDT"],
  "Australia/Sydney": ["AEST", "AEDT"],
};

/** Minutes east of UTC for a zone at an instant. */
function offsetMinutes(timeZone: string, at: Date): number {
  const name = new Intl.DateTimeFormat("en-GB", { timeZone, timeZoneName: "longOffset" })
    .formatToParts(at)
    .find((part) => part.type === "timeZoneName")?.value;
  const match = name?.match(/GMT([+-])(\d{2}):(\d{2})/);
  if (!match) return 0; // "GMT" with no offset - the zone is on UTC.
  const sign = match[1] === "-" ? -1 : 1;
  return sign * (Number(match[2]) * 60 + Number(match[3]));
}

/** The abbreviation for a zone right now - "IST", "BST", "EDT". Shown beside the
 *  times so a reader can tell at a glance which clock they are reading. */
export function zoneAbbreviation(timeZone: string, at: Date = new Date()): string {
  try {
    const known = ABBREVIATIONS[timeZone];
    if (known) {
      // Daylight saving always moves the clock *forward*, so the standard
      // offset is the smaller of the two solstices whichever hemisphere it is.
      const year = at.getUTCFullYear();
      const standard = Math.min(
        offsetMinutes(timeZone, new Date(Date.UTC(year, 0, 15))),
        offsetMinutes(timeZone, new Date(Date.UTC(year, 6, 15))),
      );
      return known[offsetMinutes(timeZone, at) > standard ? 1 : 0];
    }
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone,
      timeZoneName: "short",
    }).formatToParts(at);
    return parts.find((part) => part.type === "timeZoneName")?.value ?? timeZone;
  } catch {
    return timeZone;
  }
}
