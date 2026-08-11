"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { FeedbackTranscriptSummary } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

function statusBadge(transcript: FeedbackTranscriptSummary) {
  if (transcript.unmatched_speakers > 0) {
    return <Badge variant="warning">Needs review</Badge>;
  }
  if (transcript.published_reports > 0) {
    return <Badge variant="success">Published</Badge>;
  }
  return <Badge variant="outline">Ready to finalize</Badge>;
}

export default function AdminFeedbackPage() {
  const [transcripts, setTranscripts] = React.useState<FeedbackTranscriptSummary[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .feedbackTranscripts()
      .then(setTranscripts)
      .catch((e) => setError((e as Error).message));
  }, []);

  if (transcripts === null && !error) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-muted-foreground text-sm">
        Every recorded discussion, newest first. Fix any speaker the matcher couldn&apos;t
        place, then finalize to publish the feedback to learners.
      </p>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {transcripts?.length === 0 && (
        <Card>
          <CardContent className="text-muted-foreground py-16 text-center text-sm">
            No transcripts yet. They appear here a few minutes after a recorded
            discussion ends.
          </CardContent>
        </Card>
      )}

      {transcripts?.map((transcript) => (
        <Card key={transcript.id}>
          <CardContent className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-64">
              <div className="flex flex-wrap items-center gap-2">
                {statusBadge(transcript)}
                {transcript.unmatched_speakers > 0 && (
                  <span className="text-muted-foreground text-xs">
                    {transcript.unmatched_speakers} speaker
                    {transcript.unmatched_speakers > 1 ? "s" : ""} unmatched
                  </span>
                )}
              </div>
              <p className="mt-2 font-medium">{transcript.session_title}</p>
              <p className="text-muted-foreground mt-1 text-sm">
                {formatDateTime(transcript.session_starts_at)}
                {transcript.duration_minutes != null &&
                  ` · ${Math.round(transcript.duration_minutes)} min recorded`}
                {` · ${transcript.published_reports}/${transcript.total_reports} reports published`}
              </p>
            </div>
            <Button asChild size="sm" variant="outline">
              <Link href={`/admin/feedback/${transcript.id}`}>Review</Link>
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
