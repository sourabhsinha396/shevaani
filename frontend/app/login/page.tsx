"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Recaptcha, recaptchaEnabled, type RecaptchaHandle } from "@/components/recaptcha";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { signIn } = useAuth();

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [captcha, setCaptcha] = React.useState<string | null>(null);
  const captchaRef = React.useRef<RecaptchaHandle>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password, captcha ?? undefined);
      router.push(params.get("next") ?? "/dashboard");
    } catch (e) {
      setError((e as Error).message);
      // The token went with the failed attempt and is spent either way - a
      // retry needs a fresh tick, so clear the widget with the error.
      captchaRef.current?.reset();
    } finally {
      setBusy(false);
    }
  }

  return (
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
      <Field label="Password">
        <Input
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>

      <Link
        href="/forgot-password"
        className="text-muted-foreground hover:text-foreground -mt-1 self-start text-sm underline-offset-4 hover:underline"
      >
        Forgot your password?
      </Link>

      <Recaptcha ref={captchaRef} onChange={setCaptcha} />

      {error && <p className="text-destructive text-sm">{error}</p>}

      <Button
        type="submit"
        variant="brand"
        size="lg"
        disabled={busy || (recaptchaEnabled && !captcha)}
      >
        {busy && <Loader2 className="size-4 animate-spin" />}
        Sign in
      </Button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="bg-surface-subtle min-h-full">
      <div className="mx-auto flex max-w-md flex-col px-4 py-20">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Welcome back</CardTitle>
            <CardDescription>Sign in to book and join your sessions.</CardDescription>
          </CardHeader>
          <CardContent>
            <React.Suspense fallback={<Loader2 className="size-4 animate-spin" />}>
              <LoginForm />
            </React.Suspense>
            <p className="text-muted-foreground mt-6 text-center text-sm">
              No account yet?{" "}
              <Link href="/register" className="text-foreground underline underline-offset-4">
                Create one
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
