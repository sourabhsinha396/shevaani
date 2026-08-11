"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Loader2, Mail, MessageSquareText, Sparkles } from "lucide-react";

import { ReportView } from "@/components/feedback/report-view";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { FeedbackSpeaker, FeedbackTranscriptDetail } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const IGNORE = "__ignore__";
const UNASSIGNED = "";

/** How long to keep polling after Finalize before assuming something stalled.
 *  Generation is one model call, typically well under a minute. */
const FINALIZE_POLL_MS = 3000;
const FINALIZE_POLL_LIMIT = 60;

function speakerValue(speaker: FeedbackSpeaker): string {
  if (speaker.ignored) return IGNORE;
  return speaker.user_id ?? UNASSIGNED;
}

export default function AdminFeedbackDetailPage() {
  const { id } = useParams<{ id: string }>();

  const [data, setData] = React.useState<FeedbackTranscriptDetail | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [finalizing, setFinalizing] = React.useState(false);
  const [openReport, setOpenReport] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const detail = await api.feedbackTranscript(id);
      setData(detail);
      return detail;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, [id]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function act(key: string, action: () => Promise<unknown>, message?: string) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await action();
      await load();
      if (message) setNotice(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function mapSpeaker(speaker: FeedbackSpeaker, value: string) {
    const payload =
      value === IGNORE
        ? { user_id: null, ignored: true }
        : { user_id: value === UNASSIGNED ? null : value, ignored: false };
    void act(speaker.id, () => api.feedbackMapSpeaker(speaker.id, payload));
  }

  async function finalize() {
    setFinalizing(true);
    setError(null);
    setNotice(null);
    try {
      await api.feedbackFinalize(id);
      // The worker regenerates and publishes; poll until every report shows
      // published (or give up loudly rather than spin forever).
      for (let i = 0; i < FINALIZE_POLL_LIMIT; i++) {
        await new Promise((resolve) => setTimeout(resolve, FINALIZE_POLL_MS));
        const detail = await load();
        if (
          detail &&
          detail.total_reports > 0 &&
          detail.published_reports === detail.total_reports
        ) {
          setNotice("Feedback published — learners can see it now.");
          setFinalizing(false);
          return;
        }
      }
      setError("Still generating after a few minutes — check the worker logs.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setFinalizing(false);
    }
  }

  if (!data && !error) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  const unmatched = data?.unmatched_speakers ?? 0;

  return (
    <div className="space-y-6">
      <Link
        href="/admin/feedback"
        className="text-muted-foreground inline-flex items-center gap-1 text-sm hover:underline"
      >
        <ArrowLeft className="size-4" /> All transcripts
      </Link>

      {error && <p className="text-destructive text-sm">{error}</p>}
      {notice && <p className="text-sm text-[var(--success)]">{notice}</p>}

      {data && (
        <>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-xl tracking-tight">{data.session_title}</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                {formatDateTime(data.session_starts_at)}
                {data.duration_minutes != null &&
                  ` · ${Math.round(data.duration_minutes)} min recorded`}
              </p>
            </div>
            <Button
              variant="brand"
              disabled={finalizing || unmatched > 0}
              onClick={() => void finalize()}
            >
              {finalizing ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              {finalizing ? "Generating…" : "Finalize feedback"}
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Who is who</CardTitle>
              <CardDescription>
                Each name below is how someone appeared in the Meet. Correct any the
                matcher got wrong, mark strangers and bots as &ldquo;Not a
                participant&rdquo;, then finalize.
                {unmatched > 0 &&
                  ` ${unmatched} still need${unmatched === 1 ? "s" : ""} a decision.`}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.speakers.map((speaker) => {
                const taken = new Set(
                  data.speakers
                    .filter((s) => s.id !== speaker.id && s.user_id)
                    .map((s) => s.user_id),
                );
                const unresolved = !speaker.ignored && !speaker.user_id;
                return (
                  <div
                    key={speaker.id}
                    className="flex flex-wrap items-center justify-between gap-3"
                  >
                    <div className="flex min-w-48 items-center gap-2">
                      <span className="font-medium">{speaker.speaker_label}</span>
                      {unresolved && <Badge variant="warning">Unmatched</Badge>}
                      {speaker.resolved_via === "auto" && speaker.confidence != null && (
                        <span className="text-muted-foreground text-xs">
                          auto · {Math.round(speaker.confidence * 100)}%
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {busy === speaker.id && <Loader2 className="size-4 animate-spin" />}
                      <Select
                        className="w-64"
                        value={speakerValue(speaker)}
                        disabled={busy === speaker.id}
                        onChange={(e) => mapSpeaker(speaker, e.target.value)}
                      >
                        <option value={UNASSIGNED}>— Unassigned —</option>
                        {data.roster.map((person) => (
                          <option
                            key={person.id}
                            value={person.id}
                            disabled={taken.has(person.id)}
                          >
                            {person.full_name} ({person.email})
                            {taken.has(person.id) ? " — already mapped" : ""}
                          </option>
                        ))}
                        <option value={IGNORE}>Not a participant (bot / guest)</option>
                      </Select>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>

          <section className="space-y-4">
            <h3 className="text-lg tracking-tight">
              Reports{" "}
              <span className="text-muted-foreground text-sm font-normal">
                {data.published_reports}/{data.total_reports} published
              </span>
            </h3>

            {data.reports.length === 0 && (
              <Card>
                <CardContent className="text-muted-foreground py-10 text-center text-sm">
                  No reports yet — finalize to generate and publish them.
                </CardContent>
              </Card>
            )}

            {data.reports.map((report) => {
              const expanded = openReport === report.id;
              return (
                <Card key={report.id}>
                  <CardContent className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{report.learner.full_name}</span>
                        <Badge variant={report.status === "published" ? "success" : "outline"}>
                          {report.status}
                        </Badge>
                        {report.emailed_at && (
                          <span className="text-muted-foreground text-xs">
                            emailed {formatDateTime(report.emailed_at)}
                          </span>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setOpenReport(expanded ? null : report.id)}
                        >
                          <MessageSquareText className="size-4" />
                          {expanded ? "Hide" : "Preview"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busy === report.id || report.status !== "published"}
                          onClick={() =>
                            void act(
                              report.id,
                              () => api.feedbackEmailReport(report.id),
                              `Emailed to ${report.learner.email}.`,
                            )
                          }
                        >
                          {busy === report.id ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Mail className="size-4" />
                          )}
                          {report.emailed_at ? "Email again" : "Email feedback"}
                        </Button>
                      </div>
                    </div>
                    {expanded && (
                      <div className="border-t pt-4">
                        <ReportView markdown={report.report_md} />
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </section>
        </>
      )}
    </div>
  );
}
