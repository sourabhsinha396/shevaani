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

import { Marquee, Reveal } from "@/components/magicui/effects";
import { BentoCard, BentoGrid } from "@/components/ui/bento-grid";

/** Two-column cards carry the claims that matter most; the rest sit one wide.
 *  The spans add up to a full row three times over, so the grid never leaves a
 *  hole. Washes alternate direction so no two neighbours lean the same way. */
const FEATURES = [
  {
    Icon: Users,
    name: "Groups of four to eight",
    description:
      "Small enough that everyone actually speaks. Above eight, talk time per person collapses - so we cap it.",
    className: "lg:col-span-2",
    wash: "bg-gradient-to-br from-(--brand)/15 via-transparent to-transparent",
  },
  {
    Icon: Mic,
    name: "You figure out how to get opportunity",
    description:
      "Moderator won't give you opportunity, You learn to snatch it.",
    wash: "bg-gradient-to-bl from-(--brand)/10 to-transparent",
  },
  {
    Icon: CalendarCheck,
    name: "We never tell you the topic",
    description:
      "You can call us evil but we don't give you the topic in advance.",
    wash: "bg-gradient-to-tr from-(--brand)/10 to-transparent",
  },
  {
    Icon: Video,
    name: "One click into Google Meet",
    description:
      "No installs, no meeting IDs. Your link sits on your dashboard from the moment you book.",
    wash: "bg-gradient-to-t from-(--brand)/10 to-transparent",
  },
  {
    Icon: Globe2,
    name: "Global discussions, local time",
    description:
      "You might meet extremely capable people from around the world.",
    wash: "bg-gradient-to-b from-(--brand)/10 to-transparent",
  },
  {
    Icon: RefreshCw,
    name: "12 hours to cancel",
    description:
      "You can cancel or postpone upto 12 hours before the session. We return you the session back to your balance.",
    wash: "bg-gradient-to-tl from-(--brand)/10 to-transparent",
  },
  {
    Icon: ShieldCheck,
    name: "Secured Payment Gateway",
    description:
      "We use Stripe, Razorpay and Paypal for secure payments. Your card details are never reach our servers.",
    className: "lg:col-span-2",
    wash: "bg-gradient-to-tl from-(--brand)/15 via-transparent to-transparent",
  },
];

/** What a room actually asks of you, scrolling. This used to be the CEFR ladder;
 *  the product no longer sorts anyone into a band, and a marquee of labels
 *  nothing in the app acts on was a promise the timetable could not keep. */
const TOPICS = [
  "Will AI take your job?",
  "Neo Banks vs Traditional Banks",
  "Globalalization or Regionalization?",
  "Work from home or office?",
  "The future of AI",
  "Should Social Media be Regulated?",
  "Is Remote Work the Future?",
  "The Impact of Climate Change",
  "The Role of Technology in Education",
  "Should AI be Regulated?",
];

export function Features() {
  return (
    <section className="section">
      <div className="container-page">
        <Reveal className="max-w-2xl">
          <p className="eyebrow mb-5">Why it works</p>
          <h2 className="text-4xl text-balance">
            Our Features
          </h2>
          <p className="text-muted-foreground mt-5 text-pretty">
            Most platforms sell you lessons. Fluency comes from hours of real
            conversation, so that is the only thing we schedule.
          </p>
        </Reveal>

        <Reveal delay={80}>
          <BentoGrid className="mt-14 auto-rows-auto grid-cols-1 lg:auto-rows-[16rem] lg:grid-cols-3">
            {FEATURES.map(({ wash, className, ...card }) => (
              <BentoCard
                key={card.name}
                {...card}
                className={`col-span-1 ${className ?? ""}`}
                background={<div className={`absolute inset-0 ${wash}`} />}
              />
            ))}
          </BentoGrid>
        </Reveal>

        {/* Scrolling the other way to the topic marquee up top, so the page
            never looks like it is repeating itself. */}
        <div className="border-border/60 mt-14 border-t pt-8">
          <p className="eyebrow mb-5 text-center">Book a one-on-one session on</p>
          <Marquee speed={38} reverse>
            {TOPICS.map((topic) => (
              <span
                key={topic}
                className="border-border text-muted-foreground rounded-full border px-4 py-1.5 text-sm whitespace-nowrap"
              >
                {topic}
              </span>
            ))}
          </Marquee>
        </div>
      </div>
    </section>
  );
}
