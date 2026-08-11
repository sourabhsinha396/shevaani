import type { Metadata } from "next";

import { config } from "./config";
import { richTextToPlain } from "./rich-text";
import type { DiscussionSession } from "./types";

/**
 * Everything the crawlers see, decided in one file.
 *
 * ## What is public about a discussion
 *
 * The question ITC-63 had to answer first. A group discussion is a scheduled
 * event, and the parts of it search engines legitimately want are the parts a
 * stranger deciding whether to book would want:
 *
 *   indexable - title, topic, description, start time, duration, price in
 *               credits
 *   not       - instructor identity, seat counts, waitlist position, anything
 *               about who has booked, and above all the join URL
 *
 * The instructor is left out because a public page tying a named person to a
 * timetable is a fact about them, not about the product, and they did not sign
 * up to be indexed. Seat counts are left out because "2 seats left" as a crawled
 * fact is stale within the hour and reads as pressure copy when it isn't true.
 *
 * The join URL is a bearer credential. It is never in a serialiser, never in an
 * email, and never in a page - the hard rule from PLAN, restated here because
 * this is the file where somebody would be tempted to break it.
 */

/** Absolute, no trailing slash. Every canonical and sitemap entry is built off it. */
export const SITE_URL = config.siteUrl;

export const SITE_NAME = config.appName;

/**
 * Trailing slashes: **no**, matching Next's default.
 *
 * Worth stating rather than leaving to a default, because it has to be decided
 * before links get shared: `/discussions` and `/discussions/` are different URLs
 * to a crawler, and a site that serves both accumulates duplicate entries that
 * are then expensive to unpick. Canonicals below always emit the no-slash form.
 */
export function canonical(path = "/"): string {
  if (path === "/") return SITE_URL;
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`.replace(/\/+$/, "");
}

/** Paths that must never be crawled, sitemapped, or previewed. */
export const PRIVATE_PATHS = [
  "/admin",
  "/instructor",
  "/dashboard",
  "/referrals",
  "/checkout",
  "/login",
  "/register",
  "/reset-password",
  "/verify-email",
];

interface PageMeta {
  title: string;
  description: string;
  path: string;
  /** Signed-in surfaces opt out of indexing rather than relying on robots.txt
   *  alone - robots.txt asks crawlers not to fetch, this tells the ones that
   *  found the URL anyway not to list it. */
  noindex?: boolean;
}

export function pageMetadata({ title, description, path, noindex }: PageMeta): Metadata {
  const url = canonical(path);
  return {
    title,
    description,
    alternates: { canonical: url },
    ...(noindex ? { robots: { index: false, follow: false } } : {}),
    openGraph: {
      title,
      description,
      url,
      siteName: SITE_NAME,
      type: "website",
      locale: "en_IN",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  };
}

/* ------------------------------------------------------------ structured data */

export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE_NAME,
    url: SITE_URL,
    description:
      "Small-group English discussions and one-to-one sessions with real instructors.",
    areaServed: "IN",
    sameAs: [] as string[],
  };
}

/**
 * `Event` rather than `Course`: a group discussion happens once, at a time, with
 * a capacity. `Course` describes a body of material that recurs, which is a
 * promise this product does not make.
 *
 * `EventAttendanceMode: Online` and a `VirtualLocation` whose url is the
 * *listing page*, not the meeting. Schema.org wants a location url and the
 * honest one here is the page a person can act on.
 */
export function discussionJsonLd(session: DiscussionSession) {
  return {
    "@context": "https://schema.org",
    "@type": "Event",
    name: session.title,
    // Rich text in storage, plain text in structured data.
    description: session.description
      ? richTextToPlain(session.description)
      : (session.topic ?? undefined),
    startDate: session.starts_at,
    endDate: session.ends_at,
    eventAttendanceMode: "https://schema.org/OnlineEventAttendanceMode",
    eventStatus:
      session.status === "cancelled"
        ? "https://schema.org/EventCancelled"
        : "https://schema.org/EventScheduled",
    inLanguage: "en",
    location: {
      "@type": "VirtualLocation",
      url: canonical(`/discussions/${session.slug ?? session.id}`),
    },
    organizer: { "@type": "Organization", name: SITE_NAME, url: SITE_URL },
    // Credits, not currency. Marking this up as a money price would be a lie -
    // a session costs credits, and credits are bought separately.
    isAccessibleForFree: false,
    typicalAgeRange: "16-",
    audience: { "@type": "Audience", audienceType: "English learners" },
  };
}

/** Serialise for a `<script type="application/ld+json">` without letting a
 *  stray `</script>` in a description break out of the tag. */
export function jsonLdScript(data: object): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
