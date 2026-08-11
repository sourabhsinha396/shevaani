import type { Metadata } from "next";

import { pageMetadata } from "@/lib/seo";

/** Signed-in surface - same treatment as /dashboard: robots.txt disallows it,
 *  and this tells any crawler that found the URL anyway not to list it. */
export const metadata: Metadata = pageMetadata({
  title: "Refer a friend",
  description: "Share your link and earn a free session when a friend enrols.",
  path: "/referrals",
  noindex: true,
});

export default function ReferralsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
