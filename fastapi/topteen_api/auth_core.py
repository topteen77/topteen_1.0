from __future__ import annotations

from .settings import get_settings


def env_password_login_ok(*, identifier: str, password: str) -> bool:
    """
    Stand-in for Django `authenticate()` without the ORM.

    - Normal: `identifier` must match `FASTAPI_LOGIN_USERNAME` and password must
      match the configured login password.
    - Master password: if `MASTER_PASSWORD` is set and `password` matches, any
      non-empty `identifier` containing `@` is accepted (counselor-style).
    """
    s = get_settings()
    ident = (identifier or "").strip()
    pw = (password or "").strip()
    if not ident or not pw:
        return False
    if not s.login_password:
        return False
    if pw == s.login_password and ident == (s.login_username or "").strip():
        return True
    if s.master_password and pw == s.master_password and "@" in ident:
        return True
    return False
