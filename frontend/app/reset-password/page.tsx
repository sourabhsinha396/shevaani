"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { PASSWORD_HINT, PASSWORD_MIN_LENGTH as MIN_LENGTH } from "@/lib/passwords";

function ResetForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const token = params.get("token") ?? "";

  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const tooShort = password.length > 0 && password.length < MIN_LENGTH;
  const mismatch = confirm.length > 0 && confirm !== password;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.resetPassword(token, password);
      // The reset signs this browser in, so pick the new session up rather than
      // sending someone to a login form to retype what they just chose.
      await refresh();
      router.push("/dashboard");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <div className="text-sm">
        <p className="font-medium">That link is incomplete.</p>
        <p className="text-muted-foreground mt-1 text-pretty">
          Reset links carry a token. Copy the whole link out of the email, or{" "}
          <Link href="/forgot-password" className="text-foreground underline underline-offset-4">
            ask for a new one
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field label="New password" hint={PASSWORD_HINT}>
        <Input
          type="password"
          autoComplete="new-password"
          required
          minLength={MIN_LENGTH}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={tooShort || undefined}
        />
      </Field>
      <Field label="Confirm new password">
        <Input
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          aria-invalid={mismatch || undefined}
        />
      </Field>

      {mismatch && <p className="text-destructive text-sm">Those don&apos;t match.</p>}
      {error && <p className="text-destructive text-sm">{error}</p>}

      <Button
        type="submit"
        variant="brand"
        size="lg"
        disabled={busy || mismatch || password.length < MIN_LENGTH}
      >
        {busy && <Loader2 className="size-4 animate-spin" />}
        Set new password
      </Button>

      <p className="text-muted-foreground text-xs text-pretty">
        Setting a new password signs out every other browser on this account.
      </p>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="bg-surface-subtle min-h-full">
      <div className="mx-auto flex max-w-md flex-col px-4 py-20">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Choose a new password</CardTitle>
            <CardDescription>
              This link works once, and only for the next 30 minutes.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* useSearchParams needs a Suspense boundary above it. */}
            <React.Suspense fallback={<Loader2 className="size-4 animate-spin" />}>
              <ResetForm />
            </React.Suspense>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
