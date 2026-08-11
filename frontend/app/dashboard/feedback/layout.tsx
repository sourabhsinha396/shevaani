import type { Metadata } from "next";

import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Your feedback",
  description: "Personal feedback from your group discussions.",
  path: "/dashboard/feedback",
  noindex: true,
});

export default function FeedbackLayout({ children }: { children: React.ReactNode }) {
  return children;
}
