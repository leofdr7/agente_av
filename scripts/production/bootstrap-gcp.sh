#!/usr/bin/env bash
# Ejecutar una vez con una identidad administradora del proyecto de destino.
set -euo pipefail
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GITHUB_REPOSITORY_ID:?ID numerico del repositorio GitHub}"
: "${GITHUB_OWNER_ID:?ID numerico del propietario GitHub}"
GCP_REGION=${GCP_REGION:-us-central1}
ARTIFACT_REGISTRY_REPOSITORY=${ARTIFACT_REGISTRY_REPOSITORY:-agenta}
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-leofdr7/agente_av}
EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-openai}
case "$EMBEDDING_PROVIDER" in openai) embedding_secret=OPENAI_API_KEY;; voyage) embedding_secret=VOYAGE_API_KEY;; *) exit 1;; esac
[[ "$GITHUB_REPOSITORY_ID" =~ ^[0-9]+$ && "$GITHUB_OWNER_ID" =~ ^[0-9]+$ ]]
command -v gcloud >/dev/null
project_number=$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')
runtime_sa="agenta-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
deploy_sa="agenta-deploy@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
pool=agenta-github
provider=github

gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
  sts.googleapis.com --project="$GCP_PROJECT_ID"

if ! gcloud artifacts repositories describe "$ARTIFACT_REGISTRY_REPOSITORY" \
  --location="$GCP_REGION" --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$ARTIFACT_REGISTRY_REPOSITORY" \
    --repository-format=docker --location="$GCP_REGION" --project="$GCP_PROJECT_ID"
fi
for account in agenta-runtime agenta-deploy; do
  if ! gcloud iam service-accounts describe "${account}@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
    --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$account" --project="$GCP_PROJECT_ID"
  fi
done
# run.admin permite configurar el acceso público (la aplicación exige JWT de Clerk).
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:$deploy_sa" --role=roles/run.admin --condition=None >/dev/null
gcloud artifacts repositories add-iam-policy-binding "$ARTIFACT_REGISTRY_REPOSITORY" \
  --location="$GCP_REGION" --project="$GCP_PROJECT_ID" \
  --member="serviceAccount:$deploy_sa" --role=roles/artifactregistry.writer >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$runtime_sa" \
  --project="$GCP_PROJECT_ID" --member="serviceAccount:$deploy_sa" \
  --role=roles/iam.serviceAccountUser >/dev/null

for secret in ANTHROPIC_API_KEY SUPABASE_SERVICE_KEY CLERK_SECRET_KEY "$embedding_secret"; do
  if ! gcloud secrets describe "$secret" --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets create "$secret" --replication-policy=automatic --project="$GCP_PROJECT_ID"
  fi
  gcloud secrets add-iam-policy-binding "$secret" --project="$GCP_PROJECT_ID" \
    --member="serviceAccount:$runtime_sa" --role=roles/secretmanager.secretAccessor >/dev/null
done

if ! gcloud iam workload-identity-pools describe "$pool" --location=global \
  --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$pool" --location=global --project="$GCP_PROJECT_ID"
fi
# IDs inmutables evitan que el cambio de propietario/nombre habilite otro repositorio.
condition="assertion.repository_id=='${GITHUB_REPOSITORY_ID}' && assertion.repository_owner_id=='${GITHUB_OWNER_ID}' && assertion.ref=='refs/heads/main' && assertion.workflow_ref=='${GITHUB_REPOSITORY}/.github/workflows/deploy-production.yml@refs/heads/main' && assertion.sub=='repo:${GITHUB_REPOSITORY}:environment:production'"
provider_args=(--workload-identity-pool="$pool" --location=global --project="$GCP_PROJECT_ID"
  --issuer-uri=https://token.actions.githubusercontent.com
  "--attribute-mapping=google.subject=assertion.sub,attribute.repository_id=assertion.repository_id"
  --attribute-condition="$condition")
if gcloud iam workload-identity-pools providers describe "$provider" \
  --workload-identity-pool="$pool" --location=global --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers update-oidc "$provider" "${provider_args[@]}"
else
  gcloud iam workload-identity-pools providers create-oidc "$provider" "${provider_args[@]}"
fi
gcloud iam service-accounts add-iam-policy-binding "$deploy_sa" --project="$GCP_PROJECT_ID" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/${pool}/attribute.repository_id/${GITHUB_REPOSITORY_ID}" >/dev/null

printf 'GCP_WORKLOAD_IDENTITY_PROVIDER=projects/%s/locations/global/workloadIdentityPools/%s/providers/%s\n' "$project_number" "$pool" "$provider"
printf 'GCP_DEPLOY_SERVICE_ACCOUNT=%s\nGCP_RUNTIME_SERVICE_ACCOUNT=%s\n' "$deploy_sa" "$runtime_sa"
