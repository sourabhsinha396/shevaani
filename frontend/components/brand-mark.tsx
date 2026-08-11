import { cn } from "@/lib/utils";

/**
 * The Shevaani mark: three bars at speaking levels, inside the split ring the
 * rest of the family uses - so the products read as siblings without sharing a
 * glyph. Since our brand colour is the same lime algoholic uses, the bars are
 * the only thing telling the two marks apart; keep them.
 *
 * Drawn in `currentColor`, so the colour comes from a text utility on the
 * caller. `text-brand-ink` is the brand-correct one and already flips for dark
 * mode. `app/icon.svg` is this same artwork for the browser tab, which can't
 * see Tailwind and so carries its own colours in a media query.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      // Decorative: every lockup pairs this with the wordmark, which already
      // names the brand to a screen reader.
      aria-hidden="true"
      className={cn("size-7", className)}
    >
      <g
        opacity="0.6"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      >
        <path d="M23.27 26.78A13 13 0 0 1 5.22 8.73" />
        <path d="M8.73 5.22A13 13 0 0 1 26.78 23.27" />
      </g>
      <g stroke="currentColor" strokeWidth="3.2" strokeLinecap="round">
        <path d="M11.6 13.2V18.8" />
        <path d="M16 9.6V22.4" />
        <path d="M20.4 12.2V19.8" />
      </g>
    </svg>
  );
}
