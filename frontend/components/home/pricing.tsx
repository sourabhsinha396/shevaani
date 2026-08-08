"use client";

import * as React from "react";
import Link from "next/link";
import { Check } from "lucide-react";

import { Reveal, SpotlightCard } from "@/components/magicui/effects";
import { Badge } from "@/components/ui/badge";
import { BorderBeam } from "@/components/ui/border-beam";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PACKS, perCredit, type Currency } from "@/lib/pricing";
import { cn } from "@/lib/utils";

export function Pricing() {
  const [currency, setCurrency] = React.useState<Currency>("inr");

  return (
    <section className="section bg-surface-subtle">
      <div className="container-page">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="eyebrow mb-5">Pricing</p>
          <h2 className="text-4xl text-balance md:text-5xl">
            Credits, not subscriptions.
          </h2>
          <p className="text-muted-foreground mt-5 text-pretty">
            One credit is one session. They don&apos;t expire, and a cancelled
            session returns the credit rather than sending you through a refund.
          </p>

          {/* Two price lists, not a converter — nobody is charged an exchange
              rate they didn't choose. */}
          <Tabs
            className="mt-8 flex items-center"
            value={currency}
            onValueChange={(value) => setCurrency(value as Currency)}
          >
            <TabsList>
              <TabsTrigger value="inr">India · ₹</TabsTrigger>
              <TabsTrigger value="usd">Elsewhere · $</TabsTrigger>
            </TabsList>
          </Tabs>
        </Reveal>

        <div className="mt-12 grid items-start gap-6 md:grid-cols-3">
          {PACKS.map((pack, i) => (
            <Reveal key={pack.name} delay={i * 80}>
              <SpotlightCard
                className={cn(
                  "bg-card relative h-full rounded-xl border p-6",
                  pack.highlight
                    ? "border-brand-ink/50 md:-mt-4 md:pb-10"
                    : "border-border/60",
                )}
              >
                {pack.highlight && (
                  <BorderBeam
                    size={120}
                    duration={8}
                    colorFrom="var(--brand)"
                    colorTo="var(--brand-ink)"
                  />
                )}

                <div className="flex items-center justify-between">
                  <h3 className="font-medium">{pack.name}</h3>
                  {pack.highlight && <Badge>Most popular</Badge>}
                </div>
                <p className="text-muted-foreground mt-1.5 text-sm text-pretty">
                  {pack.blurb}
                </p>

                <div className="mt-6 flex items-baseline gap-2">
                  <span className="font-heading text-4xl tracking-tight tabular-nums">
                    {pack[currency]}
                  </span>
                  <span className="text-muted-foreground text-sm">
                    {pack.credits} credits
                  </span>
                </div>
                <p className="text-muted-foreground mt-1 text-xs">
                  Works out at {perCredit(pack, currency)} a session
                </p>

                <ul className="mt-6 flex flex-col gap-2.5 text-sm">
                  {pack.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <Check className="text-brand-ink mt-0.5 size-4 shrink-0" />
                      <span className="text-pretty">{feature}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  asChild
                  className="mt-7 w-full"
                  variant={pack.highlight ? "brand" : "outline"}
                >
                  <Link href="/register">Get started</Link>
                </Button>
              </SpotlightCard>
            </Reveal>
          ))}
        </div>

        <p className="text-muted-foreground mt-8 text-center text-sm">
          Your first discussion is free ·{" "}
          <Link href="/pricing" className="text-foreground underline-offset-4 hover:underline">
            full pricing details
          </Link>
        </p>
      </div>
    </section>
  );
}
