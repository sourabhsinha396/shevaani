"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CalendarOff, CheckCircle2, Loader2, Plus, Trash2, XCircle } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Block } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const REASONS = [
  { value: "busy", label: "Busy" },
  { value: "holiday", label: "Holiday" },
  { value: "sick", label: "Sick" },
  { value: "other", label: "Other" },
];

function GoogleCard() {
  const params = useSearchParams();
  const [status, setStatus] = React.useState<{
    connected: boolean;
    google_email: string | null;
  } | null>(null);

  const load = React.useCallback(() => {
    api.googleStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  React.useEffect(load, [load]);

  const callback = params.get("google");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Google account</CardTitle>
        <CardDescription>
          Sessions you host create a Calendar event on your account, which makes you the
          Meet host — you can admit people from the lobby, mute, and remove.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-4">
        {status?.connected ? (
          <Badge variant="success">
            <CheckCircle2 /> Connected as {status.google_email}
          </Badge>
        ) : (
          <Badge variant="destructive">
            <XCircle /> Not connected — you can&apos;t host yet
          </Badge>
        )}

        <Button asChild variant={status?.connected ? "outline" : "brand"}>
          <a href={api.googleConnectUrl()}>
            {status?.connected ? "Reconnect" : "Connect Google"}
          </a>
        </Button>

        {callback === "denied" && (
          <p className="text-muted-foreground w-full text-sm">
            You declined the Google permission request.
          </p>
        )}
        {callback === "failed" && (
          <p className="text-destructive w-full text-sm">
            Google rejected the connection. If you have authorised Shevaani before, revoke
            it at myaccount.google.com and try again.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default function FacilitatorPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [blocks, setBlocks] = React.useState<Block[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({ starts_at: "", ends_at: "", reason: "busy", note: "" });

  React.useEffect(() => {
    if (!authLoading && (!user || user.role === "learner")) router.replace("/");
  }, [authLoading, user, router]);

  const load = React.useCallback(async () => {
    if (!user) return;
    try {
      setBlocks(await api.listBlocks(user.id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [user]);

  React.useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function addBlock(event: React.FormEvent) {
    event.preventDefault();
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      await api.createBlock(user.id, {
        starts_at: new Date(form.starts_at).toISOString(),
        ends_at: new Date(form.ends_at).toISOString(),
        reason: form.reason,
        note: form.note || undefined,
      });
      setForm({ starts_at: "", ends_at: "", reason: "busy", note: "" });
      await load();
    } catch (e) {
      // The API refuses to block over live sessions and names them — surface it verbatim.
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeBlock(id: string) {
    if (!user) return;
    setBusy(true);
    try {
      await api.deleteBlock(user.id, id);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <header>
        <h1 className="text-3xl tracking-tight">Your calendar</h1>
        <p className="text-muted-foreground mt-2">
          Block the time you&apos;re unavailable and nobody can book you then.
        </p>
      </header>

      <React.Suspense fallback={null}>
        <GoogleCard />
      </React.Suspense>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Block time</CardTitle>
          <CardDescription>
            Blocked time is removed from your one-to-one slots immediately. If a session is
            already booked in the range, we&apos;ll tell you which one rather than cancelling
            it behind your back.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={addBlock} className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="From">
                <Input
                  type="datetime-local"
                  required
                  value={form.starts_at}
                  onChange={(e) => setForm({ ...form, starts_at: e.target.value })}
                />
              </Field>
              <Field label="Until">
                <Input
                  type="datetime-local"
                  required
                  value={form.ends_at}
                  onChange={(e) => setForm({ ...form, ends_at: e.target.value })}
                />
              </Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Reason">
                <Select
                  value={form.reason}
                  onChange={(e) => setForm({ ...form, reason: e.target.value })}
                >
                  {REASONS.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Note (optional)">
                <Input
                  maxLength={500}
                  value={form.note}
                  onChange={(e) => setForm({ ...form, note: e.target.value })}
                />
              </Field>
            </div>

            {error && <p className="text-destructive text-sm">{error}</p>}

            <Button type="submit" disabled={busy} className="self-start">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              Block this time
            </Button>
          </form>
        </CardContent>
      </Card>

      <section>
        <h2 className="font-sans mb-4 font-medium">Upcoming blocks</h2>
        {blocks.length === 0 ? (
          <Card>
            <CardContent className="text-muted-foreground flex flex-col items-center gap-2 py-12 text-center text-sm">
              <CalendarOff className="size-6" />
              Nothing blocked. You&apos;re bookable across the whole window.
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-2">
            {blocks.map((block) => (
              <Card key={block.id}>
                <CardContent className="flex items-center justify-between gap-4 text-sm">
                  <div>
                    <p className="font-medium">
                      {formatDateTime(block.starts_at, user?.timezone)} →{" "}
                      {formatDateTime(block.ends_at, user?.timezone)}
                    </p>
                    <p className="text-muted-foreground mt-1 capitalize">
                      {block.reason}
                      {block.note ? ` · ${block.note}` : ""}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Remove block"
                    disabled={busy}
                    onClick={() => void removeBlock(block.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
