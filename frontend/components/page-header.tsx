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
    <header className="page-header flex flex-col lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <h1 className="page-title text-ink">{title}</h1>
        {description ? (
          <p className="page-description">
            {description}
          </p>
        ) : null}
        {eyebrow ? <div className="page-context">{eyebrow}</div> : null}
      </div>
      {children ? <div className="shrink-0 lg:pb-1">{children}</div> : null}
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
        "sheet",
        className,
      )}
    >
      {children}
    </div>
  );
}
