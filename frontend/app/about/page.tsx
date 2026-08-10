import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "About",
  description:
    "Why Shevaani is built around small-group discussion, and how a session actually works.",
  path: "/about",
});

const NUMBERS = [
  { value: "6", label: "learners at most in a discussion" },
  { value: "45", label: "minutes, and everyone speaks" },
  { value: "1", label: "session at a time, no subscription" },
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 md:py-20">
      <h1 className="text-4xl tracking-tight text-balance">
        People learn to speak by speaking
      </h1>

      <div className="text-muted-foreground mt-8 flex flex-col gap-6 text-pretty">
        <p>
          Most people who want to speak better English have already done the
          courses. They know the grammar, they have the vocabulary, and they
          still hesitate for two seconds before every sentence in a meeting. The
          missing part is not knowledge. It is having said the thing out loud,
          often enough, with someone listening.
        </p>
        <p>
          So Shevaani is not a course. It is a schedule of small discussions you
          can drop into: a topic, a handful of other learners, and an
          instructor whose job is to keep the conversation moving and to correct
          you where it matters. Forty-five minutes, then you go back to your day.
        </p>
        <p>
          The size is the whole design. A group of six means everyone talks. At
          twenty, four people talk and the rest listen — which is a lecture, and
          you can watch one of those for free. When a discussion has not reached
          its minimum two hours before it starts, we cancel it and return the
          session rather than run a conversation that will not work.
        </p>
      </div>

      <div className="mt-12 grid gap-4 sm:grid-cols-3">
        {NUMBERS.map((item) => (
          <Card key={item.label}>
            <CardContent>
              <p className="font-heading text-4xl tracking-tight">{item.value}</p>
              <p className="text-muted-foreground mt-2 text-sm text-pretty">
                {item.label}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <h2 className="mt-16 text-2xl tracking-tight">How a session runs</h2>
      <ol className="text-muted-foreground mt-6 flex flex-col gap-4 text-[0.9375rem]">
        <li>
          <strong className="text-foreground">You book a slot</strong> from the
          discussions list. One session.
        </li>
        <li>
          <strong className="text-foreground">Prep arrives beforehand</strong> —
          usually a short article or a list of questions, so nobody starts cold.
        </li>
        <li>
          <strong className="text-foreground">You join on video</strong>. The
          link opens shortly before the start and your instructor lets you in.
        </li>
        <li>
          <strong className="text-foreground">You talk</strong>, and the
          instructor keeps it balanced — which mostly means making sure the
          quietest person in the room gets the floor.
        </li>
      </ol>

      <h2 className="mt-16 text-2xl tracking-tight">Instructors</h2>
      <p className="text-muted-foreground mt-6 text-pretty">
        Sessions are hosted by instructors we bring on ourselves — there is no
        open marketplace and no self-signup. Each one hosts from their own
        calendar, which is what makes them the actual host of the video call
        rather than another participant in it.
      </p>

      <div className="mt-14 flex flex-wrap gap-3">
        <Button asChild variant="brand">
          <Link href="/discussions">See upcoming discussions</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/contact">Ask us something</Link>
        </Button>
      </div>
    </div>
  );
}
