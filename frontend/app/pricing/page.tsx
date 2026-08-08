import Link from "next/link";
import { Check } from "lucide-react";

import { Ripple } from "@/components/magicui/effects";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PACKS } from "@/lib/pricing";
import { cn } from "@/lib/utils";

export default function PricingPage() {
  return (
    <div className="relative">
      <Ripple circles={5} base={240} />

      <div className="mx-auto max-w-5xl px-4 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl tracking-tight text-balance">
            Credits, not subscriptions
          </h1>
          <p className="text-muted-foreground mt-4 text-pretty">
            One credit is one session. They don&apos;t expire, and a cancelled session
            returns the credit rather than sending you through a refund.
          </p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {PACKS.map((pack) => (
            <Card
              key={pack.name}
              className={cn(
                "relative",
                pack.highlight && "border-brand-ink/60",
              )}
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
                  <p className="text-3xl font-semibold tracking-tight">{pack.inr}</p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {pack.usd} outside India · {pack.credits} credits
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

                <Button asChild variant={pack.highlight ? "brand" : "outline"}>
                  <Link href="/register">Get started</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>

        <p className="text-muted-foreground mt-10 text-center text-sm">
          Checkout isn&apos;t wired up yet — credits are granted from the admin CLI during
          the beta.
        </p>
      </div>
    </div>
  );
}
