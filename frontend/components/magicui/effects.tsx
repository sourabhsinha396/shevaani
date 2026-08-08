"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Magic UI-style effects, written in plain CSS so there's no motion library in
 * the bundle. Add the real components any time with:
 *   npx shadcn@latest add "https://magicui.design/r/ripple"
 */

/**
 * Concentric rings breathing behind a hero. Deliberately drawn in `border`
 * colour rather than brand — it should read as texture you notice on the second
 * look, not as decoration competing with the headline. Parent needs `relative`.
 */
export function Ripple({
  className,
  circles = 7,
  base = 220,
  step = 90,
}: {
  className?: string;
  circles?: number;
  base?: number;
  step?: number;
}) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden",
        "[mask-image:radial-gradient(ellipse_60%_60%_at_50%_45%,#000_30%,transparent_75%)]",
        className,
      )}
    >
      {Array.from({ length: circles }).map((_, i) => {
        const size = base + i * step;
        return (
          <span
            key={i}
            style={{
              width: size,
              height: size,
              // Staggered so the rings breathe outwards rather than in unison.
              animationDelay: `${i * 0.34}s`,
            }}
            className="border-border/70 bg-foreground/[0.015] absolute top-1/2 left-1/2 -translate-1/2 rounded-full border motion-safe:animate-[var(--animate-ripple)]"
          />
        );
      })}
    </div>
  );
}

/** A pill with a highlight that sweeps across it on hover. */
export function ShinyButton({
  children,
  className,
  ...props
}: React.ComponentProps<"button">) {
  return (
    <button
      className={cn(
        "group bg-brand text-brand-foreground relative z-0 inline-flex items-center justify-center gap-2 overflow-hidden rounded-full px-6 py-3 text-base font-medium transition-transform active:translate-y-px",
        className,
      )}
      {...props}
    >
      <span
        aria-hidden
        className="absolute inset-y-0 -left-full w-1/3 bg-white/40 motion-safe:group-hover:animate-[shine_0.9s_ease-out]"
      />
      {children}
    </button>
  );
}

/**
 * Edge-faded scroller for topics, logos or testimonials. Two copies of the
 * children scroll one full track width, so the seam is invisible. Pauses on
 * hover, and stops entirely under `prefers-reduced-motion`.
 */
export function Marquee({
  children,
  className,
  speed = 40,
  vertical = false,
  reverse = false,
}: {
  children: React.ReactNode;
  className?: string;
  speed?: number;
  vertical?: boolean;
  reverse?: boolean;
}) {
  return (
    <div
      className={cn(
        "group relative flex overflow-hidden",
        vertical
          ? "flex-col [mask-image:linear-gradient(to_bottom,transparent,#000_12%,#000_88%,transparent)]"
          : "[mask-image:linear-gradient(to_right,transparent,#000_12%,#000_88%,transparent)]",
        className,
      )}
    >
      {[0, 1].map((i) => (
        <div
          key={i}
          aria-hidden={i === 1}
          className={cn(
            "flex shrink-0 group-hover:[animation-play-state:paused]",
            vertical
              ? "flex-col gap-4 pb-4 motion-safe:animate-[marquee-vertical_linear_infinite]"
              : "items-center gap-4 pr-4 motion-safe:animate-[marquee_linear_infinite]",
          )}
          style={{
            animationDuration: `${speed}s`,
            animationDirection: reverse ? "reverse" : "normal",
          }}
        >
          {children}
        </div>
      ))}
    </div>
  );
}

/**
 * A card that lights up under the cursor. The highlight is a radial gradient
 * positioned from two CSS variables the pointer handler writes — no re-render
 * per mouse move, which matters when a grid of these is on screen at once.
 */
export function SpotlightCard({
  children,
  className,
  ...props
}: React.ComponentProps<"div">) {
  const ref = React.useRef<HTMLDivElement>(null);

  const onMouseMove = React.useCallback((event: React.MouseEvent) => {
    const node = ref.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    node.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
    node.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
  }, []);

  return (
    <div
      ref={ref}
      onMouseMove={onMouseMove}
      className={cn("group/spot relative overflow-hidden", className)}
      {...props}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover/spot:opacity-100"
        style={{
          background:
            "radial-gradient(220px circle at var(--spot-x, 50%) var(--spot-y, 50%), color-mix(in oklab, var(--brand) 22%, transparent), transparent 70%)",
        }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

/**
 * Fades and lifts its children the first time they scroll into view. Used
 * sparingly — section headings and the big set pieces, not every paragraph.
 */
export function Reveal({
  children,
  className,
  delay = 0,
  as: Tag = "div",
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  as?: React.ElementType;
}) {
  const ref = React.useRef<HTMLDivElement>(null);
  const [shown, setShown] = React.useState(false);

  React.useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        setShown(true);
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag
      ref={ref}
      data-reveal=""
      style={{ transitionDelay: `${delay}ms` }}
      className={cn(
        "transition-[opacity,transform] duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none",
        shown ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

/**
 * The speaking-level bars used in the session preview and the calculator.
 * `active` drives the animation so a silent participant reads as flat.
 */
export function VoiceBars({
  active = true,
  bars = 5,
  className,
}: {
  active?: boolean;
  bars?: number;
  className?: string;
}) {
  return (
    <span aria-hidden className={cn("flex items-center gap-0.5", className)}>
      {Array.from({ length: bars }).map((_, i) => (
        <span
          key={i}
          style={{ animationDelay: `${i * 120}ms` }}
          className={cn(
            "bg-brand-ink w-0.5 origin-center rounded-full",
            active
              ? "h-3 motion-safe:animate-[speak_1.1s_ease-in-out_infinite]"
              : "bg-muted-foreground/40 h-1",
          )}
        />
      ))}
    </span>
  );
}

/**
 * Counts up when it scrolls into view, and tweens between values afterwards —
 * so the same component works both for a static stat and for a figure a slider
 * is driving. Later runs start from whatever is on screen rather than from
 * zero, which is what stops a dragged slider looking like a slot machine.
 */
export function NumberTicker({
  value,
  className,
  duration = 1200,
}: {
  value: number;
  className?: string;
  duration?: number;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const [display, setDisplay] = React.useState(0);
  const [seen, setSeen] = React.useState(false);
  // Read inside the animation frame only, so a re-render mid-tween doesn't
  // restart the tween from a stale origin.
  const displayRef = React.useRef(0);
  displayRef.current = display;

  React.useEffect(() => {
    const node = ref.current;
    if (!node || seen) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        setSeen(true);
      },
      { threshold: 0.3 },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [seen]);

  React.useEffect(() => {
    if (!seen) return;

    // Respect reduced-motion: land on the final value immediately.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplay(value);
      return;
    }

    const from = displayRef.current;
    if (from === value) return;

    // A short hop for a small correction, the full run for a first count-up.
    const span = Math.min(duration, 220 + Math.abs(value - from) * 6);
    const start = performance.now();
    let frame = requestAnimationFrame(function tick(now: number) {
      const progress = Math.min((now - start) / span, 1);
      // easeOutExpo
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setDisplay(Math.round(from + (value - from) * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    });

    return () => cancelAnimationFrame(frame);
  }, [value, duration, seen]);

  return (
    <span ref={ref} className={className}>
      {display.toLocaleString()}
    </span>
  );
}
