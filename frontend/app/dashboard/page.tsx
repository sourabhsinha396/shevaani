"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  CalendarClock,
  Check,
  Copy,
  Loader2,
  MailWarning,
  Ticket,
  Users,
  Video,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { InviteFriends } from "@/components/invite-friends";
import { useSiteConfig } from "@/components/site-config-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { sessionBalanceLabel } from "@/lib/pricing";
import type { BookingWithSession } from "@/lib/types";
import { durationMinutes, formatDateTime, relativeToNow } from "@/lib/utils";

/** Matches JOIN_WINDOW_BEFORE_MINUTES on the API. Nothing is gated on it any
 *  more - it is only how long before the hour the instructor is expected. */
const STARTING_SOON_MINUTES = 15;

function isOneOnOne(booking: BookingWithSession) {
  // From the API, not inferred from seat counts - a group discussion can
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
            works - but reminders and joining links may not reach you.
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

/** The link itself, in full, plus the one thing people worry about when they
 *  get it days early: that arriving before the instructor means nothing is
 *  wrong. Shown rather than fetched - see the note on `recordJoin`. */
function JoinPanel({
  joinUrl,
  instructorName,
  onJoin,
}: {
  joinUrl: string;
  instructorName: string;
  onJoin: () => void;
}) {
  const [copied, setCopied] = React.useState(false);

  function copy() {
    void navigator.clipboard.writeText(joinUrl).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="border-border/60 bg-surface-subtle rounded-lg border p-4">
      <p className="flex items-center gap-2 text-sm font-medium">
        <Video className="size-4" /> Your Google Meet link
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <a
          href={joinUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={onJoin}
          className="text-brand-ink min-w-0 flex-1 font-mono text-sm break-all underline underline-offset-4"
        >
          {joinUrl}
        </a>
        <Button variant="outline" size="sm" onClick={copy}>
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>

      <p className="text-muted-foreground mt-3 text-sm text-pretty">
        We recommend joining atleast 5 minutes early: The moderator{" "}
        ({instructorName}) will give you a heads-up and the session will start on time.
      </p>

      <Button variant="brand" size="sm" className="mt-3" asChild>
        <a href={joinUrl} target="_blank" rel="noopener noreferrer" onClick={onJoin}>
          <Video className="size-4" /> Join
        </a>
      </Button>
    </div>
  );
}

/** Why there is no link yet. "Still being made" and "we failed to make it" are
 *  different things to tell someone, and only one of them is worth waiting on. */
function missingLinkNotice(booking: BookingWithSession) {
  if (booking.meeting_status === "failed") {
    return "We couldn't set up the video session for this one. We know, and we're fixing it - if the link still isn't here the day before, write to us and we'll sort it out.";
  }
  return "The Meet link is being created - it usually lands within a minute of booking. Refresh this page and it should be here.";
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
  onJoin: (booking: BookingWithSession) => void;
  onCancel: (booking: BookingWithSession) => void;
  past?: boolean;
}) {
  const session = booking.session;
  const waitlisted = booking.status === "waitlisted";
  const startsAt = new Date(booking.starts_at).getTime();
  const startingSoon =
    !waitlisted && !past && Date.now() >= startsAt - STARTING_SOON_MINUTES * 60_000;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
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
          {startingSoon && <Badge variant="success">Starting soon</Badge>}
          {past && booking.status === "attended" && <Badge variant="success">Attended</Badge>}
          {past && booking.status === "no_show" && <Badge variant="outline">Missed</Badge>}
        </div>
        <CardTitle className="text-lg">{session.title}</CardTitle>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="text-muted-foreground text-sm">
            <p className="text-foreground font-medium">
              {formatDateTime(booking.starts_at, timezone)}
            </p>
            <p className="mt-1">
              {durationMinutes(booking.starts_at, booking.ends_at)} min
              {!past && ` · ${relativeToNow(booking.starts_at)}`} 
              {/* · with{" "} {session.instructor.full_name} */}
            </p>
            {waitlisted && (
              <p className="mt-1">
                Nothing taken yet - you&apos;re charged only if a seat opens.
              </p>
            )}
          </div>

          {!past && (
            <Button
              variant="ghost"
              size="sm"
              disabled={busy === booking.id}
              onClick={() => onCancel(booking)}
            >
              Cancel
            </Button>
          )}
          {/* "confirmed" too: attendance often isn't marked, but the feedback
              page only shows what was actually published for them. */}
          {past && ["attended", "confirmed"].includes(booking.status) && !isOneOnOne(booking) && (
            <Button asChild variant="outline" size="sm">
              {/* The session's own feedback page - slug-addressed, so the URL
                  is shareable and readable. */}
              <Link href={`/dashboard/feedback/${session.slug ?? booking.session_id}`}>
                View feedback
              </Link>
            </Button>
          )}
        </div>

        {!past && session.prep_material_url && (
          <a
            href={session.prep_material_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand-ink inline-flex items-center gap-2 text-sm underline underline-offset-4"
          >
            <BookOpen className="size-4" /> Read the prep material first
          </a>
        )}

        {!past &&
          !waitlisted &&
          (booking.join_url ? (
            <JoinPanel
              joinUrl={booking.join_url}
              instructorName={session.instructor.full_name}
              onJoin={() => onJoin(booking)}
            />
          ) : (
            <p className="text-muted-foreground text-sm text-pretty">
              {missingLinkNotice(booking)}
            </p>
          ))}

        {!past && !waitlisted && (
          <InviteFriends session={session} timezone={timezone} />
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
          {/* The policy, said before the button rather than after - and the two
              cases genuinely differ, so this is not boilerplate. */}
          <p className="text-muted-foreground mt-1 text-pretty">
            {booking.credits_spent === 0
              ? "You haven't been charged for this - leaving the waitlist costs nothing."
              : refunded
                ? "It starts in over 12 hours, so it goes straight back on your balance."
                : "It starts in under 12 hours, so it will not come back. The seat was held for you and the group is small."}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="destructive" size="sm" disabled={busy} onClick={onConfirm}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {refunded ? "Cancel and get it back" : "Cancel anyway"}
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
  const { one_on_one_enabled: oneOnOneEnabled } = useSiteConfig();
  const router = useRouter();

  const [upcoming, setUpcoming] = React.useState<BookingWithSession[]>([]);
  const [past, setPast] = React.useState<BookingWithSession[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [cancelling, setCancelling] = React.useState<BookingWithSession | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/dashboard");
  }, [authLoading, user, router]);

  const load = React.useCallback(async () => {
    try {
      const [ahead, all] = await Promise.all([
        api.myBookings(true),
        // `upcoming=false` returns everything, so past is the difference.
        api.myBookings(false),
      ]);
      const aheadIds = new Set(ahead.map((b) => b.id));
      setUpcoming(ahead);
      setPast(
        all
          .filter((b) => !aheadIds.has(b.id))
          .sort((a, b) => b.starts_at.localeCompare(a.starts_at)),
      );
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

  /** The link is already opening by the time this runs - the anchor did that,
   *  and it has to, or the browser would treat a post-fetch `window.open` as a
   *  popup. All this does is tell the API that somebody went, which is what
   *  writes the audit row and the automatic attendance signal. A failure here
   *  costs the learner nothing, so it is never shown to them. */
  function recordJoin(booking: BookingWithSession) {
    void api.joinSession(booking.session_id).catch(() => undefined);
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
          <p className="text-muted-foreground mt-2 max-w-xl text-pretty">
            Your upcoming and past sessions. Your balance history lives on{" "}
            <Link href="/account" className="text-foreground underline underline-offset-4">
              your account
            </Link>
            .
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-sm">
            <Ticket className="size-3.5" />
            {sessionBalanceLabel(credits)} left
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
              {/* Same rule as the nav: don't offer what is switched off. */}
              {oneOnOneEnabled && (
                <Button asChild variant="outline">
                  <Link href="/one-on-one">Book a 1:1</Link>
                </Button>
              )}
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
                onJoin={recordJoin}
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
            session taken from your balance.
          </p>
          <div className="mt-4 flex flex-col gap-4">
            {waitlisted.map((booking) => (
              <React.Fragment key={booking.id}>
                <BookingCard
                  booking={booking}
                  timezone={user?.timezone}
                  busy={busy}
                  onJoin={recordJoin}
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
                onJoin={recordJoin}
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
