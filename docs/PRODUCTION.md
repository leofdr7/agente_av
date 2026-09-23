# Despliegue: Cloud Run + Vercel

> Guía histórica de la arquitectura GCP. El workflow actual despliega el backend
> en AWS ECR/ECS; consulta [Producción y CI/CD](../README.md#producción-y-cicd)
> para las variables y el procedimiento vigentes. No ejecutar este bootstrap
> para el pipeline AWS.

Esta guía y los scripts configuran el repositorio `leofdr7/agente_av`. Crear estos
archivos **no crea recursos remotos**: el despliegue solo queda completado después
de ejecutar el bootstrap, cargar las claves, publicar y verificar el sitio.

Destino acordado: proyecto Vercel **agente-av**, equipo **leofdr7's projects**,
subdominio [agente-av-phi.vercel.app](https://agente-av-phi.vercel.app)
verificado en Vercel y Clerk **Development** para un piloto.
El proyecto GCP es **agenta-produccion**. Debe tener una cuenta de facturación
activa vinculada antes de habilitar Cloud Run, Artifact Registry y Secret Manager.
No se necesita comprar un dominio para este piloto.

## 1. Datos y accesos

Se necesita un proyecto GCP con facturación habilitada, permisos para activar APIs,
crear cuentas de servicio, configurar IAM/WIF, Artifact Registry y Secret Manager;
acceso al equipo/proyecto Vercel indicado y al repositorio GitHub. Instala gcloud,
Docker, gh y Node 24 LTS. Desde la raíz:

```bash
gcloud auth login
gh auth login
npm install --global vercel@59.25.2
vercel login

export GCP_PROJECT_ID='agenta-produccion'
export GCP_REGION='us-central1'
export ARTIFACT_REGISTRY_REPOSITORY='agenta'
export CLOUD_RUN_SERVICE='agenta-api'
export GITHUB_REPOSITORY='leofdr7/agente_av'
export GITHUB_REPOSITORY_ID=$(gh api "repos/$GITHUB_REPOSITORY" --jq '.id')
export GITHUB_OWNER_ID=$(gh api "repos/$GITHUB_REPOSITORY" --jq '.owner.id')
export EMBEDDING_PROVIDER='openai'
export EMBEDDING_MODEL='text-embedding-3-small'
```

Comprueba la vinculación de facturación antes del bootstrap:

```bash
gcloud billing projects describe "$GCP_PROJECT_ID"
gcloud billing accounts list --filter=open=true
# Si billingEnabled es false, selecciona una cuenta activa y vincúlala:
gcloud billing projects link "$GCP_PROJECT_ID" --billing-account='ID_CUENTA_ACTIVA'
gcloud billing projects describe "$GCP_PROJECT_ID" --format='value(billingEnabled)'
```

La última consulta debe devolver `True`. Una cuenta cerrada (`open=false`) no
habilita los servicios aunque exista o haya tenido un método de pago.

El ejemplo conserva OpenAI, usado en el entorno local. Si el índice pgvector usa
Voyage, selecciona `voyage` y su modelo. Indexación y consulta deben usar el mismo
modelo y dimensión (512); cambiar de proveedor requiere reindexar el vault.

Para el piloto usa las claves `pk_test_…` y `sk_test_…` de tu instancia Clerk
**Development**, junto con su JWKS/emisor `https://<instancia>.clerk.accounts.dev`.
La instancia de Clerk y los entornos llamados `production` de Vercel/GitHub son
configuraciones independientes. Conserva `ENVIRONMENT=production`, `DEBUG=false`
y `AUTH_DISABLED=false` en Cloud Run: el backend valida también JWT de Development.
Usa siempre claves y JWKS de la misma instancia.

Clerk permite sus claves Development en los subdominios del proveedor para
pruebas. Limita esas instancias a 100 usuarios y no las considera aptas para
cargas de producción. Sus usuarios no se transfieren entre instancias.
Consulta [entornos de Clerk](https://clerk.com/docs/guides/development/managing-environments).
Clerk **Production** requiere un dominio bajo tu control y sus registros DNS;
no admite `*.vercel.app`. Consulta [Clerk en Vercel](https://clerk.com/docs/guides/development/deployment/vercel).

Deshabilita registro abierto si solo deben entrar empleados invitados. Aplica las migraciones de
[Supabase](../backend/migrations/README.md) en orden y verifica el bucket privado
`reports` antes del primer despliegue; la publicación no ejecuta SQL ni migra datos.

## 2. Infraestructura, IAM y Secret Manager

```bash
bash scripts/production/bootstrap-gcp.sh
bash scripts/production/upload-secrets.sh
```

El bootstrap activa las APIs, crea Artifact Registry y separa dos identidades:

- `agenta-runtime`: acceso únicamente a los cuatro secrets del backend.
- `agenta-deploy`: Cloud Run Admin en el proyecto, escritura en el repositorio de
  imágenes e impersonación de la cuenta runtime. No recibe acceso directo a valores
  secretos. Como puede publicar código que los utiliza, debe tratarse como identidad
  privilegiada de producción; conviene un proyecto GCP dedicado a esta aplicación.

Workload Identity Federation acepta únicamente el ID del repositorio y propietario
indicados, rama `main`, workflow `deploy-production.yml` y entorno `production`.
No se crea ni se guarda una clave JSON de cuenta de servicio. Los IDs numéricos
evitan confiar en repositorios ajenos que reutilicen un nombre.

El segundo script pide claves sin mostrarlas y usa stdin para enviarlas a
`gcloud secrets versions add --data-file=-`. No usa los `.env` locales. Carga:
`ANTHROPIC_API_KEY`, `SUPABASE_SERVICE_KEY`, `CLERK_SECRET_KEY`, `OPENAI_API_KEY`
(o `VOYAGE_API_KEY`). Guarda los **números de versión** impresos, nunca los valores
en Git. El backend verifica JWT con JWKS público; conserva la clave privada de
Clerk solicitada en Secret Manager, aunque hoy no llama a su API administrativa.
La misma clave privada de la instancia elegida (Development para el piloto) se
configura en Vercel. No cambies esa clave por una de otra instancia aisladamente.

Cada secret se crea y concede explícitamente así (el script ejecuta estos comandos):

```bash
gcloud secrets create ANTHROPIC_API_KEY --replication-policy=automatic \
  --project="$GCP_PROJECT_ID"
gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY \
  --project="$GCP_PROJECT_ID" \
  --member="serviceAccount:agenta-runtime@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor
```

## 3. Primer despliegue de Cloud Run

Define solo metadatos y referencias, sin claves en esta configuración:

```bash
export GCP_RUNTIME_SERVICE_ACCOUNT="agenta-runtime@$GCP_PROJECT_ID.iam.gserviceaccount.com"
export SUPABASE_URL='https://TU_PROYECTO.supabase.co'
export CLERK_JWKS_URL='https://TU_INSTANCIA.clerk.accounts.dev/.well-known/jwks.json'
export FRONTEND_ORIGIN='https://agente-av-phi.vercel.app'
export CLERK_AUTHORIZED_PARTIES="$FRONTEND_ORIGIN"
# Acceso verificado con la API Models de esta cuenta.
export ANTHROPIC_MODEL='claude-sonnet-5'
# Sustituir 1 por cada versión que imprimió upload-secrets.sh.
export ANTHROPIC_API_KEY_VERSION=1
export SUPABASE_SERVICE_KEY_VERSION=1
export CLERK_SECRET_KEY_VERSION=1
export OPENAI_API_KEY_VERSION=1
# Para Voyage: export VOYAGE_API_KEY_VERSION=1

gcloud auth configure-docker "$GCP_REGION-docker.pkg.dev"
export BACKEND_IMAGE="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/$ARTIFACT_REGISTRY_REPOSITORY/backend:$(git rev-parse HEAD)"
docker build --platform linux/amd64 -t "$BACKEND_IMAGE" backend
docker push "$BACKEND_IMAGE"
bash scripts/production/deploy-backend.sh

export NEXT_PUBLIC_API_URL=$(gcloud run services describe "$CLOUD_RUN_SERVICE" \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" --format='value(status.url)')
```

Antes de etiquetar por SHA, usa un commit que incluya todos los archivos de esta
fase. En Actions se publica por SHA y se despliega por digest inmutable. El script
contiene el comando completo `gcloud run deploy`: usuario runtime dedicado,
puerto 8080, 1 CPU, 1 GiB, concurrencia 8, timeout 300 s y entre 0 y 3 instancias.
Las variables se envían mediante `--env-vars-file`; las claves mediante
`--set-secrets=ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:VERSION,...` con versiones
numéricas. El rollback conserva así las referencias de la revisión anterior.

Cloud Run permite llegar a la API desde el navegador (`--allow-unauthenticated`);
las rutas `/api/v1` siguen exigiendo JWT de Clerk. Si una política de organización
impide IAM `allUsers`, un administrador debe adaptar el acceso público de Cloud
Run antes de publicar. Los orígenes CORS y el claim `azp` se limitan exactamente a
`CLERK_AUTHORIZED_PARTIES`, separados por comas, sin rutas ni comodines.
En el piloto autoriza exactamente el subdominio estable de `agente-av`, que será
el origen del inicio de sesión. No autorices `https://*.vercel.app` ni todos los
dominios de previews.

La imagen usa dos etapas, usuario 10001, dependencias fijadas, bibliotecas PDF y
`exec` para recibir SIGTERM. No contiene `.env`, tests ni pytest. `PORT` es variable.
`ENVIRONMENT=production` rechaza `DEBUG=true`, `AUTH_DISABLED=true`, orígenes HTTP
o claves ausentes. Estas comprobaciones no exigen claves `sk_live_`: el modo
Development de Clerk no desactiva la autenticación del backend. Docker Compose
fija `ENVIRONMENT=development` y puerto 8000.

`/health/live` no llama a servicios externos; lo usan el HEALTHCHECK de Docker y
las sondas HTTP de arranque/liveness de Cloud Run (Cloud Run no usa el HEALTHCHECK
del Dockerfile). `/health/ready` consulta Supabase y responde 503 si no está
operativo, sin incluir errores internos. La comprobación posterior al despliegue
falla si no puede consultar la tabla `employees`. La revisión ya pudo haber recibido
tráfico: el fallo se muestra en Actions y el rollback es manual (sección 7).

El limitador actual usa memoria por proceso: `10/hour` es por instancia y se
reinicia al reiniciar/escalar. No es un límite global de gasto. Para cuotas globales,
conecta almacenamiento compartido antes de aumentar el escalado. Los informes
persisten en Supabase Storage, no en el filesystem efímero del contenedor.

## 4. Vercel conectado a GitHub

En Vercel usa el proyecto existente **agente-av** de **leofdr7's projects**,
conecta `leofdr7/agente_av` y selecciona **Root Directory: frontend**, framework **Next.js**,
Node **24.x** y rama Production **main**. Puedes crear el proyecto sin publicar
hasta configurar variables. El archivo `frontend/vercel.json` deshabilita los
builds automáticos de Git en todas las ramas: la conexión se conserva y Actions
publica solo después de superar CI y desplegar el backend, evitando publicaciones
duplicadas y carreras. No se generan previews automáticas.

Vincula el checkout desde la **raíz del repositorio** (no desde frontend):

```bash
vercel teams ls
export VERCEL_TEAM_SLUG='leofdr7s-projects'
vercel link --project agente-av --scope "$VERCEL_TEAM_SLUG"
vercel git connect --yes
vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production --no-sensitive
vercel env add CLERK_SECRET_KEY production --sensitive
printf '%s' "$NEXT_PUBLIC_API_URL" | vercel env add NEXT_PUBLIC_API_URL production --no-sensitive
printf '%s' '/sign-in' | vercel env add NEXT_PUBLIC_CLERK_SIGN_IN_URL production
printf '%s' '/sign-up' | vercel env add NEXT_PUBLIC_CLERK_SIGN_UP_URL production
printf '%s' '/' | vercel env add NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL production
printf '%s' '/' | vercel env add NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL production

vercel deploy --prod --yes \
  --build-env="NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL" \
  --env="NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL"
```

Los comandos `env add ... production` reciben `pk_test_…` y `sk_test_…` durante
este piloto: `production` selecciona el entorno de Vercel, no crea una instancia
Clerk Production. La primera clave es **NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY**, el nombre que consume
Next.js/Clerk; `CLERK_PUBLISHABLE_KEY` solo no sirve. Solo esa clave y las URLs
son públicas. `CLERK_SECRET_KEY` queda privada en el servidor de Vercel. Ninguna
clave de Supabase/Anthropic/embeddings debe usar `NEXT_PUBLIC_` ni estar en Vercel.
Si una variable ya existe, usa `vercel env update NOMBRE production`.

Vercel ejecuta `npm ci` y `npm run build` con las variables de su entorno Production.
La clave privada se guarda como Secret; `vercel pull` la sustituye por `[SENSITIVE]`,
por lo que este flujo compila en Vercel y no descarga la clave a GitHub Actions.
`NEXT_PUBLIC_API_URL` se fija al compilar: cambiarla requiere reconstruir. Actions
la toma de la salida del backend y la pasa explícitamente al build y al runtime.
`.vercelignore` limita la subida al código del frontend, excluyendo `.env`,
dependencias instaladas y artefactos locales. No subas `.vercel` ni sus `.env`.
El comando espera a que termine el build y falla si Vercel no puede publicarlo.

## 5. GitHub Actions

Los nuevos workflows son:

- `ci.yml`: todas las pull requests, ejecución manual y llamada reutilizable.
  Backend pytest en Python 3.12, dependencias PDF; frontend `npm ci`, lint, tests,
  tipos y build con Node 24; construcción y smoke test del contenedor sin red.
  Usa datos sintéticos y no recibe secrets de producción, también en forks.
- `deploy-production.yml`: push a `main` (incluye merges) o ejecución manual desde
  `main`. Repite CI para ese commit, autentica GCP vía OIDC, publica imagen,
  despliega Cloud Run, valida Supabase y publica Vercel. Los despliegues se
  serializan y no se cancelan a mitad de publicación.

En GitHub crea el entorno **production** y limita sus ramas a `main`:

```bash
gh api --method PUT "repos/$GITHUB_REPOSITORY/environments/production" \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api --method POST "repos/$GITHUB_REPOSITORY/environments/production/deployment-branch-policies" \
  -f name=main -f type=branch
```

Añade estas **variables del entorno production** (Settings → Environments),
con los valores preparados arriba:

```text
GCP_PROJECT_ID
GCP_REGION                         (por defecto us-central1)
ARTIFACT_REGISTRY_REPOSITORY        (por defecto agenta)
CLOUD_RUN_SERVICE                  (por defecto agenta-api)
GCP_WORKLOAD_IDENTITY_PROVIDER      (salida del bootstrap)
GCP_DEPLOY_SERVICE_ACCOUNT         (salida del bootstrap)
GCP_RUNTIME_SERVICE_ACCOUNT        (salida del bootstrap)
SUPABASE_URL
CLERK_JWKS_URL
CLERK_AUTHORIZED_PARTIES
ANTHROPIC_MODEL
EMBEDDING_PROVIDER                 (openai o voyage)
EMBEDDING_MODEL
ANTHROPIC_API_KEY_VERSION
SUPABASE_SERVICE_KEY_VERSION
CLERK_SECRET_KEY_VERSION
OPENAI_API_KEY_VERSION             (o VOYAGE_API_KEY_VERSION)
VERCEL_ORG_ID                      (.vercel/project.json → orgId)
VERCEL_PROJECT_ID                  (.vercel/project.json → projectId)
```

Ejemplo de carga de metadatos:

```bash
gh variable set GCP_PROJECT_ID --repo "$GITHUB_REPOSITORY" --env production --body "$GCP_PROJECT_ID"
gh variable set CLERK_AUTHORIZED_PARTIES --repo "$GITHUB_REPOSITORY" --env production --body "$CLERK_AUTHORIZED_PARTIES"
gh secret set VERCEL_TOKEN --repo "$GITHUB_REPOSITORY" --env production
```

`VERCEL_TOKEN` es el único secret que necesita el workflow de despliegue en GitHub.
Créalo con acceso al equipo/proyecto correcto y fecha de expiración gestionada.
El inicio de sesión OAuth de la CLI no sustituye este token: en esta cuenta,
intentar crearlo mediante la API de la CLI devuelve
`Cannot create tokens for this app. (403)`. Créalo desde
[Account Settings → Tokens](https://vercel.com/account/tokens) y guárdalo con
`gh secret set` o en GitHub → Settings → Environments → production, sin pegarlo
en un commit ni en el chat.
Las claves del backend permanecen en Secret Manager; las de frontend en Vercel.
Activa un ruleset de `main` que exija PR y los tres checks de CI antes del merge;
si habilitas revisores obligatorios del entorno, la publicación esperará aprobación.

El workflow preexistente `reindex-vault.yml` sigue separado y limitado a `main`.
Necesita sus secrets de Supabase/JWKS/embeddings a nivel **repositorio**, como ya
ocurría antes, y variables de repositorio `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`
iguales a las de producción. No confundirlas con las variables del entorno
`production`; no se heredan entre ámbitos. No activa indexación solo al desplegar.

## 6. Subdominio de Vercel y migración futura

Usa el dominio estable `agente-av-phi.vercel.app` del proyecto `agente-av`.
Vercel proporciona HTTPS para ese dominio; no ejecutes `vercel domains add` ni
modifiques DNS durante el piloto. Copia la URL real en `FRONTEND_ORIGIN` y en la
variable GitHub `CLERK_AUTHORIZED_PARTIES` antes de desplegar el backend.

Verifica el piloto:

```bash
curl --fail --show-error --silent "$NEXT_PUBLIC_API_URL/health/ready"
curl --head --location "$FRONTEND_ORIGIN/sign-in"
```

Inicia sesión con un empleado invitado, crea una estimación y descarga PDF/DOCX.
Mantén el piloto limitado a las personas de prueba acordadas.

### Paso posterior a Clerk Production

Necesitarás un dominio bajo tu control. Cuando lo tengas, configura ese dominio
en Vercel y completa los registros DNS de la instancia Clerk Production. Cambia
juntos `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`,
el emisor si se fijó explícitamente, los orígenes/redirects y vuelve a desplegar.

Planifica también las cuentas: `employees.clerk_user_id` identifica al usuario
de la instancia de Clerk. Los usuarios nuevos de Production tendrán otros IDs;
cambiar solo las claves no conserva el acceso a sus expedientes. Antes de migrar
datos útiles, establece un mapeo verificado de identidades y conserva los UUID
internos de `employees`, a los que se vinculan proyectos y estimaciones. Revisa
también invitaciones, metadatos `name`/`role`, claims y proveedores de inicio de sesión.

Con un dominio que ya poseas:

```bash
vercel domains add app.tudominio.com agente-av --scope "$VERCEL_TEAM_SLUG"
vercel domains inspect app.tudominio.com --scope "$VERCEL_TEAM_SLUG"
```

En tu proveedor DNS crea **exactamente los registros A/CNAME/TXT que muestre
Vercel**, incluidos los de verificación si los pide. No fijes una IP genérica de
una guía: el destino depende del proyecto. Conserva los registros de correo y
los demás subdominios. Si existe CAA restrictivo, permite la autoridad que indique
Vercel. Vuelve a ejecutar `domains inspect` hasta que valide DNS y certificado.
Vercel emite y renueva HTTPS automáticamente cuando el dominio está verificado.

El dominio debe figurar en la configuración Production de Clerk y en
`CLERK_AUTHORIZED_PARTIES`; cualquier cambio del segundo requiere desplegar de
nuevo Cloud Run. Prueba en el dominio definitivo:

```bash
curl --fail --show-error --silent "$NEXT_PUBLIC_API_URL/health/ready"
curl --head --location https://app.tudominio.com/sign-in
curl --head http://app.tudominio.com/sign-in
```

Comprueba que HTTP redirige a HTTPS. Inicia sesión con un empleado invitado, crea
un proyecto/estimación, consulta RAG y descarga PDF/DOCX. Estas pruebas requieren
claves, datos y DNS reales: una compilación local no las sustituye.

## 7. Verificación, rotación y rollback

```bash
# Desde backend, con requirements-dev.txt instalado:
python -m pytest -q
# Desde frontend:
npm ci
npm run lint
npm test
npm run typecheck
npm run build
# Desde la raíz:
docker build -t agenta-backend:local backend
bash scripts/production/test-container.sh agenta-backend:local
```

Para rotar, agrega una versión con `upload-secrets.sh`, cambia la variable
`*_VERSION` correspondiente y ejecuta el workflow. Conserva las versiones
anteriores mientras necesites volver a revisiones que las referencian.

```bash
gcloud run revisions list --service="$CLOUD_RUN_SERVICE" \
  --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
gcloud run services update-traffic "$CLOUD_RUN_SERVICE" \
  --region="$GCP_REGION" --project="$GCP_PROJECT_ID" --to-revisions=REVISION_SANA=100
vercel rollback URL_DESPLIEGUE_SANO --scope EQUIPO
```

Consulta logs de Cloud Run y Actions si falla `/health/ready`. Un frontend fallido
no revierte automáticamente un backend publicado; mantén compatibilidad de API
entre versiones contiguas o revierte ambas partes. El siguiente despliegue de
backend mueve el tráfico a su revisión más reciente.

## Referencias oficiales

- [Secret Manager en Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
- [Opciones de gcloud run deploy](https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy)
- [Workload Identity Federation para pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
- [Vercel con GitHub Actions](https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel)
- [Control de despliegues Git de Vercel](https://vercel.com/docs/project-configuration/git-configuration)
- [Vercel CLI: dominios](https://vercel.com/docs/cli/domains)
