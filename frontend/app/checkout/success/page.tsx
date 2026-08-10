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
import { sessionLabel, sessionsFrom } from "@/lib/pricing";
import {
  type PendingBooking,
  checkoutHref,
  readPendingBooking,
} from "@/lib/pending-booking";
import type { Payment } from "@/lib/types";

//: Each attempt is a real round trip to the provider, so this is deliberately
//: short. Anything slower than half a minute is an asynchronous payment method
//: settling, and the webhook backstop is what covers those — not a longer poll.
const POLL_MS = 2500;
const MAX_POLLS = 8;

/**
 * Settles the payment rather than waiting to be told about it.
 *
 * Landing here proves the buyer has a browser and nothing else, so the page
 * hands the payment id to `/verify` and the server asks the provider what
 * actually happened. Everything shown below is that answer. Reloading is safe:
 * verify is idempotent, and a payment already credited comes back untouched.
 */
function CheckoutSuccess() {
  const params = useSearchParams();
  const { refresh } = useAuth();
  const paymentId = params.get("payment") ?? "";

  const [payment, setPayment] = React.useState<Payment | null>(null);
  const [polls, setPolls] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  // Whoever came here mid-booking picked their session before they bought
  // anything. Read after mount: session storage does not exist during the
  // server render.
  const [pending, setPending] = React.useState<PendingBooking | null>(null);
  React.useEffect(() => setPending(readPendingBooking()), []);

  // Razorpay's checkout hands these back on the way out. Absent for Stripe,
  // which redirects with nothing signed to carry. Passed through as-is — the
  // server decides what they are worth, which is: an extra barrier, never the
  // thing that grants.
  const razorpayPaymentId = params.get("razorpay_payment_id");
  const razorpaySignature = params.get("razorpay_signature");

  React.useEffect(() => {
    if (!paymentId) {
      setError("That link is missing its payment reference.");
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function check(attempt: number) {
      try {
        const next = await api.verifyPayment(paymentId, {
          ...(razorpayPaymentId ? { razorpay_payment_id: razorpayPaymentId } : {}),
          ...(razorpaySignature ? { razorpay_signature: razorpaySignature } : {}),
        });
        if (cancelled) return;
        setPayment(next);
        setPolls(attempt);

        if (next.status === "paid") {
          await refresh(); // balance in the header catches up
          return;
        }
        // `created` means the provider does not yet call it paid — an async
        // method still clearing, or the buyer abandoned the page. Ask again a
        // few times, then leave it to the webhook.
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
          <p className="font-medium">We couldn&apos;t confirm that payment</p>
          <p className="text-muted-foreground mt-1 text-pretty">{error}</p>
          <p className="text-muted-foreground mt-3 text-pretty">
            If money left your account, nothing is lost — reload this page in a
            minute, or send us the reference below.
          </p>
          <p className="text-muted-foreground mt-3 font-mono text-xs break-all">
            {paymentId}
          </p>
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
            {sessionLabel(sessionsFrom(payment.credits))} added
          </p>
          <p className="text-muted-foreground mt-1 text-pretty">
            {formatMinor(payment.amount_minor, payment.currency)} paid. They&apos;re
            on your balance and every change to it is listed on your dashboard.
            {pending &&
              (pending.kind === "discussion"
                ? " Your seat still needs taking — nothing was held while you paid."
                : " The time you picked still needs confirming — nothing was held while you paid.")}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {pending ? (
              <Button asChild variant="brand" size="sm">
                <Link href={checkoutHref(pending)}>
                  {pending.kind === "discussion"
                    ? "Finish taking your seat"
                    : "Finish booking your session"}
                </Link>
              </Button>
            ) : (
              <Button asChild variant="brand" size="sm">
                <Link href="/discussions">Book a discussion</Link>
              </Button>
            )}
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
              "The provider turned it down. Nothing was charged and nothing was added to your balance."}
          </p>
          <Button asChild variant="outline" size="sm" className="mt-4">
            <Link href={pending ? checkoutHref(pending) : "/checkout"}>Try again</Link>
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
            ? "The provider hasn't called this one settled yet. Your sessions appear on their own the moment it does — you don't need to pay again. If nothing has changed in an hour, send us the payment reference below."
            : "We're asking your provider to confirm the payment. Your sessions appear the moment it does."}
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
