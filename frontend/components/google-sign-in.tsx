"use client";

import * as React from "react";
import { useTheme } from "next-themes";

import { config } from "@/lib/config";

/**
 * The official "Sign in with Google" button, or nothing at all.
 *
 * Rendered by the login and signup forms. With no client id configured the
 * component renders nothing and the forms behave exactly as they did before
 * the button existed - mirroring how the backend answers 503 on /auth/google
 * without its GOOGLE_CLIENT_ID, so the pair go together.
 *
 * Loaded straight from Google rather than through an npm wrapper, for the
 * same reason recaptcha.tsx is: it is one script tag and two calls, and the
 * button Google draws is the one users trust. The button hands back a signed
 * ID token (the "credential"); what to do with it is the caller's business.
 */

interface CredentialResponse {
  credential: string;
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (params: {
            client_id: string;
            callback: (response: CredentialResponse) => void;
          }) => void;
          renderButton: (
            container: HTMLElement,
            options: {
              type: "standard";
              theme: "outline" | "filled_black";
              size: "large";
              text: "continue_with";
              width: number;
            },
          ) => void;
        };
      };
    };
  }
}

export const googleSignInEnabled = Boolean(config.googleClientId);

/* One script for the whole session, however many forms mount. Module state
   rather than component state so a second form reuses the load already in
   flight instead of appending a second <script>. */
let script: Promise<void> | null = null;
function loadGis(): Promise<void> {
  script ??= new Promise<void>((resolve) => {
    const el = document.createElement("script");
    el.src = "https://accounts.google.com/gsi/client";
    el.async = true;
    el.onload = () => resolve();
    document.head.appendChild(el);
  });
  return script;
}

export function GoogleSignIn({
  onCredential,
}: {
  /** Called with the ID token when the person completes Google's popup. */
  onCredential: (credential: string) => void;
}) {
  const container = React.useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();

  // The live callback, readable from an effect that must not re-run when the
  // parent re-renders with a fresh closure.
  const handleCredential = React.useRef(onCredential);
  handleCredential.current = onCredential;

  React.useEffect(() => {
    if (!googleSignInEnabled) return;
    let cancelled = false;

    void loadGis().then(() => {
      if (cancelled || !container.current || !window.google) return;
      // Page-global, and last call wins - harmless here because only one auth
      // form is ever mounted at a time.
      window.google.accounts.id.initialize({
        client_id: config.googleClientId,
        callback: (response) => handleCredential.current(response.credential),
      });
      window.google.accounts.id.renderButton(container.current, {
        type: "standard",
        // The button cannot restyle in place, so a theme change re-renders it
        // via the effect deps, same dance as the reCAPTCHA widget.
        theme: resolvedTheme === "dark" ? "filled_black" : "outline",
        size: "large",
        text: "continue_with",
        // Google clamps to [200, 400]; the auth cards sit inside max-w-md, so
        // the measured width only leaves that range on very narrow phones.
        width: Math.min(400, Math.max(200, container.current.offsetWidth)),
      });
    });

    return () => {
      // No unrender API; emptying the container is what keeps strict mode's
      // double mount from stacking two buttons.
      cancelled = true;
      if (container.current) container.current.innerHTML = "";
    };
  }, [resolvedTheme]);

  if (!googleSignInEnabled) return null;
  return <div ref={container} className="flex min-h-[44px] justify-center" />;
}
