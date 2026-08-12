"use client";

import * as React from "react";
import Image from "next/image";
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
 * here is illustrative - the point is to show what "everyone gets airtime"
 * looks like as a number, since that is the claim the product is making.
 */
const ROOM = [
  { name: "Shalini", photo: "/images/homepage-session/shalini.png", score: '91' },
  { name: "Kundan", photo: "/images/homepage-session/kundan.png", score: '59' },
  { name: "Divyanshu", photo: "/images/homepage-session/divyanshu.png", score: '63' },
  {
    name: "Sourabh",
    photo: "/images/homepage-session/sourabh.jpeg",
    score: '88',
    // The only landscape shot of the four - centring it crops the face off.
    position: "object-[70%_35%]",
  },
];

/**
 * Whose turn it is, in order. Deliberately not 0-1-2-3: a real discussion
 * bounces around the room, and stepping straight through the grid makes the
 * highlight look like a loading spinner rather than a conversation.
 */
const TURNS = [0, 2, 1, 3, 2, 0, 3, 1];

const AGENDA = [
  { icon: FileText, label: "Topic", value: "We never tell, so as to simulate real-world" },
  { icon: CalendarClock, label: "Runs for", value: "30 minutes approx" },
  { icon: Video, label: "Joins via", value: "Google Meet" },
];

/** The call controls along the bottom. Decoration - the real thing is Meet. */
const CONTROLS = [Mic, Video, Hand, MessageSquare];

export function SessionPreview() {
  // Whose turn it is, as an index into TURNS. One speaker at a time, because
  // that is what a facilitated room sounds like - people take turns rather than
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
      {/* The call window gets the wider column - the tiles are the argument,
          so they get the room to be looked at. */}
      <div className="container-page grid items-center gap-14 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <Reveal>
          <p className="eyebrow mb-5">Inside a discussion</p>
          <h2 className="text-4xl text-balance md:text-5xl">
            4-8 learners, ~30 minutes
          </h2>
          <p className="text-muted-foreground mt-5 text-pretty">
            An moderator gives a random topic, without any prep, you either speak or waste your turn. 
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
                Will AI replace human jobs?
              </p>
              <Badge variant="outline" className="ml-auto">
                30 min
              </Badge>
            </div>

            {/* Two by two, the way a four-person call actually tiles. Cameras
                on: the photo is the tile, edge to edge, with the chrome laid
                over it rather than beside it. */}
            <div className="grid grid-cols-2 gap-1.5 p-1.5 sm:gap-2 sm:p-2">
              {ROOM.map((person, i) => {
                const talking = i === speaker;
                return (
                  <div
                    key={person.name}
                    className={cn(
                      "bg-secondary relative aspect-[4/3] overflow-hidden rounded-lg ring-inset transition-all duration-300",
                      talking ? "ring-brand ring-2" : "ring-border/60 ring-1",
                    )}
                  >
                    <Image
                      src={person.photo}
                      alt=""
                      fill
                      sizes="(min-width: 1024px) 22vw, (min-width: 640px) 45vw, 48vw"
                      className={cn(
                        "object-cover transition-[filter,transform] duration-300",
                        person.position ?? "object-center",
                        // Whoever is quiet reads as background, so the eye
                        // lands on the person holding the floor.
                        talking ? "scale-[1.02]" : "brightness-90 saturate-75",
                      )}
                    />

                    {/* Enough of a wash at top and bottom for the badge and
                        the name plate to stay legible over any photograph. */}
                    <span
                      aria-hidden
                      className="absolute inset-0 bg-gradient-to-b from-black/40 via-transparent to-black/60"
                    />

                    {/* Talk time, top right - the number that carries the
                        argument, so it stays on screen the whole time. */}
                    <span className="absolute top-2 right-2 rounded-full bg-black/45 px-2 py-0.5 text-[11px] font-medium text-white tabular-nums backdrop-blur-sm">
                      {person.score}%
                    </span>

                    {/* Name plate, bottom left, exactly where a call puts it. */}
                    <span className="absolute bottom-2 left-2 flex items-center gap-1.5 text-white">
                      {/* The bars are inked for a light card; over a photo
                          they have to go white to survive. */}
                      <VoiceBars
                        active={talking}
                        bars={4}
                        className={
                          talking ? "[&>span]:bg-white" : "[&>span]:bg-white/50"
                        }
                      />
                      <span className="text-xs font-medium drop-shadow">
                        {person.name}
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
                4 of 8 · instructor in the session
              </p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
