# Migraciones de Supabase

SQL versionado para el esquema de Postgres. Aplicar los archivos **en orden numérico**.

## Archivos

| Archivo | Qué hace |
|---------|----------|
| `001_enable_pgvector.sql` | Habilita la extensión `vector` (pgvector) en el schema `extensions`. |
| `002_create_core_schema.sql` | Crea `employees`, `projects`, `estimations`, `reports` y `knowledge_chunks`, índices, trigger `updated_at` y RLS. |
| `003_rag_search.sql` | Añade `content_hash` e índice por ruta de Obsidian, y el RPC `match_knowledge_chunks` (similitud cosine). |

## Cómo aplicarlas

### Opción 1 — SQL Editor (Dashboard)

1. Abre el proyecto en [Supabase Dashboard](https://supabase.com/dashboard).
2. Ve a **SQL Editor**.
3. Pega y ejecuta el contenido de `001_enable_pgvector.sql`.
4. Pega y ejecuta el contenido de `002_create_core_schema.sql`.
5. Pega y ejecuta el contenido de `003_rag_search.sql`.

### Opción 2 — CLI

Con el [Supabase CLI](https://supabase.com/docs/guides/cli) autenticado contra el proyecto:

```bash
supabase db query --linked -f backend/migrations/001_enable_pgvector.sql
supabase db query --linked -f backend/migrations/002_create_core_schema.sql
supabase db query --linked -f backend/migrations/003_rag_search.sql
```

O copia los archivos a `supabase/migrations/` y usa `supabase db push`.

### Opción 3 — MCP `apply_migration`

Si el servidor MCP de Supabase está conectado al proyecto, aplica cada archivo como una migración nombrada (`enable_pgvector`, `create_core_schema`, `rag_search`).

## Verificación

```sql
select extname, extversion
from pg_extension
where extname = 'vector';

select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'employees',
    'projects',
    'estimations',
    'reports',
    'knowledge_chunks'
  )
order by table_name;
```

El backend usa la clave `service_role` (`SUPABASE_SERVICE_KEY`), que omite RLS. Las políticas por usuario (Clerk) se añadirán en una fase posterior.
