"use client";

import * as React from "react";
import {
  CalendarClock,
  FileText,
  Hand,
  MessageSquare,
  Mic,
  PhoneOff,
  Users,
  Video,
} from "lucide-react";

import { Reveal, VoiceBars } from "@/components/magicui/effects";
import { Badge } from "@/components/ui/badge";
import { BorderBeam } from "@/components/ui/border-beam";
import { cn } from "@/lib/utils";

/**
 * A mock of a live room, dressed as the video call it actually is. Everything
 * here is illustrative — the point is to show what "everyone gets airtime"
 * looks like as a number, since that is the claim the product is making.
 *
 * Four shares summing to 80% is not a coincidence: it is the same learner share
 * the talk-time calculator further down the page is built on.
 */
const ROOM = [
  { name: "Priya", country: "India", share: 21 },
  { name: "Arjun", country: "India", share: 19 },
  { name: "Mariana", country: "Brazil", share: 22 },
  { name: "Yusuf", country: "Türkiye", share: 18 },
];

/**
 * Whose turn it is, in order. Deliberately not 0-1-2-3: a real discussion
 * bounces around the room, and stepping straight through the grid makes the
 * highlight look like a loading spinner rather than a conversation.
 */
const TURNS = [0, 2, 1, 3, 2, 0, 3, 1];

const AGENDA = [
  { icon: FileText, label: "Prep read", value: "Sent 24h ahead" },
  { icon: CalendarClock, label: "Runs for", value: "50 minutes" },
  { icon: Video, label: "Joins via", value: "Google Meet" },
];

/** The call controls along the bottom. Decoration — the real thing is Meet. */
const CONTROLS = [Mic, Video, Hand, MessageSquare];

export function SessionPreview() {
  // Whose turn it is, as an index into TURNS. One speaker at a time, because
  // that is what a facilitated room sounds like — people take turns rather than
  // talking over each other.
  const [turn, setTurn] = React.useState(0);
  const speaker = TURNS[turn];

  React.useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setTurn((t) => (t + 1) % TURNS.length), 2600);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="section bg-surface-subtle">
      <div className="container-page grid items-center gap-14 lg:grid-cols-2">
        <Reveal>
          <p className="eyebrow mb-5">Inside a discussion</p>
          <h2 className="text-4xl text-balance md:text-5xl">
            Eight people, fifty minutes, everybody talks.
          </h2>
          <p className="text-muted-foreground mt-5 text-pretty">
            A facilitator watches the room and pulls in whoever has gone quiet.
            Nobody sits through someone else&apos;s lecture, and nobody dominates
            — the split on each tile is what a normal session looks like.
          </p>

          <dl className="mt-8 flex flex-col gap-4">
            {AGENDA.map((item) => (
              <div key={item.label} className="flex items-center gap-3">
                <span className="border-border/60 bg-background grid size-9 shrink-0 place-items-center rounded-full border">
                  <item.icon className="text-brand-ink size-4" />
                </span>
                <div className="flex items-baseline gap-2 text-sm">
                  <dt className="text-muted-foreground">{item.label}</dt>
                  <dd className="font-medium">{item.value}</dd>
                </div>
              </div>
            ))}
          </dl>
        </Reveal>

        <Reveal delay={120}>
          {/* The mock call window. A card, but dressed as app chrome so it
              reads as a product screenshot rather than another content card. */}
          <div className="bg-card border-border/60 relative overflow-hidden rounded-xl border">
            <BorderBeam
              size={140}
              duration={9}
              colorFrom="var(--brand)"
              colorTo="var(--brand-ink)"
            />

            <div className="border-border/60 flex items-center gap-3 border-b px-5 py-3.5">
              <span className="relative flex size-2">
                <span className="bg-brand-ink/60 absolute inset-0 rounded-full motion-safe:animate-[pulse-ring_2s_ease-out_infinite]" />
                <span className="bg-brand-ink relative size-2 rounded-full" />
              </span>
              <p className="text-sm font-medium">
                Remote work: is the office over?
              </p>
              <Badge variant="outline" className="ml-auto">
                B2–C1
              </Badge>
            </div>

            {/* Two by two, the way a four-person call actually tiles. Cameras
                are off — initials rather than stock faces, because invented
                photographs of learners would be a lie the layout doesn't
                need. */}
            <div className="grid grid-cols-2 gap-2 p-2 sm:gap-3 sm:p-3">
              {ROOM.map((person, i) => {
                const talking = i === speaker;
                return (
                  <div
                    key={person.name}
                    className={cn(
                      "bg-secondary/60 relative grid aspect-[4/3] place-items-center overflow-hidden rounded-lg ring-inset transition-all duration-300",
                      talking
                        ? "ring-brand bg-secondary ring-2"
                        : "ring-border/60 ring-1",
                    )}
                  >
                    {/* Talk time, top right — the number that carries the
                        argument, so it stays on screen the whole time. */}
                    <span
                      className={cn(
                        "bg-background/70 absolute top-2 right-2 rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums backdrop-blur transition-colors",
                        talking ? "text-foreground" : "text-muted-foreground",
                      )}
                    >
                      {person.share}%
                    </span>

                    <span
                      className={cn(
                        "grid size-14 place-items-center rounded-full text-base font-medium transition-all duration-300",
                        talking
                          ? "bg-brand text-brand-foreground scale-105"
                          : "bg-background text-foreground/80 border-border/60 border",
                      )}
                    >
                      {person.name.slice(0, 2)}
                    </span>

                    {/* Name plate, bottom left, exactly where a call puts it. */}
                    <span className="absolute bottom-2 left-2 flex items-center gap-1.5">
                      <VoiceBars active={talking} bars={4} />
                      <span className="text-xs font-medium">{person.name}</span>
                      <span className="text-muted-foreground hidden text-[11px] sm:inline">
                        · {person.country}
                      </span>
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="border-border/60 flex items-center gap-3 border-t px-5 py-3">
              <div aria-hidden className="flex items-center gap-1.5">
                {CONTROLS.map((Icon, i) => (
                  <span
                    key={i}
                    className="bg-secondary text-muted-foreground grid size-7 place-items-center rounded-full"
                  >
                    <Icon className="size-3.5" />
                  </span>
                ))}
                <span className="bg-destructive/15 text-destructive grid size-7 place-items-center rounded-full">
                  <PhoneOff className="size-3.5" />
                </span>
              </div>

              <p className="text-muted-foreground ml-auto flex items-center gap-2 text-xs">
                <Users className="size-3.5" />
                4 of 8 · facilitated by Anika
              </p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
