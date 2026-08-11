"use client";

import * as React from "react";
import Link from "next/link";
import { Coins, Loader2, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { LearnerSummary } from "@/lib/types";

export default function AdminLearnersPage() {
  const [query, setQuery] = React.useState("");
  const [learners, setLearners] = React.useState<LearnerSummary[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Support questions arrive as half a name, so search as you type - but not on
  // every keystroke, which would be one request per letter.
  React.useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      api
        .adminLearners(query || undefined)
        .then((rows) => {
          setLearners(rows);
          setError(null);
        })
        .catch((e: Error) => setError(e.message))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  return (
    <div className="flex flex-col gap-4">
      <div className="relative max-w-md">
        <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
        <Input
          className="pl-9"
          placeholder="Search by name or email…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {loading ? (
        <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
          <Loader2 className="size-4 animate-spin" /> Loading…
        </div>
      ) : learners.length === 0 ? (
        <Card>
          <CardContent className="text-muted-foreground py-16 text-center text-sm">
            {query ? `Nobody matches “${query}”.` : "No learners yet."}
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {learners.map((learner) => (
            <Card key={learner.id}>
              <CardContent className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="font-medium">
                    <Link
                      href={`/admin/learners/${learner.id}`}
                      className="underline-offset-4 hover:underline"
                    >
                      {learner.full_name}
                    </Link>
                    {!learner.is_active && (
                      <Badge variant="secondary" className="ml-2">
                        Inactive
                      </Badge>
                    )}
                  </p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {learner.email} · {learner.timezone}
                  </p>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <Badge variant="secondary" className="gap-1.5">
                    <Coins className="size-3" />
                    {learner.balance} credits
                  </Badge>
                  <span className="text-muted-foreground">
                    {learner.upcoming_bookings} upcoming
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
