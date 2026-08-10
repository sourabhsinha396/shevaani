"use client";

import Link from "next/link";
import { AlertTriangle, Loader2 } from "lucide-react";

import { CurrencySwitcher } from "@/components/currency-switcher";
import { Button } from "@/components/ui/button";
import type { BillingProfile, PaymentProvider } from "@/lib/types";

const LABEL: Record<PaymentProvider, string> = {
  razorpay: "Razorpay",
  stripe: "Stripe",
};


/**
 * Currency and payment method, together, in the order summary.
 *
 * They belong side by side because they are one decision: the currency decides
 * which method leads, and a switcher parked up in the page header made that
 * look like a display preference rather than part of paying.
 *
 * Both methods are offered in every currency — the second one is muted and
 * below, never hidden. Order comes from the server (`profile.providers`,
 * recommended first) rather than from a rule here: rupees lead with Razorpay,
 * which settles domestically and is the only one of the two doing UPI, and
 * everything else leads with Stripe. Changing that should not need a frontend
 * release.
 *
 * A method only renders unpressable when this deployment has no keys for it,
 * and it still renders — "not switched on yet" is information, where a silently
 * missing button looks like a method we do not support at all.
 */
export function PayMethods({
  profile,
  amountLabel,
  disabled = false,
  busyProvider,
  onPay,
}: {
  profile: BillingProfile | null;
  /** The formatted total, e.g. "₹200". Null while no pack is chosen. */
  amountLabel: string | null;
  disabled?: boolean;
  busyProvider: PaymentProvider | null;
  onPay: (provider: PaymentProvider) => void;
}) {
  const [recommended, ...rest] = profile?.providers ?? [];
  // A deployment with no gateways at all is not a state the API produces, but
  // destructuring an empty list into a required object is one crash away.
  if (!profile || !recommended) return null;

  const busy = busyProvider !== null;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground text-sm">Pay in</span>
        <CurrencySwitcher />
      </div>

      {recommended.available ? (
        <Button
          variant="brand"
          disabled={disabled || busy}
          onClick={() => onPay(recommended.provider)}
        >
          {busyProvider === recommended.provider && (
            <Loader2 className="size-4 animate-spin" />
          )}
          {amountLabel ? `Pay ${amountLabel}` : "Pay"} with{" "}
          {LABEL[recommended.provider]}
        </Button>
      ) : (
        <div className="border-warning/30 bg-warning/10 flex items-start gap-2 rounded-lg border p-3 text-xs">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-[var(--warning)]" />
          <p className="text-pretty">
            {LABEL[recommended.provider]} {recommended.unavailable_reason} Ask us
            to add sessions through the{" "}
            <Link href="/contact" className="underline">
              contact form
            </Link>{" "}
            in the meantime.
          </p>
        </div>
      )}


      {rest.map((option) => (
        <div key={option.provider} className="flex flex-col gap-1.5">
          <Button
            // `outline`, not `ghost`. Ghost paints nothing until the pointer is
            // over it, so the alternative read as a line of text rather than a
            // control — and a payment method nobody recognises as clickable is
            // the same as not offering it. The border carries the affordance;
            // the muted label is what keeps it below the brand-filled primary.
            variant="outline"
            className="text-muted-foreground font-normal"
            disabled={disabled || busy || !option.available}
            onClick={() => onPay(option.provider)}
          >
            {busyProvider === option.provider && (
              <Loader2 className="size-4 animate-spin" />
            )}
            Pay with {LABEL[option.provider]} instead
          </Button>
          {!option.available && option.unavailable_reason && (
            <p className="text-muted-foreground text-center text-xs text-pretty">
              {option.unavailable_reason}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
