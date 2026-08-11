"use client";

import Link from "next/link";
import { Check } from "lucide-react";

import { useCurrency } from "@/components/currency-provider";
import { CurrencySwitcher } from "@/components/currency-switcher";
import { Reveal, SpotlightCard } from "@/components/magicui/effects";
import { Badge } from "@/components/ui/badge";
import { BorderBeam } from "@/components/ui/border-beam";
import { Button } from "@/components/ui/button";
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

export function Pricing() {
  // Shared with /pricing and /checkout through the sitewide provider, so a
  // visitor who switches here still sees their currency two clicks later.
  const { currency } = useCurrency();
  const { packs, loading } = usePacks();

  return (
    <section className="section bg-surface-subtle">
      <div className="container-page">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="eyebrow mb-5">Pricing</p>
          <h2 className="text-4xl text-balance">
            One time payments, no <span className="line-through">subscriptions</span>.
          </h2>
          <p className="text-muted-foreground mt-5 text-pretty">
            Buy a few and spend them on group discussions or 1:1 sessions.
          </p>

          {/* Guessed from your timezone. The switcher is here because the guess
              is wrong for anyone travelling, and the price is the thing on this
              page most worth being able to correct. */}
          <div className="mt-8 flex items-center justify-center gap-3">
            <span className="text-muted-foreground text-sm">Prices in</span>
            <CurrencySwitcher />
          </div>
        </Reveal>

        <div className="mt-12 grid items-start gap-6 md:grid-cols-3">
          {loading &&
            [0, 1, 2].map((i) => (
              <div
                key={i}
                aria-hidden
                className="border-border/60 bg-card h-96 animate-pulse rounded-xl border"
              />
            ))}

          {packs?.map((pack, i) => {
            const copy = copyFor(pack.slug);
            const price = priceFor(pack, currency);
            return (
              <Reveal key={pack.id} delay={i * 80}>
                <SpotlightCard
                  className={cn(
                    "bg-card relative h-full rounded-xl border p-6",
                    copy.highlight
                      ? "border-brand-ink/50 md:-mt-4 md:pb-10"
                      : "border-border/60",
                  )}
                  overlay={
                    copy.highlight && (
                      <BorderBeam
                        size={120}
                        duration={8}
                        colorFrom="var(--brand)"
                        colorTo="var(--brand-ink)"
                      />
                    )
                  }
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium">{pack.name}</h3>
                    {copy.highlight && <Badge>Most popular</Badge>}
                  </div>
                  <p className="text-muted-foreground mt-1.5 text-sm text-pretty">
                    {copy.blurb}
                  </p>

                  <div className="mt-6 flex items-baseline gap-2">
                    <span className="font-heading text-4xl tracking-tight tabular-nums">
                      {formatMinor(price.minor, price.currency)}
                    </span>
                    <span className="text-muted-foreground text-sm">
                      {sessionLabel(sessionsFrom(pack.credits))}
                    </span>
                  </div>
                  {/* Skipped on a one-session pack, where the unit price is the
                      price already on screen. */}
                  {sessionsFrom(pack.credits) > 1 && (
                    <p className="text-muted-foreground mt-1 text-xs">
                      Works out at{" "}
                      {perSessionLabel(
                        price.minor,
                        pack.credits,
                        price.currency,
                        CREDITS_PER_SESSION,
                      )}{" "}
                      a session
                    </p>
                  )}

                  <ul className="mt-6 flex flex-col gap-2.5 text-sm">
                    {copy.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2">
                        <Check className="text-brand-ink mt-0.5 size-4 shrink-0" />
                        <span className="text-pretty">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    asChild
                    className="mt-7 w-full"
                    variant={copy.highlight ? "brand" : "outline"}
                  >
                    <Link href="/register">Get started</Link>
                  </Button>
                </SpotlightCard>
              </Reveal>
            );
          })}
        </div>

        <p className="text-muted-foreground mt-8 text-center text-sm">
          Talking to people is the only thing that improves communication ·{" "}
          <Link href="/pricing" className="text-foreground underline-offset-4 hover:underline">
            full pricing details
          </Link>
        </p>
      </div>
    </section>
  );
}
