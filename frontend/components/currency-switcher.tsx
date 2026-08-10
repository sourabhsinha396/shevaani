"use client";

import * as React from "react";

import { useCurrency } from "@/components/currency-provider";
import { CURRENCY_LABELS, SUPPORTED_CURRENCIES, type Currency } from "@/lib/currency";
import { cn } from "@/lib/utils";

/**
 * The one-click escape from a wrong guess.
 *
 * Detection is right for most visitors and wrong for travellers, expats and
 * anyone on a VPN — which is why it is a default and not a decision. Picking
 * here writes the cookie, so the choice survives the next visit.
 */
export function CurrencySwitcher({ className }: { className?: string }) {
  const { currency, setCurrency } = useCurrency();

  return (
    <label className={cn("inline-flex items-center gap-2 text-sm", className)}>
      <span className="sr-only">Currency</span>
      <select
        value={currency}
        onChange={(event) => setCurrency(event.target.value as Currency)}
        className={cn(
          "border-border/60 bg-background cursor-pointer rounded-md border px-2 py-1",
          "text-muted-foreground hover:text-foreground focus-visible:ring-ring",
          "transition-colors focus-visible:ring-2 focus-visible:outline-none",
        )}
      >
        {SUPPORTED_CURRENCIES.map((code) => (
          <option key={code} value={code}>
            {CURRENCY_LABELS[code]}
          </option>
        ))}
      </select>
    </label>
  );
}
