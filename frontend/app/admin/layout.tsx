"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";

/**
 * One shell, two roles.
 *
 * Superusers run the platform; instructors see their own work and nothing else.
 * The tabs below differ by role, but that is presentation only — every endpoint
 * behind them re-checks the caller, and the instructor endpoints derive the
 * instructor from the session rather than from anything the client sends. Hiding
 * a tab is not a security boundary and is not treated as one.
 */
const SUPERUSER_TABS = [
  { href: "/admin", label: "Sessions" },
  { href: "/admin/new", label: "New discussion" },
  { href: "/admin/learners", label: "Learners" },
  { href: "/admin/instructors", label: "Instructors" },
  { href: "/admin/messages", label: "Messages" },
  // Last, and superuser-only: it is the tab that changes what the public site
  // offers, which is not a thing an instructor gets to do.
  { href: "/admin/settings", label: "Settings" },
];

const INSTRUCTOR_TABS = [
  { href: "/admin/my-sessions", label: "My sessions" },
  { href: "/instructor", label: "My calendar" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const isSuperuser = user?.role === "superuser";
  const isInstructor = user?.role === "instructor";

  React.useEffect(() => {
    if (loading) return;
    if (!user || (!isSuperuser && !isInstructor)) {
      router.replace("/");
      return;
    }
    // An instructor landing on a superuser page goes to their own list rather
    // than seeing a 403 they can do nothing about.
    if (isInstructor && !pathname.startsWith("/admin/my-sessions")) {
      router.replace("/admin/my-sessions");
    }
  }, [loading, user, isSuperuser, isInstructor, pathname, router]);

  if (loading || !user || (!isSuperuser && !isInstructor)) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Checking access…
      </div>
    );
  }

  const tabs = isSuperuser ? SUPERUSER_TABS : INSTRUCTOR_TABS;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      {/* This shell is a client component, so it cannot export `metadata`.
          React hoists a bare <meta> into <head>, which gets the same result:
          robots.txt asks crawlers not to fetch /admin, and this tells anything
          that arrived anyway not to index it. */}
      <meta name="robots" content="noindex, nofollow" />
      <h1 className="text-2xl tracking-tight">{isSuperuser ? "Admin" : "Teaching"}</h1>
      <nav className="mt-4 flex flex-wrap gap-1 border-b">
        {tabs.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
              pathname === tab.href
                ? "border-brand-ink text-foreground"
                : "text-muted-foreground hover:text-foreground border-transparent",
            )}
          >
            {tab.label}
          </Link>
        ))}
      </nav>
      <div className="mt-8">{children}</div>
    </div>
  );
}
