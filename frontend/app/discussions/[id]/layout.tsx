import type { Metadata } from "next";

import {
  canonical,
  discussionJsonLd,
  jsonLdScript,
  pageMetadata,
} from "@/lib/seo";
import type { DiscussionSession } from "@/lib/types";

/**
 * Per-session metadata and `Event` structured data.
 *
 * The page under this is a client component — it books, cancels, and reads the
 * signed-in learner's status — so the crawlable half lives here, fetched
 * server-side with no cookie. That is not a workaround, it is the point: what
 * this layout can see is exactly what an anonymous visitor can see, which is
 * exactly what belongs in the markup.
 *
 * What it deliberately does not render: the instructor's name, seat counts, and
 * anything join-related. See `lib/seo.ts` for the reasoning.
 */

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchSession(id: string): Promise<DiscussionSession | null> {
  try {
    const response = await fetch(`${API}/api/v1/sessions/${id}`, {
      // A session's seat state changes constantly, but nothing seat-related is
      // rendered here — five minutes is plenty for a title and a start time,
      // and it keeps a crawl from hammering the API.
      next: { revalidate: 300 },
    });
    if (!response.ok) return null;
    return (await response.json()) as DiscussionSession;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const session = await fetchSession(id);

  if (!session) {
    // Unreachable or gone. Say nothing specific and keep it out of the index
    // rather than publishing a placeholder that outlives the session.
    return {
      title: "Discussion",
      robots: { index: false, follow: true },
      alternates: { canonical: canonical(`/discussions/${id}`) },
    };
  }

  const when = new Date(session.starts_at).toLocaleString("en-IN", {
    dateStyle: "full",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  });

  return pageMetadata({
    title: session.title,
    description:
      session.description?.slice(0, 160) ??
      `An English discussion on ${when} IST. Six learners at most, and everyone speaks.`,
    path: `/discussions/${session.id}`,
    // A cancelled session's page still exists so a learner following an old
    // link learns what happened — but it has no business in search results.
    noindex: session.status !== "published",
  });
}

export default async function SessionLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await fetchSession(id);

  return (
    <>
      {session && session.status === "published" && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdScript(discussionJsonLd(session)) }}
        />
      )}
      {children}
    </>
  );
}
