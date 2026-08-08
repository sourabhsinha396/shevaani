"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Coins, MessagesSquare } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { ThemeToggle } from "@/components/theme-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/discussions", label: "Group discussions" },
  { href: "/one-on-one", label: "1:1 sessions" },
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
  const { user, credits, signOut } = useAuth();
  const pathname = usePathname();

  return (
    <header className="bg-background/80 border-border/60 sticky top-0 z-50 border-b backdrop-blur-xl">
      <div className="container-page flex h-16 items-center gap-8">
        {/* Wordmark in the display serif — the only place the brand colour
            appears in the chrome, so the header stays quiet. */}
        <Link href="/" className="flex items-center gap-2.5">
          <span className="bg-brand text-brand-foreground grid size-7 place-items-center rounded-full">
            <MessagesSquare className="size-3.5" />
          </span>
          <span className="font-heading text-xl tracking-tight">Shevaani</span>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {NAV.map((item) => (
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

        <div className="ml-auto flex items-center gap-5">
          {user ? (
            <>
              <Badge variant="secondary" className="hidden gap-1.5 sm:inline-flex">
                <Coins className="size-3" />
                {credits} credits
              </Badge>
              {user.role === "superuser" && (
                <Link href="/admin" className={cn(navLink, "text-muted-foreground hidden sm:inline")}>
                  Admin
                </Link>
              )}
              {(user.role === "facilitator" || user.role === "superuser") && (
                <Link
                  href="/facilitator"
                  className={cn(navLink, "text-muted-foreground hidden sm:inline")}
                >
                  Calendar
                </Link>
              )}
              <Link href="/dashboard" className={cn(navLink, "text-foreground")}>
                My sessions
              </Link>
              <ThemeToggle />
              <button
                type="button"
                onClick={() => void signOut()}
                className={cn(navLink, "text-muted-foreground cursor-pointer")}
              >
                Sign out
              </button>
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
