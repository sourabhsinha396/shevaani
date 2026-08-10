"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2, RefreshCw } from "lucide-react";

import { CancelSessionDialog } from "@/components/admin/cancel-session-dialog";
import { MeetingBadge } from "@/components/admin/meeting-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { AdminSession } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export default function AdminSessionsPage() {
  const [sessions, setSessions] = React.useState<AdminSession[]>([]);
  const [status, setStatus] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [cancelling, setCancelling] = React.useState<AdminSession | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setSessions(await api.adminListSessions({ status: status || undefined }));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [status]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function act(id: string, action: () => Promise<unknown>) {
    setBusy(id);
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-48">
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="cancelled">Cancelled</option>
          <option value="completed">Completed</option>
        </Select>

        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="size-4" /> Refresh
          </Button>
          <Button asChild variant="brand" size="sm">
            <Link href="/admin/new">New discussion</Link>
          </Button>
        </div>
      </div>

      {error && <p className="text-destructive mt-4 text-sm">{error}</p>}

      {loading ? (
        <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
          <Loader2 className="size-4 animate-spin" /> Loading…
        </div>
      ) : (
        <div className="mt-6 flex flex-col gap-3">
          {sessions.map((session) => (
            <React.Fragment key={session.id}>
              <Card>
                <CardContent className="flex flex-wrap items-center justify-between gap-4">
                  <div className="min-w-64">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{session.status}</Badge>
                      <MeetingBadge
                        status={session.meeting_status}
                        error={session.meeting_last_error}
                      />
                    </div>
                    <p className="mt-2 font-medium">
                      <Link
                        href={`/admin/sessions/${session.id}`}
                        className="hover:underline underline-offset-4"
                      >
                        {session.title}
                      </Link>
                    </p>
                    <p className="text-muted-foreground mt-1 text-sm">
                      {formatDateTime(session.starts_at)} · {session.instructor.full_name} ·{" "}
                      {session.seats_taken}/{session.max_seats} seats
                      {session.waitlist_count > 0 && ` · ${session.waitlist_count} waiting`}
                    </p>
                    {session.meeting_status === "failed" && session.meeting_last_error && (
                      <p className="text-destructive mt-2 max-w-xl text-xs">
                        {session.meeting_last_error}
                      </p>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button asChild size="sm" variant="outline">
                      <Link href={`/admin/sessions/${session.id}`}>Open</Link>
                    </Button>
                    {session.status === "draft" && (
                      <Button
                        size="sm"
                        disabled={busy === session.id}
                        onClick={() => void act(session.id, () => api.adminPublish(session.id))}
                      >
                        Publish
                      </Button>
                    )}
                    {session.meeting_status !== "ready" && session.status !== "cancelled" && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy === session.id}
                        onClick={() =>
                          void act(session.id, () => api.adminRetryMeeting(session.id))
                        }
                      >
                        {busy === session.id ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <RefreshCw className="size-4" />
                        )}
                        Retry Meet
                      </Button>
                    )}
                    {session.status !== "cancelled" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          setCancelling(cancelling?.id === session.id ? null : session)
                        }
                      >
                        Cancel
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Inline rather than in a modal: the refund consequence should sit
                  next to the session it belongs to, not float over the list. */}
              {cancelling?.id === session.id && (
                <CancelSessionDialog
                  sessionId={session.id}
                  title={session.title}
                  onCancelled={load}
                  onClose={() => setCancelling(null)}
                />
              )}
            </React.Fragment>
          ))}

          {sessions.length === 0 && (
            <Card>
              <CardContent className="text-muted-foreground py-16 text-center text-sm">
                No sessions match this filter.
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
