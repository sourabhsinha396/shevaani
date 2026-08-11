import type { Metadata } from "next";
import { Geist, Playfair_Display } from "next/font/google";

import { AuthProvider } from "@/components/auth-provider";
import { CurrencyProvider } from "@/components/currency-provider";
import { RefCapture } from "@/components/ref-capture";
import { SiteConfigProvider } from "@/components/site-config-provider";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { ThemeProvider } from "@/components/theme-provider";
import { SITE_NAME, SITE_URL, jsonLdScript, organizationJsonLd } from "@/lib/seo";
import { getSiteConfig } from "@/lib/site-config";

import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

// Only the 400 weight is loaded - display headings are set at normal weight by
// design, so shipping the bolds would be dead bytes.
const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-playfair",
});

const DESCRIPTION =
  "Small-group English discussions and one-to-one sessions with real instructors. Book a slot, show up, talk.";

export const metadata: Metadata = {
  // Every page below sets its own `title`; this template wraps it. The
  // `default` is what the homepage and anything that forgets will use.
  title: {
    default: "Shevaani - Group Discussions and 1-1 Sessions",
    template: "%s - Shevaani",
  },
  description: DESCRIPTION,
  // Makes every relative `alternates.canonical` and OG url in child pages
  // resolve to an absolute URL, which is what crawlers require.
  metadataBase: new URL(SITE_URL),
  alternates: { canonical: "/" },
  applicationName: SITE_NAME,
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    locale: "en_IN",
    url: SITE_URL,
    title: "Shevaani - Group Discussions and 1-1 Sessions",
    description: DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: "Shevaani - Group Discussions and 1-1 Sessions",
    description: DESCRIPTION,
  },
};

/* Async for one reason: the feature flags are read here, on the server, so the
   header's first paint already has the right links in it. The fetch is cached
   (see `getSiteConfig`), so this does not make every page dynamic - it puts them
   on a one-minute revalidation window instead. */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const siteConfig = await getSiteConfig();

  return (
    <html
      lang="en"
      className={`${geist.variable} ${playfair.variable}`}
      suppressHydrationWarning
    >
      <body className="font-sans">
        {/* Organization, once, sitewide. Repeating it per page would say the
            same thing several times without adding anything. */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdScript(organizationJsonLd()) }}
        />
        {/* Scroll reveals start at opacity 0 and are un-hidden by an observer.
            If the script never runs, the page would otherwise be blank - so
            without JS, drop the animation and show everything. */}
        <noscript>
          <style>{`[data-reveal]{opacity:1!important;transform:none!important}`}</style>
        </noscript>

        <ThemeProvider>
          {/* Outermost of the data providers: it is the only one whose value is
              already known here, and both the chrome and the pages read it. */}
          <SiteConfigProvider config={siteConfig}>
            <AuthProvider>
              {/* Sitewide so the homepage, /pricing and /checkout can never
                  disagree about which currency someone is reading. Renders USD on
                  the server and swaps to the detected one after hydration. */}
              <CurrencyProvider>
                {/* Invisible: remembers a ?r= referral code from any landing
                    page so the register form can send it later. */}
                <RefCapture />
                <div className="flex min-h-screen flex-col">
                  <SiteHeader />
                  <main className="flex-1">{children}</main>
                  <SiteFooter config={siteConfig} />
                </div>
              </CurrencyProvider>
            </AuthProvider>
          </SiteConfigProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
