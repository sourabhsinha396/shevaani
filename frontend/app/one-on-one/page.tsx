"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, Clock, Info, Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { Facilitator, Slot } from "@/lib/types";
import { cn, formatDayLabel, formatTime } from "@/lib/utils";

/** Next 14 days as YYYY-MM-DD, which is what the slots endpoint expects.
 *  Built from local date parts, not toISOString() — that returns the UTC day,
 *  which is yesterday for anyone in IST before 05:30. */
function upcomingDates(count = 14) {
  return Array.from({ length: count }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() + i);
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${date.getFullYear()}-${month}-${day}`;
  });
}

export default function OneOnOnePage() {
  const router = useRouter();
  const { user, refresh } = useAuth();

  const dates = React.useMemo(() => upcomingDates(), []);
  const [facilitators, setFacilitators] = React.useState<Facilitator[]>([]);
  const [facilitatorId, setFacilitatorId] = React.useState("");
  const [date, setDate] = React.useState(dates[0]);
  const [duration, setDuration] = React.useState(60);
  const [slots, setSlots] = React.useState<Slot[]>([]);
  const [loadingSlots, setLoadingSlots] = React.useState(false);
  const [busySlot, setBusySlot] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<{ kind: "error" | "info"; text: string } | null>(
    null,
  );

  React.useEffect(() => {
    api
      .listFacilitators()
      .then((list) => {
        setFacilitators(list);
        if (list.length > 0) setFacilitatorId(list[0].id);
      })
      .catch((e: Error) => setMessage({ kind: "error", text: e.message }));
  }, []);

  React.useEffect(() => {
    if (!facilitatorId) return;
    let cancelled = false;
    setLoadingSlots(true);

    api
      .slots(facilitatorId, date, duration)
      .then((data) => !cancelled && setSlots(data))
      .catch((e: Error) => !cancelled && setMessage({ kind: "error", text: e.message }))
      .finally(() => !cancelled && setLoadingSlots(false));

    return () => {
      cancelled = true;
    };
  }, [facilitatorId, date, duration]);

  async function book(slot: Slot) {
    if (!user) {
      router.push("/login?next=/one-on-one");
      return;
    }
    setBusySlot(slot.starts_at);
    setMessage(null);
    try {
      await api.bookOneOnOne({
        facilitator_id: facilitatorId,
        starts_at: slot.starts_at,
        duration_minutes: duration,
      });
      setMessage({ kind: "info", text: "Booked. You'll find it under My sessions." });
      // The slot is gone now, and so is the hour either side of it.
      setSlots(await api.slots(facilitatorId, date, duration));
      await refresh();
    } catch (e) {
      setMessage({ kind: "error", text: (e as ApiError).message });
    } finally {
      setBusySlot(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <header>
        <h1 className="text-3xl tracking-tight sm:text-4xl">One-to-one sessions</h1>
        <p className="text-muted-foreground mt-2 max-w-lg text-pretty">
          The whole hour is yours. Pick a facilitator and a time that suits you.
        </p>
      </header>

      <Card className="bg-muted/30 mt-8">
        <CardContent className="text-muted-foreground flex items-start gap-3 text-sm">
          <Info className="mt-0.5 size-4 shrink-0" />
          <p>
            One-to-one sessions run between <strong className="text-foreground">7:00am and 7:00pm IST</strong>,
            and each booking keeps an hour clear either side — so a slot that looks
            free next to someone else's session won't appear here.
          </p>
        </CardContent>
      </Card>

      <div className="mt-8 grid gap-6 md:grid-cols-3">
        <Field label="Facilitator">
          <Select value={facilitatorId} onChange={(e) => setFacilitatorId(e.target.value)}>
            {facilitators.length === 0 && <option value="">No facilitators yet</option>}
            {facilitators.map((f) => (
              <option key={f.id} value={f.id}>
                {f.full_name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Date">
          <Select value={date} onChange={(e) => setDate(e.target.value)}>
            {dates.map((d) => (
              <option key={d} value={d}>
                {formatDayLabel(`${d}T09:00:00Z`, user?.timezone)}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Length">
          <Select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
            <option value={30}>30 minutes</option>
            <option value={60}>60 minutes</option>
          </Select>
        </Field>
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarClock className="size-4" />
            Available times
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loadingSlots ? (
            <div className="text-muted-foreground flex items-center justify-center gap-2 py-12 text-sm">
              <Loader2 className="size-4 animate-spin" /> Checking the calendar…
            </div>
          ) : slots.length === 0 ? (
            <p className="text-muted-foreground py-12 text-center text-sm">
              Nothing free on this day. Try another date.
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
              {slots.map((slot) => (
                <Button
                  key={slot.starts_at}
                  variant="outline"
                  className={cn("justify-center", busySlot === slot.starts_at && "opacity-60")}
                  disabled={busySlot !== null}
                  onClick={() => void book(slot)}
                >
                  {busySlot === slot.starts_at ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Clock className="size-3.5" />
                  )}
                  {formatTime(slot.starts_at, user?.timezone)}
                </Button>
              ))}
            </div>
          )}

          {message && (
            <p
              className={cn(
                "mt-4 text-sm",
                message.kind === "error" ? "text-destructive" : "text-[var(--success)]",
              )}
            >
              {message.text}
            </p>
          )}
        </CardContent>
      </Card>

      {user && (
        <p className="text-muted-foreground mt-4 text-sm">
          Times shown in <Badge variant="secondary">{user.timezone}</Badge>
        </p>
      )}
    </div>
  );
}
