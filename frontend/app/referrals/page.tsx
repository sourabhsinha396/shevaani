"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Check, Copy, Gift, Loader2, UserPlus, Users } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { sessionLabel, sessionsFrom } from "@/lib/pricing";
import { canonical } from "@/lib/seo";
import type { ReferralSummary } from "@/lib/types";
import { formatDate } from "@/lib/utils";

/** The link people actually share. The homepage rather than /register - the
 *  code is remembered from any landing page, and "look at this site" is a much
 *  easier message to send than "sign up for this site". */
function inviteUrl(code: string): string {
  return `${canonical("/")}/?r=${code}`;
}

function inviteMessage(code: string): string {
  return `I've been practising English on SheVaani - small group discussions, real instructors. Join me: ${inviteUrl(code)}`;
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = React.useState(false);
  const [failed, setFailed] = React.useState(false);

  function copy() {
    navigator.clipboard.writeText(text).then(
      () => {
        setFailed(false);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2000);
      },
      () => setFailed(true),
    );
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={copy}>
        {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
        {copied ? "Copied" : label}
      </Button>
      {failed && (
        <span className="text-muted-foreground text-xs">
          Couldn&apos;t reach the clipboard - select the text and copy it.
        </span>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="py-5">
        <p className="text-2xl tabular-nums">{value}</p>
        <p className="text-muted-foreground mt-1 text-sm">{label}</p>
      </CardContent>
    </Card>
  );
}

export default function ReferralsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [summary, setSummary] = React.useState<ReferralSummary | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/referrals");
  }, [authLoading, user, router]);

  React.useEffect(() => {
    if (!user) return;
    api.myReferrals().then(setSummary, (e: Error) => setError(e.message));
  }, [user]);

  if (authLoading || !user || (!summary && !error)) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-20">
        <p className="text-destructive text-sm">{error ?? "Something went wrong."}</p>
      </div>
    );
  }

  // "1 free session", in the unit the reader thinks in. The API says what a
  // referral is worth in credits so this page never hardcodes the price.
  const rewardLabel = sessionLabel(Math.max(1, sessionsFrom(summary.reward_credits)));

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl tracking-tight">Refer a friend</h1>
      <p className="text-muted-foreground mt-2 max-w-xl text-pretty">
        Share your link. When someone joins from it and enrols - you get {rewardLabel} free.
      </p>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Gift className="size-4" /> Your invite link
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            <p className="border-border/60 bg-surface-subtle min-w-0 flex-1 truncate rounded-md border p-3 font-mono text-sm select-all">
              {inviteUrl(summary.code)}
            </p>
            <CopyButton text={inviteUrl(summary.code)} label="Copy link" />
          </div>

          <p className="text-muted-foreground mt-6 mb-2 text-sm">
            Or send the whole message:
          </p>
          <div className="flex flex-wrap items-start gap-2">
            <p className="border-border/60 bg-surface-subtle min-w-0 flex-1 rounded-md border p-3 text-sm leading-relaxed text-pretty select-all">
              {inviteMessage(summary.code)}
            </p>
            <CopyButton text={inviteMessage(summary.code)} label="Copy" />
          </div>
        </CardContent>
      </Card>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Stat label="joined from your link" value={String(summary.total_joined)} />
        <Stat label="enrolled" value={String(summary.total_enrolled)} />
        <Stat
          label="free sessions earned"
          value={String(sessionsFrom(summary.credits_earned))}
        />
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Users className="size-4" /> People you&apos;ve brought
          </CardTitle>
        </CardHeader>
        <CardContent>
          {summary.referrals.length === 0 ? (
            <p className="text-muted-foreground py-6 text-center text-sm">
              Nobody yet. The first name shows up here the moment somebody signs
              up from your link.
            </p>
          ) : (
            <ul className="divide-border/60 divide-y">
              {summary.referrals.map((entry, index) => (
                <li
                  key={`${entry.first_name}-${entry.joined_at}-${index}`}
                  className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
                >
                  <span className="flex items-center gap-2">
                    <UserPlus className="text-muted-foreground size-4" />
                    <span className="font-medium">{entry.first_name}</span>
                    <span className="text-muted-foreground">
                      joined {formatDate(entry.joined_at)}
                    </span>
                  </span>
                  {entry.enrolled_at ? (
                    <span className="text-xs font-medium text-[var(--success)]">
                      Enrolled - you earned{" "}
                      {sessionLabel(Math.max(1, sessionsFrom(entry.reward_credits)))}
                    </span>
                  ) : (
                    <span className="text-muted-foreground text-xs">
                      Not enrolled yet - you&apos;ll get {rewardLabel} when they buy
                      their first sessions
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
