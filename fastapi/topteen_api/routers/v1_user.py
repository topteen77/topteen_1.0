from __future__ import annotations

from fastapi import APIRouter

from ._common import not_implemented_django

router = APIRouter()

_USER_POST_PATHS = [
    "shortlistcareer",
    "shortlistcollege",
    "shortlistexam",
    "user-note-save",
    "user-note-delete",
    "remove-hobbie",
    "resume-about",
    "resume-skill",
    "resume-certificate",
    "resume-internship",
    "resume-activity",
    "resume-volunteer",
    "resume-mail-send",
    "create-folder",
    "create-file",
    "skilllab-course-payment",
    "skilllab-course-update-payment",
]


def _make_user_stub(path_suffix: str):
    django_path = f"/api/v1/user/{path_suffix}"

    async def handler() -> None:
        not_implemented_django(method="POST", django_path=django_path)

    handler.__name__ = f"user_{path_suffix.replace('-', '_')}"
    return handler


for _p in _USER_POST_PATHS:
    router.add_api_route(f"/{_p}", _make_user_stub(_p), methods=["POST"])
