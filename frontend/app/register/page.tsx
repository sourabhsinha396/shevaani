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
import { browserTimeZone, detectCountry } from "@/lib/currency";
import { PASSWORD_HINT, PASSWORD_MIN_LENGTH } from "@/lib/passwords";

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();

  const [form, setForm] = React.useState({
    full_name: "",
    email: "",
    password: "",
  });
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.register({
        ...form,
        // Both read off the browser, which knows them better than a dropdown
        // would. The country used to be asked for because it picked the payment
        // provider; the currency does that now, so it is only kept for support
        // and can be null without costing anybody anything.
        timezone: browserTimeZone() || undefined,
        billing_country: detectCountry() ?? undefined,
      });
      await refresh();
      // Someone who came here from a pack on the pricing page is trying to buy,
      // not to browse — put them back where they were going.
      router.push(params.get("next") ?? "/discussions");
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
            <CardTitle className="text-2xl">Create your account</CardTitle>
            <CardDescription>
              Takes a minute. Half your first discussion is on us.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="flex flex-col gap-4">
              <Field label="Full name">
                <Input required value={form.full_name} onChange={set("full_name")} autoComplete="name" />
              </Field>
              <Field label="Email">
                <Input type="email" required value={form.email} onChange={set("email")} autoComplete="email" />
              </Field>
              <Field label="Password" hint={PASSWORD_HINT}>
                <Input
                  type="password"
                  required
                  minLength={PASSWORD_MIN_LENGTH}
                  value={form.password}
                  onChange={set("password")}
                  autoComplete="new-password"
                />
              </Field>
              {error && <p className="text-destructive text-sm">{error}</p>}

              <Button type="submit" variant="brand" size="lg" disabled={busy}>
                {busy && <Loader2 className="size-4 animate-spin" />}
                Create account
              </Button>
            </form>

            <p className="text-muted-foreground mt-6 text-center text-sm">
              Already have an account?{" "}
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

export default function RegisterPage() {
  // `?next=` is read with useSearchParams, which needs a boundary above it.
  return (
    <React.Suspense fallback={null}>
      <RegisterForm />
    </React.Suspense>
  );
}
