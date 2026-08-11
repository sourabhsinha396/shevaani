"use client";

import Link from "next/link";
import {
  CalendarDays,
  ChevronDown,
  Gift,
  LogOut,
  Settings,
  Shield,
  Ticket,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { sessionsFrom } from "@/lib/pricing";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/** The given name alone - "Priya Sharma" reads as Priya. Falls back to the part
 *  of the email before the @ so a profile saved without a name still names the
 *  person rather than showing an empty control. */
function firstName(fullName: string, email: string): string {
  const given = fullName.trim().split(/\s+/).filter(Boolean)[0];
  return given ?? email.split("@")[0] ?? "Account";
}

/**
 * Everything about *your* account, behind one control.
 *
 * The header used to spell out My sessions, Account, Admin, Teaching, Calendar
 * and Sign out as six separate links, which crowded out the three that are
 * actually navigation - discussions, 1:1 and pricing. Personal destinations are
 * not competing for attention with those; they are things you go looking for,
 * which is exactly what a menu is for.
 *
 * The balance stays outside on a badge. It is a number you want to notice
 * without asking for it, and burying it is how someone discovers they had none
 * only at checkout.
 */
export function UserMenu() {
  const { user, credits, signOut } = useAuth();
  if (!user) return null;

  const isStaff = user.role === "instructor" || user.role === "superuser";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          // The name is the label, so `aria-label` would only override it with
          // something less specific. The chevron is decorative and hidden.
          //
          // Outlined rather than bare text: name and chevron sitting loose in
          // the header read as two unrelated things next to each other. The
          // border draws the boundary that says they are one control, and it
          // matches the credits pill beside it - `outline` is transparent, so
          // it stays as quiet as the nav links while still being a *control*.
          className={cn(
            "group text-muted-foreground h-9 cursor-pointer gap-1.5 pr-2.5 text-sm font-normal",
            // Held open: the menu is up, so the trigger should look pressed
            // rather than snapping back to resting grey behind its own panel.
            "data-[state=open]:bg-muted data-[state=open]:text-foreground",
          )}
        >
          {/* Capped so an unusually long given name cannot push the nav around;
              the full name is in the menu header a click away. */}
          <span className="max-w-28 truncate">
            {firstName(user.full_name, user.email)}
          </span>
          <ChevronDown
            aria-hidden
            className="transition-transform duration-200 group-data-[state=open]:rotate-180"
          />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="flex flex-col gap-0.5 pb-2">
          <span className="truncate">{user.full_name}</span>
          <span className="text-muted-foreground truncate text-xs font-normal">
            {user.email}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {/* No "My sessions" here - it is a destination, so it stays in the nav
            proper rather than being duplicated behind a menu. */}
        <DropdownMenuItem asChild>
          <Link href="/checkout">
            <Ticket />
            Buy sessions
            {/* The badge is hidden on small screens, so this is where the
                balance is legible on a phone. */}
            <span className="text-muted-foreground ml-auto text-xs tabular-nums">
              {sessionsFrom(credits)}
            </span>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/referrals">
            <Gift />
            Refer a friend
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/account">
            <Settings />
            Account settings
          </Link>
        </DropdownMenuItem>

        {isStaff && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              {/* Both roles land on /admin; the shell decides what they see
                  there, and every endpoint behind it re-checks the role. */}
              <Link href="/admin">
                <Shield />
                {user.role === "superuser" ? "Admin" : "Teaching"}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/instructor">
                <CalendarDays />
                Calendar
              </Link>
            </DropdownMenuItem>
          </>
        )}

        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void signOut()}>
          <LogOut />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
