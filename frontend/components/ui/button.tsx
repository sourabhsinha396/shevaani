import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/* Every button is a pill. The variants differ only in fill, never in shape —
   which is what lets a row of mixed actions read as one control group. */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-all outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0",
  {
    variants: {
      variant: {
        // Neutral-but-loud: the highest-contrast thing available in a grey
        // system. Use where brand would be too much (dense tables, cards).
        default:
          "bg-foreground text-background hover:bg-foreground/90 active:translate-y-px",
        // The one saturated control on the page. At most one per view.
        brand:
          "bg-brand text-brand-foreground hover:opacity-90 active:translate-y-px",
        // Transparent, not `bg-background` — on a card the page background
        // would read as a hole punched through it.
        outline:
          "border-border hover:bg-muted hover:text-foreground border bg-transparent",
        secondary:
          "bg-secondary text-secondary-foreground border-border hover:bg-secondary/80 border",
        ghost: "hover:bg-muted hover:text-foreground",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        link: "rounded-none text-foreground underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-5 py-2 has-[>svg]:px-4",
        sm: "h-8 px-3.5 text-xs has-[>svg]:px-3",
        lg: "h-12 px-6 text-base has-[>svg]:px-5",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
