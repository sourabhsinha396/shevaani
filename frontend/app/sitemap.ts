import type { MetadataRoute } from "next";

import { config } from "@/lib/config";
import { canonical } from "@/lib/seo";
import type { DiscussionSession } from "@/lib/types";

/**
 * Static pages, plus every published discussion that has not started yet.
 *
 * Regenerated hourly rather than at build time: the catalogue turns over on its
 * own as sessions run and new ones are published, and a sitemap frozen at deploy
 * points at a growing pile of finished sessions.
 *
 * Nothing behind a sign-in is here, and neither is anything join-related. See
 * `lib/seo.ts` for what a discussion may say in public.
 */
export const revalidate = 3600;

const STATIC: Array<{ path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }> = [
  { path: "/", priority: 1, changeFrequency: "weekly" },
  { path: "/discussions", priority: 0.9, changeFrequency: "hourly" },
  { path: "/one-on-one", priority: 0.8, changeFrequency: "daily" },
  { path: "/pricing", priority: 0.7, changeFrequency: "monthly" },
  // The free-tool pages are the SEO play: they are what a stranger searching
  // "impromptu speaking practice" can land on without an account.
  { path: "/tools", priority: 0.6, changeFrequency: "monthly" },
  { path: "/tools/impromptu", priority: 0.7, changeFrequency: "monthly" },
  { path: "/about", priority: 0.5, changeFrequency: "monthly" },
  { path: "/contact", priority: 0.4, changeFrequency: "yearly" },
  { path: "/terms", priority: 0.2, changeFrequency: "yearly" },
  { path: "/privacy", priority: 0.2, changeFrequency: "yearly" },
  { path: "/refunds", priority: 0.2, changeFrequency: "yearly" },
  { path: "/shipping", priority: 0.2, changeFrequency: "yearly" },
];

async function upcomingDiscussions(): Promise<DiscussionSession[]> {
  try {
    const response = await fetch(`${config.apiUrl}/api/v1/sessions?kind=group&limit=100`, {
      next: { revalidate },
    });
    if (!response.ok) return [];
    return (await response.json()) as DiscussionSession[];
  } catch {
    // A sitemap is not worth a 500. If the API is unreachable the static pages
    // still get listed, and the next revalidation picks the sessions back up.
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const sessions = await upcomingDiscussions();
  const discussions = sessions
    .filter((s) => s.status === "published")
    .map((session) => ({
      url: canonical(`/discussions/${session.slug ?? session.id}`),
      // A session's URL stops being useful the moment it starts, so the change
      // frequency is honest about it rather than inviting daily recrawls.
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.6,
    }));

  return [
    ...STATIC.map(({ path, priority, changeFrequency }) => ({
      url: canonical(path),
      lastModified: now,
      changeFrequency,
      priority,
    })),
    ...discussions,
  ];
}
