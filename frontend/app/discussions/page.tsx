"use client";

import * as React from "react";
import { CalendarX2, Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { SessionCard } from "@/components/session-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { DiscussionSession } from "@/lib/types";
import { formatDayLabel } from "@/lib/utils";

export default function DiscussionsPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = React.useState<DiscussionSession[]>([]);
  const [hideFull, setHideFull] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);

    api
      .listDiscussions({
        include_full: !hideFull,
        limit: 60,
      })
      .then((data) => {
        if (!cancelled) {
          setSessions(data);
          setError(null);
        }
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [hideFull]);

  // Group by local day so the catalogue reads like a timetable, not a list.
  const byDay = React.useMemo(() => {
    const groups = new Map<string, DiscussionSession[]>();
    for (const session of sessions) {
      const key = formatDayLabel(session.starts_at, user?.timezone);
      groups.set(key, [...(groups.get(key) ?? []), session]);
    }
    return [...groups.entries()];
  }, [sessions, user?.timezone]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      <header className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl tracking-tight sm:text-4xl">Group discussions</h1>
          <p className="text-muted-foreground mt-2 max-w-lg text-pretty">
            Four to eight people, one instructor, thirty minutes of actual
            speaking.
          </p>
        </div>
{/* 
        <Button variant={hideFull ? "default" : "outline"} onClick={() => setHideFull((v) => !v)}>
          {hideFull ? "Showing open only" : "Hide full"}
        </Button> */}
      </header>

      {loading ? (
        <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
          <Loader2 className="size-4 animate-spin" />
          Loading discussions…
        </div>
      ) : error ? (
        <Card className="mt-10">
          <CardContent className="text-destructive text-sm">{error}</CardContent>
        </Card>
      ) : sessions.length === 0 ? (
        <Card className="mt-10">
          <CardContent className="text-muted-foreground flex flex-col items-center gap-3 py-16 text-center">
            <CalendarX2 className="size-8" />
            <p>
              {hideFull
                ? "Nothing with a free seat right now."
                : "No discussions scheduled yet."}
            </p>
            {hideFull && (
              <Button variant="outline" onClick={() => setHideFull(false)}>
                Show full ones too
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="mt-10 flex flex-col gap-10">
          {byDay.map(([day, daySessions]) => (
            <section key={day}>
              <h2 className="text-muted-foreground font-sans mb-4 text-sm font-medium tracking-wide uppercase">
                {day}
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {daySessions.map((session) => (
                  <SessionCard key={session.id} session={session} timezone={user?.timezone} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
