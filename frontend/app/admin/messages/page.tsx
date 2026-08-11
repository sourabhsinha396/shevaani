"use client";

import * as React from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { ContactMessage } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

/**
 * The contact form writes rows rather than sending mail, so this is where they
 * are actually read. "Handled" is a note to the next person, not a workflow.
 */
export default function AdminMessagesPage() {
  const [filter, setFilter] = React.useState("open");
  const [messages, setMessages] = React.useState<ContactMessage[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const handled = filter === "all" ? undefined : filter === "handled";
      setMessages(await api.adminContactMessages(handled));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function markHandled(id: string) {
    setBusy(id);
    try {
      const note = window.prompt("Note (optional) - what did you do about it?");
      await api.adminMarkContactHandled(id, note || undefined);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Select value={filter} onChange={(e) => setFilter(e.target.value)} className="w-48">
        <option value="open">Needs a reply</option>
        <option value="handled">Handled</option>
        <option value="all">All</option>
      </Select>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {loading ? (
        <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
          <Loader2 className="size-4 animate-spin" /> Loading…
        </div>
      ) : messages.length === 0 ? (
        <Card>
          <CardContent className="text-muted-foreground py-16 text-center text-sm">
            Nothing here.
          </CardContent>
        </Card>
      ) : (
        messages.map((message) => (
          <Card key={message.id}>
            <CardContent className="flex flex-col gap-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{message.subject}</p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {message.name} · {message.email} · {formatDateTime(message.created_at)}
                    {message.user_id ? " · has an account" : " · not signed in"}
                  </p>
                </div>
                {message.handled_at ? (
                  <Badge variant="success">
                    <CheckCircle2 /> Handled
                  </Badge>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy === message.id}
                    onClick={() => void markHandled(message.id)}
                  >
                    {busy === message.id && <Loader2 className="size-4 animate-spin" />}
                    Mark handled
                  </Button>
                )}
              </div>

              <p className="text-muted-foreground text-sm whitespace-pre-wrap">
                {message.body}
              </p>

              {message.handled_note && (
                <p className="text-muted-foreground border-border/60 border-l-2 pl-3 text-xs">
                  {message.handled_note}
                </p>
              )}

              <div>
                <Button asChild size="sm" variant="ghost">
                  <a href={`mailto:${message.email}?subject=Re: ${encodeURIComponent(message.subject)}`}>
                    Reply by email
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
