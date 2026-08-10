"use client";

import Link from "next/link";
import { ArrowRight, Play } from "lucide-react";

import { Ripple } from "@/components/magicui/effects";
import { useSiteConfig } from "@/components/site-config-provider";
import { AnimatedShinyText } from "@/components/ui/animated-shiny-text";
import { Button } from "@/components/ui/button";
import { DotPattern } from "@/components/ui/dot-pattern";
import { WordRotate } from "@/components/ui/word-rotate";
import { cn } from "@/lib/utils";

/** The verb cycles; the sentence doesn't. Each one is something you can only
 *  do by opening your mouth — which is the whole argument of the product.
 *  Keep them all within a character or two of "speaking": the rotator reserves
 *  the width of the longest word, so a long outlier leaves a visible gap after
 *  the short ones. Each must also read correctly with a bare "it". */
const VERBS = ["speaking", "debating", "arguing", "pitching"];

/** Initials on the stacked avatars under the CTAs. Deliberately not photos —
 *  stock faces on a language site read as invented testimonials. */
const FACES = ["AR", "KM", "JS", "LP", "NT"];

export function Hero() {
  const { one_on_one_enabled: oneOnOneEnabled } = useSiteConfig();

  return (
    <section className="border-border/60 relative flex items-center overflow-hidden border-b py-28">
      <DotPattern
        className={cn(
          "text-border/70",
          "[mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,#000,transparent_75%)]",
        )}
        width={26}
        height={26}
        cr={1}
      />
      <Ripple />

      <div className="container-page relative">
        <div className="mx-auto max-w-3xl text-center">
          <Link
            href="/register"
            className="border-border/80 bg-background/60 hover:border-brand-ink/50 mx-auto mb-8 flex w-fit items-center gap-2 rounded-full border px-4 py-1.5 backdrop-blur transition-colors"
          >
            <span className="bg-brand size-1.5 rounded-full" />
            <AnimatedShinyText className="text-xs font-medium tracking-[0.15em] uppercase">
              Your first discussion is free
            </AnimatedShinyText>
            <ArrowRight className="text-muted-foreground size-3 transition-transform group-hover:translate-x-0.5" />
          </Link>

          <h1 className="text-5xl leading-[1.05] text-balance md:text-7xl">
            Stop studying English.{" "}
            <span className="text-brand-ink">
              Start <WordRotate words={VERBS} duration={2200} /> in it.
            </span>
          </h1>

          <p className="text-muted-foreground mx-auto mt-6 max-w-xl text-lg text-pretty">
            Live communication is the only way to get fluent. 
          </p>

          <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
            <Button asChild size="lg" variant="brand">
              <Link href="/discussions">
                Browse discussions
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            {/* Goes with the nav link. A homepage whose second call to action
                leads somewhere that says "not open for booking" is a worse
                first impression than a single button. */}
            {oneOnOneEnabled && (
              <Button asChild size="lg" variant="secondary">
                <Link href="/one-on-one">
                  <Play className="size-4" />
                  Book a 1:1
                </Link>
              </Button>
            )}
          </div>

          <div className="text-muted-foreground mt-9 flex flex-col items-center justify-center gap-3 text-sm sm:flex-row">
            <div className="flex -space-x-2">
              {FACES.map((initials) => (
                <span
                  key={initials}
                  className="border-background bg-secondary text-secondary-foreground grid size-8 place-items-center rounded-full border-2 text-[10px] font-medium"
                >
                  {initials}
                </span>
              ))}
            </div>
            <p>
              <span className="text-foreground font-medium">12,632 learners</span>{" "}
              across 8 countries · no lessons, just conversation
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
