"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CalendarClock,
  Coins,
  Loader2,
  MailWarning,
  Users,
  Video,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { BookingWithSession, LedgerEntry } from "@/lib/types";
import { durationMinutes, formatDateTime, relativeToNow } from "@/lib/utils";

/** Matches JOIN_WINDOW_BEFORE_MINUTES on the API. */
const JOIN_OPENS_MINUTES_BEFORE = 15;

const LEDGER_LABEL: Record<string, string> = {
  purchase: "Credits purchased",
  booking_spend: "Booked a session",
  booking_refund: "Cancelled in time — refunded",
  session_cancelled: "Session cancelled — refunded",
  admin_grant: "Granted by Shevaani",
  admin_revoke: "Adjusted by Shevaani",
};

function isOneOnOne(booking: BookingWithSession) {
  // From the API, not inferred from seat counts — a group discussion can
  // legitimately have a single seat, and calling that a 1:1 would be wrong.
  return booking.session.kind === "one_on_one";
}

function VerifyBanner() {
  const { user, refresh } = useAuth();
  const [busy, setBusy] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);

  if (!user || user.email_verified_at) return null;

  async function resend() {
    setBusy(true);
    try {
      const { detail } = await api.sendEmailVerification();
      setNotice(detail);
      await refresh();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="border-warning/30 bg-warning/10 mt-6">
      <CardContent className="flex flex-wrap items-center justify-between gap-4 text-sm">
        <div className="flex items-start gap-3">
          <MailWarning className="mt-0.5 size-4 shrink-0 text-[var(--warning)]" />
          <p className="max-w-xl text-pretty">
            {/* Nothing here is blocked by an unconfirmed address, and saying
                otherwise to force the click would be untrue. */}
            <strong>{user.email}</strong> isn&apos;t confirmed yet. Booking still
            works — but reminders and joining links may not reach you.
          </p>
        </div>
        {notice ? (
          <span className="text-muted-foreground">{notice}</span>
        ) : (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => void resend()}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            Send a link
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function BookingCard({
  booking,
  timezone,
  busy,
  onJoin,
  onCancel,
  past = false,
}: {
  booking: BookingWithSession;
  timezone?: string;
  busy: string | null;
  onJoin: (sessionId: string) => void;
  onCancel: (booking: BookingWithSession) => void;
  past?: boolean;
}) {
  const waitlisted = booking.status === "waitlisted";
  const startsAt = new Date(booking.starts_at).getTime();
  // The endpoint is the real gate; this only decides whether the button looks
  // live, so an out-of-window click still fails cleanly on the server.
  const joinOpen =
    !waitlisted &&
    !past &&
    Date.now() >= startsAt - JOIN_OPENS_MINUTES_BEFORE * 60_000;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            {booking.session.level_min}–{booking.session.level_max}
          </Badge>
          {isOneOnOne(booking) ? (
            <Badge variant="secondary">One-to-one</Badge>
          ) : (
            <Badge variant="secondary" className="gap-1">
              <Users className="size-3" /> Group
            </Badge>
          )}
          {waitlisted && (
            <Badge variant="warning">
              Waitlist{booking.waitlist_position ? ` #${booking.waitlist_position}` : ""}
            </Badge>
          )}
          {joinOpen && <Badge variant="success">Room open</Badge>}
          {past && booking.status === "attended" && <Badge variant="success">Attended</Badge>}
          {past && booking.status === "no_show" && <Badge variant="outline">Missed</Badge>}
        </div>
        <CardTitle className="text-lg">{booking.session.title}</CardTitle>
      </CardHeader>

      <CardContent className="flex flex-wrap items-center justify-between gap-4">
        <div className="text-muted-foreground text-sm">
          <p className="text-foreground font-medium">
            {formatDateTime(booking.starts_at, timezone)}
          </p>
          <p className="mt-1">
            {durationMinutes(booking.starts_at, booking.ends_at)} min
            {!past && ` · ${relativeToNow(booking.starts_at)}`} · with{" "}
            {booking.session.instructor.full_name}
          </p>
          {waitlisted && (
            <p className="mt-1">
              No credit taken yet — you&apos;re charged only if a seat opens.
            </p>
          )}
        </div>

        {!past && (
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={busy === booking.id}
              onClick={() => onCancel(booking)}
            >
              Cancel
            </Button>
            {!waitlisted && (
              <Button
                size="sm"
                variant={joinOpen ? "brand" : "outline"}
                disabled={busy === booking.session_id || !joinOpen}
                title={
                  joinOpen
                    ? undefined
                    : `The room opens ${JOIN_OPENS_MINUTES_BEFORE} minutes before the start.`
                }
                onClick={() => onJoin(booking.session_id)}
              >
                {busy === booking.session_id ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Video className="size-4" />
                )}
                Join
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CancelConfirm({
  booking,
  onConfirm,
  onDismiss,
  busy,
}: {
  booking: BookingWithSession;
  onConfirm: () => void;
  onDismiss: () => void;
  busy: boolean;
}) {
  const hoursAway = (new Date(booking.starts_at).getTime() - Date.now()) / 3_600_000;
  const refunded = booking.credits_spent === 0 || hoursAway > 12;

  return (
    <Card className="border-destructive/40">
      <CardContent className="flex flex-col gap-4 text-sm">
        <div>
          <p className="font-medium">Cancel “{booking.session.title}”?</p>
          {/* The policy, said before the button rather than after — and the two
              cases genuinely differ, so this is not boilerplate. */}
          <p className="text-muted-foreground mt-1 text-pretty">
            {booking.credits_spent === 0
              ? "You haven't been charged for this — leaving the waitlist costs nothing."
              : refunded
                ? `It starts in over 12 hours, so your ${booking.credits_spent} credit(s) go straight back to your balance.`
                : `It starts in under 12 hours, so the ${booking.credits_spent} credit(s) will not come back. The seat was held for you and the group is small.`}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="destructive" size="sm" disabled={busy} onClick={onConfirm}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {refunded ? "Cancel and refund" : "Cancel anyway"}
          </Button>
          <Button variant="ghost" size="sm" onClick={onDismiss}>
            Keep it
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { user, credits, loading: authLoading, refresh } = useAuth();
  const router = useRouter();

  const [upcoming, setUpcoming] = React.useState<BookingWithSession[]>([]);
  const [past, setPast] = React.useState<BookingWithSession[]>([]);
  const [ledger, setLedger] = React.useState<LedgerEntry[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [cancelling, setCancelling] = React.useState<BookingWithSession | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/dashboard");
  }, [authLoading, user, router]);

  const load = React.useCallback(async () => {
    try {
      const [ahead, all, entries] = await Promise.all([
        api.myBookings(true),
        // `upcoming=false` returns everything, so past is the difference.
        api.myBookings(false),
        api.creditLedger(),
      ]);
      const aheadIds = new Set(ahead.map((b) => b.id));
      setUpcoming(ahead);
      setPast(
        all
          .filter((b) => !aheadIds.has(b.id))
          .sort((a, b) => b.starts_at.localeCompare(a.starts_at)),
      );
      setLedger(entries);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function join(sessionId: string) {
    setBusy(sessionId);
    setError(null);
    try {
      // Fetched on click, never embedded in the page: the URL is a bearer
      // credential and every request for one is logged against the booking.
      const info = await api.joinSession(sessionId);
      window.open(info.join_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  async function cancel(booking: BookingWithSession) {
    setBusy(booking.id);
    setError(null);
    try {
      await api.cancelBooking(booking.id, "Cancelled by learner");
      setCancelling(null);
      await Promise.all([load(), refresh()]);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
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

  const waitlisted = upcoming.filter((b) => b.status === "waitlisted");
  const confirmed = upcoming.filter((b) => b.status !== "waitlisted");

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl tracking-tight">My sessions</h1>
          <p className="text-muted-foreground mt-2">
            Everything you have coming up, in {user?.timezone}. The room opens{" "}
            {JOIN_OPENS_MINUTES_BEFORE} minutes before the start.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-sm">
            <Coins className="size-3.5" />
            {credits} credits
          </Badge>
          <Button asChild size="sm" variant="outline">
            <Link href="/checkout">Buy more</Link>
          </Button>
        </div>
      </header>

      <VerifyBanner />

      {error && <p className="text-destructive mt-6 text-sm">{error}</p>}

      {confirmed.length === 0 && waitlisted.length === 0 ? (
        <Card className="mt-10">
          <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
            <CalendarClock className="text-muted-foreground size-8" />
            <p className="text-muted-foreground">Nothing booked yet.</p>
            <div className="flex gap-3">
              <Button asChild variant="brand">
                <Link href="/discussions">Browse discussions</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/one-on-one">Book a 1:1</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <section className="mt-10 flex flex-col gap-4">
          {confirmed.map((booking) => (
            <React.Fragment key={booking.id}>
              <BookingCard
                booking={booking}
                timezone={user?.timezone}
                busy={busy}
                onJoin={join}
                onCancel={setCancelling}
              />
              {cancelling?.id === booking.id && (
                <CancelConfirm
                  booking={booking}
                  busy={busy === booking.id}
                  onConfirm={() => void cancel(booking)}
                  onDismiss={() => setCancelling(null)}
                />
              )}
            </React.Fragment>
          ))}
        </section>
      )}

      {waitlisted.length > 0 && (
        <section className="mt-12">
          <h2 className="text-xl tracking-tight">On the waitlist</h2>
          <p className="text-muted-foreground mt-1 text-sm text-pretty">
            You move up automatically when someone cancels, and only then is a
            credit taken.
          </p>
          <div className="mt-4 flex flex-col gap-4">
            {waitlisted.map((booking) => (
              <React.Fragment key={booking.id}>
                <BookingCard
                  booking={booking}
                  timezone={user?.timezone}
                  busy={busy}
                  onJoin={join}
                  onCancel={setCancelling}
                />
                {cancelling?.id === booking.id && (
                  <CancelConfirm
                    booking={booking}
                    busy={busy === booking.id}
                    onConfirm={() => void cancel(booking)}
                    onDismiss={() => setCancelling(null)}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </section>
      )}

      <section className="mt-12">
        <h2 className="text-xl tracking-tight">Credits</h2>
        <p className="text-muted-foreground mt-1 text-sm text-pretty">
          Your balance is the sum of everything below. Nothing is ever edited or
          removed, so this is the full story of every credit.
        </p>
        <Card className="mt-4">
          <CardContent className="flex flex-col divide-y text-sm">
            {ledger.length === 0 && (
              <p className="text-muted-foreground py-6 text-center">
                No credits yet.{" "}
                <Link href="/checkout" className="text-foreground underline underline-offset-4">
                  Buy some
                </Link>
                .
              </p>
            )}
            {ledger.map((entry) => (
              <div
                key={entry.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
              >
                <div>
                  <p>{LEDGER_LABEL[entry.reason] ?? entry.reason}</p>
                  <p className="text-muted-foreground mt-0.5 text-xs">
                    {formatDateTime(entry.created_at, user?.timezone)}
                    {entry.note ? ` · ${entry.note}` : ""}
                  </p>
                </div>
                <span
                  className={
                    entry.delta > 0 ? "text-[var(--success)]" : "text-muted-foreground"
                  }
                >
                  {entry.delta > 0 ? `+${entry.delta}` : entry.delta}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      {past.length > 0 && (
        <section className="mt-12">
          <h2 className="text-xl tracking-tight">Past sessions</h2>
          <div className="mt-4 flex flex-col gap-4">
            {past.map((booking) => (
              <BookingCard
                key={booking.id}
                booking={booking}
                timezone={user?.timezone}
                busy={busy}
                onJoin={join}
                onCancel={setCancelling}
                past
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
