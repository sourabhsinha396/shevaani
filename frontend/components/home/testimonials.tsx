"use client";

import Image from "next/image";
import { Quote } from "lucide-react";

import { Marquee, NumberTicker, Reveal } from "@/components/magicui/effects";
import { cn } from "@/lib/utils";

/**
 * PLACEHOLDER COPY. These are written to show the layout and the tone; swap
 * them for real quotes before launch. Keep the shape - a name, where they are,
 * their level, and one specific thing that changed.
 */
const FEATURED = {
  quote:
    "I had studied English for nine years and still froze on meetings. In about 2 months of serious practice, I became very confident.",
  name: "Iksha Sinha.",
  detail: "Product manager · Pune · B1 → B2 in 2 months",
};

const COLUMNS = [
  [
    {
      quote:
        "I was able to qualify for bank PO using the speaking skills I gained here.",
      name: "Shipra S.",
      detail: "Bangalore",
    },
    {
      quote:
        "Six people means you cannot hide. That was terrifying in week one and is the whole reason it worked by week four.",
      name: "Jin-woo K.",
      detail: "Seoul · B1",
    },
    {
      quote:
        "My instructor noticed I had gone quiet for ten minutes and motivated me in chat to speak up.",
      name: "Eduardo Taylor",
      detail: "Casablanca · B2",
    },
  ],
  [
    {
      quote:
        "Booked a one-to-one the night before an interview. Fifty minutes of being asked hard questions in English was worth more than a week of revision.",
      name: "Brendan H.",
      detail: "Bogotá · C1",
    },
    {
      quote:
        "I like the detailed feedback report that we get after each session. Thanks guys",
      name: "Harsh Raj",
      detail: "Pune",
      image: "/images/tesimonials/harsh.png",
    },
    {
      quote:
        "Helped me pitch better for my Sales presentations and I got promoted to Senior Associate.",
      name: "Arihan Prakash",
      detail: "Lucknow",
    },
  ],
];

const PROOF = [
  { value: 67, suffix: "%", label: "would book again" },
  { value: 20, suffix: "%", label: "said it helped them on their job" },
];

function TestimonialCard({
  quote,
  name,
  detail,
  image,
  className,
}: {
  quote: string;
  name: string;
  detail: string;
  /** A photo, when we have one of the actual person; initials otherwise. */
  image?: string;
  className?: string;
}) {
  return (
    <figure
      className={cn(
        "border-border/60 bg-card hover:border-brand-ink/40 rounded-xl border p-5 transition-colors",
        className,
      )}
    >
      <blockquote className="text-sm text-pretty">{quote}</blockquote>
      <figcaption className="mt-4 flex items-center gap-3">
        {image ? (
          <Image
            src={image}
            alt={name}
            width={64}
            height={64}
            className="bg-secondary size-8 shrink-0 rounded-full object-cover"
          />
        ) : (
          <span className="bg-secondary text-secondary-foreground grid size-8 shrink-0 place-items-center rounded-full text-[11px] font-medium">
            {name.slice(0, 2)}
          </span>
        )}
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{name}</span>
          <span className="text-muted-foreground block truncate text-xs">
            {detail}
          </span>
        </span>
      </figcaption>
    </figure>
  );
}

export function Testimonials() {
  return (
    <section className="section overflow-hidden">
      <div className="container-page">
        <Reveal className="max-w-2xl">
          <p className="eyebrow mb-5">What learners say</p>
          <h2 className="text-4xl text-balance">
            Testimonials
          </h2>
        </Reveal>

        <div className="mt-12 grid gap-6 lg:grid-cols-5">
          {/* The one quote worth reading in full, given the room to be read. */}
          <Reveal className="lg:col-span-2">
            <figure className="border-border/60 bg-surface-subtle flex h-full flex-col rounded-xl border p-7">
              <Quote className="text-brand-ink size-6" />
              <blockquote className="font-heading mt-5 text-xl leading-snug text-pretty">
                {FEATURED.quote}
              </blockquote>
              <figcaption className="mt-6">
                <p className="font-medium">{FEATURED.name}</p>
                <p className="text-muted-foreground text-sm">
                  {FEATURED.detail}
                </p>
              </figcaption>

              <dl className="border-border/60 mt-auto grid grid-cols-2 gap-4 border-t pt-6">
                {PROOF.map((stat) => (
                  <div key={stat.label}>
                    <dt className="font-heading text-3xl tracking-tight">
                      <NumberTicker value={stat.value} />
                      {stat.suffix}
                    </dt>
                    <dd className="text-muted-foreground mt-1 text-xs text-pretty">
                      {stat.label}
                    </dd>
                  </div>
                ))}
              </dl>
            </figure>
          </Reveal>

          {/* Two columns drifting in opposite directions. Hovering either one
              stops it, so a quote that catches your eye can be finished. */}
          <div className="grid gap-6 sm:grid-cols-2 lg:col-span-3">
            {COLUMNS.map((column, i) => (
              <Marquee
                key={i}
                vertical
                reverse={i === 1}
                speed={34 + i * 8}
                className="h-[26rem]"
              >
                {column.map((item) => (
                  <TestimonialCard key={item.name} {...item} />
                ))}
              </Marquee>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
