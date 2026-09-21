/**
 * Cliente HTTP centralizado hacia el backend FastAPI.
 *
 * No depende de Clerk directamente: recibe un `getToken` para poder usarse
 * tanto desde Server Components (`auth().getToken`) como desde Client
 * Components (`useAuth().getToken`). Ver `lib/api.server.ts` y `hooks/use-api.ts`.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ?? "http://localhost:8000";

export type TokenGetter = () => Promise<string | null>;

export interface Employee {
  id: string;
  clerk_user_id: string;
  name: string;
  role: string;
  created_at: string;
}

export type ProjectStatus =
  | "draft"
  | "active"
  | "on_hold"
  | "completed"
  | "archived";

export interface Project {
  id: string;
  name: string;
  budget: number | null;
  status: ProjectStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface EstimationSummary {
  id: string;
  problem_text: string;
  project_id: string;
  project_name: string;
  requested_by: string;
  created_at: string;
}

export interface ToolCallRecord {
  name: string;
  input: Record<string, unknown>;
  output: unknown;
  is_error: boolean;
}

export interface AgentRunTrace {
  A?: number[][] | null;
  B?: number[] | null;
  variable_names?: string[] | null;
  resource_names?: string[] | null;
  tools: ToolCallRecord[];
  cross_validation?: unknown;
  substitution?: unknown;
  feasibility?: unknown;
  final_response: string;
  model: string;
}

export interface ReportFile {
  id: string;
  file_url: string;
  file_type: "pdf" | "docx";
  generated_at: string;
}

export interface EstimationDetail {
  id: string;
  problem_text: string;
  result_json: AgentRunTrace | null;
  project_id: string;
  project: Project;
  requested_by: string;
  created_at: string;
  reports: ReportFile[];
}

export interface AgentRunResponse {
  estimation_id: string;
  final_response: string;
  result_json: AgentRunTrace;
}

export interface ReportGenerationResponse {
  estimation_id: string;
  reports: ReportFile[];
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(messageFromDetail(detail, status));
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const STATUS_HINTS: Record<number, string> = {
  401: "Tu sesión caducó. Vuelve a iniciar sesión.",
  403: "No tienes permiso para esta operación.",
  404: "No se encontró lo que pediste.",
  409: "Todavía no hay un resultado para generar el informe.",
  429: "Has alcanzado el límite de estimaciones de esta hora. Espera un rato para no disparar costos de la API.",
  500: "No se pudo completar la operación. Si se generó una estimación, queda en el historial.",
  503: "El servicio no está disponible ahora. Reintenta en unos minutos.",
};

export function messageFromDetail(detail: unknown, status?: number): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      return "";
    });
    const joined = parts.filter(Boolean).join(" ");
    if (joined) return joined;
  }
  if (detail && typeof detail === "object") {
    const record = detail as { message?: unknown; detail?: unknown };
    if (typeof record.message === "string" && record.message.trim()) {
      return record.message;
    }
    if (record.detail !== undefined && record.detail !== detail) {
      return messageFromDetail(record.detail, status);
    }
  }
  if (status && STATUS_HINTS[status]) {
    return STATUS_HINTS[status];
  }
  return status ? `Error HTTP ${status}` : "Error inesperado.";
}

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) {
    const hint = STATUS_HINTS[error.status];
    if (error.status === 429 && hint) {
      return hint;
    }
    const backend = error.message.trim();
    if (backend && backend !== `Error HTTP ${error.status}`) {
      return backend;
    }
    return hint ?? backend;
  }
  if (error instanceof TypeError) {
    return "No se pudo contactar al backend. ¿Está uvicorn en marcha?";
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "No se pudo contactar al backend. ¿Está uvicorn en marcha?";
}

export interface ApiRequestInit extends Omit<RequestInit, "body"> {
  body?: unknown;
}

export async function apiFetch<T>(
  path: string,
  getToken: TokenGetter,
  init: ApiRequestInit = {},
): Promise<T> {
  const token = await getToken();
  if (!token) {
    throw new ApiError(401, "No hay sesión activa.");
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Accept", "application/json");

  let body: BodyInit | undefined;
  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.body);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    body,
    cache: init.cache ?? "no-store",
  });

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const payload = (await response.json()) as {
        message?: unknown;
        detail?: unknown;
      };
      detail = payload.message ?? payload.detail ?? payload;
    } catch {
      // Sin cuerpo JSON: se conserva el statusText.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function fetchCurrentEmployee(getToken: TokenGetter): Promise<Employee> {
  return apiFetch<Employee>("/api/v1/me", getToken);
}
