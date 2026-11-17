import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Page header: title, one-line description, primary actions.
 * No breadcrumbs and no tab bar: the sidebar is the only navigation.
 */
export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("mb-6 flex flex-wrap items-end justify-between gap-4", className)}>
      <div>
        <h1 className="text-heading font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-body text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}

export function EmptyState({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="flex flex-col items-center rounded-card border border-dashed border-border-strong px-6 py-12 text-center">
      <div className="mb-3 text-subtle [&_svg]:size-8">{icon}</div>
      <div className="text-body font-semibold">{title}</div>
      <p className="mt-1 max-w-sm text-label text-muted">{body}</p>
    </div>
  );
}
