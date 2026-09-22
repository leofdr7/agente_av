#!/usr/bin/env bash
set -euo pipefail
image=${1:-agenta-backend:phase10}
# Fake credentials; this smoke test must never contact production services.
container=$(docker run -d --network=none \
  -e PORT=9090 -e ENVIRONMENT=production -e AUTH_DISABLED=false -e DEBUG=false \
  -e SUPABASE_URL=https://example.supabase.co -e SUPABASE_SERVICE_KEY=test-key \
  -e CLERK_JWKS_URL=https://clerk.example.com/.well-known/jwks.json \
  -e CLERK_SECRET_KEY=test-key -e CLERK_AUTHORIZED_PARTIES=https://app.example.com \
  -e ANTHROPIC_API_KEY=test-key -e EMBEDDING_PROVIDER=openai -e OPENAI_API_KEY=test-key \
  "$image")
trap 'docker rm -f "$container" >/dev/null' EXIT
for _attempt in {1..30}; do
  if docker exec "$container" python -c \
    'import urllib.request; urllib.request.urlopen("http://127.0.0.1:9090/health/live", timeout=2)' 2>/dev/null; then
    break
  fi
  sleep 1
done
docker exec -i "$container" python - <<'PY'
import importlib.util, json, os, pathlib, urllib.error, urllib.request
from weasyprint import HTML
assert os.getuid() == 10001
assert not pathlib.Path('/app/.env').exists()
assert not pathlib.Path('/app/tests').exists()
assert importlib.util.find_spec('pytest') is None
assert HTML(string='<p>Producción: álgebra vectorial</p>').write_pdf().startswith(b'%PDF-')
with urllib.request.urlopen('http://127.0.0.1:9090/health/live', timeout=3) as response:
    assert json.load(response) == {'status': 'ok'}
try:
    urllib.request.urlopen('http://127.0.0.1:9090/api/v1/me', timeout=3)
except urllib.error.HTTPError as error:
    assert error.code == 401, error.code
else:
    raise AssertionError('La API privada permitió acceso sin JWT')
print('Non-root, PDF, PORT y autenticación: OK')
PY
for _attempt in {1..40}; do
  health=$(docker inspect --format '{{.State.Health.Status}}' "$container")
  if [[ "$health" == healthy ]]; then
    printf 'Docker HEALTHCHECK: OK\n'
    exit 0
  fi
  sleep 1
done
docker logs "$container"
printf 'Healthcheck no alcanzó estado healthy\n' >&2
exit 1
