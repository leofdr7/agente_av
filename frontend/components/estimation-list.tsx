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
    <Sheet className="history-register">
      <ul className="divide-y divide-border">
        {estimations.map((item) => (
          <li key={item.id}>
            <Link
              href={`/estimaciones/${item.id}`}
              className="history-entry"
            >
                <time
                  dateTime={item.created_at}
                  className="history-date"
                >
                  {formatWhen(item.created_at)}
                </time>
              <div className="history-copy">
                <span className="project-name text-ink">{item.project_name}</span>
                <p className="mt-2 text-sm text-steel">
                  {excerpt(item.problem_text)}
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}
