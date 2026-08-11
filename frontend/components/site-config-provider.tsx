"use client";

import * as React from "react";

import { DEFAULT_SITE_CONFIG } from "@/lib/site-config";
import type { SiteConfig } from "@/lib/types";

/**
 * The feature flags, handed down from the server render.
 *
 * No fetching here on purpose. `useOneOnOneAvailability` has to probe from the
 * browser because its answer depends on a calendar that moves during a visit;
 * this one is the same for everybody and known before the HTML is written, so
 * fetching it client-side would only buy a frame of wrong chrome - the nav
 * rendering a link and then deleting it, on every load.
 *
 * The default is the context default too, so a component mounted outside the
 * provider reads "everything on" rather than throwing. Same rule as everywhere
 * else in this feature: a failure shows the site, not an empty one.
 */
const SiteConfigContext = React.createContext<SiteConfig>(DEFAULT_SITE_CONFIG);

export function SiteConfigProvider({
  config,
  children,
}: {
  config: SiteConfig;
  children: React.ReactNode;
}) {
  return <SiteConfigContext.Provider value={config}>{children}</SiteConfigContext.Provider>;
}

export function useSiteConfig(): SiteConfig {
  return React.useContext(SiteConfigContext);
}
