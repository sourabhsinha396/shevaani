"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { config } from "@/lib/config";
import {
  clearStagedTopic,
  readStagedTopic,
  stageTopic,
} from "@/lib/impromptu-stage";
import type { ImpromptuTopic } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Stage the next impromptu spin - the operator's side of the rigged reel.
 *
 * Recording a lesson means knowing the topic before the camera rolls. Pick a
 * topic here (or type one), open `/tools/impromptu` in this same browser, and
 * the next spin lands on it with all the usual theatre. One spin, then the
 * tool is honest again.
 *
 * The stage is localStorage, so it exists only on this device - see
 * `lib/impromptu-stage.ts` for why that is the right scope. This page being
 * under /admin is curation, not security: staging only rigs your own browser.
 *
 * Topics are fetched uncached, so a row added in sqladmin a moment ago is
 * stageable immediately even though the public tool's bank lags by up to
 * five minutes.
 */
export default function AdminImpromptuPage() {
  const [topics, setTopics] = React.useState<ImpromptuTopic[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [query, setQuery] = React.useState("");
  const [custom, setCustom] = React.useState("");
  const [staged, setStaged] = React.useState<ImpromptuTopic | null>(null);

  React.useEffect(() => {
    setStaged(readStagedTopic());
    void (async () => {
      try {
        const response = await fetch(`${config.apiUrl}/api/v1/tools/impromptu/topics`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        setTopics((await response.json()) as ImpromptuTopic[]);
      } catch (e) {
        setError((e as Error).message);
        setTopics([]);
      }
    })();
  }, []);

  const stage = (topic: Pick<ImpromptuTopic, "text"> & Partial<ImpromptuTopic>) => {
    stageTopic(topic);
    setStaged(readStagedTopic());
  };

  const clear = () => {
    clearStagedTopic();
    setStaged(null);
  };

  const needle = query.trim().toLowerCase();
  const filtered = (topics ?? []).filter(
    (t) =>
      needle.length === 0 ||
      t.text.toLowerCase().includes(needle) ||
      t.track.toLowerCase().includes(needle) ||
      t.category.toLowerCase().includes(needle),
  );

  // Group by track, preserving the API's popularity order.
  const grouped: Array<{ track: string; topics: ImpromptuTopic[] }> = [];
  for (const topic of filtered) {
    const group = grouped.find((g) => g.track === topic.track);
    if (group) group.topics.push(topic);
    else grouped.push({ track: topic.track, topics: [topic] });
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <Card className="bg-muted/30">
        <CardContent className="text-muted-foreground text-sm text-pretty">
          Staging fixes the <em>next</em> spin of the impromptu tool - reel,
          ticks and all - then it goes back to random. It only works in this
          browser, so open{" "}
          <Link href="/tools/impromptu" className="text-foreground underline underline-offset-4">
            the tool
          </Link>{" "}
          in this same window when you record. Learners elsewhere are never
          affected.
        </CardContent>
      </Card>

      {staged ? (
        <Card className="border-brand-ink/40">
          <CardContent className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Staged for the next spin</p>
              <p className="font-heading mt-1 text-2xl tracking-tight">{staged.text}</p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button asChild variant="brand" size="sm">
                <Link href="/tools/impromptu">
                  Open tool <ArrowUpRight className="size-3.5" />
                </Link>
              </Button>
              <Button variant="ghost" size="sm" onClick={clear}>
                <X className="size-3.5" /> Clear
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <p className="text-muted-foreground text-sm">
          Nothing staged - the tool is spinning honestly.
        </p>
      )}

      {/* A topic that is not in the bank yet (or never will be) can still be
          staged verbatim - handy for a lesson title written for the video. */}
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (custom.trim().length === 0) return;
          stage({ text: custom.trim() });
          setCustom("");
        }}
      >
        <Input
          value={custom}
          onChange={(event) => setCustom(event.target.value)}
          placeholder="Or type any topic and stage it as-is…"
          maxLength={200}
        />
        <Button type="submit" variant="outline" disabled={custom.trim().length === 0}>
          Stage it
        </Button>
      </form>

      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search the bank - try “cosine”…"
      />

      {error && (
        <p className="text-destructive text-sm">
          Couldn&apos;t load the bank ({error}) - the custom field above still works.
        </p>
      )}

      {topics === null ? (
        <div className="text-muted-foreground flex items-center gap-2 py-12">
          <Loader2 className="size-4 animate-spin" /> Loading topics…
        </div>
      ) : (
        grouped.map((group) => (
          <div key={group.track}>
            <h2 className="text-foreground text-xs font-medium tracking-[0.15em] uppercase">
              {group.track}
            </h2>
            <ul className="mt-2 flex flex-col">
              {group.topics.map((topic) => (
                <li key={topic.text}>
                  <button
                    type="button"
                    onClick={() => stage(topic)}
                    className={cn(
                      "hover:bg-muted flex w-full items-baseline justify-between gap-4 rounded-md px-3 py-2 text-left text-sm transition-colors",
                      staged?.text === topic.text && "bg-brand/15",
                    )}
                  >
                    <span>{topic.text}</span>
                    <span className="text-muted-foreground shrink-0 text-xs">
                      {topic.category}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </div>
  );
}
