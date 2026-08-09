import Link from "next/link";

/**
 * The legal pages have to be reachable from every page, not just findable —
 * Razorpay's account review checks for exactly that, and a footer link is also
 * where a learner looks for the refund rules.
 */
const COLUMNS: Array<{ heading: string; links: Array<{ href: string; label: string }> }> = [
  {
    heading: "Sessions",
    links: [
      { href: "/discussions", label: "Group discussions" },
      { href: "/one-on-one", label: "1:1 sessions" },
      { href: "/pricing", label: "Pricing" },
    ],
  },
  {
    heading: "Shevaani",
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
      { href: "/refunds", label: "Refunds and cancellations" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-border/60 border-t py-12">
      <div className="container-page">
        <div className="grid gap-8 sm:grid-cols-3">
          {COLUMNS.map((column) => (
            <div key={column.heading} className="flex flex-col gap-3">
              <p className="eyebrow">{column.heading}</p>
              <ul className="flex flex-col gap-2 text-sm">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-border/60 text-muted-foreground mt-10 flex flex-col gap-2 border-t pt-6 text-sm sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Shevaani</p>
          <p>Group discussions run daily · 1:1 sessions 7am–7pm IST</p>
        </div>
      </div>
    </footer>
  );
}
