"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { api } from "@/lib/api";

const COUNTRIES = [
  { code: "IN", label: "India" },
  { code: "US", label: "United States" },
  { code: "GB", label: "United Kingdom" },
  { code: "AE", label: "United Arab Emirates" },
  { code: "SG", label: "Singapore" },
  { code: "DE", label: "Germany" },
];

export default function RegisterPage() {
  const router = useRouter();
  const { refresh } = useAuth();

  const [form, setForm] = React.useState({
    full_name: "",
    email: "",
    password: "",
    billing_country: "IN",
  });
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.register({
        ...form,
        // The browser knows this better than any dropdown would.
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      await refresh();
      router.push("/discussions");
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
              Takes a minute. Your first discussion credit is free.
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
              <Field label="Password" hint="At least 10 characters.">
                <Input
                  type="password"
                  required
                  minLength={10}
                  value={form.password}
                  onChange={set("password")}
                  autoComplete="new-password"
                />
              </Field>
              <Field label="Country" hint="Decides which payment provider you'll check out with.">
                <Select value={form.billing_country} onChange={set("billing_country")}>
                  {COUNTRIES.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.label}
                    </option>
                  ))}
                </Select>
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
