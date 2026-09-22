"use client";

import { cn } from "cn";

export function ErrorNotice({
  title = "No se pudo completar",
  children,
  className,
}: {
  title?: string;
  children: string;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "border-l-4 border-destructive bg-[var(--alert-soft)] px-5 py-4 text-sm leading-relaxed",
        className,
      )}
    >
      <p className="font-medium text-ink">{title}</p>
      <p className="mt-0.5 text-destructive">{children}</p>
    </div>
  );
}
