"use client";

import * as React from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { AdminInstructor } from "@/lib/types";

function InstructorCard({
  instructor,
  onSaved,
}: {
  instructor: AdminInstructor;
  onSaved: () => Promise<void>;
}) {
  const [editing, setEditing] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({
    full_name: instructor.full_name,
    headline: instructor.headline ?? "",
    bio: instructor.bio ?? "",
  });

  async function save(payload: Parameters<typeof api.adminUpdateInstructor>[1]) {
    setBusy(true);
    setError(null);
    try {
      await api.adminUpdateInstructor(instructor.id, payload);
      await onSaved();
      setEditing(false);
    } catch (e) {
      // Deactivating someone who still has published sessions is refused and
      // the message names the count — show it rather than a generic failure.
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="font-medium">{instructor.full_name}</p>
            <p className="text-muted-foreground mt-1 text-sm">
              {instructor.email}
              {instructor.headline ? ` · ${instructor.headline}` : ""}
            </p>
            <p className="text-muted-foreground mt-1 text-sm">
              {instructor.upcoming_sessions} upcoming session
              {instructor.upcoming_sessions === 1 ? "" : "s"}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {!instructor.is_active && <Badge variant="secondary">Inactive</Badge>}
            {instructor.google_connected ? (
              <Badge variant="success" title={instructor.google_email ?? undefined}>
                <CheckCircle2 /> Google connected
              </Badge>
            ) : (
              <Badge variant="destructive">
                <XCircle /> Cannot host
              </Badge>
            )}
            <Button size="sm" variant="outline" onClick={() => setEditing((v) => !v)}>
              {editing ? "Close" : "Edit"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => void save({ is_active: !instructor.is_active })}
            >
              {instructor.is_active ? "Deactivate" : "Reactivate"}
            </Button>
          </div>
        </div>

        {error && <p className="text-destructive text-sm">{error}</p>}

        {editing && (
          <form
            className="border-border/60 flex flex-col gap-4 border-t pt-4"
            onSubmit={(event) => {
              event.preventDefault();
              void save({
                full_name: form.full_name,
                headline: form.headline || null,
                bio: form.bio || null,
              });
            }}
          >
            <Field label="Name">
              <Input
                required
                maxLength={200}
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              />
            </Field>
            <Field label="Headline" hint="One line, shown next to their name in the catalogue.">
              <Input
                maxLength={200}
                value={form.headline}
                onChange={(e) => setForm({ ...form, headline: e.target.value })}
              />
            </Field>
            <Field label="Bio">
              <Textarea
                rows={3}
                value={form.bio}
                onChange={(e) => setForm({ ...form, bio: e.target.value })}
              />
            </Field>
            <Button type="submit" variant="brand" size="sm" disabled={busy} className="self-start">
              {busy && <Loader2 className="size-4 animate-spin" />}
              Save
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminInstructorsPage() {
  const [instructors, setInstructors] = React.useState<AdminInstructor[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      setInstructors(await api.adminInstructors());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

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
        <CardContent className="text-muted-foreground text-sm">
          Instructors are created from the backend CLI —{" "}
          <code className="bg-muted rounded px-1.5 py-0.5 text-xs">make instructor</code>. There
          is deliberately no self-service path into the role. An instructor can only host once
          they have connected their own Google account, because the Meet link is created on their
          calendar; that is what makes them the host who can admit people from the lobby.
        </CardContent>
      </Card>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {instructors.map((instructor) => (
        <InstructorCard key={instructor.id} instructor={instructor} onSaved={load} />
      ))}
    </div>
  );
}
