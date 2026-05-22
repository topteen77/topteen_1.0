"""Psychometric completion counts: legacy (test1–3) + post-matric (4 tests)."""
from __future__ import annotations

from typing import Sequence, Set

from django.db.models import Count, Exists, OuterRef

from app.models import Results, TestCompletion


def legacy_complete_user_ids(user_ids: Sequence[int]) -> Set[int]:
    uids = {int(x) for x in user_ids if x}
    if not uids:
        return set()
    with_results = set(
        Results.objects.filter(user_id__in=uids).values_list("user_id", flat=True).distinct()
    )
    if not with_results:
        return set()
    complete = set(
        TestCompletion.objects.filter(
            user_id__in=with_results,
            test1_complete=True,
            test2_complete=True,
            test3_complete=True,
        ).values_list("user_id", flat=True)
    )
    return uids & with_results & complete


def post_matric_complete_user_ids(user_ids: Sequence[int]) -> Set[int]:
    from app_post_matric.models import TestSession

    uids = [int(x) for x in user_ids if x]
    if not uids:
        return set()
    return set(
        TestSession.objects.filter(user_id__in=uids, is_completed=True)
        .values("user_id")
        .annotate(n=Count("test_id", distinct=True))
        .filter(n__gte=4)
        .values_list("user_id", flat=True)
    )


def psychometric_complete_user_ids(user_ids: Sequence[int]) -> Set[int]:
    uids = {int(x) for x in user_ids if x}
    if not uids:
        return set()
    return legacy_complete_user_ids(uids) | post_matric_complete_user_ids(uids)


def student_management_psychometric_complete_exists():
    from app_post_matric.models import TestSession

    legacy = Exists(Results.objects.filter(user_id=OuterRef("student_id"))) & Exists(
        TestCompletion.objects.filter(
            user_id=OuterRef("student_id"),
            test1_complete=True,
            test2_complete=True,
            test3_complete=True,
        )
    )
    post = Exists(
        TestSession.objects.filter(user_id=OuterRef("student_id"), test_id=1, is_completed=True)
    )
    for tid in (2, 3, 4):
        post = post & Exists(
            TestSession.objects.filter(
                user_id=OuterRef("student_id"), test_id=tid, is_completed=True
            )
        )
    return legacy | post
