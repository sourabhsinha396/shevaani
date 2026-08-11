"use client";

import * as React from "react";

import {
  type Currency,
  detectCurrency,
  writeCurrencyCookie,
} from "@/lib/currency";

/**
 * One currency for the whole app, chosen once per visit.
 *
 * The state lives in a module-level store read through `useSyncExternalStore`
 * rather than in `useState` inside the provider, for two reasons:
 *
 * - `getServerSnapshot` can return USD unconditionally, so the server renders a
 *   dollar price and the browser swaps in the detected one after hydration.
 *   Doing the detection in an effect instead would work, but every consumer
 *   would flash the wrong price for a frame first.
 * - Detection runs once for the whole tree, not once per component that asks.
 */

let current: Currency | null = null;
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): Currency {
  // Lazily, and cached: `useSyncExternalStore` calls this on every render and
  // re-detecting each time would both cost and - because it must return a
  // stable value - risk an infinite render loop if it ever disagreed with itself.
  if (current === null) current = detectCurrency();
  return current;
}

function getServerSnapshot(): Currency {
  return "USD";
}

function setStoredCurrency(next: Currency): void {
  current = next;
  // Only an explicit choice is persisted. Detection is left free to re-run for
  // anyone who never touched the switcher.
  writeCurrencyCookie(next);
  for (const listener of listeners) listener();
}

const CurrencyContext = React.createContext<{
  currency: Currency;
  setCurrency: (next: Currency) => void;
}>({ currency: "USD", setCurrency: setStoredCurrency });

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const currency = React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const value = React.useMemo(
    () => ({ currency, setCurrency: setStoredCurrency }),
    [currency],
  );
  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency() {
  return React.useContext(CurrencyContext);
}
