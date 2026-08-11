"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { SITE_FLAGS } from "@/lib/site-config";
import type { SiteConfig } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The feature switches, one row each.
 *
 * There is no per-flag markup here: the list comes from `SITE_FLAGS`, so adding
 * a switch to this screen is one entry there plus the field on `SiteConfig`.
 * That is the whole reason the flags are typed columns rather than a key/value
 * table - the label and the prose have to live somewhere anyway, and here they
 * sit next to a key the compiler checks.
 *
 * Each toggle saves on click rather than collecting into a Save button. One
 * switch is one decision, and a settings page with an unsaved-changes state is a
 * settings page you can walk away from mid-thought.
 */

/** Local rather than a `ui/` primitive: this is the only switch on the site, and
 *  a shared component would be one more thing to keep in step with a design that
 *  has exactly one caller. `role="switch"` is what makes it a switch to a screen
 *  reader; the div is decoration. */
function Toggle({
  checked,
  busy,
  label,
  onChange,
}: {
  checked: boolean;
  busy: boolean;
  label: string;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={busy}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50",
        // The brand fill is the site's one "this is on" colour; off borrows the
        // same grey the muted chrome uses so a row of switches reads as chrome.
        checked ? "bg-brand" : "bg-muted-foreground/30",
      )}
    >
      <span
        className={cn(
          "bg-background size-5 rounded-full shadow transition-transform",
          checked ? "translate-x-[1.375rem]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

export default function AdminSettingsPage() {
  const [config, setConfig] = React.useState<SiteConfig | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState<keyof SiteConfig | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    void (async () => {
      try {
        setConfig(await api.adminSiteConfig());
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function toggle(key: keyof SiteConfig, next: boolean) {
    setSaving(key);
    setError(null);
    try {
      // The response is the whole config, so the screen re-syncs with whatever
      // the server actually holds - including a flag somebody else just moved
      // in another tab.
      setConfig(await api.adminUpdateSiteConfig({ [key]: next }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(null);
    }
  }

  if (loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-24">
        <Loader2 className="size-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="bg-muted/30">
        <CardContent className="text-muted-foreground text-sm">        
          The public site caches these for about a minute, so give it that long
          before deciding a change did not take. Anything the switch forbids is
          refused by the API immediately, cache or no cache.
        </CardContent>
      </Card>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {config &&
        SITE_FLAGS.map((flag) => (
          <Card key={flag.key}>
            <CardContent className="flex items-start justify-between gap-6">
              <div>
                <p className="font-medium">{flag.label}</p>
                <p className="text-muted-foreground mt-1 text-sm text-pretty">
                  {flag.description}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <span className="text-muted-foreground w-6 text-sm">
                  {saving === flag.key ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    (config[flag.key] ? "On" : "Off")
                  )}
                </span>
                <Toggle
                  checked={config[flag.key]}
                  busy={saving !== null}
                  label={flag.label}
                  onChange={(next) => void toggle(flag.key, next)}
                />
              </div>
            </CardContent>
          </Card>
        ))}
    </div>
  );
}
