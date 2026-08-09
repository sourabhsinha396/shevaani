"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2, MailCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = React.useState("");
  const [sent, setSent] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.forgotPassword(email);
      // The API answers identically for a registered and an unregistered
      // address, and so does this screen — branching here would hand back the
      // account oracle the endpoint is careful not to be.
      setSent(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-surface-subtle min-h-full">
      <div className="mx-auto flex max-w-md flex-col px-4 py-20">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Forgot your password?</CardTitle>
            <CardDescription>
              Put in the address you signed up with and we&apos;ll send a link to set a
              new one.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {sent ? (
              <div className="flex items-start gap-3">
                <MailCheck className="mt-0.5 size-5 shrink-0 text-[var(--success)]" />
                <div className="text-sm">
                  <p className="font-medium">Check your inbox</p>
                  <p className="text-muted-foreground mt-1 text-pretty">
                    If <strong className="text-foreground">{email}</strong> has an
                    account, a reset link is on its way. It expires in 30 minutes and
                    works once. Nothing has changed on your account yet.
                  </p>
                </div>
              </div>
            ) : (
              <form onSubmit={submit} className="flex flex-col gap-4">
                <Field label="Email">
                  <Input
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </Field>

                {error && <p className="text-destructive text-sm">{error}</p>}

                <Button type="submit" variant="brand" size="lg" disabled={busy}>
                  {busy && <Loader2 className="size-4 animate-spin" />}
                  Send reset link
                </Button>
              </form>
            )}

            <p className="text-muted-foreground mt-6 text-center text-sm">
              Remembered it?{" "}
              <Link href="/login" className="text-foreground underline underline-offset-4">
                Sign in
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
