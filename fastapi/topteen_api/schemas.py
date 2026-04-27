from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    username: str


class TokenObtainPairRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenObtainPairResponse(BaseModel):
    access: str
    refresh: str


class TokenRefreshRequest(BaseModel):
    refresh: str = Field(..., min_length=1)


class TokenRefreshResponse(BaseModel):
    access: str


class PostMatricUserMeResponse(BaseModel):
    id: int
    name: str | None
    email: str
    mobile: str | None = None
