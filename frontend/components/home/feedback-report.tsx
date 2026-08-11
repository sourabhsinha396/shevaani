import Link from "next/link";
import { ArrowRight, Hand, Lightbulb, Repeat2, Shuffle } from "lucide-react";

import { Reveal } from "@/components/magicui/effects";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * A worked example of the report every learner gets after a discussion. The
 * numbers are illustrative but shaped like real output: strong on listening,
 * short on airtime - a believable first-report profile, not a brag sheet.
 */
const SKILLS = [
  { label: "Clarity", you: 78, avg: 64 },
  { label: "Reasoning", you: 71, avg: 66 },
  { label: "Listening", you: 84, avg: 58 },
  { label: "Airtime", you: 52, avg: 67 },
  { label: "Vocabulary", you: 61, avg: 60 },
];

const MOMENTS = [
  {
    at: "04:12",
    icon: Lightbulb,
    good: true,
    text: "Opened with the strongest framing in the session.",
  },
  {
    at: "17:40",
    icon: Hand,
    good: false,
    text: "Cut off mid-point - and never reclaimed the floor.",
  },
  {
    at: "26:05",
    icon: Shuffle,
    good: true,
    text: "Turned Priya's example into your counter-argument.",
  },
  {
    at: "38:50",
    icon: Repeat2,
    good: false,
    text: "Said “basically” nine times under pressure.",
  },
];

/* Radar geometry. Axis 0 points straight up; the rest fan clockwise. */
const CX = 150;
const CY = 108;
const R = 74;

function point(axis: number, value: number): [number, number] {
  const angle = (Math.PI * 2 * axis) / SKILLS.length - Math.PI / 2;
  const r = (R * value) / 100;
  return [CX + Math.cos(angle) * r, CY + Math.sin(angle) * r];
}

function ring(value: number) {
  return SKILLS.map((_, i) => point(i, value).join(",")).join(" ");
}

function Radar() {
  return (
    <svg
      viewBox="0 0 300 216"
      role="img"
      aria-label="Radar chart of five discussion skills, you against the group average"
      className="w-full max-w-xs"
    >
      {[25, 50, 75, 100].map((step) => (
        <polygon
          key={step}
          points={ring(step)}
          className="fill-none stroke-border"
        />
      ))}
      {SKILLS.map((_, i) => {
        const [x, y] = point(i, 100);
        return (
          <line
            key={i}
            x1={CX}
            y1={CY}
            x2={x}
            y2={y}
            className="stroke-border"
          />
        );
      })}

      <polygon
        points={SKILLS.map((s, i) => point(i, s.avg).join(",")).join(" ")}
        strokeDasharray="4 3"
        className="fill-none stroke-muted-foreground/70"
      />
      <polygon
        points={SKILLS.map((s, i) => point(i, s.you).join(",")).join(" ")}
        strokeWidth={2}
        className="fill-brand/25 stroke-brand-ink"
      />
      {SKILLS.map((s, i) => {
        const [x, y] = point(i, s.you);
        return <circle key={s.label} cx={x} cy={y} r={3} className="fill-brand-ink" />;
      })}

      {SKILLS.map((s, i) => {
        const [x, y] = point(i, 127);
        return (
          <text
            key={s.label}
            x={x}
            y={y}
            dy="0.35em"
            textAnchor={
              Math.abs(x - CX) < 1 ? "middle" : x > CX ? "start" : "end"
            }
            className="fill-muted-foreground text-[11px]"
          >
            {s.label}
          </text>
        );
      })}
    </svg>
  );
}

export function FeedbackReport() {
  return (
    <section className="section">
      <div className="container-page">
        <Reveal className="max-w-2xl">
          <p className="eyebrow mb-5">The feedback</p>
          <h2 className="text-4xl text-balance">
            Feedback report, minutes after the discussion
          </h2>
          <p className="text-muted-foreground mt-5 text-pretty">
            Minutes after the session ends: how you compared with your peers,
            and exactly what to fix next time.
          </p>
        </Reveal>

        <Reveal
          delay={100}
          className="border-border/60 mt-12 grid overflow-hidden rounded-xl border lg:grid-cols-5"
        >
          {/* ------------------------------------------ you vs the session */}
          <div className="border-border/60 flex flex-col p-6 sm:p-8 lg:col-span-2 lg:border-r">
            <p className="text-muted-foreground text-xs">
              Should cities ban private cars? · group of 6 · 45 min
            </p>
            <p className="font-heading mt-4 text-3xl leading-snug text-balance">
              You rank{" "}
              <span className="bg-brand text-brand-foreground rounded-md px-2">
                4 out of 6
              </span>{" "}
              peers.
            </p>

            <div className="mt-6 flex justify-center">
              <Radar />
            </div>

            <div className="text-muted-foreground mt-4 flex justify-center gap-5 text-xs">
              <span className="flex items-center gap-1.5">
                <span className="bg-brand size-2.5 rounded-[3px]" />
                You
              </span>
              <span className="flex items-center gap-1.5">
                <span className="border-muted-foreground/70 w-3 border-t border-dashed" />
                Group average
              </span>
            </div>
          </div>

          {/* ----------------------------------------- moments that mattered */}
          <div className="bg-surface-subtle flex flex-col p-6 sm:p-8 lg:col-span-3">
            <p className="eyebrow">Moments that mattered</p>

            <div className="mt-4 flex flex-col">
              {MOMENTS.map((moment, i) => (
                <div
                  key={moment.at}
                  className={cn(
                    "flex items-start gap-3 py-3.5",
                    i < MOMENTS.length - 1 && "border-border/60 border-b",
                  )}
                >
                  <span className="text-muted-foreground w-10 shrink-0 pt-px text-xs tabular-nums">
                    {moment.at}
                  </span>
                  <moment.icon
                    aria-hidden
                    className={cn(
                      "mt-px size-4 shrink-0",
                      moment.good
                        ? "text-[var(--success)]"
                        : "text-[var(--warning)]",
                    )}
                  />
                  <p className="text-sm text-pretty">{moment.text}</p>
                </div>
              ))}
            </div>

            <div className="border-border/60 mt-auto flex flex-wrap items-center gap-4 border-t pt-6">
              <Button asChild variant="brand">
                <Link href="/discussions">
                  Find a discussion
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
              <p className="text-muted-foreground text-xs text-pretty">
                A sample report. Yours is written about you - by the instructor
                who ran your session.
              </p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
