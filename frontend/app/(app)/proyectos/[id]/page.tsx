import Link from "next/link";
import { notFound } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { ErrorNotice } from "@/components/error-notice";
import { EstimationList } from "@/components/estimation-list";
import { PageHeader } from "@/components/page-header";
import { StatusDot } from "@/components/status-dot";
import { buttonVariants } from "@/components/ui/button";
import {
  ApiError,
  formatApiError,
  type EstimationSummary,
  type Project,
} from "@/lib/api";
import { serverApiFetch } from "@/lib/api.server";
import { formatBudget } from "@/lib/format";
import { cn } from "cn";

export const dynamic = "force-dynamic";

export default async function ProyectoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let project: Project | null = null;
  let loadError: string | null = null;
  try {
    project = await serverApiFetch<Project>(`/api/v1/projects/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    loadError = formatApiError(error);
  }

  if (loadError || !project) {
    return (
      <ErrorNotice title="No se pudo abrir el proyecto">
        {loadError ?? "No se pudo cargar el proyecto."}
      </ErrorNotice>
    );
  }

  let estimations: EstimationSummary[] = [];
  let listError: string | null = null;
  try {
    estimations = await serverApiFetch<EstimationSummary[]>(
      `/api/v1/projects/${id}/estimations`,
    );
  } catch (caught) {
    listError = formatApiError(caught);
  }

  return (
    <>
      <PageHeader
        eyebrow={<StatusAndBudget project={project} />}
        title={project.name}
        description="Estimaciones de este expediente."
      >
        <Link href="/nueva" className={cn(buttonVariants({ variant: "outline" }), "h-9 bg-sheet")}>
          Nueva estimación
        </Link>
      </PageHeader>

      {listError ? (
        <ErrorNotice title="No se pudieron cargar las estimaciones">
          {listError}
        </ErrorNotice>
      ) : estimations.length === 0 ? (
        <EmptyState
          title="Este proyecto no tiene estimaciones"
          body="Envía un problema vectorial para dejar la primera corrida en el expediente."
          href="/nueva"
          action="Nueva estimación"
        />
      ) : (
        <EstimationList estimations={estimations} />
      )}
    </>
  );
}

function StatusAndBudget({ project }: { project: Project }) {
  return (
    <span className="inline-flex items-center gap-3">
      <StatusDot status={project.status} />
      <span className="font-mono text-[11px] text-steel">
        {formatBudget(project.budget)}
      </span>
    </span>
  );
}
