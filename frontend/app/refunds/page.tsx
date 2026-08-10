import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Cancellation and credit policy",
  description:
    "When a cancelled session returns its credits and when it doesn't. Shevaani returns credits, never money to your card.",
  path: "/refunds",
});

/**
 * Written against what the code actually does, not against a template. The
 * numbers here have exact counterparts in the backend:
 *
 *   12h cutoff               → CANCELLATION_FULL_REFUND_HOURS
 *   auto-cancel at T-2h      → GROUP_AUTOCANCEL_HOURS_BEFORE
 *   credits, never a card    → services/credits.py (append-only ledger, and
 *     reversal                 no code path anywhere that reverses a payment)
 *
 * If either setting changes, this page has to change with it.
 */
export default function RefundPolicyPage() {
  return (
    <LegalPage
      title="Cancellation and credit policy"
      updated="10 August 2026"
      intro={
        <>
          Shevaani sells <strong>credits</strong>, and two credits book one
          session. Everything below is about credits returning to your balance.
          We do not return money to your card — a cancelled session gives you
          back the credits, which is instant, and credits never expire.
        </>
      }
    >
      <h2>Cancelling a session you booked</h2>
      <ul>
        <li>
          <strong>More than 12 hours before it starts</strong> — cancel from{" "}
          <Link href="/dashboard">My sessions</Link> and the credits go straight
          back to your balance.
        </li>
        <li>
          <strong>Within 12 hours of the start</strong> — the credits are spent.
          The seat was held for you and the group is small enough that a late
          drop-out changes the session for everyone in it.
        </li>
        <li>
          <strong>Waitlisted and never promoted</strong> — you are never charged
          for a waitlist place. The credits are taken only at the moment a seat
          opens and you move into it.
        </li>
      </ul>

      <h2>When we cancel</h2>
      <p>
        If we cancel a session for any reason, every booking on it gets its
        credits back in full, regardless of the 12-hour cutoff. That includes the
        automatic case:
      </p>
      <ul>
        <li>
          A group discussion that has not reached its minimum number of learners{" "}
          <strong>two hours before it starts</strong> is cancelled
          automatically, and everyone booked gets their credits back at that
          moment. A discussion of two people is not the thing you paid for.
        </li>
        <li>
          If an instructor cannot make it and we cannot replace them, the same
          applies.
        </li>
      </ul>
      <p>
        Returned credits appear on your balance immediately and can be spent on
        any other session. Nothing expires.
      </p>

      <h2>Credits you have not used</h2>
      <p>
        <strong>We do not return money to your card.</strong> Everything we give
        back, we give back as credits. That is the whole policy, and it applies
        to unused credits as much as to cancelled sessions.
      </p>
      <ul>
        <li>
          Credits <strong>never expire</strong>. An unused credit keeps its value
          indefinitely, so nothing is lost by not booking this month.
        </li>
        <li>
          Credits already spent on a session that ran are gone. A session you did
          not attend, and did not cancel, counts as having run.
        </li>
        <li>
          If a purchase went wrong at our end — you were charged twice, or
          charged and given nothing — that is a mistake rather than a refund
          request, and we will put it right. Tell us through the{" "}
          <Link href="/contact">contact form</Link>.
        </li>
      </ul>

      <h2>Prices and currency</h2>
      <p>
        We sell in US dollars, rupees, euros, pounds and Australian dollars. Your
        currency is picked from your device&apos;s time zone and can be changed
        with the switcher on the pricing and checkout pages — the amount shown
        there is the amount charged, and nothing is converted after you agree to
        it. Both Razorpay and Stripe are offered in every currency, and you
        choose which one takes the payment at checkout. Because
        what comes back is always a credit rather than money, an exchange-rate
        movement after your purchase cannot change what your balance is worth.
      </p>

      <h2>If something goes wrong in a session</h2>
      <p>
        If a session did not happen as described — nobody hosted it, or the video
        link never worked — tell us within seven days through the{" "}
        <Link href="/contact">contact form</Link> and we will return the credits.
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
