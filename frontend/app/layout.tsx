import type { Metadata } from "next";
import { Geist, Playfair_Display } from "next/font/google";

import { AuthProvider } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

// Only the 400 weight is loaded — display headings are set at normal weight by
// design, so shipping the bolds would be dead bytes.
const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-playfair",
});

export const metadata: Metadata = {
  title: "Shevaani — speak English with real people",
  description:
    "Small-group English discussions and one-to-one sessions with real facilitators. Book a slot, show up, talk.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geist.variable} ${playfair.variable}`}
      suppressHydrationWarning
    >
      <body className="font-sans">
        {/* Scroll reveals start at opacity 0 and are un-hidden by an observer.
            If the script never runs, the page would otherwise be blank — so
            without JS, drop the animation and show everything. */}
        <noscript>
          <style>{`[data-reveal]{opacity:1!important;transform:none!important}`}</style>
        </noscript>

        <ThemeProvider>
          <AuthProvider>
            <div className="flex min-h-screen flex-col">
              <SiteHeader />
              <main className="flex-1">{children}</main>
              <footer className="border-border/60 border-t py-10">
                <div className="text-muted-foreground container-page flex flex-col gap-2 text-sm sm:flex-row sm:items-center sm:justify-between">
                  <p>© {new Date().getFullYear()} Shevaani</p>
                  <p>Group discussions run daily · 1:1 sessions 7am–7pm IST</p>
                </div>
              </footer>
            </div>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
