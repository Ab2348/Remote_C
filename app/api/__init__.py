from fastapi import APIRouter

from app.api.routes import router as control_router
from app.api.volume_routes import router as volume_router


router = APIRouter()
router.include_router(control_router)
router.include_router(volume_router)

__all__ = ["router"]
