"use client";

import * as React from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * The last line of defence for a render that threw.
 *
 * It shows no error text. In production `error.message` is already redacted by
 * Next, and in development the overlay is more useful than anything this could
 * print - so the message here would be either useless or noise. The digest is
 * shown instead, because that is the one string that ties what the visitor saw
 * to a line in the server log.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-6 px-6 py-24 text-center">
      <h1 className="font-display text-3xl sm:text-4xl">Something went wrong</h1>
      <p className="text-muted-foreground">
        That is on us, not on you. Trying again often works - if it doesn&apos;t,
        the contact page reaches a person.
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        <Button onClick={reset}>Try again</Button>
        <Button asChild variant="outline">
          <Link href="/contact">Contact us</Link>
        </Button>
      </div>
      {error.digest && (
        <p className="font-mono text-xs text-muted-foreground">
          Reference: {error.digest}
        </p>
      )}
    </div>
  );
}
