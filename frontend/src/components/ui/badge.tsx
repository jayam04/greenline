import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-micro font-medium whitespace-nowrap transition-colors",
  {
    variants: {
      tone: {
        neutral: "bg-surface-2 text-muted",
        outline: "border border-border-strong text-muted",
        gain: "bg-gain-soft text-gain",
        loss: "bg-loss-soft text-loss",
        info: "bg-info-soft text-info",
        warn: "bg-warn-soft text-warn",
        accent: "bg-accent text-accent-foreground",
      },
      variant: {
        default: "bg-surface-2 text-foreground",
        secondary: "bg-surface-2 text-muted",
        destructive: "bg-loss-soft text-loss",
        outline: "border border-border-strong text-muted",
        ghost: "text-muted hover:text-foreground",
        link: "text-info underline-offset-4 hover:underline",
      },
    },
    defaultVariants: { tone: "neutral" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  tone?: "neutral" | "outline" | "gain" | "loss" | "info" | "warn" | "accent";
  variant?: "default" | "secondary" | "destructive" | "outline" | "ghost" | "link";
}

export function Badge({
  className,
  tone,
  variant,
  ...props
}: BadgeProps) {
  const chosenTone = tone ?? (variant === "destructive" ? "loss" : variant === "outline" ? "outline" : undefined);
  return <span className={cn(badgeVariants({ tone: chosenTone, variant: tone ? undefined : variant }), className)} {...props} />;
}

const assetTone = {
  Stock: "info",
  ETF: "accent",
  Crypto: "warn",
  Cash: "gain",
  Bond: "neutral",
  Gold: "warn",
} as const;

export function AssetBadge({ type }: { type: keyof typeof assetTone }) {
  return <Badge tone={assetTone[type]}>{type}</Badge>;
}

/** Profit / loss pill with arrow. Value is a percentage. */
export function TrendBadge({ value, digits = 2 }: { value: number; digits?: number }) {
  const tone = value > 0 ? "gain" : value < 0 ? "loss" : "neutral";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "–";
  return (
    <Badge tone={tone} className="tnum">
      <span aria-hidden className="text-[0.6rem]">{arrow}</span>
      {Math.abs(value).toFixed(digits)}%
    </Badge>
  );
}

export { badgeVariants };
