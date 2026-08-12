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
  /** reCAPTCHA v2 checkbox site key. Empty means the widget is not rendered
   *  and the auth forms submit without a token - the backend skips the check
   *  too when its RECAPTCHA_SECRET_KEY is unset. Set both or neither. */
  recaptchaSiteKey: process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY ?? "",
  /** OAuth client id for "Sign in with Google" - the same client the backend
   *  holds as GOOGLE_CLIENT_ID, and the pair go together: empty here hides the
   *  button, empty there makes the endpoint answer 503. The site origin must
   *  be listed under the client's "Authorized JavaScript origins". */
  googleClientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "",
};
