import { notFound } from "next/navigation";

import { ErrorNotice } from "@/components/error-notice";
import { EstimationResult } from "@/components/estimation-result";
import { ApiError, formatApiError, type EstimationDetail } from "@/lib/api";
import { serverApiFetch } from "@/lib/api.server";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

export default async function EstimacionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let estimation: EstimationDetail | null = null;
  let error: string | null = null;
  try {
    estimation = await serverApiFetch<EstimationDetail>(
      `/api/v1/estimations/${id}`,
    );
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) {
      notFound();
    }
    error = formatApiError(caught);
  }

  if (error || !estimation) {
    return (
      <ErrorNotice title="No se pudo abrir la estimación">
        {error ?? "No se pudo cargar la estimación."}
      </ErrorNotice>
    );
  }

  return <EstimationResult estimation={estimation} />;
}
