"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";

/**
 * Deliberately open to people without an account — a payment provider reviewing
 * the site has to be able to reach us, and so does someone whose problem *is*
 * that they cannot sign in. Signed-in visitors get the fields filled in and the
 * message linked to their account.
 */
export default function ContactPage() {
  const { user } = useAuth();
  const [sent, setSent] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({
    name: "",
    email: "",
    subject: "",
    body: "",
  });

  // The auth state resolves after the first paint, so fill in once it arrives —
  // without clobbering anything already typed.
  React.useEffect(() => {
    if (!user) return;
    setForm((prev) => ({
      ...prev,
      name: prev.name || user.full_name,
      email: prev.email || user.email,
    }));
  }, [user]);

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.contact(form);
      setSent(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 md:py-20">
      <h1 className="text-4xl tracking-tight text-balance">Contact us</h1>
      <p className="text-muted-foreground mt-4 text-pretty">
        Questions about a booking, a credit, or the service in general. We reply
        to the address you give here within two working days.
      </p>

      {sent ? (
        <Card className="mt-10">
          <CardContent className="flex items-start gap-3 py-4">
            <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-[var(--success)]" />
            <div>
              <p className="font-medium">Message sent</p>
              <p className="text-muted-foreground mt-1 text-sm text-pretty">
                We&apos;ll reply to {form.email} within two working days. If it
                is about a session starting sooner than that, say so in a second
                message and we&apos;ll pick it up first.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="mt-10">
          <CardHeader>
            <CardTitle>Send a message</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="flex flex-col gap-5">
              <div className="grid gap-5 sm:grid-cols-2">
                <Field label="Your name">
                  <Input
                    required
                    maxLength={200}
                    value={form.name}
                    onChange={(e) => update("name", e.target.value)}
                  />
                </Field>
                <Field label="Email" hint="Where the reply goes.">
                  <Input
                    type="email"
                    required
                    value={form.email}
                    onChange={(e) => update("email", e.target.value)}
                  />
                </Field>
              </div>

              <Field label="Subject">
                <Input
                  required
                  maxLength={200}
                  placeholder="Refund for Tuesday's discussion"
                  value={form.subject}
                  onChange={(e) => update("subject", e.target.value)}
                />
              </Field>

              <Field
                label="Message"
                hint="If it's about a specific session, the date and title help."
              >
                <Textarea
                  required
                  rows={6}
                  minLength={10}
                  maxLength={5000}
                  value={form.body}
                  onChange={(e) => update("body", e.target.value)}
                />
              </Field>

              {error && <p className="text-destructive text-sm">{error}</p>}

              <div>
                <Button type="submit" variant="brand" disabled={busy}>
                  {busy && <Loader2 className="size-4 animate-spin" />}
                  Send message
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <p className="text-muted-foreground mt-8 text-sm text-pretty">
        Cancelling or refunding a session yourself is usually faster — the rules
        are on the <Link href="/refunds">refund policy</Link> page, and your
        bookings are under <Link href="/dashboard">My sessions</Link>.
      </p>
    </div>
  );
}
