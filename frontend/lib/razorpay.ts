/**
 * Razorpay Checkout, loaded on demand.
 *
 * Stripe hosts its own page and we simply leave the site. Razorpay does the
 * opposite: it opens a modal over ours, which is why it needs a script at all
 * and why nothing here navigates. The buyer stays put and the handler fires in
 * the same document.
 *
 * The script is fetched the first time somebody actually chooses Razorpay, not
 * on page load. It is a third-party script on a page that renders prices and a
 * signed-in balance; loading it for the majority who will pay by card would be
 * a request — and a set of cookies — bought for nothing.
 *
 * **Nothing the modal returns is trusted.** The handler's payload is checked
 * server-side against a fresh fetch of the order (see `billing.verify_payment`),
 * so the signature below is an extra barrier rather than the thing that grants.
 */

const SCRIPT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

interface RazorpayInstance {
  open: () => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

/** What checkout.js hands back on a successful payment. */
export interface RazorpayReturn {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

let pending: Promise<void> | null = null;

function load(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  // Shared across callers: two buttons pressed in quick succession must not
  // append two script tags.
  if (pending) return pending;

  pending = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      // Cleared so a later attempt can retry rather than resolving against a
      // promise that has already rejected.
      pending = null;
      reject(
        new Error(
          "Razorpay's checkout couldn't be loaded. Check your connection, or pay by card instead.",
        ),
      );
    };
    document.head.appendChild(script);
  });
  return pending;
}

/**
 * The public half of the order, as `create_checkout` built it.
 *
 * Everything in here reaches the browser, so everything in here is public — no
 * key secret, and no amount that matters: Razorpay charges what the *order*
 * says, not what this payload was handed.
 */
export interface RazorpayPayload {
  key_id: string;
  order_id: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  prefill?: { name?: string; email?: string };
}

export async function openRazorpayCheckout(
  payload: RazorpayPayload,
  handlers: {
    onSuccess: (result: RazorpayReturn) => void;
    /** Fired when the buyer closes the modal without paying. */
    onDismiss: () => void;
  },
): Promise<void> {
  await load();
  if (!window.Razorpay) {
    throw new Error("Razorpay's checkout couldn't be loaded. Please try again.");
  }

  const checkout = new window.Razorpay({
    key: payload.key_id,
    order_id: payload.order_id,
    amount: payload.amount,
    currency: payload.currency,
    name: payload.name,
    description: payload.description,
    prefill: payload.prefill ?? {},
    handler: handlers.onSuccess,
    modal: { ondismiss: handlers.onDismiss },
  });
  checkout.open();
}

/** Narrows the untyped `client_payload` the API returns. */
export function asRazorpayPayload(payload: Record<string, unknown>): RazorpayPayload | null {
  const { key_id, order_id, amount, currency } = payload as Partial<RazorpayPayload>;
  if (!key_id || !order_id || typeof amount !== "number" || !currency) return null;
  return {
    key_id,
    order_id,
    amount,
    currency,
    name: String(payload.name ?? "Shevaani"),
    description: String(payload.description ?? ""),
    prefill: (payload.prefill as RazorpayPayload["prefill"]) ?? {},
  };
}
