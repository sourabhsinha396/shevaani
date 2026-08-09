import type { Metadata } from "next";

import { pageMetadata } from "@/lib/seo";

/**
 * Signed-in surface. `noindex` as well as a robots.txt disallow: the disallow
 * asks crawlers not to fetch the URL, this tells the ones that found it anyway
 * — from a shared link, a referrer, a browser extension — not to list it. A
 * search result pointing at a sign-in wall helps nobody.
 */
export const metadata: Metadata = pageMetadata({
  title: "Create an account",
  description: "Create a Shevaani account.",
  path: "/register",
  noindex: true,
});

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return children;
}
