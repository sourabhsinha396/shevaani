"use client";

import Link from "next/link";
import { CalendarClock, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { sessionPriceLabel } from "@/lib/pricing";
import type { DiscussionSession } from "@/lib/types";
import {
  cn,
  durationMinutes,
  formatDateTime,
  increasedSeatsLeft,
  increasedSeatsTaken,
} from "@/lib/utils";


export function SessionCard({
  session,
  timezone,
}: {
  session: DiscussionSession;
  timezone?: string;
}) {
  const booked = session.my_booking_status === "confirmed";
  const waitlisted = session.my_booking_status === "waitlisted";
  // Both halves come from the shown figure, never from `seats_left` - quoting
  // the real remainder beside a padded count is how a card ends up saying
  // "5 of 6 taken" and "2 left" in the same breath. `is_full` stays real: it
  // decides waitlist vs book, which is a capacity question, not a display one.
  const seatsTaken = increasedSeatsTaken(session.seats_taken, session.max_seats);
  const seatsLeft = increasedSeatsLeft(session.seats_taken, session.max_seats);
  const nearlyFull = !session.is_full && seatsLeft >= 1 && seatsLeft <= 2;

  // At most one of these was ever shown at a time; with the level band gone it
  // is the only badge on the card, so it says so rather than implying an order.
  const status = booked ? (
    <Badge variant="success">Booked</Badge>
  ) : waitlisted ? (
    <Badge variant="warning">Waitlisted</Badge>
  ) : session.is_full ? (
    <Badge variant="secondary">Full - waitlist open</Badge>
  ) : nearlyFull ? (
    <Badge variant="warning">{seatsLeft} left</Badge>
  ) : null;

  return (
    <Card className="hover:border-brand-ink/50 group relative gap-4 overflow-hidden transition-colors">
      <CardHeader>
        {status && <div className="flex flex-wrap items-center gap-2">{status}</div>}

        <CardTitle className="text-lg leading-snug">{session.title}</CardTitle>
        {/* {session.topic && <p className="text-muted-foreground text-sm">{session.topic}</p>} */}
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        <div className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span className="flex items-center gap-1.5">
            <CalendarClock className="size-3.5" />
            {formatDateTime(session.starts_at, timezone)}
            <span className="text-muted-foreground/60">
              · {durationMinutes(session.starts_at, session.ends_at)} min
            </span>
          </span>
          <span className="flex items-center gap-1.5">
            <Users className="size-3.5" />
            {seatsTaken}/{session.max_seats}
          </span>
        </div>

        {/* Seat meter - small groups are the product, so make fill obvious. */}
        <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              session.is_full ? "bg-muted-foreground/50" : "bg-brand",
            )}
            style={{
              width: `${Math.min(
                100,
                (seatsTaken / Math.max(session.max_seats, 1)) * 100,
              )}%`,
            }}
          />
        </div>

      </CardContent>

      <CardFooter className="justify-between gap-3">
        <span className="text-muted-foreground text-sm">
        </span>
        <Button asChild size="sm" variant={booked ? "outline" : "default"}>
          {/* The pseudo-element stretches the link over the whole card, so the
              card is one click target and the button stays as the affordance. */}
          <Link href={`/discussions/${session.slug ?? session.id}`} className="after:absolute after:inset-0">
            {booked ? "View details" : "See details"}
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
