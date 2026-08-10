"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Loader2, RefreshCw } from "lucide-react";

import { CancelSessionDialog } from "@/components/admin/cancel-session-dialog";
import { MeetingBadge } from "@/components/admin/meeting-badge";
import { RosterPanel } from "@/components/admin/roster-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { AdminSession, Roster } from "@/lib/types";
import { durationMinutes, formatDateTime } from "@/lib/utils";

/** `datetime-local` wants a local wall-clock string with no zone on it. */
function toLocalInput(iso: string) {
  const date = new Date(iso);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export default function AdminSessionPage() {
  const { id } = useParams<{ id: string }>();

  const [session, setSession] = React.useState<AdminSession | null>(null);
  const [roster, setRoster] = React.useState<Roster | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [cancelling, setCancelling] = React.useState(false);

  const [details, setDetails] = React.useState({
    title: "",
    topic: "",
    description: "",
    prep_material_url: "",
    min_seats: 3,
    max_seats: 6,
    price_credits: 1,
  });
  const [schedule, setSchedule] = React.useState({ starts_at: "", duration_minutes: 45 });

  const load = React.useCallback(async () => {
    try {
      const found = await api.adminGetSession(id);
      setSession(found);
      if (found) {
        setDetails({
          title: found.title,
          topic: found.topic ?? "",
          description: found.description ?? "",
          prep_material_url: found.prep_material_url ?? "",
          min_seats: found.min_seats,
          max_seats: found.max_seats,
          price_credits: found.price_credits,
        });
        setSchedule({
          starts_at: toLocalInput(found.starts_at),
          duration_minutes: durationMinutes(found.starts_at, found.ends_at),
        });
      }
      setRoster(await api.adminRoster(id));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      await load();
      setNotice(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  if (!session) {
    return (
      <Card>
        <CardContent className="text-muted-foreground py-16 text-center text-sm">
          {error ?? "That session no longer exists."}
        </CardContent>
      </Card>
    );
  }

  const cancelled = session.status === "cancelled";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          href="/admin"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="size-3.5" /> All sessions
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge variant="outline">{session.status}</Badge>
          <MeetingBadge status={session.meeting_status} error={session.meeting_last_error} />
          {session.meeting_host_email && (
            <span className="text-muted-foreground text-xs">
              hosted on {session.meeting_host_email}
            </span>
          )}
        </div>
        <h2 className="mt-3 text-2xl tracking-tight">{session.title}</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          {formatDateTime(session.starts_at)} · {session.instructor.full_name} ·{" "}
          {session.seats_taken}/{session.max_seats} seats
          {session.waitlist_count > 0 && ` · ${session.waitlist_count} waiting`}
        </p>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}
      {notice && <p className="text-sm text-[var(--success)]">{notice}</p>}

      <div className="flex flex-wrap gap-2">
        {session.status === "draft" && (
          <Button
            size="sm"
            disabled={busy}
            onClick={() => void run(() => api.adminPublish(session.id), "Published.")}
          >
            Publish
          </Button>
        )}
        {!cancelled && session.meeting_status !== "ready" && (
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              void run(() => api.adminRetryMeeting(session.id), "Retrying — refresh shortly.")
            }
          >
            <RefreshCw className="size-4" /> Retry Meet
          </Button>
        )}
        {!cancelled && (
          <Button size="sm" variant="ghost" onClick={() => setCancelling((v) => !v)}>
            Cancel session
          </Button>
        )}
      </div>

      {cancelling && (
        <CancelSessionDialog
          sessionId={session.id}
          title={session.title}
          onCancelled={load}
          onClose={() => setCancelling(false)}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Details</CardTitle>
          <CardDescription>
            Title and description are mirrored into the calendar event, so saving
            re-syncs the Meet.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-5"
            onSubmit={(event) => {
              event.preventDefault();
              void run(
                () =>
                  api.adminUpdateSession(session.id, {
                    ...details,
                    topic: details.topic || null,
                    description: details.description || null,
                    prep_material_url: details.prep_material_url || null,
                  }),
                "Saved.",
              );
            }}
          >
            <Field label="Title">
              <Input
                required
                maxLength={200}
                value={details.title}
                onChange={(e) => setDetails({ ...details, title: e.target.value })}
              />
            </Field>
            <Field label="Topic">
              <Input
                maxLength={200}
                value={details.topic}
                onChange={(e) => setDetails({ ...details, topic: e.target.value })}
              />
            </Field>
            <Field label="Description">
              <Textarea
                rows={4}
                value={details.description}
                onChange={(e) => setDetails({ ...details, description: e.target.value })}
              />
            </Field>
            <Field label="Prep material URL">
              <Input
                type="url"
                value={details.prep_material_url}
                onChange={(e) =>
                  setDetails({ ...details, prep_material_url: e.target.value })
                }
              />
            </Field>

            <div className="grid gap-5 sm:grid-cols-3">
              <Field
                label="Min seats"
                hint="Below this, it auto-cancels 2h before."
              >
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={details.min_seats}
                  onChange={(e) =>
                    setDetails({ ...details, min_seats: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Max seats" hint="Can't drop below seats already taken.">
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={details.max_seats}
                  onChange={(e) =>
                    setDetails({ ...details, max_seats: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Price (credits)">
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={details.price_credits}
                  onChange={(e) =>
                    setDetails({ ...details, price_credits: Number(e.target.value) })
                  }
                />
              </Field>
            </div>

            <Button type="submit" variant="brand" disabled={busy || cancelled} className="self-start">
              {busy && <Loader2 className="size-4 animate-spin" />}
              Save details
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Reschedule</CardTitle>
          <CardDescription>
            Moves the session, every booking on it, and the calendar event
            together. Learners are not asked first, so tell them.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-end gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              void run(
                () =>
                  api.adminReschedule(session.id, {
                    starts_at: new Date(schedule.starts_at).toISOString(),
                    duration_minutes: schedule.duration_minutes,
                  }),
                "Rescheduled.",
              );
            }}
          >
            <Field label="Starts at" className="min-w-56">
              <Input
                type="datetime-local"
                required
                value={schedule.starts_at}
                onChange={(e) => setSchedule({ ...schedule, starts_at: e.target.value })}
              />
            </Field>
            <Field label="Duration (minutes)" className="w-44">
              <Input
                type="number"
                min={15}
                max={240}
                required
                value={schedule.duration_minutes}
                onChange={(e) =>
                  setSchedule({ ...schedule, duration_minutes: Number(e.target.value) })
                }
              />
            </Field>
            <Button type="submit" disabled={busy || cancelled}>
              Reschedule
            </Button>
          </form>
        </CardContent>
      </Card>

      <div>
        <h3 className="mb-4 font-medium">Roster</h3>
        <RosterPanel
          roster={roster}
          onConfirm={async (bookingId, attended) => {
            await api.adminAttendance(bookingId, attended);
            setRoster(await api.adminRoster(session.id));
          }}
        />
      </div>
    </div>
  );
}
