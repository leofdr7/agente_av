# Agente de IA para estimaciones de álgebra vectorial

Monorepo con backend FastAPI y frontend Next.js para estimaciones basadas en presupuestos.

## Estructura

```
├── backend/     # FastAPI (Python 3.11+)
├── frontend/    # Next.js 15 (App Router, TypeScript, Tailwind, shadcn/ui)
└── docker-compose.yml
```

## Prerrequisitos

- Python 3.11+
- Node.js 20+
- Docker (opcional, para backend en contenedor)

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
npm run dev
```

App disponible en `http://localhost:3000`.

## Verificación

```bash
# Backend
curl http://localhost:8000/health
# → {"status":"ok"}

# Frontend: abrir http://localhost:3000 en el navegador
```
