import type { Metadata } from "next";

import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "One-to-one English sessions",
  description:
    "Book a private hour with an instructor. Pick a date and a time in your own timezone - one session, the same as a group discussion.",
  path: "/one-on-one",
});

export default function OneOnOneLayout({ children }: { children: React.ReactNode }) {
  return children;
}
