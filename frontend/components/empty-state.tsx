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
    <div className="border-l-[3px] border-primary bg-sheet px-6 py-10 sm:px-10">
      <p className="text-xl font-medium tracking-tight text-ink">{title}</p>
      <p className="mt-3 max-w-md text-sm leading-relaxed text-steel">{body}</p>
      {href && action ? (
        <Link href={href} className={cn(buttonVariants(), "mt-5 h-9")}>
          {action}
        </Link>
      ) : null}
    </div>
  );
}
