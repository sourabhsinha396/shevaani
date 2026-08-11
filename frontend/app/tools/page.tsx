import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Free English Speaking Tools",
  description:
    "Free practice tools for spoken English: impromptu speaking rounds, interview prep and more. No account needed.",
  path: "/tools",
});

/** The catalogue is a list here rather than a filesystem convention, so a
 *  future tool is one entry plus its route - and the card copy lives next to
 *  the card that shows it. */
const TOOLS = [
  {
    href: "/tools/impromptu",
    name: "Impromptu speaking",
    description:
      "A random topic, 1 min to think, one minute to talk.",
    tag: "Speaking",
  },
];

export default function ToolsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 md:py-20">
      <p className="eyebrow">Free tools</p>
      <h1 className="mt-4 text-4xl tracking-tight text-balance md:text-5xl">
        Speaking practice free tools
      </h1>
      <p className="text-muted-foreground mt-5 max-w-2xl text-pretty">
        Small, sharp exercises you can do alone, free, without an account.
      </p>

      <div className="mt-12 grid gap-4 sm:grid-cols-2">
        {TOOLS.map((tool) => (
          <Link key={tool.href} href={tool.href} className="group">
            <Card className="h-full transition-colors group-hover:border-foreground/20">
              <CardContent>
                <p className="eyebrow">{tool.tag}</p>
                <h2 className="mt-3 flex items-center gap-2 text-2xl tracking-tight">
                  {tool.name}
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </h2>
                <p className="text-muted-foreground mt-2 text-sm text-pretty">
                  {tool.description}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <p className="text-muted-foreground mt-10 text-sm">
        Suggest more tools at: {" "}
        <Link href="/contact" className="text-foreground underline underline-offset-4">
          contact
        </Link>
        .
      </p>
    </div>
  );
}
