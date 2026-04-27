from __future__ import annotations

from fastapi import APIRouter

from .v1_counselor import router as counselor_router
from .v1_crm import router as crm_router
from .v1_institute import router as institute_router
from .v1_marketing import router as marketing_router
from .v1_user import router as user_router

router = APIRouter(prefix="/api/v1")

router.include_router(user_router, prefix="/user", tags=["api-v1-user"])
router.include_router(institute_router, prefix="/institute", tags=["api-v1-institute"])
router.include_router(counselor_router, prefix="/counselor", tags=["api-v1-counselor"])
router.include_router(marketing_router, prefix="/marketing", tags=["api-v1-marketing"])
router.include_router(crm_router, prefix="/crm", tags=["api-v1-crm"])
