"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CalendarClock, Check, Loader2, Ticket } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { useCurrency } from "@/components/currency-provider";
import { PayMethods } from "@/components/pay-methods";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatMinor, perSessionLabel } from "@/lib/money";
import {
  ONE_ON_ONE_DURATIONS,
  type PendingOneOnOne,
  checkoutHref,
  clearPendingBooking,
  writePendingBooking,
} from "@/lib/pending-booking";
import { asRazorpayPayload, openRazorpayCheckout } from "@/lib/razorpay";
import {
  CREDITS_PER_SESSION,
  priceFor,
  sessionBalanceLabel,
  sessionLabel,
  sessionsFrom,
} from "@/lib/pricing";
import {
  BOOKING_TIMEZONE,
  detectBookingZone,
  zoneAbbreviation,
} from "@/lib/timezones";
import type { BillingProfile, CreditPack, PaymentProvider } from "@/lib/types";
import { cn } from "@/lib/utils";

function readSlot(params: Pick<URLSearchParams, "get">): PendingOneOnOne | null {
  const slot = params.get("slot");
  if (!slot || Number.isNaN(Date.parse(slot))) return null;
  const duration = Number(params.get("duration"));
  return {
    kind: "one_on_one",
    slot,
    duration: duration > 0 ? duration : ONE_ON_ONE_DURATIONS[0],
  };
}

/**
 * Sells packs, never a single session (PLAN decision 9).
 *
 * The currency is the one the browser detected, shared with the pricing page
 * through the sitewide provider — so the number here is the number that was
 * quoted two clicks ago. It is sent to `/billing/profile` and `/billing/checkout`
 * as a code and never as an amount: the server re-quotes from the pack's USD
 * base price, so the displayed figure is a claim to be confirmed, not an input.
 *
 * What this page still does not do is **grant anything**. It opens an order and
 * hands the buyer to the provider. Credits appear when the webhook says the
 * money moved.
 */
function Checkout() {
  const { user, loading: authLoading, credits, refresh } = useAuth();
  const { currency } = useCurrency();
  const router = useRouter();
  const params = useSearchParams();

  const [profile, setProfile] = React.useState<BillingProfile | null>(null);
  const [packs, setPacks] = React.useState<CreditPack[]>([]);
  const [selected, setSelected] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  // Which provider is mid-flight — two buttons share this and only the pressed
  // one should spin.
  const [busy, setBusy] = React.useState<PaymentProvider | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  // A one-to-one chosen on /one-on-one, carried here in the URL. Absent when
  // somebody is just topping up, which is the page's original job.
  const pending = React.useMemo(() => readSlot(params), [params]);
  const [booking, setBooking] = React.useState(false);
  const [timeZone, setTimeZone] = React.useState(BOOKING_TIMEZONE);
  React.useEffect(() => setTimeZone(detectBookingZone()), []);

  React.useEffect(() => {
    if (authLoading || user) return;
    // Keep the slot through the sign-in detour, or the learner comes back to a
    // page that has forgotten what they picked.
    const here = pending ? checkoutHref(pending) : "/checkout";
    router.replace(`/login?next=${encodeURIComponent(here)}`);
  }, [authLoading, user, router, pending]);

  React.useEffect(() => {
    if (!user) return;
    Promise.all([api.billingProfile(currency), api.creditPacks()])
      .then(([billing, list]) => {
        setProfile(billing);
        setPacks(list);
        // ?pack=regular arrives from the pricing page, so the choice someone
        // already made over there is not thrown away here.
        const wanted = params.get("pack");
        const match = list.find((p) => p.slug === wanted);
        setSelected(
          (previous) =>
            previous ??
            (match ?? list.find((p) => p.slug === "regular") ?? list[0])?.id ??
            null,
        );
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // Re-runs on a currency switch because the *provider* can change with it —
    // rupees lead with Razorpay, everything else with Stripe. The pack prices do
    // not need refetching; each row already carries every currency.
  }, [user, params, currency]);

  const pack = packs.find((p) => p.id === selected) ?? null;
  // `profile.currency` is what the server resolved, which is USD if it does not
  // sell in what the browser detected. Trusting it over the local guess is what
  // keeps the button from promising a price the order will not be opened at.
  const active = profile?.currency ?? currency;
  const price = pack ? priceFor(pack, active) : null;

  /** Spends a credit and creates the session. The instructor is chosen by the
   *  server — the learner picked an hour, not a person. */
  async function confirmBooking() {
    if (!pending) return;
    setBooking(true);
    setError(null);
    try {
      await api.bookOneOnOne({
        starts_at: pending.slot,
        duration_minutes: pending.duration,
      });
      clearPendingBooking();
      await refresh();
      router.push("/dashboard");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBooking(false);
    }
  }

  async function pay(provider: PaymentProvider) {
    if (!pack) return;
    setBusy(provider);
    setError(null);
    try {
      if (pending) writePendingBooking(pending);
      const session = await api.startCheckout(pack.id, active, provider);

      if (session.redirect_url) {
        // Stripe hosts its own page; leave the site.
        window.location.assign(session.redirect_url);
        return;
      }

      // Razorpay keeps the buyer here and opens a modal over the page.
      const payload = asRazorpayPayload(session.client_payload);
      if (!payload) {
        setError("That payment couldn't be opened. Your card has not been charged.");
        setBusy(null);
        return;
      }

      await openRazorpayCheckout(payload, {
        onSuccess: (result) => {
          // Spent here because the signature exists nowhere else. The success
          // page verifies again on arrival, which is idempotent.
          void api
            .verifyPayment(session.payment_id, {
              razorpay_payment_id: result.razorpay_payment_id,
              razorpay_signature: result.razorpay_signature,
            })
            .catch(() => {
              // The money has moved and the success page will ask again;
              // blocking on this would strand a paid buyer on the checkout.
            })
            .finally(() => {
              router.push(`/checkout/success?payment=${session.payment_id}`);
            });
        },
        onDismiss: () => setBusy(null),
      });
      // The modal owns what happens next.
      return;
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  const slotLabel = pending
    ? new Intl.DateTimeFormat("en-GB", {
        weekday: "long",
        day: "numeric",
        month: "long",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
        timeZone,
      }).format(new Date(pending.slot))
    : null;

  // The one case that needs no payment at all: the credits are already bought.
  const bookNow = pending !== null && credits >= CREDITS_PER_SESSION;

  return (
    <div className="mx-auto max-w-4xl px-4 py-16">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl tracking-tight">
            {pending ? "Confirm your session" : "Buy sessions"}
          </h1>
          <p className="text-muted-foreground mt-2 text-pretty">
            {pending
              ? "One session from your balance books it. We'll match you with an instructor who's free."
              : "Use them on group discussions or one-to-ones. They don't expire."}
          </p>
        </div>
        {/* Currency sits in the order summary now, beside the buttons it
            actually governs — see `PayMethods`. */}
        <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-sm">
          <Ticket className="size-3.5" /> {sessionBalanceLabel(credits)} left
        </Badge>
      </header>

      {pending && (
        <Card className="mt-8">
          <CardContent className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <CalendarClock className="text-muted-foreground mt-0.5 size-5 shrink-0" />
              <div>
                <p className="font-medium">{slotLabel}</p>
                <p className="text-muted-foreground mt-1 text-sm">
                  {pending.duration} minutes, one to one · times in{" "}
                  {zoneAbbreviation(timeZone)}
                </p>
              </div>
            </div>
            <Button asChild variant="outline" size="sm">
              <Link href="/one-on-one">Change time</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {bookNow && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-base">Ready to book</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">This booking</span>
              <span>1 session</span>
            </div>
            <div className="border-border/60 flex justify-between border-t pt-4">
              <span className="text-muted-foreground">Balance afterwards</span>
              <span className="tabular-nums">
                {sessionBalanceLabel(credits - CREDITS_PER_SESSION)}
              </span>
            </div>

            {error && <p className="text-destructive text-pretty">{error}</p>}

            <Button variant="brand" disabled={booking} onClick={() => void confirmBooking()}>
              {booking && <Loader2 className="size-4 animate-spin" />}
              Confirm booking
            </Button>

            <p className="text-muted-foreground text-xs text-pretty">
              Cancel more than 12 hours before it starts and it goes back on
              your balance. Need more?{" "}
              <Link href="/checkout" className="underline underline-offset-4">
                Buy a pack
              </Link>
              .
            </p>
          </CardContent>
        </Card>
      )}

      {/* Hidden once the credit is already in hand — there is nothing to buy. */}
      {!bookNow && (
      <div className="mt-10 grid gap-6 md:grid-cols-[1fr_20rem]">
        <div className="flex flex-col gap-3">
          {packs.map((option) => {
            const chosen = option.id === selected;
            const optionPrice = priceFor(option, active);
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={chosen}
                onClick={() => setSelected(option.id)}
                className={cn(
                  "border-border/60 bg-card cursor-pointer rounded-xl border p-5 text-left transition-colors",
                  chosen ? "border-brand-ink" : "hover:border-border",
                )}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "grid size-4 place-items-center rounded-full border",
                        chosen ? "border-brand-ink bg-brand text-brand-foreground" : "border-border",
                      )}
                    >
                      {chosen && <Check className="size-3" />}
                    </span>
                    <span className="font-medium">{option.name}</span>
                    <span className="text-muted-foreground text-sm">
                      {sessionLabel(sessionsFrom(option.credits))}
                    </span>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-semibold tracking-tight tabular-nums">
                      {formatMinor(optionPrice.minor, optionPrice.currency)}
                    </p>
                    <p className="text-muted-foreground text-xs">
                      {perSessionLabel(
                        optionPrice.minor,
                        option.credits,
                        optionPrice.currency,
                        CREDITS_PER_SESSION,
                      )}{" "}
                      a session
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
            {pack && price ? (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{pack.name}</span>
                  <span>{sessionLabel(sessionsFrom(pack.credits))}</span>
                </div>
                <div className="border-border/60 flex justify-between border-t pt-4 text-base">
                  <span>Total</span>
                  <span className="font-semibold tabular-nums">
                    {formatMinor(price.minor, price.currency)}
                  </span>
                </div>
                <p className="text-muted-foreground text-xs text-pretty">
                  Balance after this purchase:{" "}
                  {sessionBalanceLabel(credits + pack.credits)}. We never see
                  your card details.
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">Pick a pack.</p>
            )}

            {error && <p className="text-destructive text-sm text-pretty">{error}</p>}

            <PayMethods
              profile={profile}
              amountLabel={price ? formatMinor(price.minor, price.currency) : null}
              disabled={!pack}
              busyProvider={busy}
              onPay={(provider) => void pay(provider)}
            />

            {pending && (
              <p className="text-muted-foreground text-xs text-pretty">
                We&apos;ll bring you back here to confirm{" "}
                {slotLabel?.toLowerCase()} once the payment clears. The slot is
                not held in the meantime — if somebody takes it first, what you
                bought is still yours to spend on another.
              </p>
            )}

            <p className="text-muted-foreground text-xs text-pretty">
              Sessions don&apos;t expire, and a cancelled booking puts its
              session back on your balance. We don&apos;t return money to the
              card — see the{" "}
              <Link href="/refunds" className="underline underline-offset-4">
                cancellation policy
              </Link>
              .
            </p>
          </CardContent>
        </Card>
      </div>
      )}
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
