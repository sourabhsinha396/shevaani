"use client";

import * as React from "react";
import { CalendarX2, Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { SessionCard } from "@/components/session-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { CEFRLevel, DiscussionSession } from "@/lib/types";
import { formatDayLabel } from "@/lib/utils";

const LEVELS: CEFRLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

export default function DiscussionsPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = React.useState<DiscussionSession[]>([]);
  const [level, setLevel] = React.useState<CEFRLevel | "">("");
  const [hideFull, setHideFull] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);

    api
      .listDiscussions({
        level: level || undefined,
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
  }, [level, hideFull]);

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
            Four to eight people, one instructor, forty-five minutes of actual
            speaking. Pick a level band that fits you.
          </p>
        </div>

        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium" htmlFor="level">
              Your level
            </label>
            <Select
              id="level"
              value={level}
              onChange={(e) => setLevel(e.target.value as CEFRLevel | "")}
              className="w-40"
            >
              <option value="">All levels</option>
              {LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </Select>
          </div>
          <Button variant={hideFull ? "default" : "outline"} onClick={() => setHideFull((v) => !v)}>
            {hideFull ? "Showing open only" : "Hide full"}
          </Button>
        </div>
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
            <p>No discussions scheduled for this filter yet.</p>
            <Button variant="outline" onClick={() => { setLevel(""); setHideFull(false); }}>
              Clear filters
            </Button>
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
