import type { MetadataRoute } from "next";

import { PRIVATE_PATHS, SITE_URL, canonical } from "@/lib/seo";

/**
 * Two rules, and the second one is the one that matters.
 *
 * Everything public is crawlable. Everything behind a sign-in is disallowed —
 * not because it would leak (those pages fetch their data with the caller's
 * cookie and a crawler has none), but because indexing a login wall produces
 * search results that are useless to the person who clicks them.
 *
 * The join URL never appears in any page, so there is nothing here that could
 * disallow it. That is the point: robots.txt is a request, not a control, and a
 * bearer credential is not something to protect with a request.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Bare paths, not `/admin/` — a Disallow is a prefix match, so this
        // covers `/admin`, `/admin/`, and everything under it. The trailing
        // slash form would leave `/admin` itself crawlable.
        disallow: PRIVATE_PATHS,
      },
    ],
    sitemap: canonical("/sitemap.xml"),
    host: SITE_URL,
  };
}
