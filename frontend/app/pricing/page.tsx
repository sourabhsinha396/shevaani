"use client";

import * as React from "react";
import Link from "next/link";
import { Check } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { useCurrency } from "@/components/currency-provider";
import { CurrencySwitcher } from "@/components/currency-switcher";
import { Ripple } from "@/components/magicui/effects";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMinor, perSessionLabel } from "@/lib/money";
import {
  CREDITS_PER_SESSION,
  copyFor,
  priceFor,
  sessionLabel,
  sessionsFrom,
} from "@/lib/pricing";
import { usePacks } from "@/lib/use-packs";
import { cn } from "@/lib/utils";

const FAQ = [
  {
    q: "Do they expire?",
    a: "No. There is no expiry date and no monthly minimum — a pack bought today is still bookable next year.",
  },
  {
    q: "Group or one-to-one?",
    a: "Either. One session from your balance books one of either, so the format is your choice to make rather than a price to weigh up. The occasional session prices itself differently, and says so before you book.",
  },
  {
    q: "What if a session gets cancelled?",
    a: "It comes straight back to your balance — including when we auto-cancel a discussion that hasn't filled two hours before it starts.",
  },
  {
    q: "Can I get money back instead?",
    a: "No — everything we return, we return to your balance. It never expires, so an unused session keeps its value until you book with it. The cancellation policy sets out exactly what comes back and when.",
  },
];

export default function PricingPage() {
  const { user } = useAuth();
  // Detected from the browser's timezone, and the same value checkout will use.
  // Unlike the old toggle, this is a claim about what somebody will be charged,
  // which is why the switcher persists rather than resetting on navigation.
  const { currency } = useCurrency();
  const { packs, loading, error } = usePacks();

  return (
    <div className="relative">
      <Ripple circles={5} base={240} />

      <div className="mx-auto max-w-5xl px-4 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl tracking-tight text-balance">
            Sessions, not subscriptions
          </h1>
          <p className="text-muted-foreground mt-4 text-pretty">
            Buy and spend them on group discussions or one-to-ones,
            whichever you feel like.
          </p>

          <div className="mt-8 flex items-center justify-center gap-3">
            <span className="text-muted-foreground text-sm">Show prices in</span>
            <CurrencySwitcher />
          </div>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {loading &&
            // Three cards' worth of space, so the FAQ below doesn't jump up and
            // then back down when the prices land.
            [0, 1, 2].map((i) => (
              <Card key={i} aria-hidden className="animate-pulse">
                <CardContent className="h-72" />
              </Card>
            ))}

          {packs?.map((pack) => {
            const copy = copyFor(pack.slug);
            const price = priceFor(pack, currency);
            return (
              <Card
                key={pack.id}
                className={cn("relative", copy.highlight && "border-brand-ink/60")}
              >
                {copy.highlight && (
                  <Badge className="absolute -top-2.5 left-6">Most popular</Badge>
                )}
                <CardHeader>
                  <CardTitle>{pack.name}</CardTitle>
                  <p className="text-muted-foreground text-sm text-pretty">{copy.blurb}</p>
                </CardHeader>
                <CardContent className="flex flex-col gap-6">
                  <div>
                    <p className="text-3xl font-semibold tracking-tight tabular-nums">
                      {formatMinor(price.minor, price.currency)}
                    </p>
                    <p className="text-muted-foreground mt-1 text-sm">
                      {sessionLabel(sessionsFrom(pack.credits))}
                      {/* The unit price is the same number as the price on a
                          one-session pack, and saying it twice reads as a
                          mistake rather than as reassurance. */}
                      {sessionsFrom(pack.credits) > 1 && (
                        <>
                          {" · works out at "}
                          {perSessionLabel(
                            price.minor,
                            pack.credits,
                            price.currency,
                            CREDITS_PER_SESSION,
                          )}{" "}
                          each
                        </>
                      )}
                    </p>
                  </div>

                  <ul className="flex flex-col gap-2 text-sm">
                    {copy.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2">
                        <Check className="text-brand-ink mt-0.5 size-4 shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>

                  <Button asChild variant={copy.highlight ? "brand" : "outline"}>
                    <Link
                      href={
                        user
                          ? `/checkout?pack=${pack.slug}`
                          : `/register?next=${encodeURIComponent(
                              `/checkout?pack=${pack.slug}`,
                            )}`
                      }
                    >
                      {user ? "Buy sessions" : "Get started"}
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {error && (
          <p className="text-destructive mt-6 text-center text-sm text-pretty">
            Prices couldn&apos;t be loaded just now. {error}
          </p>
        )}

        <div className="mt-16 grid gap-8 sm:grid-cols-2">
          {FAQ.map((item) => (
            <div key={item.q}>
              <h2 className="text-base font-medium">{item.q}</h2>
              <p className="text-muted-foreground mt-2 text-sm text-pretty">{item.a}</p>
            </div>
          ))}
        </div>

        <p className="text-muted-foreground mt-12 text-center text-sm text-pretty">
          Prices are quoted in your local currency and charged in it — the amount
          shown here is the amount taken. Full terms are in the{" "}
          <Link href="/refunds" className="underline underline-offset-4">
            cancellation and credit policy
          </Link>{" "}
          and the{" "}
          <Link href="/terms" className="underline underline-offset-4">terms of service</Link>.
        </p>
      </div>
    </div>
  );
}
