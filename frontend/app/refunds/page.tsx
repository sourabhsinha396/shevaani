import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { company } from "@/lib/company";
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
          session.
        </>
      }
    >
      <h2>Cancelling a session you booked</h2>
      <ul>
        <li>
          <strong>More than 12 hours before it starts</strong> - cancel from{" "}
          <Link href="/dashboard">My sessions</Link> and the credits go straight
          back to your balance.
        </li>
        <li>
          <strong>Within 12 hours of the start</strong> - the credits are spent.
          The seat was held for you and the group is small enough that a late
          drop-out changes the session for everyone in it.
        </li>
        <li>
          <strong>Waitlisted and never promoted</strong> - you are never charged
          for a waitlist place. The credits are taken only at the moment a seat
          opens and you move into it.
        </li>
      </ul>

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
          not attend, and did not cancel, counts as having used.
        </li>
      </ul>

      <h2>If something goes wrong in a session</h2>
      <p>
        If a session did not happen as described - nobody hosted it, or the video
        link never worked - tell us within seven days through the{" "}
        <Link href="/contact">contact form</Link> and we will return the credits.
      </p>
      <ul>
        <li>
          If a purchase went wrong at our end - you were charged twice, we will
          verify and issue refund. Tell us through the{" "}
          <Link href="/contact">contact form</Link>.
        </li>
      </ul>

      <h2>Contact</h2>
      <p>
        If you need assistance, please use the{" "}
        <Link href="/contact">contact form</Link>
        {company.supportEmail && (
          <>
            {" "}or write to{" "}
            <a href={`mailto:${company.supportEmail}`}>{company.supportEmail}</a>
          </>
        )}
        . We reply within two working days.
      </p>
    </LegalPage>
  );
}
