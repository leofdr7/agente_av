import type { ProjectStatus } from "@/lib/api";

export const PROJECT_STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: "borrador",
  active: "activo",
  on_hold: "en pausa",
  completed: "cerrado",
  archived: "archivo",
};

const money = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const when = new Intl.DateTimeFormat("es-MX", {
  dateStyle: "medium",
  timeStyle: "short",
});

export function formatBudget(value: number | null | undefined): string {
  if (value == null) return "Sin presupuesto";
  return money.format(value);
}

export function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return when.format(date);
}

export function excerpt(text: string, max = 140): string {
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= max) return compact;
  return `${compact.slice(0, max - 1)}…`;
}
