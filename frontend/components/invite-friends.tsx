"use client";

import * as React from "react";
import Link from "next/link";
import { Check, Copy, UserPlus } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { canonical } from "@/lib/seo";
import type { DiscussionSession } from "@/lib/types";
import { cn } from "@/lib/utils";

const IST = "Asia/Kolkata";

/**
 * Like `formatDateTime`, but it names the timezone - "7:00 pm IST" rather than
 * "7:00 pm". The rest of the app can leave the zone implicit because it renders
 * for one reader, in their own timezone. This string gets pasted to somebody
 * else, who is not necessarily in it, and a bare time is how people miss a
 * session they meant to join.
 */
function inviteTime(iso: string, timeZone: string = IST) {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZoneName: "short",
    timeZone,
  }).format(new Date(iso));
}

/** One line, because it is going into WhatsApp and anything longer gets edited
 *  down by the sender - badly, usually dropping the link. The sender's referral
 *  code rides along on the URL, so if the friend signs up and enrols, the
 *  sender's free session follows without them doing anything extra. */
export function inviteLine(session: DiscussionSession, timezone?: string, refCode?: string | null) {
  const when = inviteTime(session.starts_at, timezone);
  const path = `/discussions/${session.slug ?? session.id}`;
  const url = canonical(path) + (refCode ? `?r=${refCode}` : "");
  return `I'm doing a live English discussion on - ${when}. Join me at: ${url}`;
}

/**
 * Asks a booked learner to bring someone, and hands them the exact words.
 *
 * The gating lives in here rather than at the call sites so the two of them
 * cannot drift: there is no point advertising a room that is full, cancelled,
 * already over, or a one-to-one that by definition has no spare seat.
 */
export function InviteFriends({
  session,
  timezone,
  className,
}: {
  session: DiscussionSession;
  timezone?: string;
  className?: string;
}) {
  const { user } = useAuth();
  const [copied, setCopied] = React.useState(false);
  const [failed, setFailed] = React.useState(false);

  const line = inviteLine(session, timezone, user?.referral_code);

  function copy() {
    // Clipboard access rejects on an insecure origin and when the permission is
    // refused. Say so rather than showing a "Copied" that did not happen - the
    // line is on screen and selectable either way.
    navigator.clipboard.writeText(line).then(
      () => {
        setFailed(false);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2000);
      },
      () => setFailed(true),
    );
  }

  if (
    session.kind !== "group" ||
    session.is_full ||
    session.status !== "published" ||
    new Date(session.starts_at).getTime() <= Date.now()
  ) {
    return null;
  }

  return (
    <div
      className={cn(
        "border-border/60 bg-surface-subtle rounded-lg border p-4",
        className,
      )}
    >
      <p className="flex items-center gap-2 text-sm font-medium">
        <UserPlus className="size-4" /> <span className="text-brand-ink">Refer & 1 free session</span>
      </p>
      <p className="text-muted-foreground mt-1 text-sm text-pretty">
        When someone enrols from your link, you get <span className="text-brand-ink">a free session</span>.{" "}
        <Link href="/referrals" className="underline underline-offset-4">
          How referrals work
        </Link>
      </p>

      <div className="mt-3 flex flex-wrap items-start gap-2">
        <p className="border-border/60 bg-background min-w-0 flex-1 rounded-md border p-3 text-sm leading-relaxed text-pretty select-all">
          {line}
        </p>
        <Button variant="outline" size="sm" onClick={copy}>
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>

      {failed && (
        <p className="text-muted-foreground mt-2 text-sm">
          Could not reach the clipboard - select the line above and copy it.
        </p>
      )}
    </div>
  );
}
