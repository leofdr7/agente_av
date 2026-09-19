from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.api.deps import get_current_employee
from app.api.health import router as health_router
from app.api.linear_systems import router as linear_systems_router
from app.api.me import router as me_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.authorized_parties,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Público: sondas de salud sin autenticación.
app.include_router(health_router)

# Protegido: todo lo que cuelga de /api/v1 exige un empleado autenticado.
api_v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_employee)])
api_v1.include_router(me_router)
api_v1.include_router(linear_systems_router)
api_v1.include_router(agent_router)
app.include_router(api_v1)
