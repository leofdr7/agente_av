# Agente de IA para estimaciones de álgebra vectorial

Monorepo con backend FastAPI y frontend Next.js para estimaciones basadas en presupuestos.

## Estructura

```
├── backend/          # FastAPI (Python 3.12+)
├── frontend/         # Next.js 16 (App Router, TypeScript, Tailwind, shadcn/ui, Clerk)
├── vault/            # Base de conocimiento del despliegue (vacía en el repo)
├── vault-ejemplo/    # Notas de demostración; no se indexan en producción
└── docker-compose.yml
```

## Prerrequisitos

- Python 3.12+ (CI y contenedor: 3.12)
- Node.js 24 LTS (ver frontend/.nvmrc)
- Docker (opcional, para backend en contenedor)
- Una aplicación en [Clerk](https://clerk.com) (ver [Autenticación](#autenticación))

## Backend

### Desarrollo local

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

API disponible en `http://localhost:8000`. Documentación interactiva en `/docs`.

### Con Docker

Desde la raíz del repositorio:

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

### Motor de sistemas lineales

Núcleo determinista que resuelve `AX=B` por eliminación de Gauss, Gauss-Jordan y
matriz inversa, sin intervención del LLM. Antes de resolver calcula `det(A)`,
`rango(A)` y `rango([A|B])` con aritmética exacta (SymPy): si el sistema es
singular se detiene y devuelve el diagnóstico (`incompatible` o `compatible
indeterminado`) sin ningún vector solución. Cuando sí resuelve, contrasta los
tres métodos entre sí, verifica `‖AX - B‖` y marca como `infeasible` cualquier
solución con componentes negativas.

Vía API (requiere token de Clerk):

```bash
curl -X POST http://localhost:8000/api/v1/linear-systems/solve \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"A": [[2,1],[1,3]], "B": [4,5]}'
```

Vía consola, sin pasar por la API ni por Clerk:

```bash
cd backend
python -m app.cli.linear_systems sistema.json --no-steps
cat sistema.json | python -m app.cli.linear_systems --stdin
```

`sistema.json` acepta `{"A": [[...]], "B": [...], "variable_names": [...]}`.
Códigos de salida: `0` resuelto, `1` sistema singular, `2` entrada inválida,
`3` fallo interno del motor.

### Agente orquestador (Claude + tool use)

`app/services/agent.py` conecta Claude (`claude-sonnet-5` por defecto) como
orquestador: el modelo no calcula, decide qué herramienta llamar y traduce lo que
devuelve el motor a lenguaje de negocio. Las cinco herramientas son
`buscar_conocimiento` (RAG sobre el vault), `diagnosticar_sistema` (rango y
determinante) y `resolver_por_gauss`, `resolver_por_gauss_jordan` y
`resolver_por_matriz_inversa`.

El system prompt le prohíbe resolver `AX=B` o inventar valores de X y le exige
diagnosticar antes de resolver. Además, cada herramienta de resolución vuelve a
diagnosticar el sistema por su cuenta: si es singular, devuelve el diagnóstico como
error y el solver nunca corre, así que el modelo no puede obtener un vector X de un
sistema sin solución única. Cuando los tres métodos ya corrieron, el resultado del
tercero incluye `validacion_cruzada` (comparación entre métodos, `‖AX - B‖` y
factibilidad) para que el modelo compare sin recalcular.

```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "problem_text": "Nos quedamos cortos de resina de encapsulado, ¿qué plan es viable?",
    "project_id": "<uuid de projects>",
    "A": [[2,1],[1,3]],
    "B": [4,5]
  }'
```

`A` y `B` son opcionales y van juntos: si se omiten, el modelo extrae los
coeficientes del enunciado. `variable_names` (líneas de producto, por columna) y
`resource_names` (recursos, por fila) alimentan la interpretación semántica.

Cada corrida se registra en `estimations` (enunciado, `project_id`, empleado y
`result_json` con la traza) y en `audit_logs` (empleado, proyecto, timestamp y
el resumen de tools invocadas), para poder reconstruir cómo se llegó a un
resultado. El loop rechaza un vector X si el modelo no llamó antes a
`diagnosticar_sistema` o a los solvers del motor.

### Proyectos y lecturas de estimaciones

Los expedientes viven en `projects` (nombre, presupuesto, estado). El frontend
lista solo los del empleado autenticado (`created_by`):

```bash
curl http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $CLERK_TOKEN"

curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Línea AI-Edge", "budget": 120000, "status": "active"}'
```

`GET /api/v1/projects/{id}` y `PATCH /api/v1/projects/{id}` leen o actualizan un
expediente propio. `GET /api/v1/projects/{id}/estimations` y
`GET /api/v1/estimations` listan el historial (sin la traza completa).
`GET /api/v1/estimations/{id}` devuelve el resultado, el proyecto y los informes
ya generados.

Búsqueda RAG sobre el vault indexado. Con `vault/` vacío la respuesta es
`results: []`; solo devuelve fragmentos si el despliegue cargó sus propias notas:

```bash
curl "http://localhost:8000/api/v1/knowledge/search?q=termino+del+negocio&top_k=5" \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

### Informes PDF/DOCX

`POST /api/v1/estimations/{id}/report` (token de Clerk) lee el registro completo
de `estimations`, genera un DOCX (`python-docx`) y un PDF (WeasyPrint a partir de
una plantilla HTML), los sube al bucket privado `reports` de Supabase Storage y
guarda en la tabla `reports` la URL firmada, el tipo y la fecha. Responde las
URLs de descarga.

```bash
curl -X POST http://localhost:8000/api/v1/estimations/<uuid>/report \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

El PDF real exige Pango/Cairo **en el sistema**, no solo en el venv. El
`Dockerfile` del backend ya las instala. En desarrollo local, sin Docker:

**Debian / Ubuntu**

```bash
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
  libffi8 shared-mime-info fonts-dejavu-core
```

**Fedora / RHEL**

```bash
sudo dnf install pango gdk-pixbuf2 libffi
```

**Arch Linux**

```bash
sudo pacman -S pango gdk-pixbuf2 cairo libffi
```

**macOS**

```bash
brew install pango gdk-pixbuf libffi
```

**Windows:** usar Docker (`docker compose up --build`). Compilar Pango a mano no
está soportado.

Si esas librerías faltan, WeasyPrint no puede escribir PDF. Los tests **no se
saltan** ese caso: o generan un PDF real, o usan el renderer documentado
`mock_pdf_renderer` (los bytes incluyen `MOCK WeasyPrint`). Un `pytest -q` en
una máquina sin Pango sigue en verde, pero el PDF de esas corridas no es un
informe visual.

### Tests

```bash
cd backend
pytest
```

Los tests del motor y del agente usan el caso TechChip Systems S.A. definido en
`tests/fixtures/techchip.py`. El vector de disponibilidades activo se controla
con la constante `DATASET_B`. A nivel de agente (LLM simulado, motor real) se
reproducen los cuatro escenarios de estrés: plan base X=(15,20,25,10,15,20),
error de sustitución, escasez de resina de encapsulado (B3=100) y sistema
degenerado F6=2·F1.

Hay tests de integración HTTP (con mocks de Supabase) para crear una
estimación, generar el informe PDF/DOCX y buscar en el RAG. El rate limit de
estimaciones está desactivado en pytest (`RATE_LIMIT_ENABLED=false`) salvo en
`test_rate_limit.py`.

### Confiabilidad

Las excepciones no controladas responden JSON `{error, message, detail}` sin
stack trace fuera de `DEBUG=true`. `POST /api/v1/agent/run` está limitado con
slowapi (por defecto 10 estimaciones por empleado y hora;
`ESTIMATION_RATE_LIMIT`). Un 429 se muestra en el frontend como tope horario,
no como fallo genérico.

## Base de conocimiento

`vault/` es donde cada despliegue de AgentA agrega su propia base de conocimiento:
terminología de sus recursos, normas internas y casos anteriores, en Markdown.
En el repositorio solo está `vault/.gitkeep`. No viene precargada con el negocio
de nadie.

El pipeline de indexado recorre esa carpeta y actualiza `knowledge_chunks`:

```bash
cd backend
python scripts/index_vault.py
```

Si el repositorio tiene configurado `.github/workflows/reindex-vault.yml`, un push
que toque `vault/**` dispara el mismo proceso.

Un vault sin ningún `.md` no borra los chunks ya guardados: así un path mal
apuntado no vacía la base. Para retirar notas, el directorio indexado tiene que
seguir teniendo al menos un Markdown; si no, hay que borrar esas filas aparte.

`vault-ejemplo/` guarda el caso ficticio TechChip (`recursos.md`, `productos.md`).
Es contenido de ejemplo para probar el pipeline de RAG, no para uso en producción,
y ni el indexador por defecto ni el workflow lo recorren.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # completar con las claves de Clerk
npm run dev
```

App disponible en `http://localhost:3000`. Tras iniciar sesión:

| Ruta | Pantalla |
| --- | --- |
| `/` | Proyectos del empleado (estado y presupuesto) |
| `/nueva` | Formulario para crear o elegir proyecto y enviar el problema al agente |
| `/estimaciones/{id}` | Resumen ejecutivo, pasos de cálculo, descarga PDF/DOCX |
| `/historial` | Estimaciones de todos los proyectos |
| `/proyectos/{id}` | Historial de un expediente |

En el celular la navegación es una barra inferior fija (Proyectos, Nueva,
Historial). En `md` y superior, la misma lista vive en una barra lateral.

### PWA

La app es instalable (manifest nativo de Next.js + service worker de assets
estáticos). El service worker **no** se registra con `npm run dev`: hay que
servir el build de producción. En desarrollo se retiran registros previos de
`/sw.js` y las cachés `agenta-static-*`, por si antes se ejecutó producción en
el mismo origen. No se borran sesiones ni cachés de otras aplicaciones.

```bash
cd frontend
npm run build
npm run start
```

Luego, en `http://localhost:3000`:

| Navegador | Cómo instalar |
| --- | --- |
| Chrome / Edge (Android o escritorio) | Aparece **Instalar app** en el encabezado cuando el navegador dispara `beforeinstallprompt`. También sirve el icono de instalar de la barra de direcciones. |
| Safari iOS | **Instalar app** abre la pista: Compartir → Añadir a pantalla de inicio. Hace falta el icono Apple (`apple-icon`) y `apple-mobile-web-app-capable`. |

**Instalar app** sale en el encabezado de `/sign-in` y `/sign-up`, y también
en el shell autenticado (barra lateral en escritorio, cabecera en móvil). Si
la app ya está en `standalone`, el botón se oculta.

Comprobaciones rápidas:

- Manifest: `http://localhost:3000/manifest.webmanifest` (nombre, `theme_color` `#1a2332`, iconos 192 y 512).
- Service worker: Application → Service Workers; caché `agenta-static-v2` para iconos de la PWA.
- Los recursos `/_next/*` quedan a cargo de Next y la caché HTTP del navegador.
  Guardarlos con una política cache-first puede mezclar JavaScript anterior
  con HTML nuevo durante desarrollo y provocar errores de hidratación.
- No cachea HTML, sesiones de Clerk ni llamadas a FastAPI.
- El flujo de producto (crear proyecto, agente, informe) exige una sesión de
  Clerk. Sin ella, `/` redirige a `/sign-in`.

Si una pestaña anterior muestra un error de hidratación después de actualizar
el frontend, usa `Ctrl+Shift+R` para cargar el cliente nuevo y ejecutar la
limpieza de desarrollo. No se fuerza una recarga automática del formulario.

Pruebas de regresión de caché, desde `frontend`:
`node --test tests/service-worker.test.mjs`.

## Autenticación

Solo empleados autenticados con Clerk pueden usar la aplicación. El frontend
protege todas las rutas salvo `/sign-in` y `/sign-up`; el backend valida el
session token de Clerk en cada request bajo `/api/v1` y rechaza con `401` los
tokens ausentes o inválidos. `GET /health` permanece público.

### Variables de entorno

Frontend (`frontend/.env.local`, plantilla en `frontend/.env.example`):

| Variable | Descripción |
| --- | --- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Publishable key de Clerk (`pk_test_...`). Next.js exige el prefijo `NEXT_PUBLIC_` para exponerla al navegador. |
| `CLERK_SECRET_KEY` | Secret key de Clerk (`sk_test_...`). Solo en servidor; nunca en el navegador ni en el repo. |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` / `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | Rutas de login/alta servidas por esta app (`/sign-in`, `/sign-up`). |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` / `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | Destino tras autenticarse (`/`). |
| `NEXT_PUBLIC_API_URL` | URL base del backend FastAPI (`http://localhost:8000`). |

Backend (`backend/.env`, plantilla en `backend/.env.example`):

| Variable | Descripción |
| --- | --- |
| `CLERK_JWKS_URL` | URL del JWKS de la instancia: Frontend API URL + `/.well-known/jwks.json` (Dashboard → API keys). El backend descarga y cachea las claves públicas para verificar la firma RS256. |
| `CLERK_ISSUER` | Opcional. Valor esperado del claim `iss`. Si se omite se deriva de `CLERK_JWKS_URL`. |
| `CLERK_AUTHORIZED_PARTIES` | Orígenes del frontend permitidos, separados por coma. Se comparan con el claim `azp` (protección CSRF) y alimentan CORS. |
| `ANTHROPIC_API_KEY` | Clave de la API de Anthropic que usa el agente orquestador. Sin ella, `POST /api/v1/agent/run` responde `503`. |
| `ANTHROPIC_MODEL` | Opcional. Modelo del orquestador; por defecto `claude-sonnet-5`. |
| `REPORTS_BUCKET` | Bucket privado de Supabase Storage para los informes. Por defecto `reports`. Debe existir como campo de `Settings`: una variable extra en `.env` que no esté declarada hace fallar el arranque. |
| `REPORTS_SIGNED_URL_TTL_SECONDS` | Caducidad de las URLs firmadas de descarga, en segundos. Por defecto `604800` (7 días). |
| `RATE_LIMIT_ENABLED` | Activa el tope de estimaciones por empleado. Por defecto `true`. |
| `ESTIMATION_RATE_LIMIT` | Ventana de slowapi para `POST /api/v1/agent/run`. Por defecto `10/hour`. |

El backend no necesita `CLERK_SECRET_KEY`: verifica los tokens localmente con las
claves públicas del JWKS.

### Claims requeridos en el token

En el primer request autenticado el backend crea la fila del usuario en
`employees` (sincronización lazy e idempotente). La tabla exige `name` y
`role`, que se leen de claims personalizados del session token. Configurar en
Clerk Dashboard → **Sessions → Customize session token**:

```json
{
  "name": "{{user.full_name}}",
  "role": "{{user.public_metadata.role}}"
}
```

y asignar `public_metadata.role` (p. ej. `"estimator"`) a cada empleado desde el
dashboard. Si el token no incluye ambos claims, el backend responde `403` y no
crea el empleado. Accesos posteriores no sobrescriben `name` ni `role`.

### Registro solo por invitación

El alta abierta está deshabilitada; los empleados entran por invitación:

1. Clerk Dashboard → **Restrictions → Access mode**: seleccionar **Invite-only**
   (valor `restricted` en la API). Con este modo `<SignIn />` oculta el enlace
   de registro y `<SignUp />` solo acepta invitaciones válidas.
2. Dashboard → **Users → Invite**: enviar la invitación al correo del empleado.
   Si se crea por API/CLI puede incluir `publicMetadata: {"role": "..."}`, que
   se copia al usuario al aceptar; si se crea desde el dashboard, fijar
   `public_metadata.role` en el usuario tras el alta.
3. El enlace de la invitación aterriza en `/sign-up`, que completa el registro
   con el componente `<SignUp />` de Clerk.

## Verificación

```bash
# Backend público
curl http://localhost:8000/health
# → {"status":"ok","database":{"connected":true}}

# Backend protegido sin token → 401
curl -i http://localhost:8000/api/v1/me

# Frontend: abrir http://localhost:3000; sin sesión redirige a /sign-in.
# Tras iniciar sesión, `/` lista los proyectos del empleado (vacío si aún no hay).
```

Tests del backend (incluyen verificación JWT y sincronización de empleados):

```bash
cd backend && pytest
```

## Producción y CI/CD (fase 10)

La [guía de producción](docs/PRODUCTION.md) incluye el bootstrap de GCP, Secret
Manager, Workload Identity Federation, despliegue de Cloud Run, conexión de Vercel
con GitHub, variables, dominio propio con HTTPS, verificación y rollback.
Los workflows `ci.yml` y `deploy-production.yml` ejecutan las comprobaciones antes
de publicar cada merge a `main`. Se requieren las cuentas, claves y DNS descritos
en la guía para activar los recursos remotos.
