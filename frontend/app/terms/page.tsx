import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Terms of service",
  description:
    "The agreement between you and Shevaani: accounts, credits, sessions, conduct, and how either side ends it.",
  path: "/terms",
});

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of service"
      updated="8 August 2026"
      intro={
        <>
          These terms cover using Shevaani — the account, the credits, and the
          sessions themselves. Using the service means accepting them. What
          happens to a credit when a session is cancelled has its own page:{" "}
          <Link href="/refunds">cancellations and credits</Link>.
        </>
      }
    >
      <h2>1. Who we are</h2>
      <p>
        Shevaani is an online English-practice service: small-group discussions
        and one-to-one sessions, held over video with an instructor. Written
        questions go through the <Link href="/contact">contact form</Link>.
      </p>

      <h2>2. Your account</h2>
      <ul>
        <li>
          You need an account to book. Give a real email address — it is how we
          send session details and how you recover access.
        </li>
        <li>
          One account per person. Sessions are small and seats are allocated per
          learner, so sharing an account takes a seat from someone else.
        </li>
        <li>
          You are responsible for what happens under your account. Tell us
          straight away if you think someone else has access to it.
        </li>
        <li>
          Instructor and administrator accounts are created by us. There is no
          way to sign yourself up as one.
        </li>
      </ul>

      <h2>3. Credits</h2>
      <ul>
        <li>
          Credits are bought in packs and spent on sessions. Two credits book
          one session, group or one-to-one, unless a session says otherwise.
        </li>
        <li>
          Credits do not expire, have no cash value in themselves, and cannot be
          transferred between accounts.
        </li>
        <li>
          A credit is taken when a booking is confirmed. Joining a waitlist takes
          nothing until a seat opens for you.
        </li>
        <li>
          Your balance is the sum of a permanent record of every change to it. If
          you think it is wrong, ask — we can show you the history.
        </li>
      </ul>

      <h2>4. Sessions</h2>
      <ul>
        <li>
          Group discussions have a minimum and a maximum number of learners. Below
          the minimum two hours before the start, the session is cancelled
          automatically and everyone gets their credits back.
        </li>
        <li>
          One-to-one sessions are booked into an instructor&apos;s published
          availability, between 07:00 and 19:00 IST.
        </li>
        <li>
          The joining link becomes available shortly before the start and works
          only for people booked onto that session. It is personal to you —
          passing it on is not permitted, and every use of it is logged.
        </li>
        <li>
          Sessions are practice conversations, not certified tuition. We do not
          promise a particular result or level.
        </li>
        <li>
          We do not record sessions. If an instructor ever wants to, they will ask
          everyone in the room first and you can say no.
        </li>
      </ul>

      <h2>5. Conduct</h2>
      <p>
        The point of a small group is that it is comfortable to speak in. So:
        turn up on time, let other people finish, and keep it civil. We will end a
        session and close an account over harassment, hate speech, or sexual
        content, and we will not refund credits spent on a session ended that
        way.
      </p>

      <h2>6. Availability</h2>
      <p>
        We aim to keep the service running but do not guarantee it is
        uninterrupted. If a session cannot go ahead because of a failure on our
        side, the remedy is the one in the{" "}
        <Link href="/refunds">cancellation policy</Link>: your credits come back.
      </p>

      <h2>7. Your content</h2>
      <p>
        Anything you write into the service — a profile, a message to us — stays
        yours. You give us permission to store and display it only as far as
        running the service needs.
      </p>

      <h2>8. Ending it</h2>
      <ul>
        <li>
          You can stop using Shevaani at any time and ask us to delete your
          account. Bookings ahead of you are cancelled under the normal rules.
        </li>
        <li>
          We can suspend or close an account that breaks these terms. Where the
          breach is not conduct-related, we will honour the credits on the
          balance — by letting you spend them before the account closes, or by
          moving them to another account you hold.
        </li>
      </ul>

      <h2>9. Changes</h2>
      <p>
        If these terms change in a way that affects you, we will say so by email
        before the change applies to sessions you have already booked. The date
        at the top of this page always reflects the current version.
      </p>

      <h2>10. Law</h2>
      <p>
        These terms are governed by the laws of India, and the courts of India
        have jurisdiction over any dispute arising from them. Nothing here removes
        a right you have under consumer law that cannot be signed away.
      </p>
    </LegalPage>
  );
}
