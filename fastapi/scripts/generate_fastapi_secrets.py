#!/usr/bin/env python3
"""
Print values for root `.env` (FastAPI).

Usage (from repo root):
  python fastapi/scripts/generate_fastapi_secrets.py
"""
from __future__ import annotations

import secrets


def main() -> None:
    jwt_secret = secrets.token_urlsafe(48)
    api_key = secrets.token_hex(16)
    api_secret = secrets.token_hex(32)
    print("# Add to repo root .env (do not commit secrets)")
    print(f"FASTAPI_JWT_SECRET={jwt_secret}")
    print(f"FASTAPI_API_KEY={api_key}")
    print(f"FASTAPI_API_SECRET={api_secret}")


if __name__ == "__main__":
    main()
