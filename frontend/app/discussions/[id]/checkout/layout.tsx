import type { Metadata } from "next";

/**
 * A checkout has no business in the index.
 *
 * Without this it would inherit the session's own metadata from the layout
 * above — including its canonical, which would point search engines at
 * `/discussions/[id]` while serving them a page that only makes sense to a
 * signed-in learner mid-purchase.
 */
export const metadata: Metadata = {
  title: "Confirm your seat",
  robots: { index: false, follow: false },
  alternates: { canonical: null },
};

export default function CheckoutLayout({ children }: { children: React.ReactNode }) {
  return children;
}
