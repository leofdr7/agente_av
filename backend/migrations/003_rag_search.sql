-- Incremental RAG indexing (content hashes) and cosine similarity search RPC.

alter table public.knowledge_chunks
  add column if not exists content_hash text;

comment on column public.knowledge_chunks.content_hash is
  'SHA-256 of chunk content; used to skip re-embedding unchanged chunks.';

comment on column public.knowledge_chunks.metadata is
  'JSON with Obsidian source: {"obsidian_path": "...", "title": "...", "modified_at": "...", "heading": "..."}';

create index if not exists knowledge_chunks_content_hash_idx
  on public.knowledge_chunks (content_hash);

create index if not exists knowledge_chunks_obsidian_path_idx
  on public.knowledge_chunks ((metadata->>'obsidian_path'));

create or replace function public.match_knowledge_chunks(
  query_embedding extensions.vector(512),
  match_count int default 5
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity double precision
)
language sql
stable
set search_path = public, extensions
as $$
  select
    kc.id,
    kc.content,
    kc.metadata,
    1 - (kc.embedding <=> query_embedding) as similarity
  from public.knowledge_chunks kc
  where kc.embedding is not null
  order by kc.embedding <=> query_embedding
  limit least(match_count, 200);
$$;

revoke all on function public.match_knowledge_chunks(extensions.vector, integer) from public;
grant execute on function public.match_knowledge_chunks(extensions.vector, integer) to service_role;
