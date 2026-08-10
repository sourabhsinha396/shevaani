import { type ComponentPropsWithoutRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface BentoGridProps extends ComponentPropsWithoutRef<"div"> {
  children: ReactNode;
  className?: string;
}

interface BentoCardProps extends ComponentPropsWithoutRef<"div"> {
  name: string;
  description: string;
  Icon: React.ElementType;
  /** A decorative wash behind the copy. Absolutely positioned by the caller. */
  background?: ReactNode;
  className?: string;
}

/**
 * Fixed-height rows are the whole trick of a bento: cards of different widths
 * still line up, so the grid reads as one object rather than seven cards that
 * happen to sit near each other.
 */
const BentoGrid = ({ children, className, ...props }: BentoGridProps) => (
  <div
    className={cn("grid w-full auto-rows-[16rem] grid-cols-3 gap-4", className)}
    {...props}
  >
    {children}
  </div>
);

/**
 * Copy sits at the bottom, wash at the top. On hover a single beam travels the
 * border — no link, no lift, nothing that moves the text you are reading.
 */
const BentoCard = ({
  name,
  description,
  Icon,
  background,
  className,
  ...props
}: BentoCardProps) => (
  <div
    className={cn(
      "group bg-card relative col-span-3 flex flex-col justify-between overflow-hidden rounded-xl",
      "[box-shadow:0_0_0_1px_rgba(0,0,0,.04),0_2px_4px_rgba(0,0,0,.05),0_12px_24px_rgba(0,0,0,.05)]",
      "transform-gpu dark:[border:1px_solid_rgba(255,255,255,.1)] dark:[box-shadow:0_-20px_80px_-20px_#ffffff1f_inset]",
      className,
    )}
    {...props}
  >
    <div aria-hidden>{background}</div>

    <div className="relative p-6">
      <Icon className="text-brand-ink size-9" />
      <h3 className="mt-4 text-lg font-medium">{name}</h3>
      <p className="text-muted-foreground mt-1.5 max-w-lg text-sm text-pretty">
        {description}
      </p>
    </div>

    {/* The border effect. A conic wedge spins behind the card; the mask keeps
        it to the border box alone, so what shows is a light running the
        perimeter. Same masking trick as BorderBeam, without the dependency. */}
    <span
      aria-hidden
      className="pointer-events-none absolute inset-0 rounded-[inherit] border border-transparent opacity-0 mask-[linear-gradient(transparent,transparent),linear-gradient(#000,#000)] mask-intersect transition-opacity duration-500 [mask-clip:padding-box,border-box] group-hover:opacity-100"
    >
      <span className="absolute top-1/2 left-1/2 aspect-square w-[150%] -translate-x-1/2 -translate-y-1/2 [background:conic-gradient(from_0deg,transparent_0deg,var(--brand)_35deg,var(--brand-ink)_65deg,transparent_140deg)] motion-safe:animate-[border-sweep_4s_linear_infinite]" />
    </span>

    <span
      aria-hidden
      className="pointer-events-none absolute inset-0 rounded-[inherit] transition-colors duration-300 group-hover:bg-black/[0.02] dark:group-hover:bg-white/[0.03]"
    />
  </div>
);

export { BentoCard, BentoGrid };
