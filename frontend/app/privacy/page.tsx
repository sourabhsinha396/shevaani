import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { company } from "@/lib/company";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Privacy policy",
  description:
    "What Shevaani stores about you, why, who else sees it, and how to get it deleted.",
  path: "/privacy",
});

/**
 * Describes the data the system actually holds. The specifics - join-link
 * access logs, the append-only credit ledger, Google Calendar as the only place
 * a session's video link is created - are all real, and a vaguer page would be
 * both less useful and less true.
 */
export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy policy"
      updated="8 August 2026"
      intro={
        <>
          This describes what we store, why we store it, and who else can see it.
          It is written about the system as built rather than about what a
          service like this might in principle do.
        </>
      }
    >
      <h2>What we collect</h2>
      <ul>
        <li>
          <strong>Account</strong> - name, email address, password (stored only
          as an Argon2 hash, never as text), and time zone. We do not ask for
          your country: a rough one is inferred
          from your time zone for support and reporting, and your checkout
          currency comes from the same time zone, in your browser, with no
          location lookup and no third party involved.
        </li>
        <li>
          <strong>Bookings</strong> - which sessions you booked, when, whether
          you cancelled, and whether you attended.
        </li>
        <li>
          <strong>Credits</strong> - a permanent, append-only record of every
          change to your balance. It is never edited, because a balance you
          cannot audit is a balance you cannot trust.
        </li>
        <li>
          <strong>Payments</strong> - amount, currency, and the reference our
          payment provider gives us. <strong>Card numbers never reach us</strong>
          ; the card details are entered on Stripe&apos;s or Razorpay&apos;s own
          checkout.
        </li>
        <li>
          <strong>Join access</strong> - each time a session&apos;s video link is
          fetched, with the time and IP address. The link is a credential, so its
          use is logged; the same record is what tells the instructor who turned
          up.
        </li>
        <li>
          <strong>Messages</strong> - anything you send through the{" "}
          <Link href="/contact">contact form</Link>.
        </li>
      </ul>

      <h2>What we do not collect</h2>
      <ul>
        <li>No advertising or analytics trackers, and no third-party cookies.</li>
        <li>
          No session recordings, transcripts, or audio. We do not record classes.
        </li>
        <li>
          No card, UPI, or bank details - those stay with the payment provider.
        </li>
      </ul>

      <h2>Cookies</h2>
      <p>
        Two, both strictly necessary: an httpOnly sign-in cookie and its refresh
        counterpart. There is no tracking cookie to consent to, which is why this
        site has no cookie banner.
      </p>

      <h2>Who else sees it</h2>
      <ul>
        <li>
          <strong>Your instructor</strong> - your name, and whether you attended
          their session. Not your email, your balance, or your other bookings.
        </li>
        <li>
          <strong>Google</strong> - a session is a Google Calendar event on the
          instructor&apos;s own account, which is what creates the Meet link.
          Learners are deliberately <em>not</em> added as calendar guests, so your
          email address is not sent to Google.
        </li>
        <li>
          <strong>Stripe and Razorpay</strong> - whichever handles your payment
          receives what it needs to take it.
        </li>
        <li>Nobody else. We do not sell or share personal data.</li>
      </ul>

      <h2>How long we keep it</h2>
      <ul>
        <li>Account and booking history: while your account exists.</li>
        <li>
          Payment and credit records: seven years after the transaction, because
          tax law requires it - these survive account deletion in a form tied to
          the transaction rather than to a live profile.
        </li>
        <li>Join access logs: twelve months.</li>
        <li>Contact messages: two years.</li>
      </ul>

      <h2>Your rights</h2>
      <p>
        You can ask for a copy of your data, ask us to correct it, or ask us to
        delete your account. Write from the address on the account through the{" "}
        <Link href="/contact">contact form</Link> and we will act within 30 days,
        keeping only the financial records named above.
      </p>

      <h2>Security</h2>
      <p>
        Passwords are hashed with Argon2. Instructors&apos; Google tokens are
        encrypted at rest. Session video links are served only to people booked
        onto that session, only inside the joining window, and every request for
        one is logged.
      </p>

      <h2>Changes and contact</h2>
      <p>
        Material changes are announced by email before they take effect. Any
        question about this policy - including a request under it - goes to the{" "}
        <Link href="/contact">contact form</Link>
        {company.supportEmail && (
          <>
            {" "}or to{" "}
            <a href={`mailto:${company.supportEmail}`}>{company.supportEmail}</a>
          </>
        )}
        .
      </p>
    </LegalPage>
  );
}
