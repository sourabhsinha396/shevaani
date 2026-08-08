/**
 * Credit packs, shared by the homepage section and `/pricing` so the two can
 * never drift apart. Prices are listed per currency and never converted at
 * checkout — a ₹ list and a $ list, matching the `credit_packs` table. Learners
 * in India check out via Razorpay, everyone else via Stripe.
 */
export type Pack = {
  name: string;
  credits: number;
  inr: string;
  usd: string;
  blurb: string;
  features: string[];
  highlight?: boolean;
};

export const PACKS: Pack[] = [
  {
    name: "Starter",
    credits: 5,
    inr: "₹499",
    usd: "$9",
    blurb: "Try a few discussions and find your level.",
    features: [
      "5 group discussions",
      "Prep material for each",
      "Cancel free up to 12h before",
    ],
  },
  {
    name: "Regular",
    credits: 20,
    inr: "₹1,699",
    usd: "$29",
    blurb: "Two or three sessions a week — where fluency actually moves.",
    features: [
      "20 credits",
      "Use for group or 1:1",
      "Priority on waitlists",
      "Cancel free up to 12h before",
    ],
    highlight: true,
  },
  {
    name: "Intensive",
    credits: 50,
    inr: "₹3,799",
    usd: "$65",
    blurb: "Daily practice, with room for one-to-ones.",
    features: [
      "50 credits",
      "Use for group or 1:1",
      "Priority on waitlists",
      "Progress summary",
    ],
  },
];

export type Currency = "inr" | "usd";

/** Per-credit unit price, for the "works out at …" line under each pack. */
export function perCredit(pack: Pack, currency: Currency) {
  const symbol = currency === "inr" ? "₹" : "$";
  const total = Number(pack[currency].replace(/[^0-9.]/g, ""));
  const each = total / pack.credits;
  return `${symbol}${each < 10 ? each.toFixed(1) : Math.round(each).toLocaleString()}`;
}
