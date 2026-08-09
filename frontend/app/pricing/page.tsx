"use client";

import * as React from "react";
import Link from "next/link";
import { Check } from "lucide-react";

import { Ripple } from "@/components/magicui/effects";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/components/auth-provider";
import { PACKS, perCredit, type Currency } from "@/lib/pricing";
import { cn } from "@/lib/utils";

/* Prices are listed per currency and never converted — a ₹ list and a $ list,
   matching the `credit_packs` table. The toggle picks which list you are
   reading; it does not do arithmetic. */
const CURRENCIES: Array<{ id: Currency; label: string; note: string }> = [
  { id: "inr", label: "₹ INR", note: "Checkout in India runs through Razorpay." },
  { id: "usd", label: "$ USD", note: "Checkout outside India runs through Stripe." },
];

const FAQ = [
  {
    q: "Do credits expire?",
    a: "No. There is no expiry date on a credit and no monthly minimum — a pack bought today is still spendable next year.",
  },
  {
    q: "What does one credit buy?",
    a: "One session. Group discussions are one credit unless the session says otherwise; one-to-one sessions are priced per session and shown before you book.",
  },
  {
    q: "What if a session gets cancelled?",
    a: "The credit comes straight back to your balance — including when we auto-cancel a discussion that hasn't filled two hours before it starts.",
  },
  {
    q: "Can I get money back instead?",
    a: "Unused credits are refundable to the original payment method for 14 days after purchase. The refund policy sets out exactly how.",
  },
];

export default function PricingPage() {
  const { user } = useAuth();
  // ₹ by default: the country on the account decides the real checkout
  // currency, and that isn't exposed to the client, so this is a reading
  // preference rather than a claim about what someone will be charged.
  const [currency, setCurrency] = React.useState<Currency>("inr");

  const active = CURRENCIES.find((c) => c.id === currency)!;

  return (
    <div className="relative">
      <Ripple circles={5} base={240} />

      <div className="mx-auto max-w-5xl px-4 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl tracking-tight text-balance">
            Credits, not subscriptions
          </h1>
          <p className="text-muted-foreground mt-4 text-pretty">
            One credit is one session. They don&apos;t expire, and a cancelled
            session returns the credit rather than sending you through a refund.
          </p>

          <div
            role="group"
            aria-label="Currency"
            className="border-border/60 mx-auto mt-8 inline-flex rounded-full border p-1"
          >
            {CURRENCIES.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-pressed={currency === option.id}
                onClick={() => setCurrency(option.id)}
                className={cn(
                  "cursor-pointer rounded-full px-4 py-1.5 text-sm transition-colors",
                  currency === option.id
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="text-muted-foreground mt-3 text-xs">{active.note}</p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {PACKS.map((pack) => (
            <Card
              key={pack.name}
              className={cn("relative", pack.highlight && "border-brand-ink/60")}
            >
              {pack.highlight && (
                <Badge className="absolute -top-2.5 left-6">Most popular</Badge>
              )}
              <CardHeader>
                <CardTitle>{pack.name}</CardTitle>
                <p className="text-muted-foreground text-sm text-pretty">{pack.blurb}</p>
              </CardHeader>
              <CardContent className="flex flex-col gap-6">
                <div>
                  <p className="text-3xl font-semibold tracking-tight">
                    {pack[currency]}
                  </p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {pack.credits} credits · works out at {perCredit(pack, currency)} a
                    session
                  </p>
                </div>

                <ul className="flex flex-col gap-2 text-sm">
                  {pack.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <Check className="text-brand-ink mt-0.5 size-4 shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>

                {/* Signed in, this is a real purchase; signed out it can't be,
                    because the price depends on the country on the account. */}
                <Button asChild variant={pack.highlight ? "brand" : "outline"}>
                  <Link
                    href={
                      user
                        ? `/checkout?pack=${pack.name.toLowerCase()}`
                        : `/register?next=${encodeURIComponent(
                            `/checkout?pack=${pack.name.toLowerCase()}`,
                          )}`
                    }
                  >
                    {user ? "Buy credits" : "Get started"}
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="mt-16 grid gap-8 sm:grid-cols-2">
          {FAQ.map((item) => (
            <div key={item.q}>
              <h2 className="text-base font-medium">{item.q}</h2>
              <p className="text-muted-foreground mt-2 text-sm text-pretty">{item.a}</p>
            </div>
          ))}
        </div>

        <p className="text-muted-foreground mt-12 text-center text-sm text-pretty">
          Prices are shown per currency and are not converted at checkout. Full
          terms are in the <Link href="/refunds" className="underline underline-offset-4">refund
          and cancellation policy</Link> and the{" "}
          <Link href="/terms" className="underline underline-offset-4">terms of service</Link>.
        </p>
      </div>
    </div>
  );
}
