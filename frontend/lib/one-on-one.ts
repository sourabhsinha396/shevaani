"use client";

/**
 * "Is one-to-one bookable at all?" — asked once per page load, shared.
 *
 * Two places need this and they need opposite defaults. The header must not
 * delete a working page from the nav because a request failed, so it treats
 * "don't know" as yes. The page itself must not tell somebody the service is
 * closed on the strength of a failed request, so it treats "don't know" as no.
 * Both fall out of returning the summary itself, with `null` meaning unknown,
 * rather than baking one of the two defaults into the hook.
 */

import * as React from "react";

import { api } from "@/lib/api";
import type { AvailabilitySummary } from "@/lib/types";

/* A module-level promise, not state on a provider: the answer is the same for
   every visitor and moves on the order of hours, so one request per page load
   is the right budget. Client-side navigations reuse it; a reload re-asks. */
let probe: Promise<AvailabilitySummary | null> | null = null;

function fetchSummary(): Promise<AvailabilitySummary | null> {
  probe ??= api.availabilitySummary().catch(() => null);
  return probe;
}

/** `null` while in flight, and also if the probe failed — see the note above. */
export function useOneOnOneAvailability(): AvailabilitySummary | null {
  const [summary, setSummary] = React.useState<AvailabilitySummary | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    fetchSummary().then((result) => {
      if (!cancelled) setSummary(result);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return summary;
}
