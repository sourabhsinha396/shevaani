"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessagesSquare, Ticket } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { useSiteConfig } from "@/components/site-config-provider";
import { ThemeToggle } from "@/components/theme-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { UserMenu } from "@/components/user-menu";
import { useOneOnOneAvailability } from "@/lib/one-on-one";
import { sessionBalanceLabel } from "@/lib/pricing";
import type { SiteConfig } from "@/lib/types";
import { cn } from "@/lib/utils";

/* `flag` gates an item on a site setting. Adding the next switched-off-able
   section is a line here and a line in the footer's `COLUMNS` — no new
   filtering logic. 1:1 is the one item that also has a runtime condition; see
   below for why the two are not the same question. */
const NAV: { href: string; label: string; flag?: keyof SiteConfig }[] = [
  { href: "/discussions", label: "Group discussions" },
  { href: "/one-on-one", label: "1:1 sessions", flag: "one_on_one_enabled" },
  { href: "/pricing", label: "Pricing" },
];

/* Navigation is text, not controls. Pills and ghost buttons force every label
   down to `text-xs` to keep the chrome from looking chunky, and small grey text
   inside a small grey box is the least readable thing in the header. Plain
   links at body size read cleanly, and leaving the header free of button fills
   means the one brand pill is unmistakably *the* action. */
const navLink =
  "text-[0.9375rem] leading-none transition-colors hover:text-foreground";

export function SiteHeader() {
  const { user, credits } = useAuth();
  const pathname = usePathname();

  // Two different questions about 1:1, and they need different defaults.
  //
  // The flag is a decision — "are we selling this at all?" — and it arrives
  // with the server render, so it is never unknown and never moves.
  //
  // Availability is a fact about a calendar, probed from the browser. Unknown
  // counts as open, so the common case — there is availability — never moves.
  // Only a definitive "no" takes the link away, at the cost of one shift on the
  // rare load where 1:1 is genuinely closed. The reverse default would flicker
  // on every visit.
  const config = useSiteConfig();
  const availability = useOneOnOneAvailability();
  const oneOnOneHasSlots = availability === null || availability.has_slots;

  // Hidden, not disabled, and the route stays live either way: `/one-on-one`
  // explains itself to anyone arriving from a bookmark, an old email or a
  // search result.
  const nav = NAV.filter(
    (item) =>
      (!item.flag || config[item.flag]) &&
      (item.href !== "/one-on-one" || oneOnOneHasSlots),
  );

  return (
    <header className="bg-background/80 border-border/60 sticky top-0 z-50 border-b backdrop-blur-xl">
      {/* Tighter below `md`: once the nav collapses, the wordmark and the
          account controls are the only things left, and an 8-unit gap between
          them overflowed a 375px viewport by a hair. */}
      <div className="container-page flex h-16 items-center gap-4 md:gap-8">
        {/* Wordmark in the display serif — the only place the brand colour
            appears in the chrome, so the header stays quiet. */}
        <Link href="/" className="flex items-center gap-2.5">
          <span className="bg-brand text-brand-foreground grid size-7 place-items-center rounded-full">
            <MessagesSquare className="size-3.5" />
          </span>
          <span className="font-heading text-xl tracking-tight">Shevaani</span>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname.startsWith(item.href) ? "page" : undefined}
              className={cn(
                navLink,
                // The current section is marked by ink weight alone — an
                // underline here would collide with the hover affordance.
                pathname.startsWith(item.href)
                  ? "text-foreground"
                  : "text-muted-foreground",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          {user ? (
            <>
              {/* The one personal number that earns a permanent slot: a balance
                  you only discover at checkout is a balance discovered too
                  late. Everything else lives in the menu.

                  `outline`, not `secondary`: the filled variant paints its text
                  in `secondary-foreground`, which is the same near-white the
                  nav uses to mark the current section — so a balance that is
                  merely present read as the page you were on. Outline states it
                  at the weight of an inactive link and lets the border carry
                  the shape. */}
              <Link href="/checkout" className="hidden sm:inline-flex">
                <Badge
                  variant="outline"
                  className="hover:text-foreground gap-1.5 transition-colors"
                >
                  <Ticket className="size-3" />
                  {sessionBalanceLabel(credits)} left
                </Badge>
              </Link>
              <ThemeToggle />
              {/* Sits with the account controls rather than in the nav proper:
                  it is the one link that only exists for a signed-in learner,
                  so grouping it beside the avatar keeps the left-hand nav the
                  same three items whether or not anybody is signed in.

                  Still a nav link, not a control — same active rule as the
                  three on the left. It used to be pinned to `text-foreground`
                  and so read as the current section on every page. */}
              <Link
                href="/dashboard"
                aria-current={pathname.startsWith("/dashboard") ? "page" : undefined}
                className={cn(
                  navLink,
                  // Never hidden on small screens: the left-hand nav already
                  // collapses below `md` and this is not in the user menu, so
                  // hiding it here would leave no way to reach it on a phone.
                  pathname.startsWith("/dashboard")
                    ? "text-foreground"
                    : "text-muted-foreground",
                )}
              >
                My sessions
              </Link>
              <UserMenu />
            </>
          ) : (
            <>
              <ThemeToggle />
              <Link href="/login" className={cn(navLink, "text-foreground")}>
                Sign in
              </Link>
              <Button asChild variant="brand" size="sm" className="h-9 px-4 text-sm">
                <Link href="/register">Get started</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
