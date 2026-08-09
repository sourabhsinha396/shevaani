"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatMinor } from "@/lib/money";
import type { Payment } from "@/lib/types";

//: Long enough to cover a slow webhook, short enough not to look hung.
const POLL_MS = 2000;
const MAX_POLLS = 15;

/**
 * Reports what the webhook has recorded. It never grants anything.
 *
 * A buyer landing here proves they have a browser, not that money moved — so
 * this page polls the payment row and is perfectly willing to sit on "still
 * confirming" until the provider tells the backend otherwise.
 */
function CheckoutSuccess() {
  const params = useSearchParams();
  const { refresh } = useAuth();
  const paymentId = params.get("payment") ?? "";

  const [payment, setPayment] = React.useState<Payment | null>(null);
  const [polls, setPolls] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!paymentId) {
      setError("That link is missing its payment reference.");
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function check(attempt: number) {
      try {
        const next = await api.payment(paymentId);
        if (cancelled) return;
        setPayment(next);
        setPolls(attempt);

        if (next.status === "paid") {
          await refresh(); // balance in the header catches up
          return;
        }
        if (next.status === "created" && attempt < MAX_POLLS) {
          timer = setTimeout(() => void check(attempt + 1), POLL_MS);
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }

    void check(1);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // Keyed on the payment id alone — `refresh` changes identity whenever auth
    // state does, and re-running this would restart the poll loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paymentId]);

  if (error) {
    return (
      <div className="flex items-start gap-3 text-sm">
        <XCircle className="text-destructive mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-medium">We couldn&apos;t look that payment up</p>
          <p className="text-muted-foreground mt-1 text-pretty">{error}</p>
        </div>
      </div>
    );
  }

  if (!payment) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" /> Checking with the payment provider…
      </p>
    );
  }

  if (payment.status === "paid") {
    return (
      <div className="flex items-start gap-3 text-sm">
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-[var(--success)]" />
        <div>
          <p className="font-medium">
            {payment.credits} credits added
          </p>
          <p className="text-muted-foreground mt-1 text-pretty">
            {formatMinor(payment.amount_minor, payment.currency)} paid. The credits
            are on your balance and every change to it is listed on your dashboard.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button asChild variant="brand" size="sm">
              <Link href="/discussions">Book a discussion</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/dashboard">My sessions</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (payment.status === "failed") {
    return (
      <div className="flex items-start gap-3 text-sm">
        <XCircle className="text-destructive mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-medium">That payment didn&apos;t go through</p>
          <p className="text-muted-foreground mt-1 text-pretty">
            {payment.failure_reason ??
              "The provider turned it down. Nothing was charged and no credits were added."}
          </p>
          <Button asChild variant="outline" size="sm" className="mt-4">
            <Link href="/checkout">Try again</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 text-sm">
      <Clock className="mt-0.5 size-5 shrink-0 text-[var(--warning)]" />
      <div>
        <p className="font-medium">Still confirming</p>
        <p className="text-muted-foreground mt-1 text-pretty">
          {polls >= MAX_POLLS
            ? "This is taking longer than usual. Your credits will appear on their own once the provider confirms — you don't need to pay again. If nothing has changed in an hour, send us the payment reference below."
            : "Your bank has taken the payment; we're waiting for the provider to confirm it. Credits appear the moment it does."}
        </p>
        <p className="text-muted-foreground mt-3 font-mono text-xs break-all">
          {payment.id}
        </p>
      </div>
    </div>
  );
}

export default function CheckoutSuccessPage() {
  return (
    <div className="bg-surface-subtle min-h-full">
      <div className="mx-auto flex max-w-md flex-col px-4 py-20">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Thanks for your purchase</CardTitle>
          </CardHeader>
          <CardContent>
            <React.Suspense fallback={<Loader2 className="size-4 animate-spin" />}>
              <CheckoutSuccess />
            </React.Suspense>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
