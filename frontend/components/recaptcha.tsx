"use client";

import * as React from "react";
import { useTheme } from "next-themes";

import { config } from "@/lib/config";

/**
 * The reCAPTCHA v2 checkbox, or nothing at all.
 *
 * Rendered by the three anonymous auth forms (login, signup, forgot password).
 * With no site key configured the component renders nothing and the forms
 * behave exactly as they did before the widget existed - which is what keeps
 * local development free of a Google account, mirroring how the backend
 * skips verification without its secret.
 *
 * Loaded straight from Google rather than through an npm wrapper: the widget
 * is one script tag and two calls, and a dependency would only put a layer of
 * somebody else's state management between us and `grecaptcha.reset`.
 */

declare global {
  interface Window {
    grecaptcha?: {
      render: (
        container: HTMLElement,
        params: {
          sitekey: string;
          theme: "light" | "dark";
          callback: (token: string) => void;
          "expired-callback": () => void;
        },
      ) => number;
      reset: (widgetId: number) => void;
    };
  }
}

export const recaptchaEnabled = Boolean(config.recaptchaSiteKey);

const ONLOAD = "__shevaaniRecaptchaOnload";

/* One script for the whole session, however many forms mount. The promise is
   module state rather than component state so a second form reuses the load
   already in flight instead of appending a second <script>. */
let script: Promise<void> | null = null;
function loadRecaptcha(): Promise<void> {
  script ??= new Promise<void>((resolve) => {
    (window as unknown as Record<string, unknown>)[ONLOAD] = resolve;
    const el = document.createElement("script");
    // Explicit render: the auto mode scans the DOM at script load, which has
    // already happened by the time a client component mounts.
    el.src = `https://www.google.com/recaptcha/api.js?onload=${ONLOAD}&render=explicit`;
    el.async = true;
    document.head.appendChild(el);
  });
  return script;
}

export interface RecaptchaHandle {
  /** Clear the tick. Tokens are one-time: a submit that failed has spent the
   *  one it sent, so the form must reset the widget alongside showing the
   *  error or the retry would fail on a stale token. */
  reset: () => void;
}

export const Recaptcha = React.forwardRef<
  RecaptchaHandle,
  { onChange: (token: string | null) => void }
>(function Recaptcha({ onChange }, ref) {
  const container = React.useRef<HTMLDivElement>(null);
  const widgetId = React.useRef<number | null>(null);
  const { resolvedTheme } = useTheme();

  // The live callback, readable from an effect that must not re-run when the
  // parent re-renders with a fresh closure.
  const handleChange = React.useRef(onChange);
  handleChange.current = onChange;

  React.useImperativeHandle(ref, () => ({
    reset: () => {
      if (widgetId.current !== null) window.grecaptcha?.reset(widgetId.current);
      handleChange.current(null);
    },
  }));

  React.useEffect(() => {
    if (!recaptchaEnabled) return;
    let cancelled = false;

    void loadRecaptcha().then(() => {
      if (cancelled || !container.current || !window.grecaptcha) return;
      widgetId.current = window.grecaptcha.render(container.current, {
        sitekey: config.recaptchaSiteKey,
        // The widget cannot restyle in place, so a theme change re-renders it
        // via the effect deps. Any token held is dropped with the old widget,
        // exactly as if it had expired.
        theme: resolvedTheme === "dark" ? "dark" : "light",
        callback: (token: string) => handleChange.current(token),
        "expired-callback": () => handleChange.current(null),
      });
    });

    return () => {
      // No unrender API, and strict mode runs this teardown between the double
      // mount - emptying the container is what stops the second render call
      // from throwing "already been rendered in this element".
      cancelled = true;
      if (container.current) container.current.innerHTML = "";
      widgetId.current = null;
      handleChange.current(null);
    };
  }, [resolvedTheme]);

  if (!recaptchaEnabled) return null;
  return <div ref={container} className="min-h-[78px]" />;
});
