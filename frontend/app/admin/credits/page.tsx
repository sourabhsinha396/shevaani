"use client";

import * as React from "react";
import Link from "next/link";
import { Coins, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { api } from "@/lib/api";

type AdjustResult = {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  balance: number;
};

/**
 * Credits by email — one screen, one call. The learner search only surfaces
 * learners, so this is also the way to put test credits on a superuser or
 * instructor account.
 */
export default function AdminCreditsPage() {
  const [form, setForm] = React.useState({ email: "", delta: 1, note: "" });
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<AdjustResult | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await api.adminAdjustCreditsByEmail(
          form.email.trim(),
          form.delta,
          form.note || undefined,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Coins className="size-4" /> Adjust credits by email
          </CardTitle>
          <CardDescription>
            The exact address of any account — learner, instructor or superuser.
            A positive number grants, a negative one claws back and is refused if
            the balance would go below zero. Every adjustment is a ledger row.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex flex-wrap items-end gap-4">
            <Field label="Email" className="min-w-64 flex-1">
              <Input
                type="email"
                required
                maxLength={320}
                placeholder="learner@example.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </Field>
            <Field label="Adjustment" className="w-32">
              <Input
                type="number"
                min={-500}
                max={500}
                required
                value={form.delta}
                onChange={(e) => setForm({ ...form, delta: Number(e.target.value) })}
              />
            </Field>
            <Field label="Note" className="min-w-64 flex-1" hint="Shown on the ledger row.">
              <Input
                maxLength={500}
                placeholder="Goodwill after the Meet link failed"
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
              />
            </Field>
            <Button type="submit" disabled={busy || form.delta === 0}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              Apply
            </Button>
          </form>

          {error && <p className="text-destructive mt-4 text-sm">{error}</p>}

          {result && (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-[var(--success)]">
                Done — {result.full_name} ({result.email}) now has {result.balance}{" "}
                credit{result.balance === 1 ? "" : "s"}.
              </span>
              <Badge variant="outline">{result.role}</Badge>
              {result.role === "learner" && (
                <Link
                  href={`/admin/learners/${result.user_id}`}
                  className="underline underline-offset-4"
                >
                  View ledger
                </Link>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
