"use client";

import Link from "next/link";

import { Reveal } from "@/components/magicui/effects";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

/** Answers match the actual booking rules in the backend - if a rule changes
 *  there, it has to change here too. */
const FAQS = [
  {
    q: "Do I need a certain level to join?",
    a: "No, The whole point is to learn from people who are better than you. You can be a beginner and still get a lot out of it.",
  },
  {
    q: "What happens if not enough people book?",
    a: "We will postpone the discussion and return your credits. You can rebook for a later date. This rarely happens.",
  },
  {
    q: "How late can I cancel?",
    a: "Up to twelve hours before the session. It returns to your credit balance rather than going through a card refund, so it is instant and you can rebook whenever you like.",
  },
  {
    q: "Which video tool do you use?",
    a: "Google Meet. We recommend joining a couple of minutes early.",
  },
  {
    q: "Do they expire?",
    a: "No. A session you have bought is yours to spend on a group discussion or a one-to-one, whenever you get round to it.",
  },
  {
    q: "Can you provide me a recording of my session?",
    a: "No, we never record nor recommend recording by anyone. We should respect the privacy of all participants and the instructor.",
  },
];

export function Faq() {
  return (
    <section className="section bg-surface-subtle">
      <div className="container-page grid gap-12 lg:grid-cols-3">
        <Reveal>
          <p className="eyebrow mb-5">Frequently Asked Questions</p>
          <h2 className="text-4xl">FAQs.</h2>
          <p className="text-muted-foreground mt-5 text-sm text-pretty">
            Still stuck? The{" "}
            <Link
              href="/discussions"
              className="text-foreground underline-offset-4 hover:underline"
            >
              discussion list
            </Link>{" "}
            shows the real thing - topics, times and how many seats are left.
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
