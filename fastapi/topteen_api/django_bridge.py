"""
Initialize Django in-process so FastAPI can call ORM and shared analytics (same MySQL as Django).

Requires: `pip install` deps from `fastapi/requirements.txt` including Django, and a working
`DB_*` / `.env` configuration for the same database as the main app.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_repo_root: Path = Path(__file__).resolve().parents[2]
_initialized = False


def get_repo_root() -> Path:
    return _repo_root


def init_django() -> None:
    global _initialized
    if _initialized:
        return
    root = str(_repo_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topteens.settings")
    import django

    django.setup()
    _initialized = True
