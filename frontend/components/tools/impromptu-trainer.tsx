"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Mic,
  Pause,
  Play,
  RotateCcw,
  Shuffle,
  SlidersHorizontal,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { consumeStagedTopic } from "@/lib/impromptu-stage";
import type { ImpromptuTopic } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The impromptu round, in the shape people know from the reels: a topic you
 * did not choose, a short prep where you scribble three stickies, then a timed
 * minute at the mic. Near zero words on screen - the reel format works
 * because there is nothing to read, only a topic and a clock.
 *
 * The topic lands via a slot-machine reel: a strip of decoys scrolls past,
 * decelerates, overshoots a hair and settles on the real one. The theatre is
 * doing a job - the spin is the moment of "no take-backs" that a plain text
 * swap doesn't deliver.
 *
 * Everything tunable - track (MBA, IELTS, cabin crew…), topic style, timings -
 * lives behind the small settings control, because the person this tool is
 * for is the one who would otherwise fiddle with filters instead of speaking.
 *
 * Topics arrive as a prop from the server render (see `lib/impromptu.ts`);
 * the filter chips are derived from whatever tracks and categories exist in
 * that data, so a row added in sqladmin becomes a chip here with no deploy.
 */

type Phase = "idle" | "spin" | "topic" | "prep" | "speak" | "done";

const PREP_CHOICES = [60, 120, 300] as const;
const SPEAK_CHOICES = [60, 120, 300] as const;

/* Real paper stickies never sit straight, and perfectly straight ones read as
   buttons. The tilts are fixed, not random, so re-renders don't wiggle them. */
const NOTE_TILTS = ["-rotate-2", "rotate-1", "-rotate-2"];

const NOTE_PLACEHOLDERS = ["First thought…", "Second angle…", "How you'll end…"];

function formatClock(ms: number): string {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function minutesLabel(seconds: number): string {
  return `${seconds / 60} min`;
}

function shuffled<T>(items: T[]): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

/* ------------------------------------------------------------------ countdown */

/** Wall-clock based, not tick-counting: a browser tab that gets throttled in
 *  the background must not silently gift you extra speaking time. */
function useCountdown() {
  const [running, setRunning] = React.useState(false);
  const [paused, setPaused] = React.useState(false);
  const [remainingMs, setRemainingMs] = React.useState(0);
  const [totalMs, setTotalMs] = React.useState(1);
  const endAtRef = React.useRef(0);
  const onDoneRef = React.useRef<() => void>(() => {});

  const start = React.useCallback((seconds: number, onDone: () => void) => {
    onDoneRef.current = onDone;
    endAtRef.current = Date.now() + seconds * 1000;
    setTotalMs(seconds * 1000);
    setRemainingMs(seconds * 1000);
    setPaused(false);
    setRunning(true);
  }, []);

  const pause = React.useCallback(() => setPaused(true), []);

  const resume = React.useCallback(() => {
    endAtRef.current = Date.now() + remainingMs;
    setPaused(false);
  }, [remainingMs]);

  const stop = React.useCallback(() => {
    setRunning(false);
    setPaused(false);
  }, []);

  React.useEffect(() => {
    if (!running || paused) return;
    const id = setInterval(() => {
      const left = endAtRef.current - Date.now();
      if (left <= 0) {
        setRemainingMs(0);
        setRunning(false);
        onDoneRef.current();
      } else {
        setRemainingMs(left);
      }
    }, 100);
    return () => clearInterval(id);
  }, [running, paused]);

  return { running, paused, remainingMs, totalMs, start, pause, resume, stop };
}

/* ---------------------------------------------------------------------- audio */

/** The tool's three sounds: the reel's decelerating ticks, the settle ding,
 *  and a soft chime when a timed phase ends (during the round your eyes
 *  should be anywhere but the screen). The context is created inside a click
 *  handler (autoplay policy) and every call is allowed to fail silently -
 *  sound is a courtesy here, never a dependency. */
function useChime() {
  const ctxRef = React.useRef<AudioContext | null>(null);

  const arm = React.useCallback(() => {
    try {
      ctxRef.current ??= new AudioContext();
      if (ctxRef.current.state === "suspended") void ctxRef.current.resume();
    } catch {
      ctxRef.current = null;
    }
  }, []);

  const chime = React.useCallback((count: number) => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    try {
      for (let i = 0; i < count; i++) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = 880;
        const at = ctx.currentTime + i * 0.28;
        gain.gain.setValueAtTime(0.0001, at);
        gain.gain.exponentialRampToValueAtTime(0.18, at + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.24);
        osc.connect(gain).connect(ctx.destination);
        osc.start(at);
        osc.stop(at + 0.26);
      }
    } catch {
      // Sound failing is not worth interrupting the round for.
    }
  }, []);

  /** The clock's once-a-second tick. Far quieter than everything else here -
   *  it should sit at the edge of attention, a metronome, not an alarm. */
  const tick = React.useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.value = 1000;
      const at = ctx.currentTime;
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.025, at + 0.003);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.03);
      osc.connect(gain).connect(ctx.destination);
      osc.start(at);
      osc.stop(at + 0.035);
    } catch {
      // Same rule as the chime: silence over interruption.
    }
  }, []);

  /** One click per row the reel passes, then a ding on the winner. The clicks
   *  are spaced by inverting the same ease-out shape the reel moves with -
   *  approximate (the CSS bezier isn't this cubic exactly), but the ear reads
   *  "slowing down together", not milliseconds. */
  const spinSound = React.useCallback((rows: number, totalMs: number) => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      for (let k = 1; k <= rows; k++) {
        // Row k crosses the centre when progress = k/rows; ease-out
        // p = 1-(1-t)^3 inverts to t = 1-cbrt(1-p).
        const t = 1 - Math.cbrt(1 - k / rows);
        const at = now + (t * totalMs) / 1000;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.value = 1500;
        gain.gain.setValueAtTime(0.0001, at);
        gain.gain.exponentialRampToValueAtTime(0.06, at + 0.004);
        gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.035);
        osc.connect(gain).connect(ctx.destination);
        osc.start(at);
        osc.stop(at + 0.04);
      }
      // The winner's ding, a fifth up from the ticks and allowed to ring.
      const at = now + totalMs / 1000;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 1568;
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.14, at + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.45);
      osc.connect(gain).connect(ctx.destination);
      osc.start(at);
      osc.stop(at + 0.5);
    } catch {
      // Same rule as above: silence over interruption.
    }
  }, []);

  return { arm, chime, tick, spinSound };
}

/* ----------------------------------------------------------------- topic reel */

/** How long the reel decelerates for. The fallback timer below must outlast it. */
const SPIN_MS = 2200;

/** The slot-machine strip. Rendered once per spin (parent keys it), it starts
 *  at the first row and rolls the whole strip up to the last - the winner -
 *  in a single CSS transition whose bezier overshoots past 1 and comes back:
 *  that little rebound is the "damp" of a real machine.
 *
 *  Percentage transform, so the row height can differ across breakpoints
 *  without any pixel maths here. */
function TopicReel({ items, onSettle }: { items: string[]; onSettle: () => void }) {
  const [rolling, setRolling] = React.useState(false);
  const settledRef = React.useRef(false);

  const settle = React.useCallback(() => {
    if (settledRef.current) return;
    settledRef.current = true;
    onSettle();
  }, [onSettle]);

  React.useEffect(() => {
    // Two frames, not one: the strip must be committed at translateY(0)
    // before the target transform lands, or there is nothing to transition.
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setRolling(true)));
    // `transitionend` is lost if the tab is backgrounded mid-spin or the
    // transition never runs (reduced motion) - the timer guarantees arrival.
    const fallback = setTimeout(settle, SPIN_MS + 400);
    return () => {
      cancelAnimationFrame(id);
      clearTimeout(fallback);
    };
  }, [settle]);

  return (
    <div
      aria-hidden
      className="h-24 w-full overflow-hidden [mask-image:linear-gradient(to_bottom,transparent,black_25%,black_75%,transparent)] md:h-36"
    >
      <div
        onTransitionEnd={settle}
        className="flex flex-col motion-safe:transition-transform"
        style={{
          transform: rolling
            ? `translateY(calc(-100% * ${items.length - 1} / ${items.length}))`
            : "translateY(0)",
          transitionDuration: `${SPIN_MS}ms`,
          // y2 > 1 is the overshoot: the strip rolls a touch past the winner,
          // then eases back onto it.
          transitionTimingFunction: "cubic-bezier(0.15, 0.85, 0.25, 1.06)",
        }}
      >
        {items.map((text, i) => (
          <div
            key={i}
            className="flex h-24 shrink-0 items-center justify-center px-4 md:h-36"
          >
            <span className="font-heading text-brand-ink max-w-full truncate text-5xl tracking-tight md:text-7xl">
              {text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- chips */

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors",
        active
          ? "border-transparent bg-foreground text-background"
          : "border-border text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function SettingsRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="eyebrow text-left">{label}</p>
      <div className="mt-3 flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

/** Arrival order, deliberately: the API sorts by `sort_order`, which is the
 *  popularity ranking maintained in admin - re-sorting here would erase it. */
function distinctTracks(topics: ImpromptuTopic[]): string[] {
  return [...new Set(topics.map((t) => t.track))];
}

/* -------------------------------------------------------------------- trainer */

export function ImpromptuTrainer({
  topics,
  className,
}: {
  topics: ImpromptuTopic[];
  className?: string;
}) {
  const [phase, setPhase] = React.useState<Phase>("idle");
  const [settingsOpen, setSettingsOpen] = React.useState(false);

  const tracks = React.useMemo(() => distinctTracks(topics), [topics]);
  const [track, setTrack] = React.useState<string>(tracks[0] ?? "General");
  const [category, setCategory] = React.useState<string | null>(null);
  const [difficulty, setDifficulty] = React.useState<string | null>(null);
  const [prepSeconds, setPrepSeconds] = React.useState<number>(60);
  const [speakSeconds, setSpeakSeconds] = React.useState<number>(60);

  const [topic, setTopic] = React.useState<ImpromptuTopic | null>(null);
  const [reel, setReel] = React.useState<string[]>([]);
  const [spinCount, setSpinCount] = React.useState(0);
  const [notes, setNotes] = React.useState<string[]>(["", "", ""]);
  // No repeats until the pool runs dry - a shuffle that hands back the topic
  // you just skipped reads as broken.
  const usedRef = React.useRef(new Set<string>());

  const timer = useCountdown();
  const { arm, chime, tick, spinSound } = useChime();

  // The clock ticks once per displayed second, driven off the same state the
  // digits render from so sound and screen can never disagree. Pausing stops
  // it because the interval stops feeding remainingMs.
  const secondsLeft = Math.ceil(timer.remainingMs / 1000);
  const prevSecondRef = React.useRef(secondsLeft);
  React.useEffect(() => {
    if (prevSecondRef.current === secondsLeft) return;
    prevSecondRef.current = secondsLeft;
    if (timer.running && !timer.paused && secondsLeft > 0) tick();
  }, [secondsLeft, timer.running, timer.paused, tick]);

  const inTrack = React.useMemo(
    () => topics.filter((t) => t.track === track),
    [topics, track],
  );
  const categories = React.useMemo(
    () => [...new Set(inTrack.map((t) => t.category))].sort((a, b) => a.localeCompare(b)),
    [inTrack],
  );
  const difficulties = React.useMemo(
    () =>
      [...new Set(inTrack.map((t) => t.difficulty).filter((d): d is string => !!d))].sort(
        (a, b) => a.localeCompare(b),
      ),
    [inTrack],
  );

  const pool = React.useMemo(
    () =>
      inTrack.filter(
        (t) =>
          (category === null || t.category === category) &&
          (difficulty === null || t.difficulty === difficulty),
      ),
    [inTrack, category, difficulty],
  );

  const pickTrack = (next: string) => {
    setTrack(next);
    // The old category may not exist under the new track; starting from "any"
    // beats silently keeping a filter that now matches nothing.
    setCategory(null);
    setDifficulty(null);
  };

  const drawTopic = React.useCallback(() => {
    // Every path here starts from a click, which is what lets the reel tick.
    arm();
    const source = pool.length > 0 ? pool : inTrack;
    // A staged topic (set from /admin/impromptu, this browser only) wins the
    // next spin outright - the reel still rolls, so on camera it is just a
    // spin that happened to land well. One shot; the read clears it.
    const staged = consumeStagedTopic();
    let next: ImpromptuTopic | undefined = staged ?? undefined;
    if (!next) {
      const fresh = source.filter((t) => !usedRef.current.has(t.text));
      const from = fresh.length > 0 ? fresh : source;
      if (fresh.length === 0) usedRef.current.clear();
      next = from[Math.floor(Math.random() * from.length)];
    }
    if (!next) return;
    usedRef.current.add(next.text);
    setTopic(next);
    setNotes(["", "", ""]);

    // The reel needs decoys to roll past, but they are pure theatre - the
    // visitor never gets them - so a thin filter combo (a track's four "Hot
    // takes", say) borrows from the rest of the track, then the whole bank,
    // and repeats itself before it ever gives up the spin. Only a one-topic
    // bank, or a visitor who prefers reduced motion, gets the plain reveal.
    const REEL_DECOYS = 11;
    const decoyPool: string[] = [];
    const seen = new Set([next.text]);
    for (const tier of [source, inTrack, topics]) {
      for (const t of shuffled(tier)) {
        if (!seen.has(t.text)) {
          seen.add(t.text);
          decoyPool.push(t.text);
        }
      }
      if (decoyPool.length >= REEL_DECOYS) break;
    }
    let decoys = decoyPool.slice(0, REEL_DECOYS);
    while (decoys.length > 0 && decoys.length < REEL_DECOYS) {
      decoys = [...decoys, ...decoys].slice(0, REEL_DECOYS);
    }
    const skipSpin =
      decoys.length === 0 ||
      (typeof window !== "undefined" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    if (skipSpin) {
      setPhase("topic");
      return;
    }
    setReel([...decoys, next.text]);
    setSpinCount((n) => n + 1);
    spinSound(decoys.length, SPIN_MS);
    setPhase("spin");
  }, [pool, inTrack, topics, arm, spinSound]);

  const startSpeak = React.useCallback(() => {
    setPhase("speak");
    timer.start(speakSeconds, () => {
      chime(2);
      setPhase("done");
    });
  }, [timer, speakSeconds, chime]);

  const startPrep = React.useCallback(() => {
    arm();
    setPhase("prep");
    timer.start(prepSeconds, () => {
      chime(1);
      startSpeak();
    });
  }, [arm, timer, prepSeconds, chime, startSpeak]);

  const skipToSpeak = React.useCallback(() => {
    arm();
    startSpeak();
  }, [arm, startSpeak]);

  const finishEarly = React.useCallback(() => {
    timer.stop();
    setPhase("done");
  }, [timer]);

  const reset = React.useCallback(() => {
    timer.stop();
    setTopic(null);
    setNotes(["", "", ""]);
    setPhase("idle");
  }, [timer]);

  const filledNotes = notes.filter((n) => n.trim().length > 0);

  const settingsSummary = [
    track,
    category,
    difficulty,
    `${minutesLabel(prepSeconds)} prep`,
    `${minutesLabel(speakSeconds)} talk`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center px-4 text-center",
        className,
      )}
    >
      {/* The one piece of chrome: mid-round it disappears, because a settings
          panel is exactly the escape hatch a nervous speaker would take. */}
      {(phase === "idle" || phase === "topic" || phase === "done") && (
        <button
          type="button"
          onClick={() => setSettingsOpen((open) => !open)}
          aria-label={settingsOpen ? "Close practice settings" : "Practice settings"}
          aria-expanded={settingsOpen}
          className="text-muted-foreground hover:text-foreground absolute top-0 right-0 rounded-full p-2 transition-colors"
        >
          {settingsOpen ? (
            <X className="size-4.5" />
          ) : (
            <SlidersHorizontal className="size-4.5" />
          )}
        </button>
      )}

      {/* --------------------------------------------------------- settings */}
      {settingsOpen ? (
        <div className="flex w-full max-w-xl flex-col gap-7 py-2">
          <SettingsRow label="Track">
            {tracks.map((t) => (
              <Chip key={t} active={track === t} onClick={() => pickTrack(t)}>
                {t}
              </Chip>
            ))}
          </SettingsRow>

          {categories.length > 1 && (
            <SettingsRow label="Topic style">
              <Chip active={category === null} onClick={() => setCategory(null)}>
                Surprise me
              </Chip>
              {categories.map((c) => (
                <Chip key={c} active={category === c} onClick={() => setCategory(c)}>
                  {c}
                </Chip>
              ))}
            </SettingsRow>
          )}

          {/* Only when the data actually grades topics - an "Any difficulty"
              chip with nothing behind it is noise. */}
          {difficulties.length > 0 && (
            <SettingsRow label="Difficulty">
              <Chip active={difficulty === null} onClick={() => setDifficulty(null)}>
                Any
              </Chip>
              {difficulties.map((d) => (
                <Chip key={d} active={difficulty === d} onClick={() => setDifficulty(d)}>
                  {d}
                </Chip>
              ))}
            </SettingsRow>
          )}

          <SettingsRow label="Prep time">
            {PREP_CHOICES.map((s) => (
              <Chip key={s} active={prepSeconds === s} onClick={() => setPrepSeconds(s)}>
                {minutesLabel(s)}
              </Chip>
            ))}
          </SettingsRow>

          <SettingsRow label="Talk time">
            {SPEAK_CHOICES.map((s) => (
              <Chip key={s} active={speakSeconds === s} onClick={() => setSpeakSeconds(s)}>
                {minutesLabel(s)}
              </Chip>
            ))}
          </SettingsRow>

          <div>
            <Button variant="brand" onClick={() => setSettingsOpen(false)}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <>
          {/* --------------------------------------------------------- idle */}
          {phase === "idle" && (
            <div className="flex w-full max-w-2xl flex-col items-center gap-10">
              <p className="eyebrow">Impromptu</p>
              <p className="font-heading text-5xl tracking-tight text-balance md:text-7xl">
                Can you talk for a minute?
              </p>
              <div className="flex flex-col items-center gap-4">
                <Button variant="brand" size="lg" onClick={drawTopic}>
                  <Shuffle className="size-4" />
                  Topic
                </Button>
                <p className="text-muted-foreground text-xs">{settingsSummary}</p>
                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  className="border-border text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors"
                >
                  <SlidersHorizontal className="size-3" />
                  Customize
                </button>
              </div>
            </div>
          )}

          {/* --------------------------------------------------------- spin */}
          {phase === "spin" && (
            <div className="flex w-full max-w-2xl flex-col items-center gap-10">
              <p className="eyebrow">Your topic</p>
              <TopicReel
                key={spinCount}
                items={reel}
                onSettle={() => setPhase("topic")}
              />
              {/* Same footprint as the topic phase's buttons, so the settle
                  doesn't shove the reel upward. */}
              <div className="invisible flex items-center gap-3">
                <Button variant="brand">Prep</Button>
              </div>
            </div>
          )}

          {/* -------------------------------------------------------- topic */}
          {phase === "topic" && topic && (
            <div className="flex w-full max-w-2xl flex-col items-center gap-10">
              <p className="eyebrow">Your topic</p>
              {/* The star of the frame - phone-camera loud on purpose. In dark
                  mode brand-ink IS the neon lime; in light it is the olive that
                  survives on white. */}
              <p className="font-heading text-brand-ink text-6xl tracking-tight text-balance md:text-8xl">
                {topic.text}
              </p>
              <div className="flex flex-wrap items-center justify-center gap-3">
                <Button variant="brand" onClick={startPrep}>
                  <Play className="size-4" />
                  {minutesLabel(prepSeconds)} prep
                </Button>
                <Button variant="outline" onClick={skipToSpeak}>
                  <Mic className="size-4" />
                  Just talk
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={drawTopic}
                  aria-label="New topic"
                >
                  <Shuffle className="size-4" />
                </Button>
              </div>
            </div>
          )}

          {/* --------------------------------------------------------- prep */}
          {phase === "prep" && topic && (
            <div className="flex w-full max-w-2xl flex-col items-center gap-8">
              <div>
                <p className="font-heading text-brand-ink text-3xl tracking-tight text-balance md:text-4xl">
                  {topic.text}
                </p>
                <p className="text-muted-foreground mt-2 text-sm">
                  Keywords, not sentences.
                </p>
              </div>

              <TimerRing remainingMs={timer.remainingMs} totalMs={timer.totalMs} />

              <div className="grid w-full gap-3 sm:grid-cols-3">
                {notes.map((note, i) => (
                  <textarea
                    key={i}
                    value={note}
                    maxLength={80}
                    rows={3}
                    placeholder={NOTE_PLACEHOLDERS[i]}
                    onChange={(event) =>
                      setNotes((prev) =>
                        prev.map((n, j) => (j === i ? event.target.value : n)),
                      )
                    }
                    className={cn(
                      "bg-brand text-brand-foreground placeholder:text-brand-foreground/50 resize-none rounded-sm p-3 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                      NOTE_TILTS[i],
                    )}
                  />
                ))}
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3">
                <Button variant="brand" onClick={startSpeak}>
                  <Mic className="size-4" />
                  Talk now
                </Button>
                {timer.paused ? (
                  <Button variant="outline" onClick={timer.resume}>
                    <Play className="size-4" />
                    Resume
                  </Button>
                ) : (
                  <Button variant="outline" onClick={timer.pause}>
                    <Pause className="size-4" />
                    Pause
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* -------------------------------------------------------- speak */}
          {phase === "speak" && topic && (
            <div className="flex w-full max-w-2xl flex-col items-center gap-8">
              <p className="font-heading text-brand-ink text-3xl tracking-tight text-balance md:text-4xl">
                {topic.text}
              </p>

              {filledNotes.length > 0 && (
                <div className="flex flex-wrap justify-center gap-3">
                  {filledNotes.map((note, i) => (
                    <span
                      key={i}
                      className={cn(
                        "bg-brand text-brand-foreground max-w-44 rounded-sm px-3 py-2 text-left text-xs shadow-sm",
                        NOTE_TILTS[i % NOTE_TILTS.length],
                      )}
                    >
                      {note}
                    </span>
                  ))}
                </div>
              )}

              <TimerRing remainingMs={timer.remainingMs} totalMs={timer.totalMs} />

              <div className="flex flex-wrap items-center justify-center gap-3">
                {timer.paused ? (
                  <Button variant="outline" onClick={timer.resume}>
                    <Play className="size-4" />
                    Resume
                  </Button>
                ) : (
                  <Button variant="outline" onClick={timer.pause}>
                    <Pause className="size-4" />
                    Pause
                  </Button>
                )}
                <Button variant="ghost" onClick={finishEarly}>
                  Done
                </Button>
              </div>
            </div>
          )}

          {/* --------------------------------------------------------- done */}
          {phase === "done" && topic && (
            <div className="flex max-w-xl flex-col items-center gap-10">
              <div className="animate-rise">
                <p className="eyebrow">Time</p>
                <p className="font-heading mt-4 text-5xl tracking-tight text-balance md:text-6xl">
                  Again?
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3">
                <Button variant="brand" onClick={drawTopic}>
                  <Shuffle className="size-4" />
                  New topic
                </Button>
                <Button variant="ghost" onClick={reset}>
                  <RotateCcw className="size-4" />
                  Reset
                </Button>
              </div>

              <p className="text-muted-foreground text-sm">
                <Link
                  href="/discussions"
                  className="hover:text-foreground inline-flex items-center gap-1 underline underline-offset-4 transition-colors"
                >
                  Now try it with five people listening
                  <ArrowRight className="size-3.5" />
                </Link>
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- timer ring */

function TimerRing({
  remainingMs,
  totalMs,
  className,
}: {
  remainingMs: number;
  totalMs: number;
  className?: string;
}) {
  const radius = 90;
  const circumference = 2 * Math.PI * radius;
  const fraction = Math.max(0, Math.min(1, remainingMs / totalMs));

  return (
    <div
      role="timer"
      aria-label={`${formatClock(remainingMs)} remaining`}
      className={cn("relative inline-flex items-center justify-center", className)}
    >
      <svg viewBox="0 0 200 200" className="size-60 -rotate-90 md:size-80">
        <circle
          cx="100"
          cy="100"
          r={radius}
          fill="none"
          strokeWidth="6"
          className="stroke-border"
        />
        <circle
          cx="100"
          cy="100"
          r={radius}
          fill="none"
          strokeWidth="6"
          strokeLinecap="round"
          stroke="var(--brand-ink)"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - fraction)}
          className="transition-[stroke-dashoffset] duration-150 ease-linear"
        />
      </svg>
      <span className="font-heading absolute text-6xl tracking-tight tabular-nums md:text-8xl">
        {formatClock(remainingMs)}
      </span>
    </div>
  );
}
