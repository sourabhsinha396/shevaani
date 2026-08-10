import Link from "next/link";
import { MessagesSquare } from "lucide-react";

import type { SiteConfig } from "@/lib/types";

/**
 * The legal pages have to be reachable from every page, not just findable —
 * Razorpay's account review checks for exactly that, and a footer link is also
 * where a learner looks for the refund rules.
 *
 * `flag` gates a link on a site setting. A switched-off product must disappear
 * from the whole of the chrome, not just the header — a nav that has dropped
 * 1:1 above a footer still advertising it is worse than either alone. The legal
 * column has no `flag` and never will.
 */
const COLUMNS: Array<{
  heading: string;
  links: Array<{ href: string; label: string; flag?: keyof SiteConfig }>;
}> = [
  {
    heading: "Sessions",
    links: [
      { href: "/discussions", label: "Group discussions" },
      { href: "/one-on-one", label: "1:1 sessions", flag: "one_on_one_enabled" },
      { href: "/pricing", label: "Pricing" },
    ],
  },
  {
    heading: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/contact", label: "Contact" },
    ],
  },
  {
    heading: "Legal",
    links: [
      { href: "/terms", label: "Terms of service" },
      { href: "/privacy", label: "Privacy policy" },
      { href: "/refunds", label: "Cancellations and credits" },
    ],
  },
];

/* Takes the config as a prop rather than reading the context: this is a server
   component, and it is rendered by the layout that already has the value. */
export function SiteFooter({ config }: { config: SiteConfig }) {
  return (
    <footer className="border-border bg-background border-t py-16 md:py-20 print:hidden">
      <div className="container-page">
        {/* Asymmetric 12-column split: the brand block gets five columns so the
            blurb can breathe, and the three link columns share the remaining
            seven. Below `md` it all stacks, and the links fall to two columns
            rather than three so the longest labels don't wrap. */}
        <div className="grid gap-10 md:grid-cols-12">
          <div className="md:col-span-5">
            <Link
              href="/"
              className="font-heading text-brand-ink flex w-fit items-center gap-2.5 text-2xl leading-none tracking-tight"
            >
              <span className="bg-brand text-brand-foreground grid size-9 place-items-center rounded-full">
                <MessagesSquare className="size-4.5" />
              </span>
              Shevaani
            </Link>
            <p className="text-muted-foreground mt-4 max-w-sm text-sm leading-relaxed">
              Live spoken English with real people: daily group discussions and 1:1 sessions
              with an instructor, booked a session at a time.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-8 md:col-span-7 md:grid-cols-3">
            {COLUMNS.map((column) => (
              <div key={column.heading}>
                {/* Not `.eyebrow`: these are column labels sitting above their
                    own links, so they need to out-weigh them. The eyebrow is
                    muted and would read as just another link. */}
                <h3 className="text-foreground text-xs font-medium tracking-[0.15em] uppercase">
                  {column.heading}
                </h3>
                <ul className="mt-4 space-y-3">
                  {column.links
                    .filter((link) => !link.flag || config[link.flag])
                    .map((link) => (
                      <li key={link.href}>
                        <Link
                          href={link.href}
                          className="text-muted-foreground hover:text-foreground text-sm transition-colors"
                        >
                          {link.label}
                        </Link>
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="border-border/60 text-muted-foreground mt-14 flex flex-col items-start justify-between gap-4 border-t pt-8 text-xs md:flex-row md:items-center">
          <p>&copy; {new Date().getFullYear()} Shevaani. All rights reserved.</p>
          <p>Group discussions run daily · 1:1 sessions in your timezone</p>
        </div>
      </div>
    </footer>
  );
}
