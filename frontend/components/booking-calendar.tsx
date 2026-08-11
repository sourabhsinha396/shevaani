"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * A month grid whose cells are calendar dates and nothing else.
 *
 * Everything here works on `YYYY-MM-DD` strings built with `Date.UTC`, never on
 * a local `Date`. A cell is a *civil date* - "the 11th of August" - and the
 * moment you construct one as `new Date(2026, 7, 11)` it becomes an instant in
 * the browser's zone, which is the wrong zone for a calendar the reader has just
 * told us to draw in Sydney. The parent decides which dates are bookable; this
 * only draws them.
 */

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const pad = (value: number) => String(value).padStart(2, "0");

/** `month` is 0-based, like `Date`. */
export function dateKey(year: number, month: number, day: number): string {
  return `${year}-${pad(month + 1)}-${pad(day)}`;
}

export function monthOf(key: string): { year: number; month: number } {
  const [year, month] = key.split("-").map(Number);
  return { year, month: month - 1 };
}

export function monthLabel(year: number, month: number): string {
  return new Intl.DateTimeFormat("en-GB", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month, 1)));
}

/** Monday-first offset of the 1st, then every day of the month. */
function monthGrid(year: number, month: number): Array<number | null> {
  const firstWeekday = new Date(Date.UTC(year, month, 1)).getUTCDay();
  const leading = (firstWeekday + 6) % 7;
  const dayCount = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();

  return [
    ...Array.from({ length: leading }, () => null),
    ...Array.from({ length: dayCount }, (_, i) => i + 1),
  ];
}

export function BookingCalendar({
  year,
  month,
  onMonthChange,
  selected,
  onSelect,
  available,
  today,
  loading = false,
}: {
  year: number;
  /** 0-based. */
  month: number;
  onMonthChange: (year: number, month: number) => void;
  selected: string | null;
  onSelect: (key: string) => void;
  /** The dates with at least one open slot, as `YYYY-MM-DD` in the reader's zone. */
  available: Set<string>;
  /** Today's date in the reader's zone - not the browser's. */
  today: string;
  loading?: boolean;
}) {
  const cells = React.useMemo(() => monthGrid(year, month), [year, month]);
  // String comparison is date comparison for `YYYY-MM-DD`, which is the whole
  // reason the keys are shaped this way.
  const atFirstMonth = dateKey(year, month, 1) <= today;

  const step = (delta: number) => {
    const next = new Date(Date.UTC(year, month + delta, 1));
    onMonthChange(next.getUTCFullYear(), next.getUTCMonth());
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="font-medium">{monthLabel(year, month)}</p>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Previous month"
            disabled={atFirstMonth}
            onClick={() => step(-1)}
            className="hover:bg-muted grid size-8 cursor-pointer place-items-center rounded-md transition-colors disabled:pointer-events-none disabled:opacity-30"
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            type="button"
            aria-label="Next month"
            onClick={() => step(1)}
            className="hover:bg-muted grid size-8 cursor-pointer place-items-center rounded-md transition-colors"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>

      <div className="text-muted-foreground mt-4 grid grid-cols-7 gap-1 text-center text-xs">
        {WEEKDAYS.map((day) => (
          <div key={day} className="py-1 font-medium">
            {day.charAt(0)}
            <span className="sr-only">{day}</span>
          </div>
        ))}
      </div>

      <div className={cn("mt-1 grid grid-cols-7 gap-1", loading && "animate-pulse opacity-60")}>
        {cells.map((day, index) => {
          if (day === null) return <div key={`pad-${index}`} />;

          const key = dateKey(year, month, day);
          const isSelected = key === selected;
          const isToday = key === today;
          const isOpen = available.has(key);

          return (
            <button
              key={key}
              type="button"
              disabled={!isOpen}
              aria-pressed={isSelected}
              aria-label={key}
              onClick={() => onSelect(key)}
              className={cn(
                // A fixed height, not `aspect-square`: the pane is wide, and a
                // square cell in it is 90px of mostly empty box. 40px keeps the
                // tap target honest on a phone without the grid dominating.
                "relative grid h-10 cursor-pointer place-items-center rounded-lg text-sm tabular-nums transition-colors",
                isSelected
                  ? "bg-brand text-brand-foreground font-semibold"
                  : isOpen
                    ? "bg-muted/60 hover:bg-muted font-medium"
                    : // Not disabled-looking so much as quiet: a month is mostly
                      // unbookable and a grid of greyed-out buttons reads as broken.
                      "text-muted-foreground/40 cursor-default",
              )}
            >
              {day}
              {isToday && !isSelected && (
                <span className="bg-foreground/50 absolute bottom-1 size-1 rounded-full" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
