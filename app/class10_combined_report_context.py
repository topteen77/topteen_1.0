"""Build template context for Class 10 (Stream Sorter) combined reports."""
from __future__ import annotations

import logging
import os
from datetime import datetime as dt
from typing import Any, Dict, Optional

from app.aptitude_stream_selection import (
    recommend_streams_from_tiers,
    streamsubject_from_recommendation,
)
from app.models import Results, TestCompletion
from app.riasec_report_utils import get_stream_career_sections
from users.models import UserProfile

logger = logging.getLogger(__name__)


def build_class10_combined_report_context(
    request,
    target_user,
    *,
    route_user_id: Optional[int] = None,
    embed_mode: bool = False,
) -> Dict[str, Any]:
    """Shared context for Class 10 combined report pages and parent inline embed."""
    from app.views import (
        UserHasNotAttemptedTestException,
        db_results_inst_user,
        gernate_graph,
        has_attempted_test,
    )
    from core.utils import ensure_user_pdf_folder

    ensure_user_pdf_folder(target_user.id)

    if not has_attempted_test(target_user):
        return {
            "error": "No completed test found. Please complete all tests first.",
            "no_results": True,
            "user": target_user,
            "user_id": target_user.id,
            "embed_mode": embed_mode,
        }

    test1_completed = Results.objects.filter(user=target_user, test_paper="test1").exists()
    test2_completed = Results.objects.filter(user=target_user, test_paper="test2").exists()
    test3_completed = Results.objects.filter(user=target_user, test_paper="test3").exists()
    all_tests_completed = test1_completed and test2_completed and test3_completed

    if not all_tests_completed:
        return {
            "error": "Please complete all three tests (Personality, Interest, and Aptitude) to view your combined report.",
            "no_results": True,
            "user": target_user,
            "user_id": target_user.id,
            "test1_completed": test1_completed,
            "test2_completed": test2_completed,
            "test3_completed": test3_completed,
            "embed_mode": embed_mode,
        }

    try:
        user_profile = target_user.user_profile
    except UserProfile.DoesNotExist:
        user_profile = None

    try:
        top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = (
            db_results_inst_user(target_user)
        )
    except UserHasNotAttemptedTestException:
        return {
            "error": "User hasn't attempted the test yet. Please complete the test first.",
            "no_results": True,
            "user": target_user,
            "embed_mode": embed_mode,
        }
    except Exception:
        logger.exception("Error in db_results_inst_user for user %s", target_user.id)
        top_category = None
        streamsubject = set()
        courseName = set()
        max_length = ""
        min_length = ""
        below = []
        avg = []
        above_avg = []
        top_categories = []

    test1_result = Results.objects.filter(user=target_user, test_paper="test1").first()
    test2_result = Results.objects.filter(user=target_user, test_paper="test2").first()
    test3_result = Results.objects.filter(user=target_user, test_paper="test3").first()

    personality_data = {}
    if test1_result and test1_result.results:
        sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
        personality_data = {
            "results": dict(sorted_results),
            "top_categories": top_categories,
            "top_category": top_category,
        }

    interest_data = {}
    if test2_result and test2_result.scores:
        interest_data = {
            "scores": test2_result.scores,
            "max_category": max_length,
            "min_category": min_length,
        }

    intelligence_data = {}
    if test3_result and test3_result.scores:
        scores = {label.split("_")[0].upper(): value for label, value in test3_result.scores.items()}
        intelligence_data = {
            "scores": scores,
            "below_avg": below,
            "average": avg,
            "above_avg": above_avg,
        }

    from app.graph_media_utils import graph_image_basenames, graph_images_directory

    graph_dir = graph_images_directory()
    graph_basename_name = getattr(target_user, "name", None) or target_user.email
    graph_files = graph_image_basenames(graph_basename_name, target_user.id)
    need_graphs = any(not os.path.exists(os.path.join(graph_dir, f)) for f in graph_files)
    if need_graphs:
        original_user = getattr(request, "user", None)
        try:
            request.user = target_user
            gernate_graph(request)
        except Exception as exc:
            logger.warning(
                "class10_combined_report: could not generate graphs for user %s: %s",
                target_user.id,
                exc,
            )
        finally:
            if original_user is not None:
                request.user = original_user

    _student_name = getattr(target_user, "name", None) or target_user.email
    _created_date = None
    if test1_result and hasattr(test1_result, "created"):
        _created_date = test1_result.created
    if _created_date is None:
        _created_date = getattr(target_user, "date_joined", None)

    viewer_id = int(getattr(request.user, "id", 0) or 0)
    effective_route_id = route_user_id if route_user_id is not None else int(target_user.id)

    context: Dict[str, Any] = {
        "user": target_user,
        "user_profile": user_profile,
        "student_name": _student_name,
        "created_date": _created_date,
        "now": dt.now(),
        "all_tests_completed": all_tests_completed,
        "test1_completed": test1_completed,
        "test2_completed": test2_completed,
        "test3_completed": test3_completed,
        "test1_result": test1_result,
        "test2_result": test2_result,
        "test3_result": test3_result,
        "personality_data": personality_data,
        "interest_data": interest_data,
        "intelligence_data": intelligence_data,
        "top_category": top_category,
        "streamsubject": streamsubject,
        "courseName": courseName,
        "stream_career_sections": get_stream_career_sections(top_category),
        "top_categories": top_categories,
        "max_length": max_length,
        "min_length": min_length,
        "below": below,
        "avg": avg,
        "above_avg": above_avg,
        "no_results": False,
        "viewing_as_admin": effective_route_id != viewer_id,
        "user_id": effective_route_id,
        "user_name": _student_name,
        "user_ID": target_user.id,
        "embed_mode": embed_mode,
    }

    from app.interest_report_utils import interest_report_context_fields

    context.update(
        interest_report_context_fields(
            scores=test2_result.scores if test2_result and test2_result.scores else None,
            max_length=max_length,
            min_length=min_length,
        )
    )

    from app.report_visibility import should_show_extended_career_pathways
    from app.vocational_recommendations import vocational_guidance_context_for_below_areas

    context.update(vocational_guidance_context_for_below_areas(below, user=target_user))
    context["student_below_average"] = not should_show_extended_career_pathways(below, avg, above_avg)

    stream_recommendation = recommend_streams_from_tiers(above_avg, avg, below_avg=below)
    context["stream_recommendation"] = stream_recommendation

    if should_show_extended_career_pathways(below, avg, above_avg):
        from app.stream_sorter_guidance import build_report_stream_guidance

        aptitude_streams = streamsubject_from_recommendation(stream_recommendation)
        context["stream_sorter_guidance"] = (
            build_report_stream_guidance(aptitude_streams, top_category=top_category)
            if aptitude_streams
            else None
        )
    else:
        context["stream_sorter_guidance"] = None

    from app.aptitude_report_utils import aptitude_report_context_fields

    context.update(
        aptitude_report_context_fields(
            test3_result.scores if test3_result and test3_result.scores else None
        )
    )
    return context
