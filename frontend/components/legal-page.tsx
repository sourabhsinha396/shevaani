import * as React from "react";

/**
 * The shell every policy page sits in.
 *
 * Legal text is read by two audiences: a learner checking one specific thing,
 * and a payment provider's reviewer checking the page exists and says something
 * concrete. Both want a narrow measure, real headings, and a visible "last
 * updated" - so that lives here rather than being re-typed per page.
 */
export function LegalPage({
  title,
  updated,
  intro,
  children,
}: {
  title: string;
  updated: string;
  intro?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <article className="mx-auto max-w-3xl px-4 py-16 md:py-20">
      <h1 className="text-4xl tracking-tight text-balance">{title}</h1>
      <p className="text-muted-foreground mt-3 text-sm">Last updated {updated}</p>
      {intro && (
        <div className="text-muted-foreground mt-6 text-pretty">{intro}</div>
      )}

      {/* Spacing, not a typography plugin: the site has no `prose` dependency
          and the handful of tags used here are easier to control directly. */}
      <div
        className={[
          "mt-12 flex flex-col gap-6 text-[0.9375rem] leading-relaxed",
          "[&_h2]:mt-6 [&_h2]:text-2xl [&_h2]:tracking-tight",
          "[&_h3]:mt-2 [&_h3]:font-medium",
          "[&_p]:text-muted-foreground [&_p]:text-pretty",
          "[&_ul]:text-muted-foreground [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-2 [&_ul]:pl-5",
          "[&_li]:list-disc [&_li]:marker:text-border",
          "[&_a]:underline [&_a]:underline-offset-4 [&_a:hover]:text-foreground",
          "[&_strong]:text-foreground [&_strong]:font-medium",
        ].join(" ")}
      >
        {children}
      </div>
    </article>
  );
}
