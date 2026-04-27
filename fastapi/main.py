"""
Entry point: `cd fastapi && uvicorn main:app --reload --port 8001`

The package lives in `topteen_api/` because a folder named `fastapi/` would shadow the
installed `fastapi` Python package.
"""

from topteen_api.main import app  # noqa: F401
