import { ErrorNotice } from "@/components/error-notice";
import { EstimationForm } from "@/components/estimation-form";
import { PageHeader } from "@/components/page-header";
import { formatApiError, type Project } from "@/lib/api";
import { serverApiFetch } from "@/lib/api.server";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

export default async function NuevaPage() {
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
        title="Nueva estimación"
        description="Elige o crea el proyecto, anota el presupuesto y describe el sistema en lenguaje de planta."
      />
      {error ? (
        <ErrorNotice title="No se pudieron cargar los proyectos">{error}</ErrorNotice>
      ) : (
        <EstimationForm projects={projects} />
      )}
    </>
  );
}
