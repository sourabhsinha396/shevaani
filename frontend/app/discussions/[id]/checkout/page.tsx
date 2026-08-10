"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  CalendarClock,
  Check,
  Loader2,
  Ticket,
  Users,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { useCurrency } from "@/components/currency-provider";
import { PayMethods } from "@/components/pay-methods";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { formatMinor, perSessionLabel } from "@/lib/money";
import { clearPendingBooking, writePendingBooking } from "@/lib/pending-booking";
import { asRazorpayPayload, openRazorpayCheckout } from "@/lib/razorpay";
import {
  CREDITS_PER_SESSION,
  priceFor,
  sessionBalanceLabel,
  sessionLabel,
  sessionsFrom,
} from "@/lib/pricing";
import type {
  BillingProfile,
  CreditPack,
  DiscussionSession,
  PaymentProvider,
} from "@/lib/types";
import {
  cn,
  durationMinutes,
  formatDateTime,
  increasedSeatsTaken,
  relativeToNow,
} from "@/lib/utils";

/**
 * Checkout for one group discussion.
 *
 * Separate from `/checkout` on purpose. That page sells credits and treats the
 * thing being booked as a footnote; here the session *is* the purchase, so it
 * leads — a learner should be able to check the day, the topic and who is
 * hosting before they spend anything.
 *
 * Two shapes, decided by the balance:
 *
 * * **Enough credits** — one confirm button. No money moves and no provider is
 *   involved; the credits were bought earlier.
 * * **Short** — the packs appear inline, so a first booking is one page rather
 *   than a detour through `/checkout` and back.
 *
 * A full session is a third case that costs nothing: the waitlist is free to
 * join and charges on promotion, so it never asks for a card.
 */
export default function DiscussionCheckoutPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading: authLoading, credits, refresh } = useAuth();
  const { currency } = useCurrency();

  const [session, setSession] = React.useState<DiscussionSession | null>(null);
  const [profile, setProfile] = React.useState<BillingProfile | null>(null);
  const [packs, setPacks] = React.useState<CreditPack[]>([]);
  const [selected, setSelected] = React.useState<string | null>(null);

  const [loading, setLoading] = React.useState(true);
  const [booking, setBooking] = React.useState(false);
  // Which provider is mid-flight, not just "something is" — two buttons share
  // this and only the pressed one should spin.
  const [paying, setPaying] = React.useState<PaymentProvider | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (authLoading || user) return;
    router.replace(`/login?next=${encodeURIComponent(`/discussions/${id}/checkout`)}`);
  }, [authLoading, user, router, id]);

  // The session is public, so it loads for anyone; the billing half needs an
  // account and is fetched separately rather than blocking the summary on it.
  React.useEffect(() => {
    api
      .getSession(id)
      .then(setSession)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  React.useEffect(() => {
    if (!user) return;
    Promise.all([api.billingProfile(currency), api.creditPacks()])
      .then(([billing, list]) => {
        setProfile(billing);
        setPacks(list);
        // Starter, not the "most popular" pack the pricing page pushes. Someone
        // who arrived here came to book *this* discussion, and the smallest
        // pack covers it exactly — defaulting to a bigger one preselects an
        // upsell they did not ask for. The list is ordered by size, so `[0]` is
        // the right fallback if the slug ever changes.
        setSelected(
          (previous) =>
            previous ?? (list.find((p) => p.slug === "starter") ?? list[0])?.id ?? null,
        );
      })
      .catch((e: Error) => setError(e.message));
    // Re-runs on a currency switch because the *provider* can change with it —
    // rupees lead with Razorpay, everything else with Stripe.
  }, [user, currency]);

  const held =
    session?.my_booking_status === "confirmed" ||
    session?.my_booking_status === "waitlisted";

  // Already in — nothing to check out. Send them where the join link lives
  // rather than showing a buy button for a seat they hold.
  React.useEffect(() => {
    if (held) router.replace(`/discussions/${id}`);
  }, [held, router, id]);

  const pack = packs.find((p) => p.id === selected) ?? null;
  // What the server resolved, not what the browser guessed — it is what the
  // order will actually be opened in.
  const active = profile?.currency ?? currency;
  const price = pack ? priceFor(pack, active) : null;

  /** Spends the credits and takes the seat. No payment round trip. */
  async function confirm() {
    setBooking(true);
    setError(null);
    try {
      await api.bookSession(id);
      clearPendingBooking();
      await refresh();
      // Back to the session, which reads the booking state itself and switches
      // to the join button — no need to tell it what just happened.
      router.push(`/discussions/${id}`);
    } catch (e) {
      const failure = e as ApiError;
      setError(
        failure.code === "insufficient_credits"
          ? "You don't have enough left for this seat — pick a pack below and we'll bring you straight back."
          : failure.message,
      );
      // The balance may have moved under us — a promotion from another
      // waitlist, a refund. Re-read it so the page stops offering a button the
      // API just refused.
      await refresh();
    } finally {
      setBooking(false);
    }
  }

  async function pay(provider: PaymentProvider) {
    if (!pack) return;
    setPaying(provider);
    setError(null);
    try {
      // Remembered before we leave: the provider returns to a URL that knows
      // about a payment and nothing about this session.
      writePendingBooking({ kind: "discussion", sessionId: id });
      const checkout = await api.startCheckout(pack.id, active, provider);

      // Stripe hosts its own page; leave the site and let the success page
      // settle it on the way back.
      if (checkout.redirect_url) {
        window.location.assign(checkout.redirect_url);
        return;
      }

      const payload = asRazorpayPayload(checkout.client_payload);
      if (!payload) {
        setError("That payment couldn't be opened. Your card has not been charged.");
        setPaying(null);
        return;
      }

      await openRazorpayCheckout(payload, {
        onSuccess: (result) => {
          // The signature is only available here, so it is spent here. The
          // success page verifies again on arrival — idempotent, and the
          // authority is the server's own fetch of the order either way.
          void api
            .verifyPayment(checkout.payment_id, {
              razorpay_payment_id: result.razorpay_payment_id,
              razorpay_signature: result.razorpay_signature,
            })
            .catch(() => {
              // Swallowed on purpose: the money has moved and the success page
              // is about to ask again. Blocking the redirect on this call would
              // strand a paid buyer on a checkout screen.
            })
            .finally(() => {
              router.push(`/checkout/success?payment=${checkout.payment_id}`);
            });
        },
        // Closing the modal is not an error — nothing was charged, and the
        // order stays open for another attempt.
        onDismiss: () => setPaying(null),
      });
      // Left spinning deliberately: the modal is up, and the handlers above own
      // what happens next.
      return;
    } catch (e) {
      setError((e as Error).message);
      setPaying(null);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  if (!session) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-24 text-center">
        <p className="text-muted-foreground">
          {error ?? "That session could not be found."}
        </p>
        <Button asChild variant="outline" className="mt-6">
          <Link href="/discussions">Back to discussions</Link>
        </Button>
      </div>
    );
  }

  if (held) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> You already have a place — taking you back…
      </div>
    );
  }

  const bookable = session.status === "published" && new Date(session.starts_at) > new Date();
  const waitlist = session.is_full;
  // A waitlisted place is free; credits are taken on promotion, so a short
  // balance is not a reason to keep somebody out of the queue.
  const cost = waitlist ? 0 : session.price_credits;
  const short = Math.max(0, cost - credits);
  const canConfirm = bookable && short === 0;
  // Rounded up and floored at one: the shortfall is quoted in sessions like
  // everything else, and a half-session gap still means one more to buy.
  const shortSessions = short > 0 ? Math.max(1, Math.ceil(short / CREDITS_PER_SESSION)) : 0;

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <Button asChild variant="ghost" size="sm" className="mb-6 -ml-3">
        <Link href={`/discussions/${id}`}>
          <ArrowLeft className="size-4" /> Back to the discussion
        </Link>
      </Button>

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl tracking-tight text-balance">
            {waitlist ? "Join the waitlist" : "Confirm your seat"}
          </h1>
          <p className="text-muted-foreground mt-2 text-pretty">
            {waitlist
              ? "Every seat is taken. Joining costs nothing — you're charged only if a place frees up and you move in."
              : `${sessionLabel(sessionsFrom(cost))} from your balance takes this seat. Cancel more than 12 hours before it starts and it comes back.`}
          </p>
        </div>
        {/* Currency lives in the order summary now, beside the buttons it
            actually governs — see `PayMethods`. */}
        <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-sm">
          <Ticket className="size-3.5" /> {sessionBalanceLabel(credits)} left
        </Badge>
      </header>

      <div className="mt-8 grid gap-6 md:grid-cols-[1fr_20rem]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                {session.status === "cancelled" && (
                  <Badge variant="destructive">Cancelled</Badge>
                )}
                {waitlist && <Badge variant="warning">Full</Badge>}
              </div>
              <CardTitle className="mt-3 text-xl text-balance">{session.title}</CardTitle>
              {session.topic && (
                <p className="text-muted-foreground text-sm">{session.topic}</p>
              )}
            </CardHeader>
            <CardContent className="flex flex-col gap-4 text-sm">
              {session.description && (
                <p className="leading-relaxed text-pretty">{session.description}</p>
              )}

              <div className="border-border/60 flex flex-col gap-3 border-t pt-4">
                <div>
                  <p className="flex items-center gap-2 font-medium">
                    <CalendarClock className="size-4" />
                    {formatDateTime(session.starts_at, user?.timezone)}
                  </p>
                  <p className="text-muted-foreground mt-1 pl-6">
                    {durationMinutes(session.starts_at, session.ends_at)} minutes ·{" "}
                    {relativeToNow(session.starts_at)}
                  </p>
                </div>

                <div>
                  <p className="flex items-center gap-2 font-medium">
                    <Users className="size-4" />
                    {increasedSeatsTaken(session.seats_taken, session.max_seats)} of {session.max_seats} seats taken
                  </p>
                  <p className="text-muted-foreground mt-1 pl-6">
                  </p>
                </div>
              </div>

              <div className="text-muted-foreground border-border/60 border-t pt-4">
                Hosted by{" "}
                <span className="text-foreground font-medium">
                  {session.instructor.full_name}
                </span>
                {session.instructor.headline && <> · {session.instructor.headline}</>}
              </div>

              {session.prep_material_url && (
                <div className="border-border/60 flex items-start gap-3 border-t pt-4">
                  <BookOpen className="text-brand-ink mt-0.5 size-4 shrink-0" />
                  <p className="text-muted-foreground text-pretty">
                    There&apos;s prep material for this one. Skim it before you join — the
                    discussion assumes you have.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Only shown when there is something to buy. Somebody with credits in
              hand is one button from done and does not need a price list. */}
          {short > 0 && (
            <div className="flex flex-col gap-3">
              <h2 className="font-sans font-medium">
                You&apos;re {sessionLabel(shortSessions)} short — pick a pack
              </h2>
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
                            chosen
                              ? "border-brand-ink bg-brand text-brand-foreground"
                              : "border-border",
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
          )}
        </div>

        <Card className="h-fit md:sticky md:top-24">
          <CardHeader>
            <CardTitle className="text-base">
              {canConfirm ? "Ready to book" : "Order summary"}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-sm">
            {!bookable && (
              <p className="text-muted-foreground text-pretty">
                {session.status === "cancelled"
                  ? "This session was cancelled, so there's nothing left to book."
                  : "This session has already started."}
              </p>
            )}

            {bookable && canConfirm && (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    {waitlist ? "Waitlist place" : "This session"}
                  </span>
                  <span>{cost === 0 ? "Free" : sessionLabel(sessionsFrom(cost))}</span>
                </div>
                <div className="border-border/60 flex justify-between border-t pt-4">
                  <span className="text-muted-foreground">Balance afterwards</span>
                  <span className="tabular-nums">{sessionBalanceLabel(credits - cost)}</span>
                </div>

                {error && <p className="text-destructive text-pretty">{error}</p>}

                <Button variant="brand" disabled={booking} onClick={() => void confirm()}>
                  {booking && <Loader2 className="size-4 animate-spin" />}
                  {waitlist ? "Join the waitlist" : "Confirm booking"}
                </Button>

                <p className="text-muted-foreground text-xs text-pretty">
                  {waitlist
                    ? "We'll email you if a seat frees up, and take the session from your balance then. Nothing is charged now."
                    : "Cancel more than 12 hours before it starts and it goes back on your balance."}
                </p>
              </>
            )}

            {bookable && short > 0 && (
              <>
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
                  </>
                ) : (
                  <p className="text-muted-foreground">Pick a pack.</p>
                )}

                {error && <p className="text-destructive text-pretty">{error}</p>}

                <PayMethods
                  profile={profile}
                  amountLabel={price ? formatMinor(price.minor, price.currency) : null}
                  disabled={!pack}
                  busyProvider={paying}
                  onPay={(provider) => void pay(provider)}
                />

                <p className="text-muted-foreground text-xs text-pretty">
                  Your payment is securely processed by our providers. We card details never reach our servers.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
