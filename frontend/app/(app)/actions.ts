"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  formatApiError,
  type AgentRunResponse,
  type Project,
  type ReportFile,
  type ReportGenerationResponse,
} from "@/lib/api";
import { serverApiFetch } from "@/lib/api.server";

export type ActionState = { error: string } | null;

function parseBudget(raw: FormDataEntryValue | null): number | null | { error: string } {
  const text = String(raw ?? "").trim().replace(",", ".");
  if (!text) return null;
  const value = Number(text);
  if (!Number.isFinite(value) || value < 0) {
    return { error: "El presupuesto debe ser un número mayor o igual a cero." };
  }
  return value;
}

export async function submitEstimation(
  _prev: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const mode = String(formData.get("mode") ?? "");
  const problemText = String(formData.get("problem_text") ?? "").trim();
  if (!problemText) {
    return { error: "Describe el problema vectorial a resolver." };
  }

  const budget = parseBudget(formData.get("budget"));
  if (typeof budget === "object" && budget !== null) {
    return budget;
  }

  let projectId = "";
  let estimationId = "";
  try {
    if (mode === "new") {
      const name = String(formData.get("project_name") ?? "").trim();
      if (!name) {
        return { error: "Ponle un nombre al proyecto." };
      }
      const project = await serverApiFetch<Project>("/api/v1/projects", {
        method: "POST",
        body: { name, budget, status: "active" },
      });
      projectId = project.id;
    } else {
      projectId = String(formData.get("project_id") ?? "").trim();
      if (!projectId) {
        return { error: "Selecciona un proyecto o crea uno nuevo." };
      }
      if (budget !== null) {
        await serverApiFetch<Project>(`/api/v1/projects/${projectId}`, {
          method: "PATCH",
          body: { budget },
        });
      }
    }

    const result = await serverApiFetch<AgentRunResponse>("/api/v1/agent/run", {
      method: "POST",
      body: {
        problem_text: problemText,
        project_id: projectId,
      },
    });
    estimationId = result.estimation_id;
  } catch (error) {
    return { error: formatApiError(error) };
  }

  revalidatePath("/");
  revalidatePath("/historial");
  revalidatePath(`/proyectos/${projectId}`);
  redirect(`/estimaciones/${estimationId}`);
}

export async function generateReport(
  estimationId: string,
): Promise<{ ok: true; reports: ReportFile[] } | { ok: false; error: string }> {
  try {
    const result = await serverApiFetch<ReportGenerationResponse>(
      `/api/v1/estimations/${estimationId}/report`,
      { method: "POST" },
    );
    revalidatePath(`/estimaciones/${estimationId}`);
    return { ok: true, reports: result.reports };
  } catch (error) {
    return { ok: false, error: formatApiError(error) };
  }
}
