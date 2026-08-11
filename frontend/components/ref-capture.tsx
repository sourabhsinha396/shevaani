"use client";

import * as React from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { rememberReferralCode } from "@/lib/referral";

function Capture() {
  const params = useSearchParams();
  const pathname = usePathname();
  const code = params.get("r");

  React.useEffect(() => {
    rememberReferralCode(code);
  }, [code, pathname]);

  return null;
}

/**
 * Watches every page for a `?r=` referral code and stashes it for the signup
 * form. Mounted once in the root layout; renders nothing.
 *
 * Its own Suspense boundary because `useSearchParams` demands one, and the
 * root layout should not have to know that.
 */
export function RefCapture() {
  return (
    <React.Suspense fallback={null}>
      <Capture />
    </React.Suspense>
  );
}
