/**
 * Server-safe helpers for rich-text description fields.
 *
 * Descriptions are authored in Tiptap (see `components/ui/rich-text.tsx`) and
 * stored as HTML, but two consumers must never see tags: `<meta description>`
 * and JSON-LD. These run on the server, so the stripping is string work, not
 * DOM work.
 *
 * Descriptions written before the editor existed are plain text with
 * newlines; `looksLikeHtml` is how the renderer and the editor decide which
 * kind they are holding.
 */

export function looksLikeHtml(value: string): boolean {
  return /<[a-z][^>]*>/i.test(value);
}

const ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#39;": "'",
  "&nbsp;": " ",
};

/** HTML → single-line plain text, for meta descriptions and structured data. */
export function richTextToPlain(html: string): string {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (entity) => ENTITIES[entity] ?? entity)
    .replace(/\s+/g, " ")
    .trim();
}
