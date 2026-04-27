from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .settings import get_settings

_bearer = HTTPBearer(auto_error=False)
TokenUse = Literal["access", "refresh"]


def _encode(payload: dict[str, Any]) -> str:
    s = get_settings()
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(*, sub: str, expires_minutes: int) -> tuple[str, int]:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload: dict[str, Any] = {
        "sub": sub,
        "token_use": "access",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": exp,
    }
    token = _encode(payload)
    return token, int(expires_minutes * 60)


def create_refresh_token(*, sub: str, expires_days: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=expires_days)
    payload: dict[str, Any] = {
        "sub": sub,
        "token_use": "refresh",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": exp,
    }
    return _encode(payload)


def issue_token_pair(*, sub: str) -> tuple[str, str, int]:
    s = get_settings()
    access, expires_in = create_access_token(
        sub=sub, expires_minutes=s.access_token_exp_minutes
    )
    refresh = create_refresh_token(
        sub=sub, expires_days=s.refresh_token_exp_days
    )
    return access, refresh, expires_in


def decode_token(token: str, *, expected_use: TokenUse | None = None) -> dict[str, Any]:
    s = get_settings()
    payload = jwt.decode(
        token,
        s.jwt_secret,
        algorithms=[s.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )
    use = payload.get("token_use")
    if expected_use is not None:
        if use != expected_use:
            raise HTTPException(status_code=401, detail="Invalid token type")
    elif use == "refresh":
        raise HTTPException(status_code=401, detail="Refresh token not allowed here")
    return payload


def refresh_access_token(*, refresh_token: str) -> tuple[str, int]:
    s = get_settings()
    try:
        payload = jwt.decode(
            refresh_token,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token is invalid or expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token is invalid or expired")

    if payload.get("token_use") != "refresh":
        raise HTTPException(status_code=401, detail="Token is invalid or expired")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    return create_access_token(
        sub=sub, expires_minutes=s.access_token_exp_minutes
    )


def get_current_username(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        payload = decode_token(creds.credentials)
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    return sub
