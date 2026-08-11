import * as React from "react";

import type { FeedbackMetrics } from "@/lib/types";

/**
 * Renders a feedback report's markdown.
 *
 * Deliberately not a markdown library: the backend renders reports from a
 * fixed template (`services/feedback.py::render_report`), so the grammar is
 * known — `##` headings, `-` bullets, `1.` numbered lists, `**bold**`,
 * `*italic*` — and everything is emitted as React text nodes, never raw HTML.
 * A model-authored string goes nowhere near `dangerouslySetInnerHTML`.
 */

function inline(text: string, keyBase: string): React.ReactNode[] {
  // Split out **bold** first, then *italic* inside the remaining plain runs.
  const nodes: React.ReactNode[] = [];
  text.split(/(\*\*[^*]+\*\*)/g).forEach((chunk, i) => {
    if (chunk.startsWith("**") && chunk.endsWith("**")) {
      nodes.push(<strong key={`${keyBase}-b${i}`}>{chunk.slice(2, -2)}</strong>);
      return;
    }
    chunk.split(/(\*[^*]+\*)/g).forEach((piece, j) => {
      if (piece.startsWith("*") && piece.endsWith("*") && piece.length > 2) {
        nodes.push(
          <em key={`${keyBase}-i${i}-${j}`} className="text-muted-foreground">
            {piece.slice(1, -1)}
          </em>,
        );
      } else if (piece) {
        nodes.push(piece);
      }
    });
  });
  return nodes;
}

type Block =
  | { kind: "heading"; text: string }
  | { kind: "bullets"; items: string[] }
  | { kind: "numbered"; items: string[] }
  | { kind: "paragraph"; text: string };

function parse(markdown: string): Block[] {
  const blocks: Block[] = [];
  for (const line of markdown.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("## ")) {
      blocks.push({ kind: "heading", text: trimmed.slice(3) });
    } else if (trimmed.startsWith("- ")) {
      const last = blocks[blocks.length - 1];
      if (last?.kind === "bullets") last.items.push(trimmed.slice(2));
      else blocks.push({ kind: "bullets", items: [trimmed.slice(2)] });
    } else if (/^\d+\.\s/.test(trimmed)) {
      const text = trimmed.replace(/^\d+\.\s/, "");
      const last = blocks[blocks.length - 1];
      if (last?.kind === "numbered") last.items.push(text);
      else blocks.push({ kind: "numbered", items: [text] });
    } else {
      blocks.push({ kind: "paragraph", text: trimmed });
    }
  }
  return blocks;
}

export function ReportView({ markdown }: { markdown: string }) {
  return (
    <div className="space-y-4 text-sm leading-relaxed">
      {parse(markdown).map((block, i) => {
        switch (block.kind) {
          case "heading":
            return (
              <h3 key={i} className="text-foreground pt-2 text-base font-medium tracking-tight">
                {block.text}
              </h3>
            );
          case "bullets":
            return (
              <ul key={i} className="ml-4 list-disc space-y-1.5">
                {block.items.map((item, j) => (
                  <li key={j}>{inline(item, `${i}-${j}`)}</li>
                ))}
              </ul>
            );
          case "numbered":
            return (
              <ol key={i} className="ml-4 list-decimal space-y-1.5">
                {block.items.map((item, j) => (
                  <li key={j}>{inline(item, `${i}-${j}`)}</li>
                ))}
              </ol>
            );
          default:
            return <p key={i}>{inline(block.text, `${i}`)}</p>;
        }
      })}
    </div>
  );
}

/** The deterministic numbers as a compact chip row, when there are any. */
export function MetricsRow({ metrics }: { metrics: FeedbackMetrics }) {
  if (metrics.talk_time_seconds == null) return null;
  const chips = [
    `${(metrics.talk_time_seconds / 60).toFixed(1)} min speaking`,
    metrics.talk_share != null ? `${Math.round(metrics.talk_share * 100)}% of the room` : null,
    metrics.turns != null ? `${metrics.turns} turns` : null,
    metrics.questions_asked != null ? `${metrics.questions_asked} questions` : null,
  ].filter(Boolean);
  return (
    <div className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {chips.map((chip) => (
        <span key={chip as string}>{chip}</span>
      ))}
    </div>
  );
}
