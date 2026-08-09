"use client";

import Link from "next/link";

import { Reveal } from "@/components/magicui/effects";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

/** Answers match the actual booking rules in the backend — if a rule changes
 *  there, it has to change here too. */
const FAQS = [
  {
    q: "Do I need a certain level to join?",
    a: "You need enough English to hold a slow conversation — roughly A2 and up. Every discussion is published with a CEFR band, and you book into the band that fits. If you land in a room that feels wrong, cancel and the credit comes straight back.",
  },
  {
    q: "What happens if not enough people book?",
    a: "The session cancels itself two hours before it starts and refunds every learner's credit automatically. You will never be the only person in a room, and you never have to ask for the credit back.",
  },
  {
    q: "How late can I cancel?",
    a: "Up to twelve hours before the session. The credit returns to your account rather than going through a card refund, so it is instant and you can rebook the same evening.",
  },
  {
    q: "What if the discussion is full?",
    a: "You join the waitlist. If someone cancels, the next person in line is enrolled and charged automatically — you do not have to sit refreshing the page.",
  },
  {
    q: "When can I book a one-to-one?",
    a: "Between 07:00 and 19:00 IST, and each booking keeps an hour clear on either side so your instructor is never running one session straight into the next.",
  },
  {
    q: "Which video tool do you use?",
    a: "Google Meet. The link appears on your dashboard fifteen minutes before the session — no installs and no meeting IDs to type. Your instructor hosts, so join a couple of minutes early and they will let you in.",
  },
  {
    q: "Do credits expire?",
    a: "No. One credit is one session, group or one-to-one, whenever you get round to using it.",
  },
  {
    q: "Can I try it before paying?",
    a: "Yes — make an account and your first group discussion is on us.",
  },
];

export function Faq() {
  return (
    <section className="section bg-surface-subtle">
      <div className="container-page grid gap-12 lg:grid-cols-3">
        <Reveal>
          <p className="eyebrow mb-5">Common questions</p>
          <h2 className="text-4xl md:text-5xl">Answers.</h2>
          <p className="text-muted-foreground mt-5 text-sm text-pretty">
            Still stuck? The{" "}
            <Link
              href="/discussions"
              className="text-foreground underline-offset-4 hover:underline"
            >
              discussion list
            </Link>{" "}
            shows the real thing — levels, times and how many seats are left.
          </p>
        </Reveal>

        <Reveal delay={100} className="lg:col-span-2">
          <Accordion
            type="single"
            collapsible
            defaultValue="faq-0"
            className="border-border/60 border-t"
          >
            {FAQS.map((faq, i) => (
              <AccordionItem
                key={faq.q}
                value={`faq-${i}`}
                className="border-border/60 border-b last:border-b"
              >
                <AccordionTrigger className="py-5 text-base hover:no-underline">
                  {faq.q}
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground max-w-2xl pb-5 text-sm text-pretty">
                  {faq.a}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </Reveal>
      </div>
    </section>
  );
}
