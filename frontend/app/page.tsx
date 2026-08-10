import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Faq } from "@/components/home/faq";
import { Features } from "@/components/home/features";
import { Hero } from "@/components/home/hero";
import { Pricing } from "@/components/home/pricing";
import { SessionPreview } from "@/components/home/session-preview";
import { TalkTime } from "@/components/home/talk-time";
import { Testimonials } from "@/components/home/testimonials";
import { Marquee, NumberTicker, Reveal, Ripple } from "@/components/magicui/effects";
import { Button } from "@/components/ui/button";

const FOR_WHOM = [
  "For Sales Professionals", "For Working Professionals", "For Job Seekers", "For Placement Takers", "For MBA Students", "For College Students", "For Entrepreneurs", "For Afcat Aspirants", "For Cabin Crew", "For VISA Aspirants", "For IELTS Aspirants", "For TOEFL Aspirants", "For PTE Aspirants", "For OET Aspirants", "For GRE Aspirants", "For GMAT Aspirants", "For CAT Aspirants", "For UPSC Aspirants", "For Defence Aspirants"
];

const STATS = [
  { value: 4200, suffix: "+", label: "Sessions run" },
  { value: 38, suffix: "", label: "Countries" },
  { value: 96, suffix: "%", label: "Would return" },
];

const STEPS = [
  { n: "01", title: "Pick a discussion", body: "Browse by topic and time. Book with one session." },
  { n: "02", title: "Read the prep", body: "A short article and a handful of questions, a day ahead." },
  { n: "03", title: "Show up and talk", body: "An instructor keeps it moving and everyone gets airtime." },
];

export default function HomePage() {
  return (
    <>
      <Hero />

      {/* ------------------------------------------------------- topics */}
      <section className="border-border/60 bg-surface-subtle border-b py-6">
        <Marquee speed={45}>
          {FOR_WHOM.map((audience) => (
            <span
              key={audience}
              className="text-muted-foreground border-border rounded-full border px-4 py-1.5 text-sm whitespace-nowrap"
            >
              {audience}
            </span>
          ))}
        </Marquee>
      </section>

      <SessionPreview />
      <Features />

      {/* ---------------------------------------------------------- stats */}
      <section className="border-border/60 bg-surface-subtle border-b py-20">
        <dl className="container-page grid max-w-3xl grid-cols-3 gap-6 text-center">
          {STATS.map((stat, i) => (
            <Reveal key={stat.label} delay={i * 90}>
              <dt className="font-heading text-4xl tracking-tight sm:text-5xl">
                <NumberTicker value={stat.value} />
                {stat.suffix}
              </dt>
              <dd className="text-muted-foreground mt-2 text-xs tracking-[0.2em] uppercase">
                {stat.label}
              </dd>
            </Reveal>
          ))}
        </dl>
      </section>

      <TalkTime />

      {/* -------------------------------------------------- how it works */}
      <section className="section">
        <div className="container-page">
          <Reveal>
            <p className="eyebrow mb-5">How it works</p>
            <h2 className="text-4xl md:text-5xl">Three steps, then you talk.</h2>
          </Reveal>

          <div className="mt-14 grid gap-10 sm:grid-cols-3">
            {STEPS.map((step, i) => (
              <Reveal key={step.n} delay={i * 110} className="border-border/60 border-t pt-6">
                <span className="text-brand-ink text-sm font-medium tracking-[0.2em]">
                  {step.n}
                </span>
                <h3 className="mt-3 font-medium">{step.title}</h3>
                <p className="text-muted-foreground mt-2 text-sm text-pretty">{step.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <Pricing />
      <Testimonials />
      <Faq />

      {/* ------------------------------------------------------------ cta */}
      <section className="border-border/60 relative overflow-hidden border-b py-28 text-center md:py-36">
        <Ripple circles={5} base={280} />

        <div className="container-page relative flex flex-col items-center gap-6">
          <h2 className="max-w-xl text-5xl leading-[1.05] text-balance md:text-6xl">
            Your first discussion is <span className="text-brand-ink">on us.</span>
          </h2>
          <p className="text-muted-foreground max-w-md text-pretty">
            Make an account, claim half your first session free, and join a group tonight.
          </p>
          <Button asChild size="lg" variant="brand">
            <Link href="/register">
              Create an account
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>
      </section>
    </>
  );
}
