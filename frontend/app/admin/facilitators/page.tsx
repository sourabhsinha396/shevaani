"use client";

import * as React from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AdminFacilitator } from "@/lib/types";

export default function AdminFacilitatorsPage() {
  const [facilitators, setFacilitators] = React.useState<AdminFacilitator[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .adminFacilitators()
      .then(setFacilitators)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="bg-muted/30">
        <CardContent className="text-muted-foreground text-sm">
          Facilitators are created from the backend CLI —{" "}
          <code className="bg-muted rounded px-1.5 py-0.5 text-xs">
            docker compose run --rm api python -m app.cli create-facilitator
          </code>
          . A facilitator can only host once they have connected their own Google account,
          because the Meet link is created on their calendar; that is what makes them the
          host who can admit people from the lobby.
        </CardContent>
      </Card>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {facilitators.map((f) => (
        <Card key={f.id}>
          <CardContent className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="font-medium">{f.full_name}</p>
              <p className="text-muted-foreground mt-1 text-sm">{f.email}</p>
            </div>
            <div className="flex items-center gap-2">
              {!f.is_active && <Badge variant="secondary">Inactive</Badge>}
              {f.google_connected ? (
                <Badge variant="success" title={f.google_email ?? undefined}>
                  <CheckCircle2 /> Google connected
                </Badge>
              ) : (
                <Badge variant="destructive">
                  <XCircle /> Cannot host
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
