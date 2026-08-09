import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Payment cancelled — Shevaani",
};

/**
 * The buyer backed out at the provider. There is a `payments` row sitting at
 * `created` and that is correct — an abandoned attempt is a real thing that
 * happened, and deleting it would lose the trail if the provider later says the
 * money moved after all.
 */
export default function CheckoutCancelledPage() {
  return (
    <div className="bg-surface-subtle min-h-full">
      <div className="mx-auto flex max-w-md flex-col px-4 py-20">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Payment cancelled</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-sm">
            <p className="text-muted-foreground text-pretty">
              Nothing was charged and your balance is unchanged. If you meant to
              buy credits, pick a pack again — it takes a minute.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="brand" size="sm">
                <Link href="/checkout">Back to packs</Link>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link href="/dashboard">My sessions</Link>
              </Button>
            </div>
            <p className="text-muted-foreground text-xs text-pretty">
              If something went wrong rather than you changing your mind, tell us
              on the{" "}
              <Link href="/contact" className="underline underline-offset-4">
                contact form
              </Link>{" "}
              — we would rather know.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
