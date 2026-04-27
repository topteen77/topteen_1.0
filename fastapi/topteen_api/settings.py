from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


def _load_root_env() -> Path:
    """Load repository root `.env` (sibling of `fastapi/`)."""
    root_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=root_env, override=False)
    return root_env


@dataclass(frozen=True)
class Settings:
    env_file: Path
    environment: str
    debug: bool
    host: str
    port: int
    jwt_secret: str
    jwt_algorithm: str
    access_token_exp_minutes: int
    refresh_token_exp_days: int
    login_username: str
    login_password: str
    master_password: str | None


def get_settings() -> Settings:
    env_file = _load_root_env()

    environment = os.getenv("ENVIRONMENT", "development")
    debug = os.getenv("DEBUG", "False").lower() in {"1", "true", "yes", "y", "on"}
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", os.getenv("APP_PORT", "8000")))

    jwt_secret = (os.getenv("FASTAPI_JWT_SECRET") or "").strip()
    if not jwt_secret:
        raise RuntimeError(
            "FASTAPI_JWT_SECRET is missing in root .env. "
            "Run: python fastapi/scripts/generate_fastapi_secrets.py"
        )

    jwt_algorithm = os.getenv("FASTAPI_JWT_ALGORITHM", "HS256")
    access_token_exp_minutes = int(
        os.getenv(
            "FASTAPI_JWT_ACCESS_MINUTES",
            os.getenv("FASTAPI_ACCESS_TOKEN_EXP_MINUTES", "60"),
        )
    )
    refresh_token_exp_days = int(os.getenv("FASTAPI_JWT_REFRESH_DAYS", "1"))

    login_username = os.getenv("FASTAPI_LOGIN_USERNAME", "admin")
    login_password = os.getenv(
        "FASTAPI_LOGIN_PASSWORD",
        os.getenv("MASTER_PASSWORD", os.getenv("DEFAULT_PASSWORD", "")),
    )
    master_pw = (os.getenv("MASTER_PASSWORD") or "").strip()
    master_password = master_pw or None

    return Settings(
        env_file=env_file,
        environment=environment,
        debug=debug,
        host=host,
        port=port,
        jwt_secret=jwt_secret,
        jwt_algorithm=jwt_algorithm,
        access_token_exp_minutes=access_token_exp_minutes,
        refresh_token_exp_days=refresh_token_exp_days,
        login_username=login_username,
        login_password=login_password,
        master_password=master_password,
    )
