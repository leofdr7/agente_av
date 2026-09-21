-- Trazabilidad de cada estimación: empleado, proyecto, timestamp y tools del agente.

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  employee_id uuid not null references public.employees (id) on delete restrict,
  project_id uuid not null references public.projects (id) on delete restrict,
  estimation_id uuid references public.estimations (id) on delete restrict,
  tools_used text[] not null default '{}',
  tools_summary text not null,
  created_at timestamptz not null default now()
);

comment on table public.audit_logs is
  'Una fila por estimación generada: quién la pidió, sobre qué proyecto y qué herramientas invocó el agente.';

comment on column public.audit_logs.tools_used is
  'Nombres de las tools en el orden en que el agente las ejecutó.';

comment on column public.audit_logs.tools_summary is
  'Resumen legible de la traza de tools (p. ej. "4 llamada(s): diagnosticar_sistema → …").';

create index audit_logs_employee_id_idx on public.audit_logs (employee_id);
create index audit_logs_project_id_idx on public.audit_logs (project_id);
create index audit_logs_estimation_id_idx on public.audit_logs (estimation_id);
create index audit_logs_created_at_idx on public.audit_logs (created_at desc);

alter table public.audit_logs enable row level security;
