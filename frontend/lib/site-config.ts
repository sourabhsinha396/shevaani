import { config } from "./config";
import type { SiteConfig } from "./types";

/**
 * Which parts of the product are switched on, fetched on the server.
 *
 * **Why not `NEXT_PUBLIC_*`.** Next inlines those at build time, so hiding a nav
 * item would mean rebuilding and redeploying the web image. These come from one
 * row in `site_settings`, edited at `/admin/settings`, and change without a
 * deploy.
 *
 * **Why not `lib/api.ts`.** That client sends credentials and `no-store`,
 * because everything it fetches is somebody's own data. This is the opposite:
 * public, identical for every visitor, and wanted on the server before the first
 * byte of HTML so the header renders with the right links rather than correcting
 * itself after hydration. Its own fetch, with its own caching.
 */

/** Every flag on. The answer when the API is unreachable, and - deliberately -
 *  when it is unreachable *at build time*, which is the normal case for a fresh
 *  container starting before the backend. Degrading to a working site beats
 *  degrading to a site with its nav emptied out. */
export const DEFAULT_SITE_CONFIG: SiteConfig = {
  one_on_one_enabled: true,
};

/** How stale the browser's copy may get, in seconds.
 *
 *  The cost of zero would be making every page on the site dynamically
 *  rendered, for a value that changes a few times a year. A minute between
 *  flipping a switch in `/admin/settings` and seeing it on the public site is
 *  the trade. The admin form itself reads uncached - see `api.adminSiteConfig`. */
const REVALIDATE_SECONDS = 60;

const BASE = config.apiUrl;

/** Server components only - it relies on Next's fetch cache, which does not
 *  exist in the browser. Client components read the same value out of
 *  `useSiteConfig()`, which the root layout seeds from this. */
export async function getSiteConfig(): Promise<SiteConfig> {
  try {
    const response = await fetch(`${BASE}/api/v1/config`, {
      next: { revalidate: REVALIDATE_SECONDS },
    });
    if (!response.ok) return DEFAULT_SITE_CONFIG;
    // Spread over the defaults rather than trusting the response wholesale: an
    // older API that does not know about a flag added here should leave it at
    // its default, not `undefined`.
    return { ...DEFAULT_SITE_CONFIG, ...((await response.json()) as Partial<SiteConfig>) };
  } catch {
    // The backend being down must not take the whole site's HTML with it.
    return DEFAULT_SITE_CONFIG;
  }
}

/** One entry per flag, and the only place a flag's prose lives.
 *
 *  `/admin/settings` renders this list, so adding a switch to the admin is a
 *  line here plus the field on `SiteConfig` - there is no per-flag markup to
 *  write. `key` is typed against `SiteConfig`, so a typo does not compile. */
export const SITE_FLAGS: {
  key: keyof SiteConfig;
  label: string;
  description: string;
}[] = [
  {
    key: "one_on_one_enabled",
    label: "1:1 sessions",
    description:
      "Off hides 1:1 from the nav and refuses new bookings. Sessions already booked are untouched - cancel those yourself if that is what you meant. Leaving this on does not force the link to appear: it still hides itself when nobody has an hour free in the next month.",
  },
];
