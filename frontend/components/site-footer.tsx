import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { company } from "@/lib/company";
import type { SiteConfig } from "@/lib/types";

/**
 * The legal pages have to be reachable from every page, not just findable -
 * Razorpay's account review checks for exactly that, and a footer link is also
 * where a learner looks for the refund rules.
 *
 * `flag` gates a link on a site setting. A switched-off product must disappear
 * from the whole of the chrome, not just the header - a nav that has dropped
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
    heading: "Free tools",
    links: [
      { href: "/tools/impromptu", label: "Impromptu speaking" },
      { href: "/tools", label: "All tools" },
    ],
  },
  {
    heading: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/contact", label: "Contact" },
      // The address itself, not a "Email us" label: a reviewer scanning for a
      // reachable email needs to see one, and a learner gets the address
      // without a click. Absent from the column when the env var is unset.
      ...(company.supportEmail
        ? [{ href: `mailto:${company.supportEmail}`, label: company.supportEmail }]
        : []),
    ],
  },
  {
    heading: "Legal",
    links: [
      { href: "/terms", label: "Terms of service" },
      { href: "/privacy", label: "Privacy policy" },
      { href: "/refunds", label: "Cancellations and credits" },
      { href: "/shipping", label: "Shipping policy" },
    ],
  },
];

/* Takes the config as a prop rather than reading the context: this is a server
   component, and it is rendered by the layout that already has the value. */
export function SiteFooter({ config }: { config: SiteConfig }) {
  return (
    <footer className="border-border bg-background border-t py-16 md:py-20 print:hidden">
      <div className="container-page">
        {/* Asymmetric 12-column split: the brand block gets four columns so the
            blurb can breathe, and the four link columns share the remaining
            eight. Below `md` it all stacks, and the links fall to two columns
            rather than four so the longest labels don't wrap. */}
        <div className="grid gap-10 md:grid-cols-12">
          <div className="md:col-span-4">
            <Link
              href="/"
              className="font-heading text-brand-ink flex w-fit items-center gap-2.5 text-2xl leading-none tracking-tight"
            >
              {/* The link itself is already `text-brand-ink`, so the mark picks
                  up the brand colour from `currentColor`. */}
              <BrandMark className="size-9" />
              Shevaani
            </Link>
            <p className="text-muted-foreground mt-4 max-w-sm text-sm leading-relaxed">
              Live spoken English with real people: daily group discussions and 1:1 sessions
              with an instructor, booked a session at a time.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-8 md:col-span-8 md:grid-cols-4">
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
