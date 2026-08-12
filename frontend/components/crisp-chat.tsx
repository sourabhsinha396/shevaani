import Script from "next/script";

/**
 * Crisp live-chat widget, mounted once in the root layout.
 *
 * Production builds only: dev sessions would otherwise show up as visitors in
 * the real inbox. A missing website id also renders nothing, so an unset env
 * var degrades to "no chat" rather than a broken widget. Both checks are
 * resolved at build time (NODE_ENV and NEXT_PUBLIC_* are inlined), so
 * non-production bundles carry no trace of the script.
 */
export function CrispChat() {
  const websiteId = process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID;
  if (process.env.NODE_ENV !== "production" || !websiteId) return null;

  // The official Crisp snippet, verbatim apart from the injected id.
  // lazyOnload: a chat bubble is not worth competing with hydration for.
  return (
    <Script id="crisp-chat" strategy="lazyOnload">
      {`window.$crisp=[];window.CRISP_WEBSITE_ID=${JSON.stringify(websiteId)};(function(){var d=document,s=d.createElement("script");s.src="https://client.crisp.chat/l.js";s.async=1;d.getElementsByTagName("head")[0].appendChild(s);})();`}
    </Script>
  );
}
