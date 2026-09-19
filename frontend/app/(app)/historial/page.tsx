import { EmptyState } from "@/components/empty-state";
import { EstimationList } from "@/components/estimation-list";
import { PageHeader } from "@/components/page-header";
import { formatApiError, type EstimationSummary } from "@/lib/api";
import { serverApiFetch } from "@/lib/api.server";

export const dynamic = "force-dynamic";

export default async function HistorialPage() {
  let estimations: EstimationSummary[] = [];
  let error: string | null = null;
  try {
    estimations = await serverApiFetch<EstimationSummary[]>("/api/v1/estimations");
  } catch (caught) {
    error = formatApiError(caught);
  }

  return (
    <>
      <PageHeader
        title="Historial"
        description="Corridas anteriores, de todos los proyectos."
      />
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : estimations.length === 0 ? (
        <EmptyState
          title="Aún no hay estimaciones"
          body="Cuando envíes un problema, la traza y el resumen quedan aquí."
          href="/nueva"
          action="Nueva estimación"
        />
      ) : (
        <EstimationList estimations={estimations} />
      )}
    </>
  );
}
