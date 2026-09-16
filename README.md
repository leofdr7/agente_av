# Agente de IA para estimaciones de álgebra vectorial

Monorepo con backend FastAPI y frontend Next.js para estimaciones basadas en presupuestos.

## Estructura

```
├── backend/     # FastAPI (Python 3.11+)
├── frontend/    # Next.js 16 (App Router, TypeScript, Tailwind, shadcn/ui, Clerk)
└── docker-compose.yml
```

## Prerrequisitos

- Python 3.11+
- Node.js 20+
- Docker (opcional, para backend en contenedor)
- Una aplicación en [Clerk](https://clerk.com) (ver [Autenticación](#autenticación))

## Backend

### Desarrollo local

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
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

### Tests

```bash
cd backend
pytest
```

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # completar con las claves de Clerk
npm run dev
```

App disponible en `http://localhost:3000`.

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
# Tras iniciar sesión, la tarjeta "Sesión" muestra el empleado devuelto por /api/v1/me.
```

Tests del backend (incluyen verificación JWT y sincronización de empleados):

```bash
cd backend && pytest
```
