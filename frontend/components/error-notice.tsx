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
        "border-l-[3px] border-destructive bg-sheet px-3 py-2 text-sm dark:bg-destructive/15",
        className,
      )}
    >
      <p className="font-medium text-ink">{title}</p>
      <p className="mt-0.5 text-destructive">{children}</p>
    </div>
  );
}
