import posthog from "posthog-js";

/*
 * PostHog analytics, initialised before the app hydrates (Next.js runs this
 * file on every page load - see the instrumentation-client convention).
 *
 * Production builds only, and only when a token is configured: dev sessions
 * would otherwise pollute the real project's numbers. NODE_ENV and the
 * NEXT_PUBLIC_* values are inlined at build time, so non-production bundles
 * strip the whole block.
 *
 * `defaults: "2025-05-24"` opts into history-based pageview capture, which is
 * what makes client-side route changes count as pageviews in an app-router
 * SPA - without it only hard loads would be recorded.
 */
const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN;

if (process.env.NODE_ENV === "production" && token) {
  posthog.init(token, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
    defaults: "2025-05-24",
  });
}
