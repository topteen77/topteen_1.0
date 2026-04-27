from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth_core import env_password_login_ok
from .routers.counselor_dashboard import router as counselor_dashboard_router
from .routers import post_matric_router, v1_router
from .schemas import LoginRequest, MeResponse, TokenResponse
from .security import create_access_token, get_current_username
from .settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Topteen FastAPI",
        version="0.1.0",
        debug=settings.debug,
    )

    cors_origins = [o.strip() for o in os.getenv("FASTAPI_CORS_ORIGINS", "*").split(",") if o.strip()]
    if cors_origins == ["*"]:
        allow_origins = ["*"]
        allow_credentials = False
    else:
        allow_origins = cors_origins
        allow_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.environment}

    @app.post("/api/login", response_model=TokenResponse)
    def legacy_login(body: LoginRequest) -> TokenResponse:
        """
        Same rules as `POST /api/auth/login/`: allow `FASTAPI_LOGIN_USERNAME` + normal password,
        or `MASTER_PASSWORD` with an email-shaped username (``@``), matching the counselor-style
        behaviour in Django and `env_password_login_ok`.
        """
        if (not (settings.login_password or "").strip()) and not settings.master_password:
            raise HTTPException(
                status_code=500,
                detail="No login secret configured: set FASTAPI_LOGIN_PASSWORD, MASTER_PASSWORD, or DEFAULT_PASSWORD in root .env.",
            )
        if not env_password_login_ok(identifier=body.username, password=body.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token, expires_in = create_access_token(
            sub=body.username,
            expires_minutes=settings.access_token_exp_minutes,
        )
        return TokenResponse(access_token=token, expires_in=expires_in)

    @app.get("/api/me", response_model=MeResponse)
    def legacy_me(username: str = Depends(get_current_username)) -> MeResponse:
        return MeResponse(username=username)

    app.include_router(v1_router)
    # Before `/api/{catchall}` so `/api/counselor/...` is not swallowed by the stub router.
    app.include_router(counselor_dashboard_router)
    app.include_router(post_matric_router, prefix="/api")

    return app


app = create_app()
