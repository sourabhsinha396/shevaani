"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, MailWarning } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { PASSWORD_HINT, PASSWORD_MIN_LENGTH as MIN_LENGTH } from "@/lib/passwords";
import { sessionBalanceLabel, sessionDeltaLabel } from "@/lib/pricing";
import type { LedgerEntry } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const LEDGER_LABEL: Record<string, string> = {
  purchase: "Sessions bought",
  booking_spend: "Booked a session",
  booking_refund: "Cancelled in time - returned",
  session_cancelled: "Session cancelled - returned",
  admin_grant: "Granted by Shevaani",
  admin_revoke: "Adjusted by Shevaani",
  signup_bonus: "Welcome bonus",
  referral_bonus: "Friend enrolled - thank you",
};

/** The full ledger, moved here from the dashboard - the dashboard is about
 *  sessions; what you've bought and spent is an account matter. */
function BalanceCard() {
  const { user, credits } = useAuth();
  const [ledger, setLedger] = React.useState<LedgerEntry[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .creditLedger()
      .then(setLedger)
      .catch((e) => setError((e as Error).message));
  }, []);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Your balance</CardTitle>
            <CardDescription>
              Nothing is ever edited or removed, so this is the full story of
              every session you have bought and spent.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="px-3 py-1.5 text-sm">
              {sessionBalanceLabel(credits)} left
            </Badge>
            <Button asChild size="sm" variant="outline">
              <Link href="/checkout">Buy more</Link>
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col divide-y text-sm">
        {error && <p className="text-destructive py-2">{error}</p>}
        {ledger !== null && ledger.length === 0 && (
          <p className="text-muted-foreground py-6 text-center">
            Nothing here yet.{" "}
            <Link href="/checkout" className="text-foreground underline underline-offset-4">
              Buy some
            </Link>
            .
          </p>
        )}
        {ledger?.map((entry) => (
          <div
            key={entry.id}
            className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
          >
            <div>
              <p>{LEDGER_LABEL[entry.reason] ?? entry.reason}</p>
              <p className="text-muted-foreground mt-0.5 text-xs">
                {formatDateTime(entry.created_at, user?.timezone)}
                {entry.note ? ` · ${entry.note}` : ""}
              </p>
            </div>
            <span
              className={
                entry.delta > 0 ? "text-[var(--success)]" : "text-muted-foreground"
              }
            >
              {sessionDeltaLabel(entry.delta)}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function EmailCard() {
  const { user, refresh } = useAuth();
  const [busy, setBusy] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const verified = Boolean(user?.email_verified_at);

  async function resend() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { detail } = await api.sendEmailVerification();
      setNotice(detail);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Email</CardTitle>
        <CardDescription>{user?.email}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {verified ? (
          <Badge variant="success" className="w-fit">
            <CheckCircle2 /> Confirmed {formatDateTime(user!.email_verified_at!, user?.timezone)}
          </Badge>
        ) : (
          <div className="flex items-start gap-3 text-sm">
            <MailWarning className="mt-0.5 size-4 shrink-0 text-[var(--warning)]" />
            <div>
              <p className="font-medium">Not confirmed yet</p>
              {/* Say what it actually costs. Nothing is blocked, and claiming
                  otherwise to force the click would be a lie. */}
              <p className="text-muted-foreground mt-1 text-pretty">
                Everything still works - booking, joining, your balance. What an
                unconfirmed address risks is the reminders and joining links we
                send you going nowhere.
              </p>
            </div>
          </div>
        )}

        {notice && <p className="text-sm text-[var(--success)]">{notice}</p>}
        {error && <p className="text-destructive text-sm">{error}</p>}

        {!verified && (
          <Button variant="outline" size="sm" className="w-fit" disabled={busy} onClick={() => void resend()}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            Send a confirmation link
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function PasswordCard() {
  const [form, setForm] = React.useState({ current: "", next: "", confirm: "" });
  const [busy, setBusy] = React.useState(false);
  const [done, setDone] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const mismatch = form.confirm.length > 0 && form.confirm !== form.next;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await api.changePassword(form.current, form.next);
      setForm({ current: "", next: "", confirm: "" });
      setDone(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Password</CardTitle>
        <CardDescription>
          Changing it signs out every other browser signed into this account.
          This one stays signed in.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex max-w-sm flex-col gap-4">
          <Field label="Current password">
            <Input
              type="password"
              autoComplete="current-password"
              required
              value={form.current}
              onChange={(e) => setForm({ ...form, current: e.target.value })}
            />
          </Field>
          <Field label="New password" hint={PASSWORD_HINT}>
            <Input
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_LENGTH}
              value={form.next}
              onChange={(e) => setForm({ ...form, next: e.target.value })}
            />
          </Field>
          <Field label="Confirm new password">
            <Input
              type="password"
              autoComplete="new-password"
              required
              value={form.confirm}
              onChange={(e) => setForm({ ...form, confirm: e.target.value })}
              aria-invalid={mismatch || undefined}
            />
          </Field>

          {mismatch && <p className="text-destructive text-sm">Those don&apos;t match.</p>}
          {error && <p className="text-destructive text-sm">{error}</p>}
          {done && <p className="text-sm text-[var(--success)]">Password changed.</p>}

          <Button
            type="submit"
            variant="brand"
            className="w-fit"
            disabled={busy || mismatch || form.next.length < MIN_LENGTH}
          >
            {busy && <Loader2 className="size-4 animate-spin" />}
            Change password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function AccountPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!loading && !user) router.replace("/login?next=/account");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-12">
      <header>
        <h1 className="text-3xl tracking-tight">Your account</h1>
        <p className="text-muted-foreground mt-2">
          {user.full_name} · times are shown in {user.timezone}.
        </p>
      </header>

      <BalanceCard />
      <EmailCard />
      <PasswordCard />

      <Card className="bg-muted/30">
        <CardContent className="text-muted-foreground text-sm text-pretty">
          To close the account or ask for a copy of your data, use the{" "}
          <Link href="/contact" className="text-foreground underline underline-offset-4">
            contact form
          </Link>
          .
        </CardContent>
      </Card>
    </div>
  );
}
