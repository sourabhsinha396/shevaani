import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Refund and cancellation policy",
  description:
    "When a session refunds a credit, when it doesn't, and how to get money back for credits you haven't used.",
  path: "/refunds",
});

/**
 * Written against what the code actually does, not against a template. The
 * numbers here have exact counterparts in the backend:
 *
 *   12h full-refund cutoff   → CANCELLATION_FULL_REFUND_HOURS
 *   auto-cancel at T-2h      → GROUP_AUTOCANCEL_HOURS_BEFORE
 *   refund = credits, never  → services/credits.py (append-only ledger)
 *     a card reversal
 *
 * If either setting changes, this page has to change with it.
 */
export default function RefundPolicyPage() {
  return (
    <LegalPage
      title="Refund and cancellation policy"
      updated="8 August 2026"
      intro={
        <>
          Shevaani sells <strong>credits</strong>, and one credit books one
          session. Almost everything below is therefore about credits returning
          to your balance rather than money returning to your card — that part
          is faster, and it is what happens automatically.
        </>
      }
    >
      <h2>Cancelling a session you booked</h2>
      <ul>
        <li>
          <strong>More than 12 hours before it starts</strong> — cancel from{" "}
          <Link href="/dashboard">My sessions</Link> and the credit goes straight
          back to your balance.
        </li>
        <li>
          <strong>Within 12 hours of the start</strong> — the credit is spent.
          The seat was held for you and the group is small enough that a late
          drop-out changes the session for everyone in it.
        </li>
        <li>
          <strong>Waitlisted and never promoted</strong> — you are never charged
          for a waitlist place. The credit is taken only at the moment a seat
          opens and you move into it.
        </li>
      </ul>

      <h2>When we cancel</h2>
      <p>
        If we cancel a session for any reason, every booking on it is refunded in
        full, regardless of the 12-hour cutoff. That includes the automatic case:
      </p>
      <ul>
        <li>
          A group discussion that has not reached its minimum number of learners{" "}
          <strong>two hours before it starts</strong> is cancelled
          automatically, and everyone booked gets their credit back at that
          moment. A discussion of two people is not the thing you paid for.
        </li>
        <li>
          If an instructor cannot make it and we cannot replace them, the same
          applies.
        </li>
      </ul>
      <p>
        Refunded credits appear on your balance immediately and can be spent on
        any other session. Nothing expires.
      </p>

      <h2>Getting money back for credits you have not used</h2>
      <ul>
        <li>
          Unused credits are refundable to the original payment method for{" "}
          <strong>14 days</strong> after the purchase that created them. Ask via
          the <Link href="/contact">contact form</Link> from the email address on
          the account.
        </li>
        <li>
          Credits already spent on a session that ran are not refundable in
          money. A session you did not attend, without cancelling, counts as
          having run.
        </li>
        <li>
          Refunds go back to the card, UPI handle, or wallet that paid — we
          cannot send them anywhere else. Expect <strong>5–7 working days</strong>{" "}
          for the money to appear, which is your bank&apos;s timeline rather than
          ours.
        </li>
        <li>
          Partly used packs are refunded pro rata: the credits still on your
          balance, at the price actually paid per credit for that purchase.
        </li>
      </ul>

      <h2>Prices and currency</h2>
      <p>
        Prices are listed per currency and never converted at checkout. Learners
        in India pay in rupees through Razorpay; everyone else pays in dollars
        through Stripe. A refund is made in the currency you paid in, so an
        exchange-rate movement between purchase and refund does not change the
        amount you get back.
      </p>

      <h2>If something goes wrong in a session</h2>
      <p>
        If a session did not happen as described — nobody hosted it, or the video
        link never worked — tell us within seven days through the{" "}
        <Link href="/contact">contact form</Link> and we will return the credit.
        You do not need to have raised it during the session.
      </p>

      <h2>Contact</h2>
      <p>
        Every request above goes through the{" "}
        <Link href="/contact">contact form</Link>. We reply within two working
        days, and we will tell you what we have done rather than only that we
        received it.
      </p>
    </LegalPage>
  );
}
