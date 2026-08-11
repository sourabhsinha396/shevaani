import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { company } from "@/lib/company";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Shipping policy",
  description:
    "Shevaani sells online sessions only. Nothing physical is ever shipped.",
  path: "/shipping",
});

/** Exists for the payment provider's account review, which expects a shipping
 *  policy even from a business with nothing to ship. Hence the length. */
export default function ShippingPolicyPage() {
  return (
    <LegalPage title="Shipping policy" updated="11 August 2026">
      <p>
        Shevaani sells online services only - live group discussions and 1:1
        sessions delivered over video call. <strong>We do not sell or ship any
        physical products</strong>, so no shipping charges, delivery timelines,
        or courier partners apply.
      </p>
      <p>
        Everything you buy is available from your{" "}
        <Link href="/dashboard">dashboard</Link> immediately after payment.
      </p>
      <p>
        Questions go through the <Link href="/contact">contact form</Link>
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
