import type { Metadata } from "next";

import { ImpromptuTrainer } from "@/components/tools/impromptu-trainer";
import { getImpromptuTopics } from "@/lib/impromptu";
import { SITE_NAME, SITE_URL, canonical, jsonLdScript, pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Impromptu Speaking Practice - Free Tool",
  description:
    "Get a random topic, 30 seconds to think, one minute to talk. Free impromptu speaking practice for interviews, IELTS, MBA and everyday fluency - no account needed.",
  path: "/tools/impromptu",
});

/** `WebApplication`, and `isAccessibleForFree: true` is the point - this page
 *  exists to rank for "impromptu speaking practice", and free is the claim
 *  that earns the click. */
function toolJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: "Impromptu Speaking Practice",
    url: canonical("/tools/impromptu"),
    applicationCategory: "EducationalApplication",
    operatingSystem: "Any",
    isAccessibleForFree: true,
    offers: { "@type": "Offer", price: "0", priceCurrency: "INR" },
    provider: { "@type": "Organization", name: SITE_NAME, url: SITE_URL },
    audience: { "@type": "Audience", audienceType: "English learners" },
  };
}

/**
 * The page IS the tool - the reel format works because there is nothing to
 * read. The heading exists for crawlers and screen readers only; every word a
 * visitor sees belongs to the trainer itself. Longer-form copy about why
 * impromptu practice works lives on `/tools`, not here.
 */
export default async function ImpromptuPage() {
  const topics = await getImpromptuTopics();

  return (
    <div className="container-page">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: jsonLdScript(toolJsonLd()) }}
      />
      <h1 className="sr-only">Impromptu speaking practice - free tool</h1>
      {/* Fills the viewport under the sticky 4rem header, so the tool opens
          looking like the reels: one screen, one prompt, nothing to scroll. */}
      <ImpromptuTrainer topics={topics} className="min-h-[calc(100dvh-4rem)] py-16" />
    </div>
  );
}
