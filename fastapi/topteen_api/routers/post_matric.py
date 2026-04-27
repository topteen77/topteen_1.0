from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth_core import env_password_login_ok
from ..schemas import (
    PostMatricUserMeResponse,
    TokenObtainPairRequest,
    TokenObtainPairResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from ..security import get_current_username, issue_token_pair, refresh_access_token
from ._common import not_implemented_django

router = APIRouter(tags=["api-post-matric"])


@router.post("/auth/login/", response_model=TokenObtainPairResponse)
async def auth_login(body: TokenObtainPairRequest) -> TokenObtainPairResponse:
    if not env_password_login_ok(identifier=body.username, password=body.password):
        raise HTTPException(
            status_code=401,
            detail="No active account found with the given credentials",
        )
    access, refresh, _ = issue_token_pair(sub=body.username.strip())
    return TokenObtainPairResponse(access=access, refresh=refresh)


@router.post("/auth/refresh/", response_model=TokenRefreshResponse)
async def auth_refresh(body: TokenRefreshRequest) -> TokenRefreshResponse:
    access, _ = refresh_access_token(refresh_token=body.refresh)
    return TokenRefreshResponse(access=access)


@router.post("/auth/register/")
async def auth_register(_: Request) -> None:
    not_implemented_django(method="POST", django_path="/api/auth/register/")


@router.get("/users/me/", response_model=PostMatricUserMeResponse)
async def users_me_get(
    email: str = Depends(get_current_username),
) -> PostMatricUserMeResponse:
    name = email.split("@", 1)[0] if "@" in email else email
    return PostMatricUserMeResponse(id=0, name=name, email=email, mobile=None)


@router.patch("/users/me/")
async def users_me_patch(_: Request) -> None:
    not_implemented_django(method="PATCH", django_path="/api/users/me/")


@router.api_route(
    "/{catchall:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def post_matric_drf_stub(request: Request, catchall: str) -> None:
    not_implemented_django(method=request.method, django_path=f"/api/{catchall}")
