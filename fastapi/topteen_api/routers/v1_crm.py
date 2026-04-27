from __future__ import annotations

from fastapi import APIRouter

from ._common import not_implemented_django

router = APIRouter()


@router.post("/leads")
async def crm_leads() -> None:
    not_implemented_django(method="POST", django_path="/api/v1/crm/leads")
