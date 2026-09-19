import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ProjectList } from "@/components/project-list";
import { buttonVariants } from "@/components/ui/button";
import { formatApiError, type Project } from "@/lib/api";
import { serverApiFetch } from "@/lib/api.server";
import { cn } from "cn";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let projects: Project[] = [];
  let error: string | null = null;
  try {
    projects = await serverApiFetch<Project[]>("/api/v1/projects");
  } catch (caught) {
    error = formatApiError(caught);
  }

  return (
    <>
      <PageHeader
        title="Proyectos"
        description="Expedientes de la planta con su estado y presupuesto."
      >
        <Link href="/nueva" className={cn(buttonVariants(), "h-9")}>
          Nueva estimación
        </Link>
      </PageHeader>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : projects.length === 0 ? (
        <EmptyState
          title="Todavía no hay proyectos"
          body="La primera estimación abre el expediente. Elige un nombre, un presupuesto y describe el problema."
          href="/nueva"
          action="Nueva estimación"
        />
      ) : (
        <ProjectList projects={projects} />
      )}
    </>
  );
}
