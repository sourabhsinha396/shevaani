"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

/**
 * Opened from an email, which means it usually lands in whichever browser the
 * mail app chose — often not the one holding the session. So this page does not
 * require a signed-in user: the token is the proof. If a session happens to be
 * present, it is refreshed so the banner disappears immediately.
 */
function VerifyEmail() {
  const params = useSearchParams();
  const { user, refresh } = useAuth();
  const token = params.get("token") ?? "";

  const [state, setState] = React.useState<"working" | "done" | "failed">("working");
  const [message, setMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!token) {
      setState("failed");
      setMessage("That link is incomplete — copy the whole one out of the email.");
      return;
    }
    let cancelled = false;
    api
      .verifyEmail(token)
      .then(async () => {
        if (cancelled) return;
        setState("done");
        await refresh();
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setState("failed");
        setMessage(e.message);
      });
    return () => {
      cancelled = true;
    };
    // Deliberately keyed on the token alone: `refresh` changes identity on every
    // auth state change and would re-spend a single-use token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (state === "working") {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" /> Confirming…
      </p>
    );
  }

  if (state === "done") {
    return (
      <div className="flex items-start gap-3 text-sm">
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-[var(--success)]" />
        <div>
          <p className="font-medium">Address confirmed</p>
          <p className="text-muted-foreground mt-1 text-pretty">
            Session reminders and joining links will reach you now.
          </p>
          <Button asChild variant="brand" size="sm" className="mt-4">
            <Link href={user ? "/dashboard" : "/login"}>
              {user ? "Back to my sessions" : "Sign in"}
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 text-sm">
      <XCircle className="text-destructive mt-0.5 size-5 shrink-0" />
      <div>
        <p className="font-medium">Couldn&apos;t confirm that link</p>
        <p className="text-muted-foreground mt-1 text-pretty">{message}</p>
        <p className="text-muted-foreground mt-3 text-pretty">
          Nothing is broken — your account works either way. Sign in and send
          yourself a fresh link from{" "}
          <Link href="/account" className="text-foreground underline underline-offset-4">
            your account
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="bg-surface-subtle min-h-full">
      <div className="mx-auto flex max-w-md flex-col px-4 py-20">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Confirming your email</CardTitle>
          </CardHeader>
          <CardContent>
            <React.Suspense fallback={<Loader2 className="size-4 animate-spin" />}>
              <VerifyEmail />
            </React.Suspense>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
