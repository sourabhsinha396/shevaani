"use client";

import * as React from "react";

import { api } from "@/lib/api";
import type { CreditPack } from "@/lib/types";

/**
 * The price list, fetched once per mount.
 *
 * Takes no currency. Every pack arrives carrying prices for every currency we
 * sell in, so switching is a re-render - flipping the switcher must not put a
 * network round trip between the click and the new number.
 */
export function usePacks() {
  const [packs, setPacks] = React.useState<CreditPack[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    // Guarded because a fast unmount would otherwise set state on a gone
    // component - the pricing page is reachable from the header on every route.
    let cancelled = false;
    api
      .creditPacks()
      .then((list) => {
        if (!cancelled) setPacks(list);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { packs, loading: packs === null && error === null, error };
}
