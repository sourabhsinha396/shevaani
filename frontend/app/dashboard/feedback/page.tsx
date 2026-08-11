"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Loader2, TrendingDown, TrendingUp, Trophy } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { MetricsRow } from "@/components/feedback/report-view";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { FeedbackReport } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

/** GD score with a delta against the learner's previous scored session -
 *  the one-glance "am I improving?" answer. Deltas only compare scores from
 *  the same rubric version; across a version boundary the number alone shows. */
function ScoreBadge({
  report,
  reports,
}: {
  report: FeedbackReport;
  reports: FeedbackReport[];
}) {
  const score = report.score;
  if (score?.composite == null) return null;
  // Newest first, so the previous session is the next scored report after this one.
  const index = reports.findIndex((r) => r.id === report.id);
  const previous = reports
    .slice(index + 1)
    .find(
      (r) =>
        r.score?.composite != null && r.score.rubric_version === score.rubric_version,
    );
  const delta = previous?.score?.composite != null ? score.composite - previous.score.composite : null;
  return (
    <Badge variant="secondary" className="gap-1.5 tabular-nums">
      {score.composite}
      <span className="text-muted-foreground font-normal">/ 100</span>
      {delta != null && delta !== 0 && (
        <span
          className={`flex items-center gap-0.5 ${
            delta > 0 ? "text-[var(--success)]" : "text-[var(--warning)]"
          }`}
        >
          {delta > 0 ? (
            <TrendingUp className="size-3" />
          ) : (
            <TrendingDown className="size-3" />
          )}
          {delta > 0 ? `+${delta}` : delta}
        </span>
      )}
    </Badge>
  );
}

/** The index: one card per published report, each linking to the session's
 *  own feedback page at `/dashboard/feedback/<slug>` - where the full
 *  report, the talk-time graph, and the rank live. */
export default function FeedbackIndexPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [reports, setReports] = React.useState<FeedbackReport[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/dashboard/feedback");
  }, [authLoading, user, router]);

  React.useEffect(() => {
    if (!user) return;
    api
      .myFeedback()
      .then((data) => {
        // One report needs no list - go straight to it.
        if (data.length === 1) {
          router.replace(`/dashboard/feedback/${data[0].session_slug}`);
          return;
        }
        setReports(data);
      })
      .catch((e) => setError((e as Error).message));
  }, [user, router]);

  if (authLoading || !user || (reports === null && !error)) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <Link
        href="/dashboard"
        className="text-muted-foreground inline-flex items-center gap-1 text-sm hover:underline"
      >
        <ArrowLeft className="size-4" /> Back to your sessions
      </Link>
      <h1 className="mt-4 text-2xl tracking-tight">Your feedback</h1>
      <p className="text-muted-foreground mt-1 text-sm">
        Personal feedback from each group discussion, written up after the session.
      </p>

      {error && <p className="text-destructive mt-6 text-sm">{error}</p>}

      {reports !== null && reports.length === 0 && !error && (
        <Card className="mt-8">
          <CardContent className="text-muted-foreground py-16 text-center text-sm">
            Nothing here yet. Feedback appears after a discussion you attended has been
            reviewed by your instructor.
          </CardContent>
        </Card>
      )}

      <div className="mt-8 space-y-4">
        {reports?.map((report) => (
          <Link
            key={report.id}
            href={`/dashboard/feedback/${report.session_slug}`}
            className="group block"
          >
            <Card className="transition-colors group-hover:border-brand-ink/40">
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-lg">{report.session_title}</CardTitle>
                    <p className="text-muted-foreground mt-1 text-sm">
                      {formatDateTime(report.session_starts_at, user.timezone)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <ScoreBadge report={report} reports={reports} />
                    {report.metrics.rank != null &&
                      report.metrics.peer_count != null &&
                      report.metrics.peer_count > 1 && (
                        <Badge variant="secondary" className="gap-1">
                          <Trophy className="size-3 text-[var(--warning)]" />
                          {report.metrics.rank}/{report.metrics.peer_count}
                        </Badge>
                      )}
                    <ArrowRight className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5" />
                  </div>
                </div>
                <MetricsRow metrics={report.metrics} />
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
