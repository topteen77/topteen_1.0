from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..auth_core import env_password_login_ok
from ..security import issue_token_pair
from ._common import parse_post_flat, parse_remember_me

router = APIRouter()


@router.post("/login/")
async def counselor_login(request: Request):
    data: dict = {}
    fields = await parse_post_flat(request)
    email = (fields.get("email") or "").strip()
    password = (fields.get("password") or "").strip()
    remember_me = parse_remember_me(fields.get("remember_me"))
    errors: dict[str, list[str]] = {}
    if not email:
        errors["email"] = ["Email is required"]
    if not password:
        errors["password"] = ["Password is required"]
    if errors:
        data["success"] = False
        data["errors"] = errors
        data["message"] = "Please provide email and password"
        return JSONResponse(data, status_code=400)

    if not env_password_login_ok(identifier=email, password=password):
        data["success"] = False
        data["message"] = "Invalid email or password"
        data["errMsg"] = "Invalid email or password"
        return JSONResponse(data, status_code=200)

    access, refresh, _ = issue_token_pair(sub=email)
    data["success"] = True
    data["message"] = "Login successful"
    data["redirect_url"] = "/counselor/counselor_dashboard/0/"
    data["access"] = access
    data["refresh"] = refresh
    _ = remember_me
    return JSONResponse(data, status_code=200)
