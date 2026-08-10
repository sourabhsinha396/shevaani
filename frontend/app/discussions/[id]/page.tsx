"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, BookOpen, CalendarClock, Loader2, Users, Video } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { sessionPriceLabel } from "@/lib/pricing";
import type { DiscussionSession } from "@/lib/types";
import {
  durationMinutes,
  formatDateTime,
  increasedSeatsTaken,
  relativeToNow,
} from "@/lib/utils";

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();

  const [session, setSession] = React.useState<DiscussionSession | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState<{ kind: "error" | "info"; text: string } | null>(
    null,
  );

  const increasedSeatsTaken = React.useCallback((seatsTaken: number, maxSeats: number) => {
    if (seatsTaken <= maxSeats - 3) {
      return seatsTaken + 2;
    }
    return seatsTaken;
  }, []);

  const load = React.useCallback(async () => {
    try {
      setSession(await api.getSession(id));
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }, [id]);

  React.useEffect(() => {
    void load();
  }, [load]);

  /** Nothing is spent here. Booking is a decision worth showing the price, the
   *  time and the host for, so it happens on the session's own checkout — which
   *  also sells credits inline when the balance is short. */
  function book() {
    const checkout = `/discussions/${id}/checkout`;
    router.push(user ? checkout : `/login?next=${encodeURIComponent(checkout)}`);
  }

  if (loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  if (!session) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-24 text-center">
        <p className="text-muted-foreground">That session could not be found.</p>
        <Button asChild variant="outline" className="mt-6">
          <Link href="/discussions">Back to discussions</Link>
        </Button>
      </div>
    );
  }

  const booked = session.my_booking_status === "confirmed";
  const waitlisted = session.my_booking_status === "waitlisted";
  const startsSoon = new Date(session.starts_at).getTime() - Date.now() < 15 * 60_000;
  const seatsTaken = increasedSeatsTaken(session.seats_taken, session.max_seats);

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <Button asChild variant="ghost" size="sm" className="mb-6 -ml-3">
        <Link href="/discussions">
          <ArrowLeft className="size-4" /> All discussions
        </Link>
      </Button>

      <div className="grid gap-8 md:grid-cols-[1fr_320px]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            {booked && <Badge variant="success">You're booked</Badge>}
            {waitlisted && <Badge variant="warning">Waitlisted</Badge>}
            {session.status === "cancelled" && <Badge variant="destructive">Cancelled</Badge>}
          </div>

          <h1 className="mt-4 text-3xl tracking-tight text-balance">
            {session.title}
          </h1>
          {session.topic && <p className="text-muted-foreground mt-2">{session.topic}</p>}

          {session.description && (
            <p className="mt-6 leading-relaxed text-pretty">{session.description}</p>
          )}

          {session.prep_material_url && (
            <Card className="mt-6">
              <CardContent className="flex items-start gap-3">
                <BookOpen className="text-brand-ink mt-0.5 size-5 shrink-0" />
                <div>
                  <p className="font-medium">Prep material</p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    Skim this before you join — the discussion assumes you have.
                  </p>
                  <a
                    href={session.prep_material_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-brand-ink mt-2 inline-block text-sm underline underline-offset-4"
                  >
                    Open the reading
                  </a>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-base">Before you join</CardTitle>
            </CardHeader>
            <CardContent className="text-muted-foreground flex flex-col gap-2 text-sm">
              <p>
                Book, and the Meet link is waiting on{" "}
                <Link href="/dashboard" className="text-foreground underline underline-offset-4">
                  My sessions
                </Link>{" "}
                straight away. Open it whenever you like — if you are early you
                will wait in a short lobby, because the room opens when the
                instructor arrives.
              </p>
              <p>Headphones make a real difference to how well the group can hear each other.</p>
            </CardContent>
          </Card>
        </div>

        <aside className="md:sticky md:top-24 md:self-start">
          <Card>
            <CardContent className="flex flex-col gap-4">
              <div className="text-sm">
                <p className="flex items-center gap-2 font-medium">
                  <CalendarClock className="size-4" />
                  {formatDateTime(session.starts_at, user?.timezone)}
                </p>
                <p className="text-muted-foreground mt-1 pl-6">
                  {durationMinutes(session.starts_at, session.ends_at)} minutes ·{" "}
                  {relativeToNow(session.starts_at)}
                </p>
              </div>

              <div className="text-sm">
                <p className="flex items-center gap-2 font-medium">
                  <Users className="size-4" />
                  {seatsTaken} of {session.max_seats} seats taken
                </p>
                <p className="text-muted-foreground mt-1 pl-6">
                </p>
              </div>

              <div className="text-muted-foreground border-t pt-4 text-sm">
                Hosted by{" "}
                <span className="text-foreground font-medium">{session.instructor.full_name}</span>
                {session.instructor.headline && <> · {session.instructor.headline}</>}
              </div>

              {booked ? (
                // This page knows the session, not the booking — the link, the
                // prep and the cancel button all live on the dashboard. Sending
                // people there is one place to look after booking instead of two.
                <Button asChild variant="brand" size="lg">
                  <Link href="/dashboard">
                    <Video className="size-4" />
                    {startsSoon ? "Join now — go to my sessions" : "Go to my sessions"}
                  </Link>
                </Button>
              ) : waitlisted ? (
                <Button asChild variant="outline" size="lg">
                  <Link href="/dashboard">See your place in the queue</Link>
                </Button>
              ) : (
                <Button onClick={book} disabled={session.status !== "published"} size="lg">
                  {session.is_full
                    ? "Join the waitlist"
                    : `Book · ${sessionPriceLabel(session.price_credits)}`}
                </Button>
              )}

              {message && (
                <p
                  className={
                    message.kind === "error"
                      ? "text-destructive text-sm"
                      : "text-[var(--success)] text-sm"
                  }
                >
                  {message.text}
                </p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
