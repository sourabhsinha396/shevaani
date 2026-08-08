"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarClock, Coins, Loader2, Video } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { BookingWithSession } from "@/lib/types";
import { durationMinutes, formatDateTime, relativeToNow } from "@/lib/utils";

export default function DashboardPage() {
  const { user, credits, loading: authLoading, refresh } = useAuth();
  const router = useRouter();

  const [bookings, setBookings] = React.useState<BookingWithSession[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/dashboard");
  }, [authLoading, user, router]);

  const load = React.useCallback(async () => {
    try {
      setBookings(await api.myBookings(true));
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
      const info = await api.joinSession(sessionId);
      window.open(info.join_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  async function cancel(bookingId: string) {
    setBusy(bookingId);
    setError(null);
    try {
      await api.cancelBooking(bookingId, "Cancelled by learner");
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

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl tracking-tight">My sessions</h1>
          <p className="text-muted-foreground mt-2">
            Everything you have coming up. Join opens 15 minutes before the start.
          </p>
        </div>
        <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-sm">
          <Coins className="size-3.5" />
          {credits} credits
        </Badge>
      </header>

      {error && <p className="text-destructive mt-6 text-sm">{error}</p>}

      {bookings.length === 0 ? (
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
        <div className="mt-10 flex flex-col gap-4">
          {bookings.map((booking) => {
            const startsSoon =
              new Date(booking.starts_at).getTime() - Date.now() < 15 * 60_000;
            const waitlisted = booking.status === "waitlisted";

            return (
              <Card key={booking.id}>
                <CardHeader>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">
                      {booking.session.level_min}–{booking.session.level_max}
                    </Badge>
                    {waitlisted && (
                      <Badge variant="warning">Waitlist #{booking.waitlist_position}</Badge>
                    )}
                    {startsSoon && !waitlisted && <Badge variant="success">Starting soon</Badge>}
                  </div>
                  <CardTitle className="text-lg">{booking.session.title}</CardTitle>
                </CardHeader>

                <CardContent className="flex flex-wrap items-center justify-between gap-4">
                  <div className="text-muted-foreground text-sm">
                    <p className="text-foreground font-medium">
                      {formatDateTime(booking.starts_at, user?.timezone)}
                    </p>
                    <p className="mt-1">
                      {durationMinutes(booking.starts_at, booking.ends_at)} min ·{" "}
                      {relativeToNow(booking.starts_at)} · with{" "}
                      {booking.session.facilitator.full_name}
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy === booking.id}
                      onClick={() => void cancel(booking.id)}
                    >
                      Cancel
                    </Button>
                    {!waitlisted && (
                      <Button
                        size="sm"
                        variant={startsSoon ? "brand" : "outline"}
                        disabled={busy === booking.session_id}
                        onClick={() => void join(booking.session_id)}
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
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
