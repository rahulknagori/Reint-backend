from fastapi import APIRouter

from app.api.v1.views.wind_power import router as wind_power_router

router = APIRouter()
router.include_router(wind_power_router, tags=["wind-power"])
