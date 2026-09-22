import Link from "next/link";
import { FolderClosed } from "lucide-react";

import { StatusDot } from "@/components/status-dot";
import { Sheet } from "@/components/page-header";
import type { Project } from "@/lib/api";
import { formatBudget } from "@/lib/format";

export function ProjectList({ projects }: { projects: Project[] }) {
  return (
    <Sheet className="project-register">
      <div className="project-register-heading" aria-hidden>
        <span>Expedientes</span>
        <span>Presupuesto</span>
      </div>
      <ul className="divide-y divide-border border-t border-border">
        {projects.map((project) => (
          <li key={project.id}>
            <Link
              href={`/proyectos/${project.id}`}
              className="project-row"
            >
              <FolderClosed className="project-glyph" aria-hidden />
              <span className="min-w-0">
                <span className="project-name text-ink">
                  {project.name}
                </span>
                <span className="mt-2 block"><StatusDot status={project.status} /></span>
              </span>
              <span className="project-budget text-ink">
                {formatBudget(project.budget)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}
