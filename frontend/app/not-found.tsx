import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Reached most often by a link to a session that has since run or been
 * cancelled, so it offers the catalogue rather than the homepage - the visitor
 * wanted a discussion, and there are others.
 *
 * Next serves this with a 404 status automatically, which is what keeps the
 * dead URL out of the index rather than sitting there as a thin page.
 */
export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-6 px-6 py-24 text-center">
      <p className="font-mono text-sm text-muted-foreground">404</p>
      <h1 className="font-display text-3xl sm:text-4xl">This page isn&apos;t here</h1>
      <p className="text-muted-foreground">
        The link may be old, or the session it pointed at has already run. Both
        happen - discussions come and go every week.
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        <Button asChild>
          <Link href="/discussions">Browse discussions</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/">Back to the homepage</Link>
        </Button>
      </div>
    </div>
  );
}
