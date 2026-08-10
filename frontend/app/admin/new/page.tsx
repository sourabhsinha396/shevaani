"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { AdminInstructor } from "@/lib/types";

export default function NewSessionPage() {
  const router = useRouter();
  const [instructors, setInstructors] = React.useState<AdminInstructor[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [form, setForm] = React.useState({
    instructor_id: "",
    title: "",
    topic: "",
    description: "",
    prep_material_url: "",
    starts_at: "",
    duration_minutes: 45,
    min_seats: 3,
    max_seats: 6,
    price_credits: 1,
    publish: true,
  });

  React.useEffect(() => {
    api
      .adminInstructors()
      .then((list) => {
        setInstructors(list);
        const hostable = list.find((f) => f.google_connected && f.is_active);
        if (hostable) setForm((prev) => ({ ...prev, instructor_id: hostable.id }));
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const selected = instructors.find((f) => f.id === form.instructor_id);
  const cannotHost = form.publish && selected && !selected.google_connected;

  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.adminCreateSession({
        ...form,
        topic: form.topic || null,
        description: form.description || null,
        prep_material_url: form.prep_material_url || null,
        // datetime-local has no offset; interpret it in the admin's own zone.
        starts_at: new Date(form.starts_at).toISOString(),
      });
      router.push("/admin");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="max-w-3xl">
      <CardHeader>
        <CardTitle>New group discussion</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-5">
          <Field
            label="Instructor"
            hint="Only instructors who have connected a Google account can host — the Meet link is created on their calendar."
          >
            <Select
              required
              value={form.instructor_id}
              onChange={(e) => update("instructor_id", e.target.value)}
            >
              <option value="">Choose an instructor…</option>
              {instructors.map((f) => (
                <option key={f.id} value={f.id} disabled={!f.is_active}>
                  {f.full_name}
                  {f.google_connected ? "" : " — no Google account"}
                </option>
              ))}
            </Select>
          </Field>

          {cannotHost && (
            <div className="border-warning/30 bg-warning/10 flex items-start gap-3 rounded-lg border p-3 text-sm">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[var(--warning)]" />
              <p>
                {selected?.full_name} hasn&apos;t connected a Google account, so this session
                can&apos;t get a Meet link. Save it as a draft, or pick someone else.
              </p>
            </div>
          )}

          <Field label="Title">
            <Input
              required
              maxLength={200}
              placeholder="Tuesday Debate Club — is remote work over?"
              value={form.title}
              onChange={(e) => update("title", e.target.value)}
            />
          </Field>

          <Field label="Topic" hint="Shown under the title in the catalogue.">
            <Input
              maxLength={200}
              placeholder="Remote work"
              value={form.topic}
              onChange={(e) => update("topic", e.target.value)}
            />
          </Field>

          <Field label="Description">
            <Textarea
              rows={4}
              placeholder="What the group will actually talk about, and who it suits."
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
            />
          </Field>

          <Field
            label="Prep material URL"
            hint="An article or question list, emailed to learners a day before."
          >
            <Input
              type="url"
              placeholder="https://…"
              value={form.prep_material_url}
              onChange={(e) => update("prep_material_url", e.target.value)}
            />
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Starts at">
              <Input
                type="datetime-local"
                required
                value={form.starts_at}
                onChange={(e) => update("starts_at", e.target.value)}
              />
            </Field>
            <Field label="Duration (minutes)">
              <Input
                type="number"
                min={15}
                max={240}
                required
                value={form.duration_minutes}
                onChange={(e) => update("duration_minutes", Number(e.target.value))}
              />
            </Field>
          </div>

          <div className="grid gap-5 sm:grid-cols-3">
            <Field label="Min seats" hint="Below this, it auto-cancels 2h before.">
              <Input
                type="number"
                min={1}
                max={50}
                required
                value={form.min_seats}
                onChange={(e) => update("min_seats", Number(e.target.value))}
              />
            </Field>
            <Field label="Max seats" hint="Above 8, talk time collapses.">
              <Input
                type="number"
                min={1}
                max={50}
                required
                value={form.max_seats}
                onChange={(e) => update("max_seats", Number(e.target.value))}
              />
            </Field>
            <Field label="Price (credits)">
              <Input
                type="number"
                min={0}
                max={100}
                required
                value={form.price_credits}
                onChange={(e) => update("price_credits", Number(e.target.value))}
              />
            </Field>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="accent-primary size-4"
              checked={form.publish}
              onChange={(e) => update("publish", e.target.checked)}
            />
            Publish immediately (creates the Meet link now)
          </label>

          {error && <p className="text-destructive text-sm">{error}</p>}

          <div className="flex gap-3">
            <Button type="submit" variant="brand" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              Create discussion
            </Button>
            <Button type="button" variant="ghost" onClick={() => router.push("/admin")}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
