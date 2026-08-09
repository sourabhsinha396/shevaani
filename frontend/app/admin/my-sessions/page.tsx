"use client";

import * as React from "react";
import Link from "next/link";
import { CalendarClock, Loader2 } from "lucide-react";

import { MeetingBadge } from "@/components/admin/meeting-badge";
import { RosterPanel } from "@/components/admin/roster-panel";
import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AdminSession, Roster } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

/**
 * The instructor's own list. Superusers can reach it too — it just shows their
 * own sessions, since the endpoint scopes to the caller and never takes an
 * instructor id from the client.
 */
export default function MySessionsPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = React.useState<AdminSession[]>([]);
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [roster, setRoster] = React.useState<Roster | null>(null);
  const [rosterLoading, setRosterLoading] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .myInstructorSessions()
      .then(setSessions)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function toggleRoster(sessionId: string) {
    if (openId === sessionId) {
      setOpenId(null);
      setRoster(null);
      return;
    }
    setOpenId(sessionId);
    setRosterLoading(true);
    try {
      setRoster(await api.myInstructorRoster(sessionId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRosterLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="bg-muted/30">
        <CardContent className="text-muted-foreground flex flex-wrap items-center justify-between gap-4 text-sm">
          <p className="max-w-xl text-pretty">
            Your sessions, and who turned up. Attendance here is the
            authoritative record — the join click is only an automatic guess at
            it, so correct it after the session.
          </p>
          <Button asChild size="sm" variant="outline">
            <Link href="/instructor">
              <CalendarClock className="size-4" /> Block time · Google
            </Link>
          </Button>
        </CardContent>
      </Card>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {sessions.length === 0 ? (
        <Card>
          <CardContent className="text-muted-foreground py-16 text-center text-sm">
            Nothing scheduled for {user?.full_name ?? "you"} yet.
          </CardContent>
        </Card>
      ) : (
        sessions.map((session) => (
          <Card key={session.id}>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{session.status}</Badge>
                    <Badge variant="secondary">
                      {session.level_min}–{session.level_max}
                    </Badge>
                    <MeetingBadge
                      status={session.meeting_status}
                      error={session.meeting_last_error}
                    />
                  </div>
                  <p className="mt-2 font-medium">{session.title}</p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {formatDateTime(session.starts_at, user?.timezone)} ·{" "}
                    {session.seats_taken}/{session.max_seats} seats
                    {session.waitlist_count > 0 && ` · ${session.waitlist_count} waiting`}
                  </p>
                </div>

                <Button size="sm" variant="outline" onClick={() => void toggleRoster(session.id)}>
                  {openId === session.id ? "Hide roster" : "Roster and attendance"}
                </Button>
              </div>

              {openId === session.id && (
                <div className="border-border/60 border-t pt-4">
                  <RosterPanel
                    roster={roster}
                    loading={rosterLoading}
                    // An instructor sees who is in their room and their level,
                    // not the contact details of everyone who booked.
                    hideEmails
                    onConfirm={async (bookingId, attended) => {
                      await api.myConfirmAttendance(bookingId, attended);
                      setRoster(await api.myInstructorRoster(session.id));
                    }}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
