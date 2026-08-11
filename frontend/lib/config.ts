/**
 * Every environment variable the frontend reads, resolved in one place. Import
 * from here rather than reading `process.env` inline - a var referenced in one
 * file is greppable; the same var defaulted differently in five files is a bug
 * that only shows up in production.
 *
 * All NEXT_PUBLIC_ values are inlined at build time: changing one in the deploy
 * environment needs a rebuild, not just a restart.
 */
export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "Shevaani",
  /** Absolute origin of the public site, no trailing slash. Canonicals, the
   *  sitemap and robots.txt are built from it - wrong in production means
   *  publishing wrong canonical URLs, which is worse than none. */
  siteUrl: (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(
    /\/+$/,
    "",
  ),
  isProduction: process.env.NODE_ENV === "production",
};
