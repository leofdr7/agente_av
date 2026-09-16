-- Enable pgvector for embedding storage and similarity search.
create extension if not exists vector
  with schema extensions;
