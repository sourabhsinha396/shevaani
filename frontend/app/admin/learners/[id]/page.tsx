"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Coins, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { LearnerDetail } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const REASON_LABEL: Record<string, string> = {
  purchase: "Purchase",
  booking_spend: "Booked a session",
  booking_refund: "Cancelled in time",
  session_cancelled: "Session cancelled",
  admin_grant: "Granted by admin",
  admin_revoke: "Revoked by admin",
  signup_bonus: "Welcome credit",
  referral_bonus: "Referral reward",
};

export default function AdminLearnerPage() {
  const { id } = useParams<{ id: string }>();

  const [data, setData] = React.useState<LearnerDetail | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [adjust, setAdjust] = React.useState({ delta: 1, note: "" });

  const load = React.useCallback(async () => {
    try {
      setData(await api.adminLearner(id));
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

  async function submitAdjustment(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.adminAdjustCredits(id, adjust.delta, adjust.note || undefined);
      setAdjust({ delta: 1, note: "" });
      await load();
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

  if (!data) {
    return (
      <Card>
        <CardContent className="text-muted-foreground py-16 text-center text-sm">
          {error ?? "No such learner."}
        </CardContent>
      </Card>
    );
  }

  const { learner, bookings, ledger } = data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          href="/admin/learners"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="size-3.5" /> All learners
        </Link>
        <h2 className="mt-3 text-2xl tracking-tight">{learner.full_name}</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          {learner.email} · {learner.timezone} · joined{" "}
          {formatDateTime(learner.created_at)}
        </p>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Coins className="size-4" /> {learner.balance} credits
          </CardTitle>
          <CardDescription>
            The balance is the sum of the entries below - nothing is ever edited,
            so an adjustment adds a row rather than changing one. A negative
            number claws credits back and is refused if it would go below zero.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submitAdjustment} className="flex flex-wrap items-end gap-4">
            <Field label="Adjustment" className="w-32">
              <Input
                type="number"
                min={-500}
                max={500}
                required
                value={adjust.delta}
                onChange={(e) => setAdjust({ ...adjust, delta: Number(e.target.value) })}
              />
            </Field>
            <Field label="Note" className="min-w-64 flex-1" hint="Shown on the ledger row.">
              <Input
                maxLength={500}
                placeholder="Goodwill after the Meet link failed"
                value={adjust.note}
                onChange={(e) => setAdjust({ ...adjust, note: e.target.value })}
              />
            </Field>
            <Button type="submit" disabled={busy || adjust.delta === 0}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              Apply
            </Button>
          </form>
        </CardContent>
      </Card>

      <section>
        <h3 className="mb-3 font-medium">Bookings</h3>
        {bookings.length === 0 ? (
          <Card>
            <CardContent className="text-muted-foreground py-10 text-center text-sm">
              Nothing booked yet.
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-2">
            {bookings.map((booking) => (
              <Card key={booking.id}>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 text-sm">
                  <div>
                    <p className="font-medium">
                      <Link
                        href={`/admin/sessions/${booking.session_id}`}
                        className="underline-offset-4 hover:underline"
                      >
                        {booking.session_title}
                      </Link>
                    </p>
                    <p className="text-muted-foreground mt-1">
                      {formatDateTime(booking.starts_at)}
                      {booking.waitlist_position !== null &&
                        ` · waitlist #${booking.waitlist_position}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-muted-foreground">
                      {booking.credits_spent} credit
                      {booking.credits_spent === 1 ? "" : "s"}
                    </span>
                    <Badge variant="outline">{booking.status}</Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-3 font-medium">Credit ledger</h3>
        <Card>
          <CardContent className="flex flex-col divide-y text-sm">
            {ledger.length === 0 && (
              <p className="text-muted-foreground py-6 text-center">No entries.</p>
            )}
            {ledger.map((entry) => (
              <div
                key={entry.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
              >
                <div>
                  <p>{REASON_LABEL[entry.reason] ?? entry.reason}</p>
                  <p className="text-muted-foreground mt-0.5 text-xs">
                    {formatDateTime(entry.created_at)}
                    {entry.note ? ` · ${entry.note}` : ""}
                  </p>
                </div>
                <span
                  className={
                    entry.delta > 0 ? "text-[var(--success)]" : "text-muted-foreground"
                  }
                >
                  {entry.delta > 0 ? `+${entry.delta}` : entry.delta}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
