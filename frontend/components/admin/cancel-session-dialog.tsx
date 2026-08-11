"use client";

import * as React from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { CancellationImpact } from "@/lib/types";

/**
 * Cancelling refunds *every* live booking regardless of the 12-hour cutoff that
 * applies to a learner cancelling their own seat. That is the right behaviour
 * and also the surprising one, so the cost is fetched and spelled out before the
 * button does anything.
 */
export function CancelSessionDialog({
  sessionId,
  title,
  onCancelled,
  onClose,
}: {
  sessionId: string;
  title: string;
  onCancelled: () => void | Promise<void>;
  onClose: () => void;
}) {
  const [impact, setImpact] = React.useState<CancellationImpact | null>(null);
  const [reason, setReason] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .adminCancellationImpact(sessionId)
      .then(setImpact)
      .catch((e: Error) => setError(e.message));
  }, [sessionId]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.adminCancel(sessionId, reason);
      await onCancelled();
      onClose();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <Card className="border-destructive/40">
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="text-destructive mt-0.5 size-4 shrink-0" />
            <div className="text-sm">
              <p className="font-medium">Cancel “{title}”?</p>
              <p className="text-muted-foreground mt-1 text-pretty">
                {impact === null
                  ? "Working out what this would refund…"
                  : impact.bookings_affected === 0
                    ? "Nobody has booked it, so nothing will be refunded."
                    : `${impact.bookings_affected} booking(s) will be cancelled and ` +
                      `${impact.credits_refunded} credit(s) returned to ` +
                      `${impact.learners_refunded} learner(s), ignoring the usual ` +
                      `12-hour cutoff` +
                      (impact.waitlisted > 0
                        ? `. ${impact.waitlisted} waitlisted learner(s) will be dropped - they were never charged.`
                        : ".")}
              </p>
            </div>
          </div>

          <Field
            label="Reason"
            hint="Sent to everyone booked, so write it for them rather than for the log."
          >
            <Textarea
              required
              rows={2}
              minLength={1}
              maxLength={500}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="The instructor is unwell - we'll run this again on Thursday."
            />
          </Field>

          {error && <p className="text-destructive text-sm">{error}</p>}

          <div className="flex gap-2">
            <Button type="submit" variant="destructive" size="sm" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              Cancel session and refund
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Keep it
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
