#!/usr/bin/env bash
# Carga interactiva: valores ocultos, sin archivos temporales ni argumentos secretos.
set -euo pipefail
set +x
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-openai}
case "$EMBEDDING_PROVIDER" in openai) embedding_secret=OPENAI_API_KEY;; voyage) embedding_secret=VOYAGE_API_KEY;; *) exit 1;; esac
for secret in ANTHROPIC_API_KEY SUPABASE_SERVICE_KEY CLERK_SECRET_KEY "$embedding_secret"; do
  IFS= read -r -s -p "Valor de producción para ${secret}: " value
  printf '\n' >&2
  if [[ -z "$value" || "$value" == *$'\r'* ]]; then
    printf 'Valor vacío o inválido para %s\n' "$secret" >&2
    exit 1
  fi
  version=$(printf '%s' "$value" | gcloud secrets versions add "$secret" \
    --project="$GCP_PROJECT_ID" --data-file=- --format='value(name)')
  unset value
  printf '%s_VERSION=%s\n' "$secret" "${version##*/}"
done
