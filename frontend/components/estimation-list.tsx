import Link from "next/link";

import { Sheet } from "@/components/page-header";
import type { EstimationSummary } from "@/lib/api";
import { excerpt, formatWhen } from "@/lib/format";

export function EstimationList({
  estimations,
}: {
  estimations: EstimationSummary[];
}) {
  return (
    <Sheet>
      <ul className="divide-y divide-ink/10">
        {estimations.map((item) => (
          <li key={item.id}>
            <Link
              href={`/estimaciones/${item.id}`}
              className="block px-4 py-3.5 hover:bg-paper/80"
            >
              <span className="flex items-baseline justify-between gap-3">
                <span className="truncate text-sm font-medium text-ink">
                  {item.project_name}
                </span>
                <time
                  dateTime={item.created_at}
                  className="shrink-0 font-mono text-[11px] text-steel"
                >
                  {formatWhen(item.created_at)}
                </time>
              </span>
              <p className="mt-1 text-sm text-steel">
                {excerpt(item.problem_text)}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}
