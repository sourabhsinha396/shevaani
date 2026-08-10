"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Globe, Loader2 } from "lucide-react";

import { BookingCalendar, dateKey, monthOf } from "@/components/booking-calendar";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useOneOnOneAvailability } from "@/lib/one-on-one";
import { ONE_ON_ONE_DURATIONS } from "@/lib/pending-booking";
import { CREDITS_PER_SESSION } from "@/lib/pricing";
import {
  BOOKING_TIMEZONE,
  BOOKING_ZONES,
  detectBookingZone,
  writeTimezoneCookie,
  zonedDateKey,
  zoneAbbreviation,
} from "@/lib/timezones";
import { cn } from "@/lib/utils";

const DURATIONS = ONE_ON_ONE_DURATIONS;

/** Shifts a `YYYY-MM-DD` key by whole days without ever touching local time. */
function shiftKey(key: string, days: number): string {
  const [year, month, day] = key.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day + days));
  return dateKey(shifted.getUTCFullYear(), shifted.getUTCMonth(), shifted.getUTCDate());
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
}

function formatSlot(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone,
  }).format(new Date(iso));
}

function formatDateKey(key: string): string {
  const { year, month } = monthOf(key);
  const day = Number(key.split("-")[2]);
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month, day)));
}

/**
 * Pick a date, pick a time. No instructor anywhere on the page.
 *
 * The times come from `/instructors/availability`, which is the union of what
 * everyone on the team can take; who teaches the hour is decided by the server
 * when the booking is made. That is the whole reason this page can look like a
 * calendar instead of a form — there is only one question on it.
 *
 * **Slots are regrouped by the reader's zone**, not served that way. The API
 * keys days by IST because that is the zone the booking window is defined in,
 * and 07:00 IST is the previous evening in New York. Trusting the server's date
 * keys would file Tuesday's late slots under Wednesday for half the world.
 */
export default function OneOnOnePage() {
  const router = useRouter();
  const { user } = useAuth();

  // Rendered in IST until the browser has been asked, so the server and the
  // first client render agree. Nothing time-shaped is on screen before the
  // availability request lands anyway, so the correction is never seen.
  const [timeZone, setTimeZone] = React.useState(BOOKING_TIMEZONE);
  React.useEffect(() => setTimeZone(detectBookingZone()), []);

  const [duration, setDuration] = React.useState<number>(DURATIONS[0]);
  const [today, setToday] = React.useState(() => zonedDateKey(new Date(), BOOKING_TIMEZONE));
  const [view, setView] = React.useState(() =>
    monthOf(zonedDateKey(new Date(), BOOKING_TIMEZONE)),
  );

  const [slotsByDate, setSlotsByDate] = React.useState<Map<string, string[]>>(new Map());
  const [selectedDate, setSelectedDate] = React.useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setToday(zonedDateKey(new Date(), timeZone));
  }, [timeZone]);

  // Detection can land the reader a day behind IST, and on the 1st that is a
  // whole month behind. Snap forward, never back — otherwise browsing to
  // September and changing zone would yank the calendar home.
  React.useEffect(() => {
    const current = monthOf(today);
    setView((shown) =>
      shown.year * 12 + shown.month < current.year * 12 + current.month ? current : shown,
    );
  }, [today]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    // A day either side of the month: an IST evening slot on the 31st is the
    // 1st in Sydney, and an IST morning slot on the 1st is the previous month
    // in New York. The server clamps `from` to today on its own.
    const first = dateKey(view.year, view.month, 1);
    api
      .availability({
        from: shiftKey(first, -1),
        days: daysInMonth(view.year, view.month) + 2,
        duration_minutes: duration,
      })
      .then((data) => {
        if (cancelled) return;
        const grouped = new Map<string, string[]>();
        for (const day of data.days) {
          for (const slot of day.slots) {
            const key = zonedDateKey(slot, timeZone);
            const bucket = grouped.get(key);
            if (bucket) bucket.push(slot);
            else grouped.set(key, [slot]);
          }
        }
        for (const list of grouped.values()) list.sort();
        setSlotsByDate(grouped);
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [view.year, view.month, duration, timeZone]);

  // Land on the first bookable date rather than on an empty right-hand pane.
  React.useEffect(() => {
    if (loading) return;
    setSelectedDate((current) => {
      if (current && slotsByDate.has(current)) return current;
      const inView = [...slotsByDate.keys()]
        .filter((key) => monthOf(key).year === view.year && monthOf(key).month === view.month)
        .sort();
      return inView[0] ?? null;
    });
  }, [loading, slotsByDate, view.year, view.month]);

  React.useEffect(() => setSelectedSlot(null), [selectedDate, duration, timeZone]);

  const available = React.useMemo(() => new Set(slotsByDate.keys()), [slotsByDate]);
  const slots = selectedDate ? (slotsByDate.get(selectedDate) ?? []) : [];

  // The month request can only say "nothing in *this* month". Distinguishing
  // that from "nothing at all" needs the wider horizon, and a probe that failed
  // (`null`) must not be read as closed — hence the explicit `has_slots` test.
  const summary = useOneOnOneAvailability();
  const closedOutright = summary !== null && !summary.has_slots;

  function confirm(slot: string) {
    // Checkout is where a session is paid for and confirmed, so the choice is
    // carried there in the URL rather than booked from under this page.
    const target = `/checkout?slot=${encodeURIComponent(slot)}&duration=${duration}`;
    router.push(user ? target : `/login?next=${encodeURIComponent(target)}`);
  }

  return (
    // Narrower than the rest of the site on purpose: with short date cells a
    // full-width grid spreads seven numbers across 700px and stops reading as a
    // calendar. This is roughly the width the two panes actually want.
    <div className="mx-auto max-w-3xl px-4 py-12">
      <header>
        <h1 className="text-3xl tracking-tight sm:text-4xl">One-to-one sessions</h1>
        <p className="text-muted-foreground mt-2 max-w-lg text-pretty">
          Pick a date and a time that suits you.
        </p>
      </header>

      <Card className="mt-8 overflow-hidden py-0">
        <CardContent className="grid gap-0 p-0 md:grid-cols-[1fr_17rem]">
          <div className="p-6">
            <div className="flex flex-wrap items-center gap-1.5 pb-6">
              {/* With nothing to choose between, the row states the length
                  rather than offering it — a toggle that cannot toggle still
                  takes a tab stop and announces itself as pressable. */}
              {DURATIONS.length === 1 ? (
                <span className="text-muted-foreground rounded-full border border-border/60 px-3 py-1 text-sm">
                  {DURATIONS[0]} min
                </span>
              ) : (
                DURATIONS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    aria-pressed={duration === option}
                    onClick={() => setDuration(option)}
                    className={cn(
                      "cursor-pointer rounded-full border px-3 py-1 text-sm transition-colors",
                      duration === option
                        ? "border-brand-ink bg-brand text-brand-foreground"
                        : "border-border/60 text-muted-foreground hover:border-border",
                    )}
                  >
                    {option} min
                  </button>
                ))
              )}
            </div>

            <BookingCalendar
              year={view.year}
              month={view.month}
              onMonthChange={(year, month) => setView({ year, month })}
              selected={selectedDate}
              onSelect={setSelectedDate}
              available={available}
              today={today}
              loading={loading}
            />

            <div className="border-border/60 mt-6 flex items-center gap-2 border-t pt-4">
              <Globe className="text-muted-foreground size-4 shrink-0" />
              <Select
                aria-label="Timezone"
                value={timeZone}
                onChange={(e) => {
                  setTimeZone(e.target.value);
                  writeTimezoneCookie(e.target.value);
                }}
                className="h-9 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
              >
                {BOOKING_ZONES.map((zone) => (
                  <option key={zone.id} value={zone.id}>
                    {zone.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="border-border/60 bg-surface-subtle flex flex-col border-t md:border-t-0 md:border-l">
            <div className="border-border/60 flex items-baseline justify-between gap-2 border-b px-5 py-4">
              <p className="text-sm font-medium">
                {selectedDate ? formatDateKey(selectedDate) : "Pick a date"}
              </p>
              <span className="text-muted-foreground text-xs">
                {zoneAbbreviation(timeZone)}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-3 md:max-h-[24rem]">
              {loading ? (
                <div className="text-muted-foreground flex items-center justify-center gap-2 py-16 text-sm">
                  <Loader2 className="size-4 animate-spin" /> Loading times…
                </div>
              ) : error ? (
                <p className="text-destructive px-2 py-16 text-center text-sm text-pretty">
                  {error}
                </p>
              ) : slots.length === 0 ? (
                <div className="text-muted-foreground px-2 py-16 text-center text-sm text-pretty">
                  {available.size > 0 ? (
                    <p>Nothing free on this day. Pick another from the calendar.</p>
                  ) : closedOutright ? (
                    // "Try the next one" is a lie when there is no next one.
                    // Say so, and offer the thing that *is* bookable.
                    <>
                      <p>One-to-one sessions aren&apos;t open for booking right now.</p>
                      <p className="mt-3">
                        <Link
                          href="/discussions"
                          className="text-foreground underline underline-offset-4"
                        >
                          Browse group discussions
                        </Link>{" "}
                        instead — they come out of the same balance.
                      </p>
                    </>
                  ) : (
                    <p>Nothing open this month. Try the next one.</p>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {slots.map((slot) => {
                    const chosen = slot === selectedSlot;
                    return (
                      <div key={slot} className="flex gap-2">
                        <button
                          type="button"
                          aria-pressed={chosen}
                          onClick={() => setSelectedSlot(chosen ? null : slot)}
                          className={cn(
                            "flex-1 cursor-pointer rounded-lg border py-2.5 text-center text-sm font-medium tabular-nums transition-colors",
                            chosen
                              ? "border-brand-ink bg-brand text-brand-foreground"
                              : "border-border/60 bg-background hover:border-brand-ink/50",
                          )}
                        >
                          {formatSlot(slot, timeZone)}
                        </button>
                        {chosen && (
                          <Button
                            variant="brand"
                            className="flex-1"
                            onClick={() => confirm(slot)}
                          >
                            Continue
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <p className="text-muted-foreground mt-4 text-sm text-pretty">
        {CREDITS_PER_SESSION} credits book one session, the same as a group
        discussion. Cancel more than 12 hours before it starts and they return to
        your balance.
      </p>
    </div>
  );
}
