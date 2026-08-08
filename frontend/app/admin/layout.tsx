"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/admin", label: "Sessions" },
  { href: "/admin/new", label: "New discussion" },
  { href: "/admin/facilitators", label: "Facilitators" },
];

/**
 * Client-side gate for UX only. Every admin endpoint re-checks the role on the
 * server — this just avoids rendering a screen the user can't use.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  React.useEffect(() => {
    if (!loading && (!user || user.role !== "superuser")) router.replace("/");
  }, [loading, user, router]);

  if (loading || !user || user.role !== "superuser") {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-32">
        <Loader2 className="size-4 animate-spin" /> Checking access…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl tracking-tight">Admin</h1>
      <nav className="mt-4 flex gap-1 border-b">
        {TABS.map((tab) => (
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
