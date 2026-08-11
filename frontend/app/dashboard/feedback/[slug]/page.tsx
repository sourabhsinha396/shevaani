"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  Clock,
  Gauge,
  HelpCircle,
  Lightbulb,
  ListChecks,
  Loader2,
  MessagesSquare,
  Mic,
  Quote,
  BadgeCheck,
  Target,
  ThumbsUp,
  Timer,
  TrendingUp,
  Trophy,
  Users,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { ReportView } from "@/components/feedback/report-view";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type {
  FeedbackLanguageNote,
  FeedbackMetrics,
  FeedbackReport,
  GDScore,
} from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

function ordinal(n: number): string {
  const rem10 = n % 10;
  const rem100 = n % 100;
  if (rem10 === 1 && rem100 !== 11) return `${n}st`;
  if (rem10 === 2 && rem100 !== 12) return `${n}nd`;
  if (rem10 === 3 && rem100 !== 13) return `${n}rd`;
  return `${n}th`;
}

function minutesLabel(seconds: number): string {
  return `${(seconds / 60).toFixed(1)} min`;
}

/** One number with an icon and a caption. Not a chart on purpose - a single
 *  value reads faster as a tile than as a one-bar graph. */
function Stat({
  icon: Icon,
  value,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>;
  value: string;
  label: string;
}) {
  return (
    <div className="border-border/60 bg-surface-subtle flex flex-col gap-1 rounded-lg border p-4">
      <Icon className="text-brand-ink size-4" />
      <p className="text-foreground mt-1 text-xl font-medium tracking-tight">{value}</p>
      <p className="text-muted-foreground text-xs">{label}</p>
    </div>
  );
}

/** Horizontal talk-time bars, one per speaking learner, you in the brand
 *  colour and everyone else in a neutral - the page's one splash of colour,
 *  which is the house rule. Names and numbers stay in text ink; the bar only
 *  carries length. Toggleable between minutes and share of the room. */
function TalkTimeChart({ metrics }: { metrics: FeedbackMetrics }) {
  const [mode, setMode] = React.useState<"minutes" | "share">("minutes");
  const peers = metrics.peers ?? [];
  if (peers.length === 0) return null;

  const max = Math.max(
    ...peers.map((p) => (mode === "minutes" ? p.talk_time_seconds : p.talk_share)),
    0.001,
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Mic className="text-brand-ink size-4" /> Who spoke how much
          </CardTitle>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant={mode === "minutes" ? "secondary" : "ghost"}
              onClick={() => setMode("minutes")}
            >
              Minutes
            </Button>
            <Button
              size="sm"
              variant={mode === "share" ? "secondary" : "ghost"}
              onClick={() => setMode("share")}
            >
              % of room
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {peers.map((peer, i) => {
          const value = mode === "minutes" ? peer.talk_time_seconds : peer.talk_share;
          const label =
            mode === "minutes"
              ? minutesLabel(peer.talk_time_seconds)
              : `${Math.round(peer.talk_share * 100)}%`;
          return (
            <div key={`${peer.name}-${i}`} className="grid grid-cols-[6rem_1fr_3.5rem] items-center gap-3 text-sm">
              <span
                className={
                  peer.is_you ? "text-foreground truncate font-medium" : "text-muted-foreground truncate"
                }
              >
                {peer.is_you ? "You" : peer.name}
              </span>
              <div className="bg-muted/40 h-3 overflow-hidden rounded-full">
                <div
                  className={`h-full rounded-full transition-[width] duration-500 ${
                    peer.is_you ? "bg-brand" : "bg-muted-foreground/30"
                  }`}
                  style={{ width: `${Math.max((value / max) * 100, 2)}%` }}
                />
              </div>
              <span className="text-muted-foreground text-right text-xs tabular-nums">
                {label}
              </span>
            </div>
          );
        })}
        <p className="text-muted-foreground mt-1 text-xs text-pretty">
          Learners only - the instructor&apos;s time isn&apos;t counted. Computed
          from the transcript, so it&apos;s the same numbers your instructor sees.
        </p>
      </CardContent>
    </Card>
  );
}

/** Filler phrases as chips, biggest habit first. Counted mechanically from the
 *  transcript - the point is a number you can push down next session. */
function FillerWords({ metrics }: { metrics: FeedbackMetrics }) {
  const fillers = Object.entries(metrics.filler_words ?? {}).sort((a, b) => b[1] - a[1]);
  if (fillers.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessagesSquare className="text-brand-ink size-4" /> Filler words
          <Badge variant="secondary">{metrics.filler_total} total</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {fillers.map(([word, count]) => (
            <span
              key={word}
              className="border-border/60 bg-surface-subtle inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm"
            >
              &ldquo;{word}&rdquo;
              <span className="text-muted-foreground text-xs tabular-nums">×{count}</span>
            </span>
          ))}
        </div>
        <p className="text-muted-foreground mt-3 text-xs text-pretty">
          Everyone has these - fluent speakers just have fewer per minute. Pick
          your top one and try replacing it with a short pause next time.
        </p>
      </CardContent>
    </Card>
  );
}

/** Pillar order, weight, and whether the number comes from AI judgment of the
 *  transcript or from direct measurement. Mirrors services/gd_score.py. */
const SCORE_PILLARS = [
  { key: "content", label: "Content", llm: true },
  { key: "communication", label: "Communication", llm: false },
  { key: "collaboration", label: "Collaboration", llm: true },
  { key: "leadership", label: "Leadership", llm: true },
  { key: "participation", label: "Participation", llm: false },
] as const;

/** The composite headline plus five pillar bars. AI-judged pillars carry a
 *  spark so learners know which numbers are judgment and which are math. */
function ScoreCard({ score }: { score: GDScore }) {
  if (score.composite == null) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingUp className="text-brand-ink size-4" /> Your GD score
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <span className="text-foreground text-4xl font-medium tracking-tight tabular-nums">
            {score.composite}
          </span>
          <span className="text-muted-foreground text-sm">/ 100</span>
        </div>
        <div className="mt-5 flex flex-col gap-2.5">
          {SCORE_PILLARS.filter((p) => score.pillars[p.key] != null).map((p) => (
            <div
              key={p.key}
              className="grid grid-cols-[8rem_1fr_2.5rem] items-center gap-3 text-sm"
            >
              <span className="text-muted-foreground flex items-center gap-1.5">
                {p.label}
                {p.llm && <BadgeCheck className="size-3 opacity-60" />}
              </span>
              <div className="bg-muted/40 h-2 overflow-hidden rounded-full">
                <div
                  className="bg-brand h-full rounded-full transition-[width] duration-500"
                  style={{ width: `${score.pillars[p.key]}%` }}
                />
              </div>
              <span className="text-muted-foreground text-right text-xs tabular-nums">
                {score.pillars[p.key]}
              </span>
            </div>
          ))}
        </div>
        <p className="text-muted-foreground mt-4 text-xs text-pretty">
          <BadgeCheck className="mr-1 inline size-3 opacity-60" />
          Initiating or concluding, giving opportunities to others, speaking capabilites, including facts and figures are important for a good GD score. 
        </p>
      </CardContent>
    </Card>
  );
}

function NoteCard({ note, compact }: { note: FeedbackLanguageNote; compact?: boolean }) {
  return (
    <div className="border-border/60 bg-surface-subtle rounded-lg border p-3">
      <p className="text-muted-foreground italic">&ldquo;{note.quote}&rdquo;</p>
      <p className="mt-2 text-pretty">{note.issue}</p>
      <p className="text-brand-ink mt-2 flex items-start gap-1.5 font-medium">
        <ArrowRight className="mt-0.5 size-4 shrink-0" />
        <span>&ldquo;{note.better}&rdquo;</span>
      </p>
      {!compact && note.why && (
        <p className="text-muted-foreground mt-2 flex items-start gap-1.5 text-xs">
          <Lightbulb className="mt-0.5 size-3.5 shrink-0" />
          <span className="text-pretty">Why it matters: {note.why}</span>
        </p>
      )}
    </div>
  );
}

/** Major notes up front, each with its "why it matters" line; minor slips
 *  collapsed behind a toggle so the report reads as coaching, not as a list
 *  of everything the model noticed. Pre-severity reports have no severity
 *  field and render everything up front, as before. */
function LanguageNotes({ notes }: { notes: FeedbackLanguageNote[] }) {
  const [showMinor, setShowMinor] = React.useState(false);
  const major = notes.filter((n) => n.severity !== "minor");
  const minor = notes.filter((n) => n.severity === "minor");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Quote className="text-brand-ink size-4" /> Language notes
          {major.length > 0 && minor.length > 0 && (
            <Badge variant="secondary">{major.length} worth your attention</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm leading-relaxed">
        <div className="flex flex-col gap-4">
          {major.map((note, i) => (
            <NoteCard key={i} note={note} />
          ))}
          {minor.length > 0 && (
            <>
              <button
                type="button"
                onClick={() => setShowMinor((v) => !v)}
                className="text-muted-foreground hover:text-foreground flex items-center gap-2 text-left text-sm transition-colors"
              >
                <ChevronDown
                  className={`size-4 shrink-0 transition-transform ${showMinor ? "rotate-180" : ""}`}
                />
                {minor.length === 1
                  ? "1 minor note - a small slip that didn't change how you came across"
                  : `${minor.length} minor notes - small slips that didn't change how you came across`}
              </button>
              {showMinor && minor.map((note, i) => <NoteCard key={i} note={note} compact />)}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="text-brand-ink size-4" /> {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm leading-relaxed">{children}</CardContent>
    </Card>
  );
}

export default function SessionFeedbackPage() {
  const { slug } = useParams<{ slug: string }>();
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [report, setReport] = React.useState<FeedbackReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [notFound, setNotFound] = React.useState(false);

  React.useEffect(() => {
    if (!authLoading && !user)
      router.replace(`/login?next=${encodeURIComponent(`/dashboard/feedback/${slug}`)}`);
  }, [authLoading, user, router, slug]);

  React.useEffect(() => {
    if (!user) return;
    api
      .sessionFeedback(slug)
      .then(setReport)
      .catch((e) => {
        if ((e as ApiError).status === 404) setNotFound(true);
        else setError((e as Error).message);
      });
  }, [user, slug]);

  if (authLoading || !user || (report === null && !error && !notFound)) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-24 text-center">
        <p className="text-muted-foreground text-pretty">
          No feedback for this session yet. It appears here once your instructor
          has reviewed and published it - usually within a day or two of the
          discussion.
        </p>
        <Button asChild variant="outline" className="mt-6">
          <Link href="/dashboard/feedback">All your feedback</Link>
        </Button>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-24 text-center">
        <p className="text-destructive text-sm">{error}</p>
      </div>
    );
  }

  const { metrics, structured } = report;
  const hasNumbers = metrics.talk_time_seconds != null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <Link
        href="/dashboard/feedback"
        className="text-muted-foreground inline-flex items-center gap-1 text-sm hover:underline"
      >
        <ArrowLeft className="size-4" /> All your feedback
      </Link>

      <header className="mt-4">
        <div className="flex flex-wrap items-center gap-2">
          {metrics.rank != null && metrics.peer_count != null && metrics.peer_count > 1 && (
            <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-sm">
              <Trophy className="size-3.5 text-[var(--warning)]" />
              {ordinal(metrics.rank)} of {metrics.peer_count} speakers
            </Badge>
          )}
        </div>
        <h1 className="mt-3 text-2xl tracking-tight text-balance">{report.session_title}</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          {formatDateTime(report.session_starts_at, user.timezone)} · feedback
          published {formatDateTime(report.published_at, user.timezone)}
        </p>
      </header>

      <div className="mt-8 flex flex-col gap-6">
        {structured?.summary && (
          <Section icon={BadgeCheck} title="How you did">
            <p className="text-pretty">{structured.summary}</p>
          </Section>
        )}

        {report.score && <ScoreCard score={report.score} />}

        {hasNumbers && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat
              icon={Clock}
              value={minutesLabel(metrics.talk_time_seconds!)}
              label={
                metrics.talk_share != null
                  ? `speaking time · ${Math.round(metrics.talk_share * 100)}% of the room`
                  : "speaking time"
              }
            />
            {metrics.turns != null && (
              <Stat icon={MessagesSquare} value={`${metrics.turns}`} label="times you took the floor" />
            )}
            {metrics.questions_asked != null && (
              <Stat icon={HelpCircle} value={`${metrics.questions_asked}`} label="questions you asked" />
            )}
            {metrics.longest_monologue_seconds != null && (
              <Stat
                icon={Timer}
                value={minutesLabel(metrics.longest_monologue_seconds)}
                label="longest stretch"
              />
            )}
            {metrics.words_per_minute != null && metrics.words_per_minute > 0 && (
              <Stat icon={Gauge} value={`${Math.round(metrics.words_per_minute)}`} label="words per minute" />
            )}
            {metrics.filler_total != null && (
              <Stat icon={Quote} value={`${metrics.filler_total}`} label="filler words" />
            )}
          </div>
        )}

        <TalkTimeChart metrics={metrics} />
        <FillerWords metrics={metrics} />

        {structured ? (
          <>
            {structured.strengths.length > 0 && (
              <Section icon={ThumbsUp} title="What worked">
                <ul className="flex flex-col gap-2">
                  {structured.strengths.map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <Check className="text-brand-ink mt-0.5 size-4 shrink-0" />
                      <span className="text-pretty">{item}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {structured.areas_to_improve.length > 0 && (
              <Section icon={Target} title="What to work on">
                <ul className="flex flex-col gap-2">
                  {structured.areas_to_improve.map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <ArrowUpRight className="text-muted-foreground mt-0.5 size-4 shrink-0" />
                      <span className="text-pretty">{item}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {structured.language_notes.length > 0 && (
              <LanguageNotes notes={structured.language_notes} />
            )}

            {structured.collaboration && (
              <Section icon={Users} title="Working with the group">
                <p className="text-pretty">{structured.collaboration}</p>
              </Section>
            )}

            {structured.suggestions.length > 0 && (
              <Section icon={ListChecks} title="Before your next session">
                <ol className="flex flex-col gap-2.5">
                  {structured.suggestions.map((item, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <span className="bg-brand text-brand-foreground flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-medium">
                        {i + 1}
                      </span>
                      <span className="text-pretty">{item}</span>
                    </li>
                  ))}
                </ol>
              </Section>
            )}
          </>
        ) : (
          // Reports written before feedback was structured (and silent-
          // participant reports) only exist as markdown - render that.
          <Card>
            <CardContent>
              <ReportView markdown={report.report_md} />
            </CardContent>
          </Card>
        )}

        <div className="flex justify-center pb-4">
          <Button asChild variant="brand">
            <Link href="/discussions">Book your next discussion</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
