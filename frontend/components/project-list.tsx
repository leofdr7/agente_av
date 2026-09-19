import Link from "next/link";

import { StatusDot } from "@/components/status-dot";
import { Sheet } from "@/components/page-header";
import type { Project } from "@/lib/api";
import { formatBudget } from "@/lib/format";

export function ProjectList({ projects }: { projects: Project[] }) {
  return (
    <Sheet>
      <ul className="divide-y divide-ink/10">
        {projects.map((project) => (
          <li key={project.id}>
            <Link
              href={`/proyectos/${project.id}`}
              className="flex items-baseline justify-between gap-4 px-4 py-3.5 hover:bg-paper/80"
            >
              <span className="min-w-0">
                <span className="block truncate font-medium text-ink">
                  {project.name}
                </span>
                <StatusDot status={project.status} />
              </span>
              <span className="shrink-0 font-mono text-sm text-steel">
                {formatBudget(project.budget)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}
