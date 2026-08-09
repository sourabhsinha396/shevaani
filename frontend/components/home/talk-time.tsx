"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Info } from "lucide-react";

import { NumberTicker, Reveal } from "@/components/magicui/effects";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

/**
 * The talk-time model, stated once so the maths on screen is auditable.
 *
 * `share` is the fraction of the clock that learners — not the person running
 * the room — are speaking for. It is higher here than in a classroom because a
 * instructor's job is to ask a question and then get out of the way, and it is
 * only 0.5 in a one-to-one because the other half is your partner talking,
 * which you do want.
 *
 * Everything downstream is that share divided by the number of learners.
 */
const LEARNER_SHARE = 0.8;
const CLASSROOM_SHARE = 0.55;
const WEEKS_PER_YEAR = 48; // Two holidays and a bad month, allowed for.

/** Where the group cap comes from: past eight, per-person airtime collapses. */
const GROUP_CAP = 8;

function minutesEach(sessionMinutes: number, people: number, share: number) {
  return (sessionMinutes * share) / people;
}

export function TalkTime() {
  const [people, setPeople] = React.useState(6);
  const [perWeek, setPerWeek] = React.useState(2);
  const [sessionMinutes, setSessionMinutes] = React.useState(50);

  const yours = minutesEach(sessionMinutes, people, LEARNER_SHARE);
  const hoursPerYear = Math.round((yours * perWeek * WEEKS_PER_YEAR) / 60);

  // The comparison row is deliberately fixed — it is the alternative you would
  // otherwise buy, not another thing to fiddle with.
  const alternatives = [
    {
      label: `Shevaani group of ${people}`,
      detail: `${sessionMinutes} min · facilitated`,
      minutes: yours,
      mine: true,
    },
    {
      label: "Shevaani one-to-one",
      detail: `${sessionMinutes} min · you and an instructor`,
      minutes: minutesEach(sessionMinutes, 1, 0.5),
    },
    {
      label: "Group class of 20",
      detail: "60 min · teacher-led",
      minutes: minutesEach(60, 20, CLASSROOM_SHARE),
    },
    {
      label: "Solo app, no partner",
      detail: "20 min · scripted repetition",
      minutes: 0,
      empty: "nobody listening",
    },
  ];

  const ceiling = Math.max(...alternatives.map((a) => a.minutes));

  return (
    <section className="section">
      <div className="container-page">
        <Reveal className="max-w-2xl">
          <p className="eyebrow mb-5">Do the maths</p>
          <h2 className="text-4xl text-balance md:text-5xl">
            How much do you actually speak?
          </h2>
          <p className="text-muted-foreground mt-5 text-pretty">
            Fluency is a function of hours spent talking, so it is worth knowing
            how many you are buying. Move the sliders — the room size is the part
            that matters most.
          </p>
        </Reveal>

        <Reveal
          delay={100}
          className="border-border/60 mt-12 grid overflow-hidden rounded-xl border lg:grid-cols-5"
        >
          {/* ------------------------------------------------------ controls */}
          <div className="border-border/60 flex flex-col gap-8 p-6 sm:p-8 lg:col-span-2 lg:border-r">
            <div>
              <div className="flex items-baseline justify-between">
                <label className="text-sm font-medium" htmlFor="people">
                  People in the room
                </label>
                <span className="font-heading text-2xl tabular-nums">
                  {people}
                </span>
              </div>
              <Slider
                id="people"
                className="mt-4"
                min={2}
                max={24}
                step={1}
                value={[people]}
                onValueChange={([next]) => setPeople(next)}
              />
              <p
                className={cn(
                  "mt-3 flex items-start gap-2 text-xs text-pretty",
                  people > GROUP_CAP
                    ? "text-[var(--warning)]"
                    : "text-muted-foreground",
                )}
              >
                <Info className="mt-px size-3.5 shrink-0" />
                {people > GROUP_CAP
                  ? `Past ${GROUP_CAP} the airtime is gone. Which is why we stop selling seats there.`
                  : `We cap discussions at ${GROUP_CAP} for exactly this reason.`}
              </p>
            </div>

            <div>
              <div className="flex items-baseline justify-between">
                <label className="text-sm font-medium" htmlFor="per-week">
                  Sessions per week
                </label>
                <span className="font-heading text-2xl tabular-nums">
                  {perWeek}
                </span>
              </div>
              <Slider
                id="per-week"
                className="mt-4"
                min={1}
                max={7}
                step={1}
                value={[perWeek]}
                onValueChange={([next]) => setPerWeek(next)}
              />
            </div>

            <div>
              <p className="text-sm font-medium">Session length</p>
              <Tabs
                className="mt-3"
                value={String(sessionMinutes)}
                onValueChange={(value) => setSessionMinutes(Number(value))}
              >
                <TabsList className="w-full">
                  {[30, 50, 90].map((length) => (
                    <TabsTrigger key={length} value={String(length)}>
                      {length} min
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            </div>
          </div>

          {/* ------------------------------------------------------- results */}
          <div className="bg-surface-subtle flex flex-col gap-8 p-6 sm:p-8 lg:col-span-3">
            <div className="flex flex-wrap items-end gap-x-10 gap-y-6">
              <div>
                <p className="eyebrow">You speak, per year</p>
                <p className="font-heading mt-2 text-5xl tracking-tight sm:text-6xl">
                  <NumberTicker value={hoursPerYear} />
                  <span className="text-muted-foreground ml-2 text-2xl">
                    hours
                  </span>
                </p>
              </div>
              <div>
                <p className="eyebrow">Each session</p>
                <p className="font-heading mt-2 text-3xl tracking-tight">
                  {yours.toFixed(1)}
                  <span className="text-muted-foreground ml-1.5 text-lg">
                    min
                  </span>
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <p className="eyebrow">Minutes you speak, per session</p>
              {alternatives.map((row) => (
                <div key={row.label}>
                  <div className="flex items-baseline justify-between gap-4 text-sm">
                    <span
                      className={cn("truncate", row.mine && "font-medium")}
                    >
                      {row.label}
                      <span className="text-muted-foreground ml-2 text-xs">
                        {row.detail}
                      </span>
                    </span>
                    <span className="shrink-0 tabular-nums">
                      {row.empty ?? `${row.minutes.toFixed(1)} min`}
                    </span>
                  </div>
                  <div className="bg-muted mt-1.5 h-2 overflow-hidden rounded-full">
                    <div
                      className={cn(
                        "h-full rounded-full transition-[width] duration-500 ease-out",
                        row.mine ? "bg-brand" : "bg-foreground/25",
                      )}
                      style={{
                        width: `${ceiling ? (row.minutes / ceiling) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <Button asChild variant="brand">
                <Link href="/discussions">
                  Find a discussion
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
              <p className="text-muted-foreground text-xs text-pretty">
                Assumes learners hold {Math.round(LEARNER_SHARE * 100)}% of a
                facilitated room and {Math.round(CLASSROOM_SHARE * 100)}% of a
                teacher-led class, over {WEEKS_PER_YEAR} weeks a year.
              </p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
