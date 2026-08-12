import type { Metadata } from "next";

import { pageMetadata } from "@/lib/seo";

/**
 * The page itself is a client component - it filters and reads the signed-in
 * learner's booking state - so its metadata lives here. A layout is a server
 * component regardless of what it wraps, which is the only way to export
 * `metadata` for a `"use client"` page without splitting it in two.
 */
export const metadata: Metadata = {
  ...pageMetadata({
    title: "Group English discussions",
  description:
    "Small-group English conversation sessions. Six learners at most, thirty minutes, one session each.",
    path: "/discussions",
  }),
  // Re-declared at this level so session pages below inherit it. A parent that
  // sets `title` as a plain string is the segment where the root template stops
  // being applied to children, and a session page titled just "Food & culture"
  // is a worse search result than one that says whose site it is.
  title: {
    default: "Group English discussions",
    template: "%s - Shevaani",
  },
};

export default function DiscussionsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
