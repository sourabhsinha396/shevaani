"use client";

import {
  CalendarCheck,
  Globe2,
  Mic,
  RefreshCw,
  ShieldCheck,
  Users,
  Video,
} from "lucide-react";

import { Marquee, Reveal, SpotlightCard } from "@/components/magicui/effects";
import { cn } from "@/lib/utils";

/** `wide` cards take both columns on desktop — the two claims that carry the
 *  most weight get the most room, and the grid stays a grid. */
const FEATURES = [
  {
    icon: Users,
    title: "Groups of four to eight",
    body: "Small enough that everyone actually speaks. Above eight, talk time per person collapses — so we cap it.",
    wide: true,
  },
  {
    icon: Mic,
    title: "Matched by level",
    body: "Every discussion carries a CEFR band. A nervous A2 is never dropped into a room of C1 speakers.",
  },
  {
    icon: CalendarCheck,
    title: "Prep sent in advance",
    body: "An article and a question list land in your inbox a day before, so you arrive with something to say.",
  },
  {
    icon: Video,
    title: "One click into Google Meet",
    body: "No installs, no meeting IDs. The link appears fifteen minutes before your session starts.",
  },
  {
    icon: Globe2,
    title: "Rooms across 38 countries",
    body: "You practise against accents you will actually meet, not against one teacher from one place.",
  },
  {
    icon: RefreshCw,
    title: "Cancel and keep the credit",
    body: "Up to twelve hours before. The credit comes straight back — no refund queue to stand in.",
  },
  {
    icon: ShieldCheck,
    title: "Under-booked sessions auto-cancel",
    body: "If a discussion hasn't filled two hours out, it cancels itself and everyone is refunded. You never sit in an empty room.",
    wide: true,
  },
];

/** The level bands, scrolling. Real CEFR labels, in the order a learner moves
 *  through them. */
const LEVELS = [
  "A2 · Getting by",
  "B1 · Holding a conversation",
  "B1+ · Opinions",
  "B2 · Debating",
  "B2+ · Nuance",
  "C1 · Arguing well",
  "C1+ · Idioms and jokes",
];

export function Features() {
  return (
    <section className="section">
      <div className="container-page">
        <Reveal className="max-w-2xl">
          <p className="eyebrow mb-5">Why it works</p>
          <h2 className="text-4xl text-balance md:text-5xl">
            Built around the thing that actually helps — talking.
          </h2>
          <p className="text-muted-foreground mt-5 text-pretty">
            Most platforms sell you lessons. Fluency comes from hours of real
            conversation, so that is the only thing we schedule.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, i) => (
            <Reveal
              key={feature.title}
              delay={i * 60}
              className={cn(feature.wide && "lg:col-span-2")}
            >
              <SpotlightCard className="border-border/60 bg-card hover:border-brand-ink/40 h-full rounded-xl border p-6 transition-colors">
                <span className="border-border/60 bg-background grid size-10 place-items-center rounded-full border">
                  <feature.icon className="text-brand-ink size-4.5" />
                </span>
                <h3 className="mt-5 font-medium">{feature.title}</h3>
                <p className="text-muted-foreground mt-2 text-sm text-pretty">
                  {feature.body}
                </p>
              </SpotlightCard>
            </Reveal>
          ))}
        </div>

        {/* Levels, scrolling the other way to the topic marquee up top, so the
            page never looks like it is repeating itself. */}
        <div className="border-border/60 mt-14 border-t pt-8">
          <p className="eyebrow mb-5 text-center">Rooms run at every level</p>
          <Marquee speed={38} reverse>
            {LEVELS.map((level) => (
              <span
                key={level}
                className="border-border text-muted-foreground rounded-full border px-4 py-1.5 text-sm whitespace-nowrap"
              >
                {level}
              </span>
            ))}
          </Marquee>
        </div>
      </div>
    </section>
  );
}
