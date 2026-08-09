"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Check, Coins, Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatMinor, perCreditLabel } from "@/lib/money";
import type { BillingProfile, CreditPack } from "@/lib/types";
import { cn } from "@/lib/utils";

const PROVIDER_LABEL: Record<string, string> = {
  razorpay: "Razorpay",
  stripe: "Stripe",
};

/**
 * Sells packs, never a single session (PLAN decision 9).
 *
 * Two things this page deliberately does not do:
 *
 * - **Guess the currency or the provider.** Both come from `/billing/profile`,
 *   which derives them from the country on the account. A page that guessed
 *   from the browser would show a price the checkout then refuses.
 * - **Grant anything.** It opens an order and hands the buyer to the provider.
 *   Credits appear when the webhook says the money moved.
 */
function Checkout() {
  const { user, loading: authLoading, credits } = useAuth();
  const router = useRouter();
  const params = useSearchParams();

  const [profile, setProfile] = React.useState<BillingProfile | null>(null);
  const [packs, setPacks] = React.useState<CreditPack[]>([]);
  const [selected, setSelected] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/checkout");
  }, [authLoading, user, router]);

  React.useEffect(() => {
    if (!user) return;
    Promise.all([api.billingProfile(), api.creditPacks()])
      .then(([billing, list]) => {
        setProfile(billing);
        setPacks(list);
        // ?pack=regular arrives from the pricing page, so the choice someone
        // already made over there is not thrown away here.
        const wanted = params.get("pack");
        const match = list.find((p) => p.slug === wanted);
        setSelected((match ?? list.find((p) => p.slug === "regular") ?? list[0])?.id ?? null);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [user, params]);

  const pack = packs.find((p) => p.id === selected) ?? null;

  async function pay() {
    if (!pack) return;
    setBusy(true);
    setError(null);
    try {
      const session = await api.startCheckout(pack.id);
      if (session.redirect_url) {
        // Stripe hosts its own page; leave the site.
        window.location.assign(session.redirect_url);
        return;
      }
      // Razorpay returns a payload for a client-side modal instead. Until that
      // adapter is real (ITC-52) there is nothing to open, so say so rather
      // than leaving the buyer looking at a spinner.
      setError(
        "This provider's checkout isn't finished yet. Your order was recorded but no payment was taken.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-16">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl tracking-tight">Buy credits</h1>
          <p className="text-muted-foreground mt-2 text-pretty">
            One credit books one session. They don&apos;t expire.
          </p>
        </div>
        <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-sm">
          <Coins className="size-3.5" /> {credits} now
        </Badge>
      </header>

      <div className="mt-10 grid gap-6 md:grid-cols-[1fr_20rem]">
        <div className="flex flex-col gap-3">
          {packs.map((option) => {
            const active = option.id === selected;
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={active}
                onClick={() => setSelected(option.id)}
                className={cn(
                  "border-border/60 bg-card cursor-pointer rounded-xl border p-5 text-left transition-colors",
                  active ? "border-brand-ink" : "hover:border-border",
                )}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "grid size-4 place-items-center rounded-full border",
                        active ? "border-brand-ink bg-brand text-brand-foreground" : "border-border",
                      )}
                    >
                      {active && <Check className="size-3" />}
                    </span>
                    <span className="font-medium">{option.name}</span>
                    <span className="text-muted-foreground text-sm">
                      {option.credits} credits
                    </span>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-semibold tracking-tight">
                      {formatMinor(option.amount_minor, option.currency)}
                    </p>
                    <p className="text-muted-foreground text-xs">
                      {perCreditLabel(option.amount_minor, option.credits, option.currency)} a
                      session
                    </p>
                  </div>
                </div>
              </button>
            );
          })}

          {packs.length === 0 && (
            <Card>
              <CardContent className="text-muted-foreground py-12 text-center text-sm">
                No packs are on sale right now.
              </CardContent>
            </Card>
          )}
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">Order summary</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-sm">
            {pack ? (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{pack.name}</span>
                  <span>{pack.credits} credits</span>
                </div>
                <div className="border-border/60 flex justify-between border-t pt-4 text-base">
                  <span>Total</span>
                  <span className="font-semibold">
                    {formatMinor(pack.amount_minor, pack.currency)}
                  </span>
                </div>
                <p className="text-muted-foreground text-xs text-pretty">
                  Balance after this purchase: {credits + pack.credits} credits.
                  {profile && (
                    <>
                      {" "}
                      Payment is handled by{" "}
                      {PROVIDER_LABEL[profile.provider] ?? profile.provider}, in{" "}
                      {pack.currency}. We never see your card details.
                    </>
                  )}
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">Pick a pack.</p>
            )}

            {profile && !profile.provider_ready && (
              <div className="border-warning/30 bg-warning/10 flex items-start gap-2 rounded-lg border p-3 text-xs">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-[var(--warning)]" />
                <p className="text-pretty">
                  {PROVIDER_LABEL[profile.provider] ?? profile.provider} isn&apos;t
                  connected yet, so payment can&apos;t be taken. Ask us for credits
                  through the <Link href="/contact" className="underline">contact form</Link> in
                  the meantime.
                </p>
              </div>
            )}

            {error && <p className="text-destructive text-sm text-pretty">{error}</p>}

            <Button
              variant="brand"
              disabled={!pack || busy || !profile?.provider_ready}
              onClick={() => void pay()}
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              {pack ? `Pay ${formatMinor(pack.amount_minor, pack.currency)}` : "Pay"}
            </Button>

            <p className="text-muted-foreground text-xs text-pretty">
              Unused credits are refundable for 14 days — see the{" "}
              <Link href="/refunds" className="underline underline-offset-4">
                refund policy
              </Link>
              .
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function CheckoutPage() {
  return (
    // `?pack=` is read with useSearchParams, which needs a boundary above it.
    <React.Suspense
      fallback={
        <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
          <Loader2 className="size-4 animate-spin" /> Loading…
        </div>
      }
    >
      <Checkout />
    </React.Suspense>
  );
}
