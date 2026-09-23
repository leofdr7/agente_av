#!/usr/bin/env bash
# La imagen debe estar publicada. No lee .env locales ni maneja valores secretos.
set -euo pipefail
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${BACKEND_IMAGE:?Define la imagen inmutable de Artifact Registry (digest o SHA)}"
: "${GCP_RUNTIME_SERVICE_ACCOUNT:?Define GCP_RUNTIME_SERVICE_ACCOUNT}"
: "${SUPABASE_URL:?Define SUPABASE_URL}"
: "${CLERK_JWKS_URL:?Define CLERK_JWKS_URL}"
: "${CLERK_AUTHORIZED_PARTIES:?Define los origenes HTTPS de produccion}"
: "${ANTHROPIC_MODEL:?Define un modelo habilitado en tu cuenta Anthropic}"
GCP_REGION=${GCP_REGION:-us-central1}
CLOUD_RUN_SERVICE=${CLOUD_RUN_SERVICE:-agenta-api}
EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-openai}
case "$EMBEDDING_PROVIDER" in
  openai) embedding_secret=OPENAI_API_KEY; EMBEDDING_MODEL=${EMBEDDING_MODEL:-text-embedding-3-small};;
  voyage) embedding_secret=VOYAGE_API_KEY; EMBEDDING_MODEL=${EMBEDDING_MODEL:-voyage-4-lite};;
  *) printf 'Proveedor de embeddings inválido\n' >&2; exit 1;;
esac
secret_bindings=()
for secret in ANTHROPIC_API_KEY SUPABASE_SERVICE_KEY CLERK_SECRET_KEY "$embedding_secret"; do
  variable="${secret}_VERSION"
  version=${!variable:-}
  if [[ ! "$version" =~ ^[1-9][0-9]*$ ]]; then
    printf 'Define %s con una versión numérica de Secret Manager.\n' "$variable" >&2
    exit 1
  fi
  secret_bindings+=("${secret}=${secret}:${version}")
done
secrets_arg=$(IFS=,; printf '%s' "${secret_bindings[*]}")
export SUPABASE_URL CLERK_JWKS_URL CLERK_AUTHORIZED_PARTIES ANTHROPIC_MODEL EMBEDDING_PROVIDER EMBEDDING_MODEL
config_file=$(mktemp)
trap 'rm -f "$config_file"' EXIT
# JSON es YAML válido; evita errores con comas en CLERK_AUTHORIZED_PARTIES.
python3 - "$config_file" <<'PY'
import json, os, sys
from urllib.parse import urlsplit
names = ('SUPABASE_URL', 'CLERK_JWKS_URL', 'CLERK_AUTHORIZED_PARTIES',
         'ANTHROPIC_MODEL', 'EMBEDDING_PROVIDER', 'EMBEDDING_MODEL')
config = {name: os.environ[name] for name in names}
for origin in config['CLERK_AUTHORIZED_PARTIES'].split(','):
    parsed = urlsplit(origin.strip())
    if (parsed.scheme != 'https' or not parsed.hostname or '*' in origin
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        raise SystemExit('CLERK_AUTHORIZED_PARTIES requiere orígenes HTTPS exactos')
config.update(ENVIRONMENT='production', DEBUG='false', AUTH_DISABLED='false',
              RATE_LIMIT_ENABLED='true', ESTIMATION_RATE_LIMIT='10/hour',
              REPORTS_BUCKET='reports', REPORTS_SIGNED_URL_TTL_SECONDS='604800')
with open(sys.argv[1], 'w') as stream:
    json.dump(config, stream)
PY

gcloud run deploy "$CLOUD_RUN_SERVICE" --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --image="$BACKEND_IMAGE" --service-account="$GCP_RUNTIME_SERVICE_ACCOUNT" \
  --port=8080 --cpu=1 --memory=1Gi --concurrency=8 --timeout=300 \
  --min=0 --max=3 --ingress=all --allow-unauthenticated \
  --env-vars-file="$config_file" --set-secrets="$secrets_arg" \
  --startup-probe=httpGet.path=/health/live,httpGet.port=8080,initialDelaySeconds=0,periodSeconds=5,timeoutSeconds=3,failureThreshold=24 \
  --liveness-probe=httpGet.path=/health/live,httpGet.port=8080,periodSeconds=30,timeoutSeconds=3,failureThreshold=3 \
  --quiet
# Garantiza que una revisión anterior fijada por un rollback no retenga el tráfico.
gcloud run services update-traffic "$CLOUD_RUN_SERVICE" --project="$GCP_PROJECT_ID" \
  --region="$GCP_REGION" --to-latest --quiet
backend_url=$(gcloud run services describe "$CLOUD_RUN_SERVICE" --project="$GCP_PROJECT_ID" \
  --region="$GCP_REGION" --format='value(status.url)')
curl --fail --silent --show-error --retry 5 --retry-all-errors --retry-delay 5 \
  --max-time 30 "$backend_url/health/ready"
printf '\nBackend: %s\n' "$backend_url"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'url=%s\n' "$backend_url" >> "$GITHUB_OUTPUT"
fi
