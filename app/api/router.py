from fastapi import APIRouter

from app.api.v1.router import router as v1_router
from app.api.views.health import router as health_router
from app.core.config import get_settings

api_router = APIRouter()
settings = get_settings()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(v1_router, prefix=settings.api_v1_prefix)
