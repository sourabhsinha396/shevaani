/**
 * The `?r=` referral code, remembered across the visit.
 *
 * A referred visitor rarely lands on /register - they land on a discussion
 * page or the homepage, wander, and sign up minutes later from a URL that no
 * longer carries the code. So the code is stashed in localStorage the moment
 * any page sees it (see `components/ref-capture.tsx`) and read back at
 * registration.
 *
 * Last-writer-wins on purpose: if two people's links are opened, the one that
 * actually led to the signup is the most recent one.
 */

const KEY = "shevaani_ref";

/** Codes are short lowercase alphanumerics - anything else is line noise from
 *  a mangled URL and not worth storing. */
const VALID = /^[a-z0-9]{4,32}$/;

export function rememberReferralCode(raw: string | null | undefined): void {
  if (!raw) return;
  const code = raw.trim().toLowerCase();
  if (!VALID.test(code)) return;
  try {
    window.localStorage.setItem(KEY, code);
  } catch {
    // Storage can be unavailable (private mode, quota). The code still works
    // for this page-load if the user registers directly from this URL.
  }
}

export function storedReferralCode(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** Called once the signup that used it has succeeded - a stale code lingering
 *  for months would misattribute an unrelated future account. */
export function clearReferralCode(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // Nothing to clear if nothing could be stored.
  }
}
