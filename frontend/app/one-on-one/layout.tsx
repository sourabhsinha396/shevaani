import type { Metadata } from "next";

import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "One-to-one English sessions",
  description:
    "Book a private hour with an instructor, in slots between 07:00 and 19:00 IST. One credit, same as a group discussion.",
  path: "/one-on-one",
});

export default function OneOnOneLayout({ children }: { children: React.ReactNode }) {
  return children;
}
