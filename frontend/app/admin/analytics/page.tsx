"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2, RefreshCw } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { formatMinor } from "@/lib/money";
import type { AdminAnalytics, AnalyticsDay } from "@/lib/types";

/* One point per business-timezone day; each chart is a single series, so the
   card title is the legend and the only colour is the brand ink. */

const RANGES = [
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
  { days: 180, label: "Last 6 months" },
  { days: 365, label: "Last year" },
];

function shortDay(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" }).format(
    new Date(`${iso}T00:00:00`),
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardContent className="py-5">
        <p className="text-2xl tabular-nums">{value}</p>
        <p className="text-muted-foreground mt-1 text-sm">{label}</p>
        {hint && <p className="text-muted-foreground mt-0.5 text-xs">{hint}</p>}
      </CardContent>
    </Card>
  );
}

/**
 * A single-series daily bar chart in plain divs.
 *
 * Small enough to not warrant a chart library: one measure, one hue, hover
 * tooltip per bar (CSS-only, so it works without any listener wiring), and the
 * peak value annotated so the y-scale is readable without an axis.
 */
function DailyBars({ series, pick }: { series: AnalyticsDay[]; pick: (d: AnalyticsDay) => number }) {
  const max = Math.max(1, ...series.map(pick));
  const total = series.reduce((sum, d) => sum + pick(d), 0);

  return (
    <div>
      <p className="text-muted-foreground mb-1 text-xs tabular-nums">
        {total} total · peak {max}
      </p>
      <div className="flex h-28 items-end gap-px" role="img" aria-label={`${total} over ${series.length} days, peaking at ${max}`}>
        {series.map((day) => {
          const value = pick(day);
          return (
            <div key={day.date} className="group relative flex h-full min-w-0 flex-1 items-end">
              {/* Full-height hit target, so quiet days are still hoverable. */}
              <div
                className="bg-brand-ink w-full rounded-t-[3px]"
                style={{ height: `${Math.max(value > 0 ? 4 : 1, (value / max) * 100)}%`, opacity: value > 0 ? 1 : 0.25 }}
              />
              <span className="bg-popover text-popover-foreground border-border/60 pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 rounded-md border px-2 py-1 text-xs whitespace-nowrap shadow-sm group-hover:block">
                {shortDay(day.date)} · {value}
              </span>
            </div>
          );
        })}
      </div>
      <div className="text-muted-foreground mt-1 flex justify-between text-xs">
        <span>{shortDay(series[0].date)}</span>
        <span>{shortDay(series[series.length - 1].date)}</span>
      </div>
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const [days, setDays] = React.useState(30);
  const [data, setData] = React.useState<AdminAnalytics | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.adminAnalytics(days));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [days]);

  React.useEffect(() => {
    void load();
  }, [load]);

  if (loading && !data) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Select
          value={String(days)}
          onChange={(e) => setDays(Number(e.target.value))}
          className="w-44"
        >
          {RANGES.map((range) => (
            <option key={range.days} value={range.days}>
              {range.label}
            </option>
          ))}
        </Select>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RefreshCw className="size-4" /> Refresh
        </Button>
      </div>

      {error && <p className="text-destructive mt-4 text-sm">{error}</p>}

      {data && (
        <div className="mt-6 flex flex-col gap-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="learners" value={String(data.totals.learners)} hint={`${data.totals.new_learners} new in this window`} />
            <Stat
              label="bookings"
              value={String(data.totals.bookings_confirmed)}
              hint={`${data.totals.bookings_cancelled} cancelled`}
            />
            <Stat
              label="payments"
              value={String(data.totals.payments_paid)}
              hint={`${data.totals.credits_purchased} credits bought · ${data.totals.credits_spent} spent`}
            />
            <Stat
              label="referrals"
              value={`${data.totals.referrals_enrolled}/${data.totals.referrals_joined}`}
              hint={`enrolled/joined · ${data.totals.referral_credits_awarded} credits awarded`}
            />
          </div>

          {/* Small multiples, not one grouped chart: three measures on three
              different scales have no honest shared axis. */}
          <div className="grid gap-3 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Signups per day</CardTitle>
              </CardHeader>
              <CardContent>
                <DailyBars series={data.series} pick={(d) => d.signups} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Bookings per day</CardTitle>
              </CardHeader>
              <CardContent>
                <DailyBars series={data.series} pick={(d) => d.bookings} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Payments per day</CardTitle>
              </CardHeader>
              <CardContent>
                <DailyBars series={data.series} pick={(d) => d.payments} />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Revenue</CardTitle>
              </CardHeader>
              <CardContent>
                {data.revenue.length === 0 ? (
                  <p className="text-muted-foreground py-6 text-center text-sm">
                    No settled payments in this window.
                  </p>
                ) : (
                  <table className="w-full text-sm">
                    <tbody className="divide-border/60 divide-y">
                      {/* One row per currency, never a combined total - ₹ plus €
                          is not a number. */}
                      {data.revenue.map((row) => (
                        <tr key={row.currency}>
                          <td className="py-2">{row.currency}</td>
                          <td className="text-muted-foreground py-2">
                            {row.payments} payment{row.payments === 1 ? "" : "s"}
                          </td>
                          <td className="py-2 text-right tabular-nums">
                            {formatMinor(row.amount_minor, row.currency)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Top referrers (all time)</CardTitle>
              </CardHeader>
              <CardContent>
                {data.top_referrers.length === 0 ? (
                  <p className="text-muted-foreground py-6 text-center text-sm">
                    Nobody has referred anyone yet.
                  </p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-muted-foreground text-left text-xs">
                        <th className="pb-2 font-normal">Learner</th>
                        <th className="pb-2 text-right font-normal">Joined</th>
                        <th className="pb-2 text-right font-normal">Enrolled</th>
                        <th className="pb-2 text-right font-normal">Credits</th>
                      </tr>
                    </thead>
                    <tbody className="divide-border/60 divide-y">
                      {data.top_referrers.map((referrer) => (
                        <tr key={referrer.user_id}>
                          <td className="py-2">
                            <Link
                              href={`/admin/learners/${referrer.user_id}`}
                              className="hover:underline underline-offset-4"
                            >
                              {referrer.full_name}
                            </Link>
                            <span className="text-muted-foreground block text-xs">
                              {referrer.email}
                            </span>
                          </td>
                          <td className="py-2 text-right tabular-nums">{referrer.joined}</td>
                          <td className="py-2 text-right tabular-nums">{referrer.enrolled}</td>
                          <td className="py-2 text-right tabular-nums">
                            {referrer.credits_earned}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
