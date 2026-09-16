-- Core domain schema for employees, projects, estimations, reports, and RAG chunks.

create table public.employees (
  id uuid primary key default gen_random_uuid(),
  clerk_user_id text not null unique,
  name text not null,
  role text not null,
  created_at timestamptz not null default now()
);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  budget numeric(14, 2),
  status text not null default 'draft'
    check (status in ('draft', 'active', 'on_hold', 'completed', 'archived')),
  created_by uuid not null references public.employees (id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.estimations (
  id uuid primary key default gen_random_uuid(),
  problem_text text not null,
  result_json jsonb,
  project_id uuid not null references public.projects (id) on delete restrict,
  requested_by uuid not null references public.employees (id) on delete restrict,
  created_at timestamptz not null default now()
);

create table public.reports (
  id uuid primary key default gen_random_uuid(),
  estimation_id uuid not null references public.estimations (id) on delete restrict,
  file_url text not null,
  file_type text not null,
  generated_at timestamptz not null default now()
);

create table public.knowledge_chunks (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  embedding extensions.vector(512),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

comment on column public.knowledge_chunks.metadata is
  'JSON with original Obsidian file path and title: {"obsidian_path": "...", "title": "..."}';

create index projects_created_by_idx on public.projects (created_by);
create index estimations_project_id_idx on public.estimations (project_id);
create index estimations_requested_by_idx on public.estimations (requested_by);
create index reports_estimation_id_idx on public.reports (estimation_id);

create index knowledge_chunks_embedding_hnsw_idx
  on public.knowledge_chunks
  using hnsw (embedding vector_cosine_ops);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger set_projects_updated_at
  before update on public.projects
  for each row
  execute function public.set_updated_at();

alter table public.employees enable row level security;
alter table public.projects enable row level security;
alter table public.estimations enable row level security;
alter table public.reports enable row level security;
alter table public.knowledge_chunks enable row level security;
