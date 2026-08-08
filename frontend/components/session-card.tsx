"use client";

import Link from "next/link";
import { CalendarClock, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { DiscussionSession } from "@/lib/types";
import { cn, durationMinutes, formatDateTime } from "@/lib/utils";

export function SessionCard({
  session,
  timezone,
}: {
  session: DiscussionSession;
  timezone?: string;
}) {
  const booked = session.my_booking_status === "confirmed";
  const waitlisted = session.my_booking_status === "waitlisted";
  const nearlyFull = !session.is_full && session.seats_left <= 2;

  return (
    <Card className="hover:border-brand-ink/50 group relative gap-4 overflow-hidden transition-colors">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <Badge variant="outline">
            {session.level_min === session.level_max
              ? session.level_min
              : `${session.level_min}–${session.level_max}`}
          </Badge>
          {booked && <Badge variant="success">Booked</Badge>}
          {waitlisted && <Badge variant="warning">Waitlisted</Badge>}
          {!booked && !waitlisted && session.is_full && (
            <Badge variant="secondary">Full — waitlist open</Badge>
          )}
          {!booked && !waitlisted && nearlyFull && (
            <Badge variant="warning">{session.seats_left} left</Badge>
          )}
        </div>

        <CardTitle className="text-lg leading-snug">{session.title}</CardTitle>
        {session.topic && <p className="text-muted-foreground text-sm">{session.topic}</p>}
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
            {session.seats_taken}/{session.max_seats}
          </span>
        </div>

        {/* Seat meter — small groups are the product, so make fill obvious. */}
        <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              session.is_full ? "bg-muted-foreground/50" : "bg-brand",
            )}
            style={{
              width: `${Math.min(
                100,
                (session.seats_taken / Math.max(session.max_seats, 1)) * 100,
              )}%`,
            }}
          />
        </div>

        <p className="text-muted-foreground text-sm">
          Hosted by <span className="text-foreground font-medium">{session.facilitator.full_name}</span>
        </p>
      </CardContent>

      <CardFooter className="justify-between gap-3">
        <span className="text-muted-foreground text-sm">
          {session.price_credits === 0
            ? "Free"
            : `${session.price_credits} credit${session.price_credits > 1 ? "s" : ""}`}
        </span>
        <Button asChild size="sm" variant={booked ? "outline" : "default"}>
          <Link href={`/discussions/${session.id}`}>{booked ? "View details" : "See details"}</Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
