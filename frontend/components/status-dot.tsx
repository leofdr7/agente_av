import { cn } from "cn";

import type { ProjectStatus } from "@/lib/api";
import { PROJECT_STATUS_LABEL } from "@/lib/format";

export function StatusDot({ status }: { status: ProjectStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-steel">
      <span
        aria-hidden
        className={cn(
          "size-2 shrink-0 rounded-full",
          status === "active" && "bg-copper",
          status === "draft" && "bg-steel/50",
          status === "on_hold" && "bg-steel",
          status === "completed" && "bg-[var(--verification)]",
          status === "archived" && "bg-ink/30",
        )}
      />
      {PROJECT_STATUS_LABEL[status]}
    </span>
  );
}
