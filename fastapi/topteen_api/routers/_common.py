from __future__ import annotations

from fastapi import HTTPException, Request


def not_implemented_django(*, method: str, django_path: str) -> None:
    raise HTTPException(
        status_code=501,
        detail={
            "code": "not_implemented",
            "message": "This FastAPI service mirrors Django routes; business logic is not wired yet.",
            "django": f"{method} {django_path}",
        },
    )


async def parse_post_flat(request: Request) -> dict[str, str]:
    ct = (request.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        body = await request.json()
        if not isinstance(body, dict):
            return {}
        return {str(k): "" if v is None else str(v) for k, v in body.items()}
    form = await request.form()
    return {str(k): "" if v is None else str(v) for k, v in form.items()}


def parse_remember_me(raw: str | None) -> bool:
    if raw is None or raw == "":
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}
