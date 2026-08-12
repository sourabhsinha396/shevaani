"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Loader2, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { RichTextEditor } from "@/components/ui/rich-text";
import { api } from "@/lib/api";
import type { AdminInstructor } from "@/lib/types";

/** Mirrors `services/slugs.py::slugify` so the form shows what the server will
 *  store. Uniqueness is still the server's job - a taken slug gets `-2`. */
function slugify(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 240)
      .replace(/-+$/, "") || "session"
  );
}

export default function NewSessionPage() {
  const router = useRouter();
  const [instructors, setInstructors] = React.useState<AdminInstructor[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [quickBusy, setQuickBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  // The slug follows the title until somebody edits it by hand.
  const [slugTouched, setSlugTouched] = React.useState(false);

  const [form, setForm] = React.useState({
    instructor_id: "",
    title: "",
    slug: "",
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

  /** One click, one bookable session five minutes out. For rehearsing the
   *  learner flow end to end - booking, the Meet link, joining - without
   *  filling the form. Published immediately, so it needs a hostable
   *  instructor: the selected one if they can host, else the first who can. */
  async function createQuickTest() {
    const host =
      (selected?.google_connected && selected.is_active ? selected : null) ??
      instructors.find((f) => f.google_connected && f.is_active);
    if (!host) {
      setError(
        "No active instructor has a Google account connected, so a published test session can't get its Meet link.",
      );
      return;
    }

    setQuickBusy(true);
    setError(null);
    try {
      const startsAt = new Date(Date.now() + 5 * 60_000);
      // The date-time in the title keeps every test's slug distinct on its own,
      // and tells the tests apart in the session list.
      const stamp = startsAt.toLocaleString(undefined, {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
      const created = await api.adminCreateSession({
        instructor_id: host.id,
        title: `Quick test ${stamp}`,
        slug: null,
        topic: "Test - ignore",
        description: null,
        prep_material_url: null,
        starts_at: startsAt.toISOString(),
        duration_minutes: 15, // the shortest the API allows
        min_seats: 1, // never auto-cancels for want of bookings
        max_seats: 6,
        price_credits: 1,
        publish: true,
      });
      // Straight to the session's admin page, where the Meet link status lives.
      router.push(`/admin/sessions/${created.id}`);
    } catch (e) {
      setError((e as Error).message);
      setQuickBusy(false);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.adminCreateSession({
        ...form,
        slug: form.slug || null,
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
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>New group discussion</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={quickBusy || instructors.length === 0}
            onClick={() => void createQuickTest()}
          >
            {quickBusy ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Zap className="size-4" />
            )}
            Quick test in 5 min
          </Button>
        </div>
        <p className="text-muted-foreground text-sm">
          The quick test publishes a 15-minute, 1-credit session starting in 5
          minutes - no form needed.
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-5">
          <Field
            label="Instructor"
            hint="Only instructors who have connected a Google account can host - the Meet link is created on their calendar."
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
                  {f.google_connected ? "" : " - no Google account"}
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
              placeholder="Tuesday Debate Club - is remote work over?"
              value={form.title}
              onChange={(e) => {
                const title = e.target.value;
                setForm((prev) => ({
                  ...prev,
                  title,
                  ...(slugTouched ? {} : { slug: slugify(title) }),
                }));
              }}
            />
          </Field>

          <Field
            label="Slug"
            hint={`The session's URL: /discussions/${form.slug || "…"}. Auto-filled from the title; edit if you want a different one. If it's taken, the server appends -2.`}
          >
            <Input
              maxLength={250}
              placeholder="tuesday-debate-club-is-remote-work-over"
              value={form.slug}
              onChange={(e) => {
                setSlugTouched(true);
                update("slug", e.target.value);
              }}
              onBlur={() => {
                if (!form.slug.trim()) {
                  // Cleared by hand - go back to following the title.
                  setSlugTouched(false);
                  update("slug", slugify(form.title));
                } else {
                  update("slug", slugify(form.slug));
                }
              }}
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
            <RichTextEditor
              placeholder="What the group will actually talk about, and who it suits."
              value={form.description}
              onChange={(html) => update("description", html)}
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
