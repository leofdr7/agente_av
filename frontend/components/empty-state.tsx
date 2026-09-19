import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "cn";

export function EmptyState({
  title,
  body,
  href,
  action,
}: {
  title: string;
  body: string;
  href?: string;
  action?: string;
}) {
  return (
    <div className="border border-dashed border-ink/20 bg-sheet/60 px-4 py-10">
      <p className="text-base font-medium text-ink">{title}</p>
      <p className="mt-1 max-w-md text-sm text-steel">{body}</p>
      {href && action ? (
        <Link href={href} className={cn(buttonVariants(), "mt-5 h-9")}>
          {action}
        </Link>
      ) : null}
    </div>
  );
}

