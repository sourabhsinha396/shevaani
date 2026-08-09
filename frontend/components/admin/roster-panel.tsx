"use client";

import * as React from "react";
import { Check, Loader2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { Roster } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

/**
 * Who is in the session, and the attendance controls.
 *
 * Shared by the superuser session page and the instructor's own list — the two
 * must never disagree about who is on the list, so they render the same
 * component over the same payload. Only the endpoint behind `onConfirm`
 * differs, because the instructor's version is scoped to their own sessions
 * server-side.
 */
export function RosterPanel({
  roster,
  loading,
  onConfirm,
  hideEmails = false,
}: {
  roster: Roster | null;
  loading?: boolean;
  onConfirm: (bookingId: string, attended: boolean) => Promise<void>;
  hideEmails?: boolean;
}) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function confirm(bookingId: string, attended: boolean) {
    setBusy(bookingId);
    setError(null);
    try {
      await onConfirm(bookingId, attended);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 py-8 text-sm">
        <Loader2 className="size-4 animate-spin" /> Loading roster…
      </div>
    );
  }

  if (!roster) return null;

  const { confirmed, waitlist } = roster;

  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-destructive text-sm">{error}</p>}

      {confirmed.length === 0 ? (
        <Card className="bg-muted/30">
          <CardContent className="text-muted-foreground py-8 text-center text-sm">
            Nobody has booked this yet.
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {confirmed.map((entry) => (
            <Card key={entry.booking_id}>
              <CardContent className="flex flex-wrap items-center justify-between gap-4 text-sm">
                <div className="min-w-56">
                  <p className="font-medium">
                    {entry.name}
                    {entry.level && (
                      <Badge variant="secondary" className="ml-2">
                        {entry.level}
                      </Badge>
                    )}
                  </p>
                  <p className="text-muted-foreground mt-1">
                    {/* The instructor's roster arrives without addresses at all;
                        `hideEmails` only stops an empty separator showing. */}
                    {!hideEmails && entry.email && <>{entry.email} · </>}
                    {/* The join click is the automatic attendance signal; the
                        instructor's confirmation overrides it. */}
                    {entry.first_joined_at
                      ? `joined ${formatDateTime(entry.first_joined_at)}`
                      : "no join recorded"}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {entry.status === "attended" && (
                    <Badge variant="success">Attended</Badge>
                  )}
                  {entry.status === "no_show" && (
                    <Badge variant="destructive">No show</Badge>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy === entry.booking_id}
                    onClick={() => void confirm(entry.booking_id, true)}
                  >
                    {busy === entry.booking_id ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Check className="size-4" />
                    )}
                    Attended
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy === entry.booking_id}
                    onClick={() => void confirm(entry.booking_id, false)}
                  >
                    <X className="size-4" /> No show
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {waitlist.length > 0 && (
        <div>
          <p className="eyebrow mb-2">Waitlist</p>
          <div className="flex flex-col gap-2">
            {waitlist.map((entry) => (
              <Card key={entry.booking_id}>
                <CardContent className="flex items-center justify-between gap-4 text-sm">
                  <span>{entry.name}</span>
                  {/* No credit is taken for a waitlist place — it is charged on
                      promotion — so there is nothing to refund here. */}
                  <span className="text-muted-foreground">#{entry.position}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
