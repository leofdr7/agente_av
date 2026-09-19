import type { ReactNode } from "react";
import { cn } from "cn";

export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: ReactNode;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="border-l-[3px] border-copper pl-3">
        {eyebrow ? (
          <div className="font-mono text-[11px] text-steel">{eyebrow}</div>
        ) : null}
        <h1 className="text-2xl font-medium tracking-tight text-ink">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-prose text-sm text-steel">{description}</p>
        ) : null}
      </div>
      {children ? <div className="sm:pb-0.5">{children}</div> : null}
    </header>
  );
}

export function Sheet({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "bg-sheet ring-1 ring-ink/10",
        className,
      )}
    >
      {children}
    </div>
  );
}
