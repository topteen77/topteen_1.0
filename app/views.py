import time
from django.shortcuts import redirect, render
from core.breadcrumbs import get_breadcrumb
from core.utils import (
    class10_assessment_pdf_filename,
    class10_combined_report_pdf_filename,
    class10_web_report_pdf_filename,
    ensure_user_pdf_folder,
    save_user_pdf,
    serve_user_pdf_response,
    user_pdf_exists,
)
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from .forms import UploadFileForm
from .models import Question
from django.http import HttpResponse
from django.template.loader import get_template
from django.template import engines
import json
from django.contrib import messages

import os
import matplotlib.pyplot as plt
import shutil

import weasyprint
from django.conf import settings
import csv
from django.contrib.staticfiles import finders
import re
import logging
from django.shortcuts import get_object_or_404
# from django.contrib.auth.models import User
from .models import TestCompletion,Answer,Results

logger = logging.getLogger(__name__)

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.models import Category, Course, Stream
from app.aptitude_stream_selection import (
    premium_career_groups_from_recommendation,
    recommend_streams_from_tiers,
    streamsubject_from_recommendation,
    suitable_combinations_from_recommendation,
)

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.core.cache import cache
final_score = None

from .forms import UserRegisterForm
from users.models import UserProfile
from django.middleware.csrf import get_token
from django.core.exceptions import ObjectDoesNotExist

from django.contrib.auth import get_user_model
from institute.decorators import (
    institute_user_only,
    institute_authenticated_user_only,
    institute_block_student_only,
    institute_update_delete_student_only,
    institute_change_student_password_only,
    institute_profile_update_delete,
    only_superuser,
    institute_group_user_only
)
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


User = get_user_model()

# Define a custom exception for handling the case where the user hasn't attempted the test
class UserHasNotAttemptedTestException(Exception):
    pass


@csrf_exempt
@require_http_methods(['POST'])
def speed_test(request):
    """Dummy endpoint for instruction-page internet speed meter upload test. Returns 200."""
    return HttpResponse(status=200)


def custom_logout(request):
    logger.info('Logging out %s', request.user)  # Logging the user who is logging out
    logout(request)
    return redirect('/')

def career_tree1(request):
    return render(request, 'sub.html')

def career_tree(request):
    return render(request, 'topteenfrontend/user/app/career_tree.html')

def quick_link(request):
    return render(request, 'topteenfrontend/user/app/quick_link.html')

def db_results(request):

    user = request.user
    if not has_attempted_test(user):
        raise UserHasNotAttemptedTestException("User hasn't attempted the test yet.")
    
    top_3_categories = ""
    top_categories = []
    questions= Question.objects.all()
    # Get the data from the database fro the Personality test
    try:
        if questions is not None:
            test1_result = Results.objects.get(user = request.user, test_paper='test1')
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            
            for i, (category, score) in enumerate(sorted_results, start=1):
                if i > 3:
                    break
                top_categories.append({
                    'rank': i,
                    'category': category,
                    'score': f"{score:.2f}%"
                })
                top_3_categories += category[0]

            top_3_categories_str = "".join(top_3_categories)

        top_3 = top_3_categories_str.split(',')
        top_category_code = top_3[0]
    except:
        top_categories = ''
        top_category_code = ''


    # Get the data from the database for the Career interest test
    try:
        from app.interest_report_utils import resolve_interest_extrema
        test2_result = Results.objects.get(user=request.user, test_paper='test2')
        lengths = test2_result.scores
        max_length, min_length, _, _ = resolve_interest_extrema(lengths)
    except Results.DoesNotExist:
        max_length = ''
        min_length = ''

    # Get the data from the database for the Intelligence test
    try:
        test3_result = Results.objects.get(user=request.user, test_paper='test3')
        personality_res = test3_result.scores
        scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
        below = []
        avg = []
        above_avg = []
        for key in scores:
            if scores[key] <= 5:
                below.append(key)
            elif scores[key] <= 10:
                avg.append(key)
            else:
                above_avg.append(key)
    except Results.DoesNotExist:
        below = ''
        avg = ''
        above_avg = ''

    # Get the top category using the code
    top_category = Category.objects.filter(category=top_category_code).first()
    streamsubject = set()
    courseName = set()
    if top_category:
        category_id = top_category.id
        # Get streams related to this category using the category ID
        streams = Stream.objects.filter(category_id=category_id)
        # Print the details of each stream
        for stream in streams:
            streamsubject.add((stream.stream_name, stream.subjects))

        # Get courses related to this category using the category ID
        courses = Course.objects.filter(category_id=category_id)
        for course in courses:
            # Print the details of each courses
            courseName.add(course.course_name)

    else:
        logger.debug("No category found with the code: %s", top_category_code)

    return top_category, streamsubject,courseName, max_length, min_length, below, avg, above_avg, top_categories
# Example implementation of has_attempted_test function

def has_attempted_test(user):
    return TestCompletion.objects.filter(user=user).exists()


APTITUDE_STREAM_MAP = {
    'NUMERICAL': ['PCM', 'CWM'],
    'VERBAL': ['HUM', 'CWM'],
    'LOGICAL': ['PCM', 'PCB'],
    'MECHANICAL': ['PCM', 'CS'],
    'SPATIAL': ['PCM', 'Fine Arts'],
    'LANGUAGE': ['HUM', 'HWL'],
    'CRITICAL': ['PCM', 'HUM'],
}

STREAM_SUBJECT_MAP = {
    'PCM': {'label': 'PCM (Physics, Chemistry, Mathematics)', 'stream': 'PCM', 'subjects': 'Physics, Chemistry, Mathematics', 'color_class': 'stream-chip-pcm'},
    'PCB': {'label': 'PCB (Physics, Chemistry, Biology)', 'stream': 'PCB', 'subjects': 'Physics, Chemistry, Biology', 'color_class': 'stream-chip-pcb'},
    'HUM': {'label': 'HUM (Humanities)', 'stream': 'HUM', 'subjects': 'Humanities', 'color_class': 'stream-chip-hum'},
    'HWL': {'label': 'HWL (Humanities with Languages)', 'stream': 'HWL', 'subjects': 'Humanities with Languages', 'color_class': 'stream-chip-hwl'},
    'CWM': {'label': 'CWM (Commerce with Mathematics)', 'stream': 'CWM', 'subjects': 'Commerce with Mathematics', 'color_class': 'stream-chip-cwm'},
    'CWOM': {'label': 'CWOM (Commerce without Mathematics)', 'stream': 'CWOM', 'subjects': 'Commerce without Mathematics', 'color_class': 'stream-chip-cwom'},
    'CS': {'label': 'CS (Computer Science)', 'stream': 'CS', 'subjects': 'Computer Science', 'color_class': 'stream-chip-cs'},
    'FINE ARTS': {'label': 'Fine Arts', 'stream': 'Fine Arts', 'subjects': 'Fine Arts', 'color_class': 'stream-chip-finearts'},
}


def _normalize_stream_code(stream_code):
    return str(stream_code or '').upper().strip()


def _build_stream_questionnaire_options(intelligence_scores_by_code, primary_aptitude, suitable_combinations):
    """Attach intelligence match scores to suggested and alternate stream options."""
    stream_to_aptitudes = {}
    for aptitude, streams in APTITUDE_STREAM_MAP.items():
        for stream in streams:
            key = _normalize_stream_code(stream)
            stream_to_aptitudes.setdefault(key, [])
            if aptitude not in stream_to_aptitudes[key]:
                stream_to_aptitudes[key].append(aptitude)

    primary_aptitude = _normalize_stream_code(primary_aptitude)
    primary_streams = {_normalize_stream_code(s) for s in APTITUDE_STREAM_MAP.get(primary_aptitude, [])}

    def compute_score(stream_code):
        code = _normalize_stream_code(stream_code)
        aptitudes = stream_to_aptitudes.get(code, [])
        if not aptitudes and primary_aptitude:
            aptitudes = [primary_aptitude]
        if not aptitudes:
            if intelligence_scores_by_code:
                fallback_score = int(round(
                    sum(intelligence_scores_by_code.values()) / len(intelligence_scores_by_code)
                ))
                return max(0, min(100, fallback_score)), ['Overall aptitude']
            return 0, []
        score_values = [int(intelligence_scores_by_code.get(area, 0)) for area in aptitudes]
        base_score = int(round(sum(score_values) / len(score_values)))
        if code in primary_streams:
            base_score = min(100, base_score + 8)
        return max(0, min(100, base_score)), aptitudes

    suggested_codes = {_normalize_stream_code(item.get('stream')) for item in suitable_combinations}

    scored_suggested = []
    for combo in suitable_combinations:
        entry = dict(combo)
        code = _normalize_stream_code(entry.get('stream'))
        match_score, aptitude_areas = compute_score(code)
        entry['match_score'] = match_score
        entry['aptitude_areas'] = aptitude_areas
        entry['aptitude_areas_display'] = ', '.join(str(area).title() for area in aptitude_areas)
        scored_suggested.append(entry)

    scored_other = []
    for key, meta in STREAM_SUBJECT_MAP.items():
        entry = dict(meta)
        code = _normalize_stream_code(entry.get('stream', key))
        if code in suggested_codes:
            continue
        match_score, aptitude_areas = compute_score(code)
        entry['match_score'] = match_score
        entry['aptitude_areas'] = aptitude_areas
        entry['aptitude_areas_display'] = ', '.join(str(area).title() for area in aptitude_areas)
        scored_other.append(entry)

    scored_other.sort(key=lambda item: item.get('match_score', 0), reverse=True)
    return scored_suggested, scored_other


@login_required(login_url=reverse_lazy('users:login'))
def dashboard(request, student_id=None, user_id=None):
    embed_mode = (request.GET.get("embed") or "").strip() == "1"
    route_user_id = user_id or student_id
    if not route_user_id:
        try:
            route_user_id = int(request.GET.get("user_id") or 0) or None
        except (TypeError, ValueError):
            route_user_id = None

    original_user = request.user
    target_user = original_user
    if route_user_id and int(route_user_id) != int(getattr(original_user, "id", 0) or 0):
        target_user = get_object_or_404(User, id=int(route_user_id))
        from app_post_matric.views import _staff_can_view_student_report
        from core import choices

        if not _staff_can_view_student_report(request, target_user.id):
            messages.error(request, "You do not have permission to view this report.")
            if getattr(original_user, "user_type", None) == choices.UserType.PARENT:
                return redirect("parents_dashboard")
            return redirect("users:userdashboard")

    user_swapped = False
    if int(target_user.id) != int(getattr(original_user, "id", 0) or 0):
        request.user = target_user
        user_swapped = True

    try:
        top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results(request)
        
        
        test1_result = Results.objects.get(user=request.user, test_paper='test1')
        sorted_result = test1_result.results

        # Find the highest value and its corresponding category
        personality_results = max(sorted_result, key=sorted_result.get, default=None)
        personality_highest_value = sorted_result.get(personality_results, 0)
        
        '''Interest: Find the highest value and its corresponding category'''
        test2_result = Results.objects.get(user=request.user, test_paper='test2')
        sorted_test2_result = test2_result.scores
        interest_results = max(sorted_test2_result, key=sorted_test2_result.get)
        interest_highest_value = sorted_test2_result[interest_results]

        '''Intelligence: Find the highest value and its corresponding category'''
        test3_result = Results.objects.get(user=request.user, test_paper='test3')
        sorted_test3_result = test3_result.scores
        intelligence_results = max(sorted_test3_result, key=sorted_test3_result.get)
        avg_intelligence = intelligence_results.split('_')[0]  # This will split the string into a list
        above_avg_score = avg_intelligence.upper()
        intelligence_highest_value = sorted_test3_result[intelligence_results]


        # User profile data
        user = request.user
        user_profile = None
        try:
            user_profile, created = UserProfile.objects.get_or_create(user=user)
        except UserProfile.DoesNotExist:
            pass

        # Handle 'intelligence' based on above_avg
        if above_avg_score in above_avg:
            intelligence_entry = {}
            if 'NUMERICAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'CWM']}
            elif 'VERBAL' in above_avg_score:
                intelligence_entry = {'streams': ['HUM', 'CWM']}
            elif 'LOGICAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'PCB']}
            elif 'MECHANICAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'CS']}
            elif 'SPATIAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'Fine Arts']}
            elif 'LANGUAGE' in above_avg_score:
                intelligence_entry = {'streams': ['HUM', 'HWL']}
            elif 'CRITICAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'HUM']}

            test3_result.results['intelligence'] = intelligence_entry

        # Initialize or ensure personality is a list
        if not isinstance(test3_result.results.get('personality'), list):
            test3_result.results['personality'] = []

        # Iterate through streamsubject and add stream/subject pairs to 'personality'
        for stream, subject in streamsubject:
            personality_entry = {'stream': stream, 'subject': subject}
            if personality_entry not in test3_result.results['personality']:
                test3_result.results['personality'].append(personality_entry)

        # Save the updated test3_result to the database
        test3_result.save()

        # Display percentages for Psychometric Test Report cards (match dashboard screen)
        personality_pct = round(float(personality_highest_value)) if personality_highest_value is not None else 0
        try:
            total_interest = sum(sorted_test2_result.values()) if sorted_test2_result else 0
            interest_pct = round(100 * interest_highest_value / total_interest) if total_interest else 0
        except (TypeError, ZeroDivisionError):
            interest_pct = 0
        try:
            intelligence_pct = round(float(intelligence_highest_value)) if intelligence_highest_value is not None else 0
            if intelligence_pct > 100:
                intelligence_pct = min(100, intelligence_pct)
        except (TypeError, ValueError):
            intelligence_pct = 0

        # Structured breakdowns for modern psychometric cards (DB-backed)
        personality_breakdown = []
        try:
            for label, score in sorted((sorted_result or {}).items(), key=lambda item: item[1], reverse=True):
                try:
                    pct = int(round(float(score)))
                except (TypeError, ValueError):
                    pct = 0
                personality_breakdown.append({
                    'label': str(label).strip(),
                    'score_pct': max(0, min(100, pct)),
                })
        except Exception:
            personality_breakdown = []

        interest_breakdown = []
        try:
            interest_scale_max = 36.0
            sorted_interest_items = sorted((sorted_test2_result or {}).items(), key=lambda item: item[1], reverse=True)
            for label, raw_score in sorted_interest_items:
                try:
                    numeric_score = float(raw_score)
                except (TypeError, ValueError):
                    numeric_score = 0.0
                # Bar width = score out of 36 (matches "27/36" label on dashboard)
                pct = int(round((numeric_score / interest_scale_max) * 100.0)) if interest_scale_max else 0
                interest_breakdown.append({
                    'label': str(label).strip().title(),
                    'score_pct': max(0, min(100, pct)),
                    'score_value': int(round(numeric_score)),
                    'score_max': int(interest_scale_max),
                })
        except Exception:
            interest_breakdown = []

        # Interest top/lowest metadata + "careers to avoid" suggestions for UI card
        interest_label_map = {
            'R': 'Realistic',
            'I': 'Investigative',
            'A': 'Artistic',
            'S': 'Social',
            'E': 'Enterprising',
            'C': 'Conventional',
            'REALISTIC': 'Realistic',
            'INVESTIGATIVE': 'Investigative',
            'ARTISTIC': 'Artistic',
            'SOCIAL': 'Social',
            'ENTERPRISING': 'Enterprising',
            'CONVENTIONAL': 'Conventional',
        }
        interest_avoid_map = {
            # Keep this aligned with class10_combined_report_content "Careers to Avoid" blocks
            'REALISTIC': [
                'Construction Industry',
                'Mechanical Trades',
                'Electrical Engineering',
                'Environmental and Outdoor Work',
                'Agricultural Sector',
            ],
            'INVESTIGATIVE': [
                'Scientific Research',
                'Academic Research',
                'Laboratory Technician',
                'Data Analysis and Data Science',
                'Engineering and Technical Analysis',
            ],
            'ARTISTIC': [
                'Graphic Design',
                'Creative Writing and Publishing',
                'Fine Arts',
                'Performing Arts (e.g., Acting, Music)',
                'Interior and Fashion Design',
            ],
            'SOCIAL': [
                'Counseling and Therapy',
                'Teaching and Education',
                'Social Work',
                'Healthcare (e.g., Nursing, Patient Care)',
                'Human Resources and Organizational Development',
            ],
            'ENTERPRISING': [
                'Entrepreneurship and Startups',
                'Sales and Marketing Management',
                'Business Leadership and Executive Roles',
                'Real Estate Sales',
                'Strategic Business Consulting',
            ],
            'CONVENTIONAL': [
                'Accounting and Financial Management',
                'Administrative Support',
                'Data Entry and Clerical Work',
                'Banking and Financial Services',
                'Compliance and Regulatory Roles',
            ],
        }
        from app.interest_report_utils import (
            codes_from_code_string,
            career_suggestion_groups,
            interest_report_context_fields,
            riasec_code_display_label,
            RIASEC_CODE_TO_NAME,
            RIASEC_CAREERS_TO_CHOOSE,
        )
        interest_ctx = interest_report_context_fields(
            scores=sorted_test2_result,
            max_length=max_length,
            min_length=min_length,
        )
        dominant_interest_name = interest_ctx.get('dominant_interest_labels') or ''
        dominant_interest_display = interest_ctx.get('dominant_interest_display') or ''
        dominant_interest_codes = interest_ctx.get('dominant_interest_codes') or []
        lowest_interest_name = ''
        interest_avoid_careers = []
        try:
            lowest_key = str(min_length or '').strip().upper()
            lowest_codes = codes_from_code_string(min_length)
            if lowest_codes:
                lowest_interest_name = ', '.join(RIASEC_CODE_TO_NAME[c] for c in lowest_codes)
            else:
                lowest_interest_name = interest_label_map.get(
                    lowest_key, str(min_length or '').strip().title()
                )
            for code in lowest_codes or [lowest_key[:1] if lowest_key else '']:
                if code in interest_avoid_map:
                    interest_avoid_careers = interest_avoid_map[code]
                    break
            if not interest_avoid_careers and lowest_interest_name:
                interest_avoid_careers = interest_avoid_map.get(lowest_interest_name.upper(), [])
        except Exception:
            dominant_interest_name = interest_ctx.get('dominant_interest_labels') or str(max_length or '').strip()
            dominant_interest_display = riasec_code_display_label(max_length)
            lowest_interest_name = str(min_length or '').strip()
            interest_avoid_careers = []

        intelligence_breakdown = []
        top_intelligence_label = ''
        top_intelligence_band = ''
        try:
            above_set = {str(item).upper().strip() for item in (above_avg or [])}
            avg_set = {str(item).upper().strip() for item in (avg or [])}
            below_set = {str(item).upper().strip() for item in (below or [])}
            sorted_intelligence_items = sorted((sorted_test3_result or {}).items(), key=lambda item: item[1], reverse=True)
            for raw_label, raw_score in sorted_intelligence_items:
                code = str(raw_label).split('_')[0].upper().strip()
                label = code.title()
                try:
                    numeric_score = float(raw_score)
                except (TypeError, ValueError):
                    numeric_score = 0.0
                pct = int(round(max(0.0, min(100.0, (numeric_score / 15.0) * 100.0))))
                if code in above_set:
                    band = 'Above Avg'
                elif code in avg_set:
                    band = 'Avg'
                elif code in below_set:
                    band = 'Below'
                else:
                    band = 'Avg'
                intelligence_breakdown.append({
                    'label': label,
                    'score_pct': pct,
                    'band': band,
                })
            if intelligence_breakdown:
                top_intelligence_label = intelligence_breakdown[0].get('label', '')
                top_intelligence_band = intelligence_breakdown[0].get('band', '')
        except Exception:
            intelligence_breakdown = []
            top_intelligence_label = ''
            top_intelligence_band = ''

        # Skill readiness index from TopTeen DB (test3 intelligence scores)
        # test3 section scores are usually on a 0-15 scale, convert to percentage for UI bars.
        skill_readiness_index = []
        try:
            scale_max = 15.0
            label_map = {
                'NUMERICAL': 'Numerical',
                'VERBAL': 'Verbal',
                'LOGICAL': 'Logical',
                'MECHANICAL': 'Mechanical',
                'SPATIAL': 'Spatial',
                'LANGUAGE': 'Language',
                'CRITICAL': 'Critical',
                'EMOTIONAL': 'Emotional',
            }
            for raw_label, raw_score in (sorted_test3_result or {}).items():
                code = str(raw_label).split('_')[0].upper().strip()
                label = label_map.get(code, code.title())
                try:
                    numeric_score = float(raw_score)
                except (TypeError, ValueError):
                    numeric_score = 0.0
                score_pct = int(round(max(0.0, min(100.0, (numeric_score / scale_max) * 100.0))))
                skill_readiness_index.append({
                    'code': code,
                    'label': label,
                    'raw_score': numeric_score,
                    'score_pct': score_pct,
                })
            skill_readiness_index.sort(key=lambda item: item['score_pct'], reverse=True)
        except Exception:
            skill_readiness_index = []

        # Vocational careers for below-average reasoning areas (DB-backed mappings).
        from app.report_visibility import student_all_growth_areas
        from app.vocational_recommendations import vocational_guidance_context_for_below_areas

        student_below_average = student_all_growth_areas(below, avg, above_avg)
        vocational_ctx = vocational_guidance_context_for_below_areas(below, user=request.user)
        vocational_guidance_cards = vocational_ctx['vocational_guidance_cards']
        vocational_guidance_groups = vocational_ctx['vocational_guidance_groups']
        below_area_vocational_urls_map = vocational_ctx['below_area_vocational_urls']
        vocational_guidance_section_url = vocational_ctx['vocational_guidance_section_url']
        aptitude_improvement_plan = vocational_ctx.get('aptitude_improvement_plan', [])

        # Suggested careers block (grouped by RIASEC / aptitude heading for dashboard)
        interest_suggested_careers = []
        interest_suggested_career_groups = []
        aptitude_suggested_careers = []
        aptitude_suggested_career_groups = []
        suitable_subject_combinations = []
        stream_sorter_guidance = None
        try:
            dominant_codes = (
                dominant_interest_codes
                or codes_from_code_string(max_length)
                or [str(max_length or '').strip().upper()[:1]]
            )
            interest_suggested_career_groups = career_suggestion_groups(
                dominant_codes,
                RIASEC_CAREERS_TO_CHOOSE,
                fallback_careers=sorted(courseName) if courseName else None,
                fallback_title='From your interest profile',
            )
            interest_suggested_careers = [
                c for g in interest_suggested_career_groups for c in g['careers']
            ]
        except Exception:
            interest_suggested_careers = []
            interest_suggested_career_groups = []

        stream_recommendation = recommend_streams_from_tiers(above_avg, avg, below_avg=below)
        suitable_subject_combinations = suitable_combinations_from_recommendation(stream_recommendation)
        stream_sorter_guidance = None
        try:
            from app.report_visibility import should_show_extended_career_pathways
            from app.stream_sorter_guidance import (
                build_report_stream_guidance,
                career_groups_for_dashboard,
            )

            if should_show_extended_career_pathways(below, avg, above_avg):
                aptitude_streams = streamsubject_from_recommendation(stream_recommendation)
                if aptitude_streams:
                    stream_sorter_guidance = build_report_stream_guidance(
                        aptitude_streams,
                        top_category=top_category,
                    )
        except Exception:
            stream_sorter_guidance = None

        if stream_sorter_guidance:
            aptitude_suggested_career_groups = career_groups_for_dashboard(stream_sorter_guidance)
        else:
            aptitude_suggested_career_groups = premium_career_groups_from_recommendation(
                stream_recommendation
            )
        aptitude_suggested_careers = [
            career
            for group in aptitude_suggested_career_groups
            for career in group.get('careers', [])
        ]

        personality_suggested_careers = []
        personality_suggested_career_groups = []
        personality_display_name = ''
        stream_career_sections = get_stream_career_sections(top_category)
        try:
            if top_category:
                personality_display_name = (
                    getattr(top_category, 'fullname', None)
                    or getattr(top_category, 'category_name', None)
                    or getattr(top_category, 'category', None)
                    or ''
                )
            from app.riasec_report_utils import get_personality_career_groups as _personality_career_groups
            personality_suggested_career_groups = _personality_career_groups(top_category)
            if not personality_suggested_career_groups and courseName:
                personality_suggested_career_groups.append({
                    'code': str(getattr(top_category, 'category', '') or 'P').upper()[:1],
                    'name': personality_display_name or 'Personality match',
                    'careers': sorted(courseName),
                    'combined': False,
                })
            personality_suggested_careers = [
                c for g in personality_suggested_career_groups for c in g.get('careers', [])
            ]
        except Exception:
            personality_suggested_careers = []
            personality_suggested_career_groups = []
            personality_display_name = ''
            stream_career_sections = get_stream_career_sections(top_category)

        # Interest / personality / aptitude careers use report catalog labels (no fuzzy remap).
        # Statistics for template20 dashboard (trophies, points, streak, level)
        trophy_details = []
        points_details = []
        streak_details = {}
        level_details = {}
        try:
            from core.dashboard_stats import get_student_dashboard_stats
            stats = get_student_dashboard_stats(request.user)
            trophies_unlocked = stats['trophies_unlocked']
            total_points = stats['total_points']
            streak_days = stats['streak_days']
            current_level = stats['current_level']
            next_level_min_points = stats.get('next_level_min_points')
            level_progress_percent = stats.get('level_progress_percent', 0)
            trophy_details = stats.get('trophy_details', [])
            points_details = stats.get('points_details', [])
            streak_details = stats.get('streak_details', {})
            level_details = stats.get('level_details', {})
        except Exception:
            trophies_unlocked = 0
            total_points = 0
            streak_days = 0
            current_level = 'Explorer'
            next_level_min_points = None
            level_progress_percent = 0

        all_tests_complete = False
        stream_questionnaire_completed = False
        stream_questionnaire_answers = {}
        stream_questionnaire_completed_at = ''
        try:
            test_completion = TestCompletion.objects.get(user=request.user)
            all_subtests_complete = (
                test_completion.numerical_complete and
                test_completion.verbal_complete and
                test_completion.logical_complete and
                test_completion.emotional_complete and
                test_completion.machanical_complete and
                test_completion.language_complete and
                test_completion.spatial_complete
            )
            all_tests_complete = (
                test_completion.test1_complete and
                test_completion.test2_complete and
                test_completion.test3_complete and
                all_subtests_complete
            )
        except Exception:
            pass

        try:
            from app.stream_decision import get_questionnaire_data
            questionnaire_data = get_questionnaire_data(test3_result.results)
            stream_questionnaire_completed = bool(questionnaire_data.get('completed'))
            stream_questionnaire_answers = questionnaire_data.get('answers') or {}
            stream_questionnaire_completed_at = questionnaire_data.get('completed_at') or ''
        except Exception:
            pass

        show_stream_questionnaire = (
            all_tests_complete and
            bool(suitable_subject_combinations) and
            not stream_questionnaire_completed
        )

        intelligence_scores_by_code = {
            str(item.get('code', '')).upper(): int(item.get('score_pct', 0))
            for item in (skill_readiness_index or [])
        }
        stream_questionnaire_suggested = []
        stream_questionnaire_other = []
        if show_stream_questionnaire:
            primary_aptitude_code = str(above_avg_score or top_intelligence_label or '').upper().strip()
            stream_questionnaire_suggested, stream_questionnaire_other = _build_stream_questionnaire_options(
                intelligence_scores_by_code,
                primary_aptitude_code,
                suitable_subject_combinations,
            )

        from app.stream_decision import STREAM_DECISION_STREAM_OPTIONS

        context = {
            'user_profile': user_profile,
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'max_length': max_length,
            'min_length': min_length,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
            'above_avg_score': above_avg_score,
            'highest_value': personality_highest_value,
            'interest_highest_value': interest_highest_value,
            'intelligence_highest_value': intelligence_highest_value,
            'personality_pct': personality_pct,
            'interest_pct': interest_pct,
            'intelligence_pct': intelligence_pct,
            'personality_breakdown': personality_breakdown[:6],
            'interest_breakdown': interest_breakdown[:6],
            'dominant_interest_name': dominant_interest_name,
            'dominant_interest_display': dominant_interest_display,
            'dominant_interest_codes': dominant_interest_codes,
            'lowest_interest_name': lowest_interest_name,
            'interest_avoid_careers': interest_avoid_careers,
            'intelligence_breakdown': intelligence_breakdown[:7],
            'top_intelligence_label': top_intelligence_label,
            'top_intelligence_band': top_intelligence_band,
            'trophies_unlocked': trophies_unlocked,
            'total_points': total_points,
            'streak_days': streak_days,
            'current_level': current_level,
            'next_level_min_points': next_level_min_points,
            'level_progress_percent': level_progress_percent,
            'trophy_details': trophy_details,
            'points_details': points_details,
            'streak_details': streak_details,
            'level_details': level_details,
            'student_below_average': student_below_average,
            'vocational_guidance_cards': vocational_guidance_cards,
            'vocational_guidance_groups': vocational_guidance_groups,
            'vocational_guidance_section_url': vocational_guidance_section_url,
            'aptitude_improvement_plan': aptitude_improvement_plan,
            'below_area_vocational_urls': below_area_vocational_urls_map,
            'interest_suggested_careers': interest_suggested_careers,
            'interest_suggested_career_groups': interest_suggested_career_groups,
            'aptitude_suggested_careers': aptitude_suggested_careers,
            'aptitude_suggested_career_groups': aptitude_suggested_career_groups,
            'personality_suggested_careers': personality_suggested_careers,
            'personality_suggested_career_groups': personality_suggested_career_groups,
            'personality_display_name': personality_display_name,
            'stream_career_sections': stream_career_sections,
            'career_suggestions_preview_count': 2,
            'suitable_subject_combinations': suitable_subject_combinations,
            'stream_recommendation': stream_recommendation,
            'stream_sorter_guidance': stream_sorter_guidance,
            'skill_readiness_index': skill_readiness_index,
            'report_user_id': target_user.id,
            'embed_mode': embed_mode,
            'all_tests_complete': all_tests_complete,
            'show_stream_questionnaire': show_stream_questionnaire,
            'stream_questionnaire_completed': stream_questionnaire_completed,
            'stream_questionnaire_answers': stream_questionnaire_answers,
            'stream_questionnaire_completed_at': stream_questionnaire_completed_at,
            'stream_questionnaire_suggested': stream_questionnaire_suggested,
            'stream_questionnaire_other': stream_questionnaire_other,
            'stream_decision_options': STREAM_DECISION_STREAM_OPTIONS,
        }

        resp = render(request, 'template20/psychometric/dashboard.html', context)
        if embed_mode:
            return _add_no_cache_headers(resp)
        return resp

    except Exception as e:
        # Log the error for debugging purposes (optional)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in dashboard: {str(e)}")
        if embed_mode:
            resp = render(
                request,
                'template20/psychometric/dashboard.html',
                {
                    'embed_mode': True,
                    'report_user_id': target_user.id,
                    'error_message': 'Assessment results are not available yet. Please complete all tests first.',
                },
            )
            return _add_no_cache_headers(resp)
        messages.error(request, "Please start your test. Then you can access the dashboard.")
        # Redirect to home without displaying any error on the frontend
        return redirect('/psychometric/home')
    finally:
        if user_swapped:
            request.user = original_user

def final_assessment_pdf(request):

    top_category, streamsubject,courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results(request)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None

    user_name = request.user
    user_ID = request.user.id
    # Prepare context dictionary
    context = {
        'user_name':user_name,
        'user_ID':user_ID,
        'user_profile': user_profile,
        'top_category':top_category,
        'streamsubject': streamsubject,
        'courseName':courseName,
        'max_length':max_length,
        'min_length':min_length,
        'below':below,
        'avg':avg,
        'above_avg':above_avg,
        'top_categories':top_categories,
    }
    return render(request, 'Asessment_report.html',context)


def get_stream_career_sections(top_category):
    from app.riasec_report_utils import get_stream_career_sections as _get_sections
    return _get_sections(top_category)


def db_results_inst_user(user):

    if not has_attempted_test(user):
        raise UserHasNotAttemptedTestException("User hasn't attempted the test yet.")
    top_3_categories_str = ""
    top_categories = []
    questions= Question.objects.all()
    # Get the data from the database fro the Personality test
    try:
        if questions is not None:
            test1_result = Results.objects.get(user = user, test_paper='test1')
            # Check if results dict exists and has data
            if test1_result.results and isinstance(test1_result.results, dict):
                sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
                for i, (category, score) in enumerate(sorted_results, start=1):
                    if i > 3:
                        break
                    top_categories.append({
                        'rank': i,
                        'category': category,
                        'score': f"{score:.2f}%"
                    })
                    # Get first letter of category name (e.g., "Realistic" -> "R")
                    top_3_categories_str += category[0] if category else ''

        # Extract category code (first 3 letters)
        top_category_code = top_3_categories_str[:3] if top_3_categories_str else ''
    except Results.DoesNotExist:
        top_categories = []
        top_category_code = ''
    except Exception as e:
        logger.exception("Error processing test1 results for user %s", user.id)
        top_categories = []
        top_category_code = ''


    # Get the data from the database for the Career interest test
    try:
        from app.interest_report_utils import resolve_interest_extrema
        test2_result = Results.objects.get(user=user, test_paper='test2')
        lengths = test2_result.scores
        max_length, min_length, _, _ = resolve_interest_extrema(lengths)
    except Results.DoesNotExist:
        max_length = ''
        min_length = ''

    # Get the data from the database for the Intelligence test
    try:
        test3_result = Results.objects.get(user=user, test_paper='test3')
        personality_res = test3_result.scores
        scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
        below = []
        avg = []
        above_avg = []
        for key in scores:
            if scores[key] <= 5:
                below.append(key)
            elif scores[key] <= 10:
                avg.append(key)
            else:
                above_avg.append(key)
    except Results.DoesNotExist:
        below = ''
        avg = ''
        above_avg = ''

    # Get the top category using the code
    top_category = Category.objects.filter(category=top_category_code).first()
    streamsubject = set()
    courseName = set()
    if top_category:
        category_id = top_category.id
        # Get streams related to this category using the category ID
        streams = Stream.objects.filter(category_id=category_id)
        # Print the details of each stream
        for stream in streams:
            streamsubject.add((stream.stream_name, stream.subjects))

        # Get courses related to this category using the category ID
        courses = Course.objects.filter(category_id=category_id)
        for course in courses:
            # Print the details of each courses
            courseName.add(course.course_name)

    else:
        logger.debug("No category found with the code: %s", top_category_code)

    return top_category, streamsubject,courseName, max_length, min_length, below, avg, above_avg, top_categories


def Assessment_pdf_inst_user(request, user_id=None):

    """
    View to generate and display the final assessment report for the logged-in user.
    """
    
    embed_mode = (request.GET.get("embed") or "").strip() == "1"
    # Fetch the user based on the provided user_id parameter or fallback to the current user
    user = get_object_or_404(User, id=user_id) if user_id else request.user

    # top_category, streamsubject,courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(user)
    
    # Call your function and check for issues
    try:
        top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(user)
    except UserHasNotAttemptedTestException as e:
        # User hasn't attempted test - return error page or redirect
        from django.http import HttpResponse
        return HttpResponse(f"User {user.name} hasn't attempted the test yet. Please complete the test first.", status=400)
    except Exception as e:
        # Log the error but don't crash - return with empty data
        import traceback
        logger.exception(f"Error in db_results_inst_user for user {user.id}: {str(e)}")
        # Set default values to prevent template errors
        top_category = None
        streamsubject = set()
        courseName = set()
        max_length = ''
        min_length = ''
        below = []
        avg = []
        above_avg = []
        top_categories = []
    
    
    user_name = getattr(user, 'name', None) or getattr(user, 'email', None) or str(user)
    user_ID = user.id if user_id is None else user_id
    # Ensure graph images exist for the report (personality, interest, intelligence)
    from app.graph_media_utils import graph_image_basenames, graph_images_directory

    graph_dir = graph_images_directory()
    graph_files = graph_image_basenames(user_name, user_ID)
    need_graphs = any(not os.path.exists(os.path.join(graph_dir, f)) for f in graph_files)
    if need_graphs:
        original_user = request.user
        try:
            request.user = user
            gernate_graph(request)
        except Exception as e:
            import traceback
            logger.warning("Assessment_pdf_inst_user: could not generate graphs for user %s: %s", user.id, e)
        finally:
            request.user = original_user
    # Prepare context dictionary
    context = {
        'user_name': user_name,
        'user_ID': user_ID,
        'top_category': top_category,
        'streamsubject': streamsubject,
        'courseName': courseName,
        'max_length': max_length,
        'min_length': min_length,
        'below': below,
        'avg': avg,
        'above_avg': above_avg,
        'top_categories': top_categories,
        'embed_mode': embed_mode,
    }
    return render(request, 'Asessment_report.html', context)


def _add_no_cache_headers(response):
    """Set headers so the report is not cached (fixes view result in normal browser mode after Google login)."""
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['Vary'] = 'Cookie'  # Ensure cached responses (if any) are not shared across users
    return response


def _pdf_preparing_response():
    """Auto-refresh page while Celery finishes WeasyPrint."""
    return HttpResponse(
        """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="2"/>
<title>Preparing PDF…</title>
<style>
 body{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;
  min-height:100vh;margin:0;background:#f7f7fb;color:#222}
 .box{text-align:center;padding:2rem;max-width:28rem}
</style></head>
<body><div class="box">
<h1 style="font-size:1.25rem">Preparing your PDF…</h1>
<p>This usually takes a few seconds. This page will refresh automatically.</p>
</div></body></html>""",
        content_type="text/html; charset=utf-8",
    )


def _try_serve_or_enqueue_web_report_pdf(request, target_user, report_kind, *, _sync_generate=False):
    """
    Serve a stored PDF or enqueue Celery generation.

    Returns an HttpResponse when handled; None means caller should generate sync.
    """
    if _sync_generate or (request.GET.get("debug") or "").strip() == "true":
        return None
    filename = class10_web_report_pdf_filename(target_user, report_kind)
    try:
        if user_pdf_exists(target_user.id, filename):
            served = serve_user_pdf_response(target_user.id, filename, download_name=filename)
            if served is not None:
                return served
    except Exception:
        logger.exception(
            "web report PDF exists-check failed user=%s kind=%s",
            getattr(target_user, "id", None),
            report_kind,
        )
    try:
        from app.task import enqueue_class10_web_report_pdf

        if enqueue_class10_web_report_pdf(
            target_user.id,
            report_kind,
            request.build_absolute_uri("/"),
        ):
            return _pdf_preparing_response()
    except Exception:
        logger.exception(
            "web report PDF enqueue failed user=%s kind=%s; falling back to sync",
            getattr(target_user, "id", None),
            report_kind,
        )
    return None


@login_required(login_url=reverse_lazy('users:login'))
def class10_combined_report(request, user_id=None):
    """
    Class 10 combined assessment report.

    Uses Redis-cached context (and a short HTML cache) so repeat views stay fast.
    """
    try:
        from django.core.cache import cache
        from app.class10_combined_report_context import build_class10_combined_report_context
        from app.report_cache import (
            CLASS10_HTML_CACHE_TTL,
            class10_combined_report_html_cache_key,
            get_or_build_class10_combined_report_context,
        )

        embed_mode = (request.GET.get("embed") or "").strip() == "1"
        route_user_id = int(user_id) if user_id else None
        if route_user_id:
            target_user = get_object_or_404(User, id=route_user_id)
        else:
            target_user = request.user
            route_user_id = int(target_user.id)

        # Fast path: cached full HTML (skip for debug / incomplete reports need fresh errors)
        html_key = class10_combined_report_html_cache_key(target_user.id, embed_mode)
        if not request.GET.get('nocache'):
            try:
                cached_html = cache.get(html_key)
            except Exception:
                cached_html = None
            if cached_html:
                resp = HttpResponse(cached_html, content_type='text/html; charset=utf-8')
                return _add_no_cache_headers(resp)

        context = get_or_build_class10_combined_report_context(
            request,
            target_user,
            build_class10_combined_report_context,
            route_user_id=route_user_id,
            embed_mode=embed_mode,
        )

        template_name = (
            'template20/app/class10_combined_report.html'
            if context.get('no_results') and (context.get('error') or '').startswith('No completed')
            else 'template20/app/class10_combined_report_new.html'
        )
        resp = render(request, template_name, context)
        resp = _add_no_cache_headers(resp)

        if (
            resp.status_code == 200
            and not context.get('no_results')
            and not context.get('error')
        ):
            try:
                cache.set(html_key, resp.content, CLASS10_HTML_CACHE_TTL)
            except Exception:
                pass
        return resp

    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.exception("Error in class10_combined_report: %s", e)
        resp = render(request, 'template20/app/class10_combined_report_new.html', {
            'error': f'An error occurred: {str(e)}',
            'traceback': trace,
            'no_results': True,
            'embed_mode': (request.GET.get("embed") or "").strip() == "1",
        })
        return _add_no_cache_headers(resp)


@login_required(login_url=reverse_lazy('users:login'))
def class10_report_download_pdf(request, user_id=None, _sync_generate=False):
    """
    Generate and download PDF for Class 10 combined report.

    Serves a stored copy when available; otherwise enqueues Celery (WeasyPrint off-request).
    Pass ``_sync_generate=True`` from the worker.
    """
    target_user = None
    try:
        import weasyprint
        import ssl
        from datetime import datetime
        
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists
        ensure_user_pdf_folder(target_user.id)

        early = _try_serve_or_enqueue_web_report_pdf(
            request, target_user, 'combined', _sync_generate=_sync_generate
        )
        if early is not None:
            return early
        
        # Check if user has attempted tests
        if not has_attempted_test(target_user):
            return HttpResponse('No completed test found. Please complete all tests first.', status=404)
        
        # Check if all tests are completed
        test1_completed = Results.objects.filter(user=target_user, test_paper='test1').exists()
        test2_completed = Results.objects.filter(user=target_user, test_paper='test2').exists()
        test3_completed = Results.objects.filter(user=target_user, test_paper='test3').exists()
        
        if not (test1_completed and test2_completed and test3_completed):
            return HttpResponse('Please complete all three tests to download the report.', status=400)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get test results
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            logger.exception(f"Error getting results: {e}")
            return HttpResponse('Error generating report data.', status=500)
        
        # Get individual test results
        test1_result = Results.objects.filter(user=target_user, test_paper='test1').first()
        test2_result = Results.objects.filter(user=target_user, test_paper='test2').first()
        test3_result = Results.objects.filter(user=target_user, test_paper='test3').first()
        
        # Process personality data
        personality_data = {}
        if test1_result and test1_result.results:
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            personality_data = {
                'results': dict(sorted_results),
                'top_categories': top_categories,
                'top_category': top_category
            }
        
        # Process interest data
        interest_data = {}
        if test2_result and test2_result.scores:
            interest_data = {
                'scores': test2_result.scores,
                'max_category': max_length,
                'min_category': min_length
            }
        
        # Process intelligence data
        intelligence_data = {}
        if test3_result and test3_result.scores:
            scores = {label.split("_")[0].upper(): value for label, value in test3_result.scores.items()}
            intelligence_data = {
                'scores': scores,
                'below_avg': below,
                'average': avg,
                'above_avg': above_avg
            }
        
        # Refresh graph images before PDF so chart layout/margins stay current
        original_user = getattr(request, 'user', None)
        try:
            request.user = target_user
            gernate_graph(request)
        except Exception as e:
            logger.warning("class10_report_download_pdf: could not generate graphs for user %s: %s", target_user.id, e)
        finally:
            if original_user is not None:
                request.user = original_user
        
        # Student info for first page (same as test1 report)
        student_name = getattr(target_user, 'name', None) or target_user.email
        created_date = None
        if test1_result and hasattr(test1_result, 'created'):
            created_date = test1_result.created
        if created_date is None:
            created_date = getattr(target_user, 'date_joined', None)
        now = datetime.now()

        graph_user_name = getattr(target_user, 'name', None) or target_user.email

        # Build context for PDF (same as HTML report so content include matches)
        # show_student_info_on_cover: only True for PDF so student info appears on first page of download only
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'user_id': target_user.id,
            'user_name': graph_user_name,
            'user_ID': target_user.id,
            'show_student_info_on_cover': True,
            'student_name': student_name,
            'created_date': created_date,
            'now': now,
            'personality_data': personality_data,
            'interest_data': interest_data,
            'intelligence_data': intelligence_data,
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'stream_career_sections': get_stream_career_sections(top_category),
            'top_categories': top_categories,
            'max_length': max_length,
            'min_length': min_length,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
        }
        from app.report_visibility import should_show_extended_career_pathways
        from app.vocational_recommendations import vocational_guidance_context_for_below_areas

        context.update(vocational_guidance_context_for_below_areas(below, user=target_user))
        context['student_below_average'] = not should_show_extended_career_pathways(below, avg, above_avg)

        stream_recommendation = recommend_streams_from_tiers(above_avg, avg, below_avg=below)
        context['stream_recommendation'] = stream_recommendation

        if should_show_extended_career_pathways(below, avg, above_avg):
            from app.stream_sorter_guidance import build_report_stream_guidance
            aptitude_streams = streamsubject_from_recommendation(stream_recommendation)
            context['stream_sorter_guidance'] = (
                build_report_stream_guidance(aptitude_streams, top_category=top_category)
                if aptitude_streams
                else None
            )
        else:
            context['stream_sorter_guidance'] = None

        from app.aptitude_report_utils import aptitude_report_context_fields
        context.update(
            aptitude_report_context_fields(
                test3_result.scores if test3_result and test3_result.scores else None
            )
        )

        from app.interest_report_utils import interest_report_context_fields
        context.update(
            interest_report_context_fields(
                scores=test2_result.scores if test2_result and test2_result.scores else None,
                max_length=max_length,
                min_length=min_length,
            )
        )

        # Render HTML with Jinja2 so PDF template (uses {% set %}, .items()) is correct
        pdf_template_name = 'template20/app/class10_combined_report_pdf.html'
        try:
            jinja2_engine = engines['jinja2']
            template = jinja2_engine.get_template(pdf_template_name)
        except (KeyError, Exception):
            template = get_template(pdf_template_name)
        html = template.render(context)
        html = _resolve_static_urls_to_local_paths(html, request.build_absolute_uri('/'))
        
        # Debug: return raw HTML to verify template/CSS (?debug=true)
        if request.GET.get('debug') == 'true':
            from django.http import HttpResponse as HttpResp
            r = HttpResp(html, content_type='text/html; charset=utf-8')
            r['Content-Disposition'] = 'inline; filename=combined-report-debug.html'
            r['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            return r
        
        # Generate PDF (WeasyPrint) - wrap for clear production logging if it fails
        try:
            original_ssl_context = ssl._create_default_https_context
            ssl._create_default_https_context = ssl._create_unverified_context
            try:
                pdf_file = weasyprint.HTML(
                    string=html,
                    base_url=request.build_absolute_uri('/')
                ).write_pdf()
            finally:
                ssl._create_default_https_context = original_ssl_context
        except Exception as pdf_err:
            logger.exception(
                "class10_report_download_pdf: PDF generation failed for user_id=%s (WeasyPrint/template): %s",
                target_user.id, pdf_err
            )
            return HttpResponse(
                'PDF generation failed. Check server logs (WeasyPrint).',
                status=500
            )
        
        # Create response (prevent any caching of PDF)
        response = HttpResponse(content_type='application/pdf')
        filename = class10_combined_report_pdf_filename(target_user)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response.write(pdf_file)
        
        # Persist a copy to media storage (S3 when enabled) - best-effort, never blocks the download.
        save_user_pdf(target_user.id, filename, pdf_file)

        return response
        
    except Exception as e:
        uid = getattr(target_user, 'id', None) if target_user else getattr(request.user, 'id', None)
        logger.exception("class10_report_download_pdf failed for user_id=%s: %s", uid, e)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # Process uploaded file
            handle_uploaded_file(request.FILES['file'])
            return HttpResponseRedirect('/psychometric/home')
    else:
        form = UploadFileForm()
    return render(request, 'topteenfrontend/user/app/upload.html', {'form': form})

@login_required(login_url=reverse_lazy('users:login'))
def test_buttons(request):
    # Import redirect and reverse at the top
    from django.shortcuts import redirect
    from django.urls import reverse
    from psychometric_tests.models import PsychometricTestPayment
    from core import choices
    
    # Initialize variables with default values
    user_profile = None
    created_date = None
    gender = None
    schoolname = None
    grade = None
    student_class = None  # Will be "10" or "12"

    if request.user.is_authenticated:
        user = request.user

        try:
            # Retrieve the UserProfile for the logged-in user (create if not exists)
            user_profile, created = UserProfile.objects.get_or_create(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        try:
            # Retrieve the UserProfile for the logged-in user
            user_profile = user.user_profile
            # Access attributes from the User object
            created_date = user.created
            gender = user_profile.gender if user_profile else None
            schoolname = user_profile.schoolname if user_profile else None
            student_name = user.email  # Assuming email is used as student name
            
            # Determine student class: First check StudentManagement (for institute students)
            # Then fallback to UserProfile.grade (for direct signups)
            from institute.models import StudentManagement
            student_management = StudentManagement.objects.filter(student=user).first()
            
            if student_management and student_management.class_and_section:
                # Get class from StudentManagement (institute students)
                class_name = student_management.class_and_section.class_and_section
                if class_name:
                    # Extract first 2 characters to get class number
                    import re
                    numbers = re.findall(r'\d+', class_name)
                    if numbers:
                        class_number = int(numbers[0])
                        if class_number >= 11:
                            student_class = "12"  # Class 11-12
                        else:
                            student_class = "10"  # Class 10 and below
                    grade = class_name  # Use full class name for display
            elif user_profile and user_profile.grade:
                # Fallback to UserProfile.grade (direct signups)
                student_class = str(user_profile.grade)
                grade = f"Class {user_profile.grade}"
            else:
                # Default to class 10 if nothing is set
                student_class = "10"
                grade = "Class 10"

        except (UserProfile.DoesNotExist, AttributeError):
            logger.debug("UserProfile does not exist.")
            user_profile = None
            student_class = "10"  # Default
            grade = "Class 10"

    else:
        logger.debug("User is not authenticated.")
        # Redirect to login if not authenticated
        return redirect(reverse('users:login'))
    
    # Check if user is an institute-registered student (exempt from payment check)
    is_institute_student = StudentManagement.objects.filter(student=request.user).exists()
    from core.assessment_access import (
        build_class10_psychometric_page_context,
        can_access_psychometric_dashboard,
        institute_student_exempt_from_payment,
    )

    # UPDATED: After completing all psychometric tests, institute students must add/verify mobile to continue.
    # Allow login, but block this dashboard/action until mobile is present.
    try:
        if is_institute_student and (not request.user.mobile or not str(request.user.mobile).strip()):
            tc = TestCompletion.objects.filter(user=request.user).first()
            is_completed = bool(
                tc and
                tc.test1_complete and
                tc.test2_complete and
                tc.test3_complete and
                tc.numerical_complete and
                tc.verbal_complete and
                tc.logical_complete and
                tc.emotional_complete and
                tc.machanical_complete and
                tc.language_complete and
                tc.spatial_complete
            )
            if is_completed:
                request.session['force_mobile_popup'] = True
                request.session['post_mobile_redirect'] = reverse('app:test_buttons')
                return redirect(reverse('users:userdashboard'))
    except Exception:
        pass
    
    # Only check payment for non-exempt students
    if not institute_student_exempt_from_payment(request.user):
        if not can_access_psychometric_dashboard(request.user):
            if student_class == "12":
                return redirect(reverse('psychometrictests:PsychometricTest12'))
            return redirect(reverse('psychometrictests:psychometrictest'))

    try:
        test_completion = TestCompletion.objects.get(user=request.user)
    except TestCompletion.DoesNotExist:
        # Create a new TestCompletion object if it doesn't exist
        test_completion = TestCompletion.objects.create(user=request.user)
        pass

    # Check if tests have been started but not completed
    test_started_status = {
        'test1_started': Results.objects.filter(user=request.user, test_paper='test1').exists(),
        'test2_started': Results.objects.filter(user=request.user, test_paper='test2').exists(),
        'test3_started': Results.objects.filter(user=request.user, test_paper='test3').exists(),
    }

    # Check if all test3 subtests are complete (same logic as app_submit)
    all_test3_subtests_complete = False
    if test_completion:
        # Check if all subtests are complete using TestCompletion fields
        all_test3_subtests_complete = (
            test_completion.numerical_complete and
            test_completion.verbal_complete and
            test_completion.logical_complete and
            test_completion.emotional_complete and
            test_completion.machanical_complete and
            test_completion.language_complete and
            test_completion.spatial_complete
        )
        
        # Verify and correct test3_complete status if needed
        if test_completion.test3_complete and not all_test3_subtests_complete:
            test_completion.test3_complete = False
            test_completion.save()
        elif not test_completion.test3_complete and all_test3_subtests_complete:
            test_completion.test3_complete = True
            test_completion.save()
    
    context = {
        'user_profile': user_profile,
        'test_completion': test_completion,
        'test_started_status': test_started_status,
        "School_Name:": schoolname,
        'created_date': created_date,
        "Gender:": gender,
        "Grade:": grade,
        'student_class': student_class,  # "10" or "12" for filtering tests
        'all_test3_subtests_complete': all_test3_subtests_complete,
        **build_class10_psychometric_page_context(request.user),
    }
    return render(request, 'template20/psychometric/home.html', context)

def handle_uploaded_file(file):
    decoded_file = file.read().decode('utf-8').splitlines()
    reader = csv.reader(decoded_file)
    next(reader) # Skip the header row

    for row in reader:
        question_text = row[0].strip()
        category = row[1].strip()
        test_paper = row[2].strip() # Assuming the third column is test_paper

        question_obj, created = Question.objects.get_or_create(
            question_text=question_text,
            category=category,
            test_paper=test_paper,
   
        )

@login_required(login_url=reverse_lazy('users:login'))
def test1_intro(request):
    # Ensure user PDF folder exists before starting test
    ensure_user_pdf_folder(request.user.id)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'template20/psychometric/test1_intro.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test2_intro(request):
    # Ensure user PDF folder exists before starting test
    ensure_user_pdf_folder(request.user.id)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'template20/psychometric/test2_intro.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_intro(request):
    from core.assessment_access import redirect_if_no_class10_test_access
    denied = redirect_if_no_class10_test_access(request, 'test3')
    if denied:
        return denied
    # Ensure user PDF folder exists before starting test
    ensure_user_pdf_folder(request.user.id)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'template20/psychometric/test3_intro.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test1_view(request):
    from core.assessment_access import has_class10_test_access
    if not has_class10_test_access(request.user, 'test1'):
        return redirect(reverse('app:test_buttons'))
    questions = Question.objects.filter(test_paper='test1')
    csrf_token = get_token(request)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
        'questions': questions,
        'test_paper': 'test1',
        'csrf_token':csrf_token,
    }
    test_completion, created = TestCompletion.objects.get_or_create(user=request.user)
    return render(request, 'template20/psychometric/test1_view.html',context)

@login_required(login_url=reverse_lazy('users:login'))
def test2_view(request):
    from core.assessment_access import has_class10_test_access
    if not has_class10_test_access(request.user, 'test2'):
        return redirect(reverse('app:test_buttons'))
    questions = list(Question.objects.filter(test_paper='test2'))
    csrf_token = get_token(request)
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
    except TestCompletion.DoesNotExist:
        test_completion = TestCompletion.objects.create(user=request.user)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    context = {
        'user_profile': user_profile,
        'questions': questions,
        'test_paper': 'test2',
        'csrf_token':csrf_token,
    }
    # return render(request, 'topteenfrontend/user/app/interest-assessment-test2.html', context)
    return render(request, 'template20/psychometric/test2_view.html', context)


@login_required(login_url=reverse_lazy('users:login'))
def test3_view(request):
    from core.assessment_access import has_class10_test_access
    if not has_class10_test_access(request.user, 'test3'):
        return redirect(reverse('app:test_buttons'))
    context = {}
    if request.method == 'POST':
        test_paper = request.POST.get('test_paper')
        questions = Question.objects.filter(test_paper=test_paper)       

        if not questions.exists():
            return render(request, 'topteenfrontend/404page.html', status=404)
        
        from collections import defaultdict
        score = 0
        selected_options = {}
        submitted_answer = []
        selected_answers_by_category = defaultdict(list)
        processed_questions = defaultdict(set)

        if test_paper == 'test3':
            # Get existing scores to preserve other sections
            try:
                test3_result = Results.objects.get(user=request.user, test_paper='test3')
                existing_scores = test3_result.scores or {}
                existing_selected_answers = test3_result.selected_answers or {}
            except Results.DoesNotExist:
                existing_scores = {}
                existing_selected_answers = {}

            # Initialize scores with existing values (preserve other sections)
            logical_score = existing_scores.get('logical_score', 0)
            verbal_score = existing_scores.get('verbal_score', 0)
            numerical_score = existing_scores.get('numerical_score', 0)
            emotional_score = existing_scores.get('critical_score', 0)
            language_score = existing_scores.get('language_score', 0)
            spatial_score = existing_scores.get('spatial_score', 0)
            mechanical_score = existing_scores.get('mechanical_score', 0)

            # Track which categories are being attempted in this submission
            attempted_categories = set()

            for question in questions:
                answer = request.POST.get(f'question_{question.id}', None)
                if answer:
                    attempted_categories.add(question.category)
                    selected_answer = get_object_or_404(Answer, pk=answer)
                    correct_answer = question.answer_set.filter(is_correct=True).first()

                    # Build the full image URL
                    image_url = None
                    if question.question_image:
                        image_url = request.build_absolute_uri(question.question_image.url)
                    
                    selected_answer_dict = {
                        "question_image_url": image_url if image_url else '-',
                        "question_text": question.question_text if question.question_text else "-",
                        "selected_answer": selected_answer.answer_text,
                        "correct_answer": correct_answer.answer_text if correct_answer else "-",
                        "category": question.category,
                    }
                    
                    # Add to the current category
                    if question.id not in processed_questions[question.category]:
                        selected_answers_by_category[question.category].append(selected_answer_dict)
                        processed_questions[question.category].add(question.id)

                    if selected_answer.is_correct:
                        score += 1

            # Reset scores only for attempted categories, then recalculate
            for category in attempted_categories:
                if category == 'Logical':
                    logical_score = 0
                elif category == 'Verbal':
                    verbal_score = 0
                elif category == 'Numerical':
                    numerical_score = 0
                elif category == 'Emotional':
                    emotional_score = 0
                elif category == 'Language':
                    language_score = 0
                elif category == 'Spatial':
                    spatial_score = 0
                elif category == 'Mechanical':
                    mechanical_score = 0

            # Now calculate fresh scores for attempted categories only
            for question in questions:
                answer = request.POST.get(f'question_{question.id}', None)
                if answer:
                    selected_answer = get_object_or_404(Answer, pk=answer)
                    if selected_answer.is_correct:
                        if question.category == 'Logical':
                            logical_score += 1
                        elif question.category == 'Verbal':
                            verbal_score += 1
                        elif question.category == 'Numerical':
                            numerical_score += 1
                        elif question.category == 'Emotional':
                            emotional_score += 1
                        elif question.category == 'Language':
                            language_score += 1
                        elif question.category == 'Spatial':
                            spatial_score += 1
                        elif question.category == 'Mechanical':
                            mechanical_score += 1

            # Merge existing selected_answers with new data
            for category, answers in selected_answers_by_category.items():
                # Replace the category data completely if it's being attempted
                existing_selected_answers[category] = answers

            # Update or create the result with preserved + updated scores
            test3_result, created = Results.objects.update_or_create(
                user=request.user,
                test_paper='test3',
                defaults={
                    'scores': {
                        'logical_score': logical_score,
                        'verbal_score': verbal_score,
                        'numerical_score': numerical_score,
                        'critical_score': emotional_score,
                        'language_score': language_score,
                        'spatial_score': spatial_score,
                        'mechanical_score': mechanical_score,
                    }, 
                    'results': {}, 
                    'selected_answers': existing_selected_answers
                }
            )
            try:
                from app.report_cache import invalidate_class10_report_cache
                invalidate_class10_report_cache(request.user.id)
            except Exception:
                pass
    
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
            
    test_completion, created = TestCompletion.objects.get_or_create(user=request.user)
    
    # Check if all subtests are completed before marking test3 as complete
    all_subtests_complete = (
        test_completion.numerical_complete and
        test_completion.verbal_complete and
        test_completion.logical_complete and
        test_completion.emotional_complete and
        test_completion.machanical_complete and
        test_completion.language_complete and
        test_completion.spatial_complete
    )
    
    # Only mark test3 as complete if all subtests are completed
    if all_subtests_complete:
        test_completion.test3_complete = True
        test_completion.save()

    context = {
        'user_profile': user_profile,
        # 'questions': questions,
        'test_paper': 'test3',
        'test_completion': test_completion,
        'all_subtests_complete': all_subtests_complete
    }
    
    return render(request, 'template20/psychometric/test3_view.html', context)


@login_required(login_url=reverse_lazy('users:login'))
def test3_numerical(request):
    from core.assessment_access import redirect_if_no_class10_test_access
    denied = redirect_if_no_class10_test_access(request, 'test3')
    if denied:
        return denied
    questions = list(Question.objects.filter(test_paper='test3', category='Numerical'))
    user = 'unique_identifier_for_test11'  # This should be dynamically determined
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.numerical_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        # Handle case where the TestCompletion object does not exist
        test_completion = None
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Numerical',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_numerical.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_logical(request):
    from core.assessment_access import redirect_if_no_class10_test_access
    denied = redirect_if_no_class10_test_access(request, 'test3')
    if denied:
        return denied
    questions = list(Question.objects.filter(test_paper='test3', category ='Logical'))
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.logical_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None
    
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Logical',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_logical.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_verbal(request):
    from core.assessment_access import redirect_if_no_class10_test_access
    denied = redirect_if_no_class10_test_access(request, 'test3')
    if denied:
        return denied
    
    questions = list(Question.objects.filter(test_paper='test3', category ='Verbal'))
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.verbal_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Verbal',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_verbal.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_emotional(request):
    from core.assessment_access import redirect_if_no_class10_test_access
    denied = redirect_if_no_class10_test_access(request, 'test3')
    if denied:
        return denied
    questions = Question.objects.filter(test_paper='test3', category ='Emotional')
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.emotional_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Emotional',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_emotional.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_language(request):
    from core.assessment_access import redirect_if_no_class10_test_access
    denied = redirect_if_no_class10_test_access(request, 'test3')
    if denied:
        return denied
    questions = Question.objects.filter(test_paper='test3', category ='Language')
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.language_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None
    
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Language',
        'user_profile': user_profile
    }

    return render(request, 'template20/psychometric/test3_language.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_machanical(request):
    from core.assessment_access import redirect_if_no_class10_test_access
    denied = redirect_if_no_class10_test_access(request, 'test3')
    if denied:
        return denied
    questions = Question.objects.filter(test_paper='test3', category ='Mechanical')
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.machanical_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Mechanical',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_machanical.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_spatial(request):
    from core.assessment_access import redirect_if_no_class10_test_access
    denied = redirect_if_no_class10_test_access(request, 'test3')
    if denied:
        return denied
    questions = Question.objects.filter(test_paper='test3', category ='Spatial')
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.spatial_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Spatial',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_spatial.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def generate_pdf(request):

    try:
    
        if request.method == 'POST':
            test_paper = request.POST.get('test_paper')
            questions = Question.objects.filter(test_paper=test_paper)

            if not questions:
                return HttpResponse("No questions found for this test.", status=404)
            
            score = 0
            selected_options = {}
            submitted_answer = []
            if test_paper == 'test1':
                categories = {
                    'R': 'Realistic',
                    'I': 'Investigative',
                    'A': 'Artistic',
                    'S': 'Social',
                    'E': 'Enterprising',
                    'C': 'Conventional'
                }
                results = {
                    'Realistic': 0,
                    'Investigative': 0,
                    'Artistic': 0,
                    'Social': 0,
                    'Enterprising': 0,
                    'Conventional': 0
                }
            
                # Pre-allocate 60 slots (question i -> index i-1); use 0 for missing answers
                num_questions = 60
                submitted_answer = [0] * num_questions
                for idx, question in enumerate(questions):
                    if idx >= num_questions:
                        break
                    answer = request.POST.get(f"question_{idx + 1}", None)
                    if answer is not None:
                        selected_options[question.id] = answer
                        submitted_answer[idx] = int(answer)
                        score += 1
                total_score = sum(submitted_answer)

                variable_indices = {
                'R': [1, 7, 13, 19, 25, 31, 37, 43, 49, 55],
                'I': [2, 8, 14, 20, 26, 32, 38, 44, 50, 56],
                'A': [3, 9, 15, 21, 27, 33, 39, 45, 51, 57],
                'S': [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
                'E': [5, 11, 17, 23, 29, 35, 41, 47, 53, 59],
                'C': [6, 12, 18, 24, 30, 36, 42, 48, 54, 60],
                }

                # Calculate sums (submitted_answer[i-1] is answer for question i)
                sum_R = sum(submitted_answer[i-1] for i in variable_indices['R'])
                sum_I = sum(submitted_answer[i-1] for i in variable_indices['I'])
                sum_A = sum(submitted_answer[i-1] for i in variable_indices['A'])
                sum_S = sum(submitted_answer[i-1] for i in variable_indices['S'])
                sum_E = sum(submitted_answer[i-1] for i in variable_indices['E'])
                sum_C = sum(submitted_answer[i-1] for i in variable_indices['C'])

                
                # Calculate percentages
                results['Realistic'] = round((sum_R / 50) * 100, 2)
                results['Investigative'] = round((sum_I / 50) * 100, 2)
                results['Artistic'] = round((sum_A / 50) * 100, 2)
                results['Social'] = round((sum_S / 50) * 100, 2)
                results['Enterprising'] = round((sum_E / 50) * 100, 2)
                results['Conventional'] = round((sum_C / 50) * 100, 2)
                # user = User.objects.get(username=request.user.username)
                user = request.user
                test1_result, created = Results.objects.update_or_create(
                user=user,  # Use the ForeignKey field
                test_paper='test1',  # Lookup field
                defaults={
                    'scores': {
                        'sum_R': sum_R,
                        'sum_I': sum_I,
                        'sum_A': sum_A,
                        'sum_S': sum_S,
                        'sum_E': sum_E,
                        'sum_C': sum_C
                    },
                    'results': results
                    }
                )
                # Add submitted_answer to the results dictionary
                submitted_answers_dict = {
                    f'Question_{i + 1}': ans for i, ans in enumerate(submitted_answer)
                }
                # Add to the results dictionary
                test1_result.selected_answers['submitted_answers'] = submitted_answers_dict

                # Save updated results back to the database
                test1_result.save()
                try:
                    from app.report_cache import invalidate_class10_report_cache
                    invalidate_class10_report_cache(user.id)
                except Exception:
                    pass

            # return score, selected_options
            
        else:
            return JsonResponse({'message': 'Invalid request'}, status=400)
        
    except Exception as e:
        logger.exception(
            "generate_pdf failed (test_paper=%s, user_id=%s): %s",
            request.POST.get('test_paper') if request.method == 'POST' else None,
            getattr(request.user, 'id', None),
            e,
        )
        return HttpResponse("Result could not be saved. Please try again.", status=500)
        
 
def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            # for item in data:
            #     category_obj, created = Category.objects.update_or_create(
            #         category=item['category'],
            #         fullname=item['fullname'],
            #         summary=item['summary'],
            #         fields=item['fields'],
            #         best_colleges=item.get('best_colleges', '')
            #     )
                
            #     for course in item['courses']:
            #         Course.objects.create(category=category_obj, course_name=course)
                
            #     for stream, subjects in item['streams'].items():
            #         Stream.objects.create(category=category_obj, stream_name=stream, subjects=', '.join(subjects))
        
        if isinstance(data, list):
            dictionary_array = []
            for data_set in data:
                dictionary = dict(data_set)
                dictionary_array.append(dictionary)
            return dictionary_array
        else:
            messages.error("Error: The JSON data is not a list.")
    except FileNotFoundError:
        messages.error(f"Error: {file_path} file not found.")
    except json.JSONDecodeError:
        messages.error(f"Error: Invalid JSON format in {file_path}.")
    except Exception as e:
        messages.error(f"Error: {e}")

@login_required(login_url=reverse_lazy('users:login'))
def stream_decision_questionnaire_submit(request):
    from app.stream_decision import is_questionnaire_completed, save_questionnaire, validate_answers

    if request.method != 'POST':
        return JsonResponse({'message': 'Invalid request'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'message': 'Invalid JSON data'}, status=400)

    answers = data.get('answers') or {}
    validation_error = validate_answers(answers)
    if validation_error:
        return JsonResponse({'message': validation_error}, status=400)

    try:
        test_completion = TestCompletion.objects.get(user=request.user)
    except TestCompletion.DoesNotExist:
        return JsonResponse({'message': 'Test completion record not found.'}, status=400)

    all_subtests_complete = (
        test_completion.numerical_complete and
        test_completion.verbal_complete and
        test_completion.logical_complete and
        test_completion.emotional_complete and
        test_completion.machanical_complete and
        test_completion.language_complete and
        test_completion.spatial_complete
    )
    if not (
        test_completion.test1_complete and
        test_completion.test2_complete and
        test_completion.test3_complete and
        all_subtests_complete
    ):
        return JsonResponse({'message': 'Complete all mandatory tests first.'}, status=400)

    try:
        test3_result = Results.objects.get(user=request.user, test_paper='test3')
        if is_questionnaire_completed(test3_result.results):
            return JsonResponse({'message': 'You have already submitted your stream decision.'}, status=400)
        save_questionnaire(test3_result, answers)
        return JsonResponse({'message': 'Success', 'completed': True}, status=200)
    except Results.DoesNotExist:
        return JsonResponse({'message': 'Aptitude test results not found.'}, status=400)
    except Exception as exc:
        logger.error('stream_decision_questionnaire_submit failed for user %s: %s', request.user.id, exc)
        return JsonResponse({'message': 'Unable to save your responses.'}, status=500)


@csrf_exempt
@login_required(login_url=reverse_lazy('users:login'))
def submit_clicks(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            clicks = data.get('clicks', {})
            question1_clicks = clicks.get('question1', [])
            question2_clicks = clicks.get('question2', [])
            question3_clicks = clicks.get('question3', [])
            question4_clicks = clicks.get('question4', [])
            question5_clicks = clicks.get('question5', [])
            question6_clicks = clicks.get('question6', [])
            # Process the clicks data as needed
            
            question1_clicks = len(question1_clicks)            
            question2_clicks = len(question2_clicks)            
            question3_clicks = len(question3_clicks)            
            question4_clicks = len(question4_clicks)
            question5_clicks = len(question5_clicks)
            question6_clicks = len(question6_clicks)

            # save to the database
            user = request.user
            test2_result, created = Results.objects.update_or_create(
                    user = user,
                    test_paper='test2',
                    defaults={
                        'scores': {
                            'Realistic': question1_clicks,
                            'Investigative': question2_clicks,
                            'Artistic': question3_clicks,
                            'Social': question4_clicks,
                            'Enterprising': question5_clicks,
                            'Conventional': question6_clicks,
                        }
                    }
                )
            test2_result.save()
            # get_or_create: TC may be missing if test2 is attempted before other tests
            test_completion, _ = TestCompletion.objects.get_or_create(user=request.user)
            test_completion.test2_complete = True
            test_completion.save(update_fields=['test2_complete'])
            try:
                from app.report_cache import invalidate_class10_report_cache
                invalidate_class10_report_cache(request.user.id)
            except Exception:
                pass

            # Generate Interest Assessment PDF in background (avoids blocking under load).
            try:
                from app.task import enqueue_class10_assessment_pdf
                enqueue_class10_assessment_pdf(
                    request.user.id,
                    'test2',
                    request.build_absolute_uri('/'),
                )
            except Exception:
                logger.exception(
                    "submit_clicks: failed to enqueue test2 PDF for user_id=%s",
                    getattr(request.user, 'id', None),
                )
            
            return JsonResponse({'message': 'Success'}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'message': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.exception("submit_clicks failed for user_id=%s: %s", getattr(request.user, 'id', None), e)
            return JsonResponse({'message': 'Unable to save career interest responses.'}, status=500)
    return JsonResponse({'message': 'Invalid request'}, status=400)
    
@login_required(login_url=reverse_lazy('users:login'))
def app_submit(request):
    cache.clear()
    if request.method == 'POST':
        test_paper = request.POST.get('test_paper')
        test_completion = TestCompletion.objects.get(user=request.user)

        # For test1, save result first via generate_pdf; only then mark complete (so "View result" always finds data)
        if test_paper == 'test1':
            error_resp = generate_pdf(request)
            if error_resp is not None:
                return error_resp
            test_completion.test1_complete = True
            test_completion.save()
        elif test_paper == 'test2':
            test_completion.test2_complete = True
            test_completion.save()
        elif test_paper == 'test3':
            # Check if all subtests are completed before marking test3 as complete
            all_subtests_complete = (
                test_completion.numerical_complete and
                test_completion.verbal_complete and
                test_completion.logical_complete and
                test_completion.emotional_complete and
                test_completion.machanical_complete and
                test_completion.language_complete and
                test_completion.spatial_complete
            )
            
            if all_subtests_complete:
                test_completion.test3_complete = True
                test_completion.save()

    # Load analysis content from a JSON file
    # analysis_content = read_json_file('RIASEC.json')
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    test_completion = TestCompletion.objects.get(user=request.user)
    
    # Verify and correct test3_complete status - only True if ALL subtests are complete
    all_subtests_complete = (
        test_completion.numerical_complete and
        test_completion.verbal_complete and
        test_completion.logical_complete and
        test_completion.emotional_complete and
        test_completion.machanical_complete and
        test_completion.language_complete and
        test_completion.spatial_complete
    )
    
    # Correct test3_complete if it's incorrectly set
    if test_completion.test3_complete and not all_subtests_complete:
        test_completion.test3_complete = False
        test_completion.save()
        logger.info("Corrected test3_complete for user %s: was True but not all subtests complete", request.user.id)
    elif not test_completion.test3_complete and all_subtests_complete:
        test_completion.test3_complete = True
        test_completion.save()
    
    # Check if tests have been started but not completed
    test_started_status = {
        'test1_started': Results.objects.filter(user=request.user, test_paper='test1').exists(),
        'test2_started': Results.objects.filter(user=request.user, test_paper='test2').exists(),
        'test3_started': Results.objects.filter(user=request.user, test_paper='test3').exists(),
    }
    
    # Prepare context for rendering the template
    from core.assessment_access import (
        build_class10_psychometric_page_context,
        has_legacy_full_bundle_access,
    )

    context = {
        # 'analysis_content': analysis_content,
        'test_completion': test_completion,
        'test_started_status': test_started_status,
        'user_profile': user_profile,
        'all_test3_subtests_complete': all_subtests_complete,  # Add this for template check
        **build_class10_psychometric_page_context(request.user),
    }
    generate_pdf(request)
    # When student has finished all tests, show psychometric dashboard
    if has_legacy_full_bundle_access(request.user):
        if (
            test_completion.test1_complete
            and test_completion.test2_complete
            and test_completion.test3_complete
            and all_subtests_complete
        ):
            return redirect(reverse('app:dashboard'))
    return render(request, 'template20/psychometric/test_submit.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def gernate_graph(request):
    # Get the data for the personality test
    test1_result = Results.objects.get(user=request.user, test_paper='test1')
    sorted_result = test1_result.results

    # Get the data for the Career interest test
    try:
        test2_result = Results.objects.get(user=request.user, test_paper='test2')
        lengths = test2_result.scores
        max_length = max(lengths, key=lengths.get)
        min_length = min(lengths, key=lengths.get)
    except Results.DoesNotExist:
        max_length = ''
        min_length = ''

    # Get the data for the Intelligence test
    try:
        test3_result = Results.objects.get(user=request.user, test_paper='test3')
        personality_res = test3_result.scores
        scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
        below = []
        avg = []
        above_avg = []
        for key in scores:
            if scores[key] <= 5:
                below.append(key)
            elif scores[key] <= 10:
                avg.append(key)
            else:
                above_avg.append(key)
    except Results.DoesNotExist:
        below = ''
        avg = ''
        above_avg = ''

    # Define the graph images folder for the user
    from app.graph_media_utils import graph_image_path, graph_images_directory

    user_name = getattr(request.user, 'name', None) or getattr(request.user, 'email', None) or str(request.user)
    user_ID = request.user.id
    graph_images_folder = graph_images_directory()

    graph_images = []

    # Assuming sorted_result contains scores between 0 and 100.
    if sorted_result:
        # Define RIASEC order: Realistic, Investigative, Artistic, Social, Enterprising, Conventional
        riasec_order = ['Realistic', 'Investigative', 'Artistic', 'Social', 'Enterprising', 'Conventional']
        
        # Reorder labels and values according to RIASEC order
        labels = []
        values = []
        for category in riasec_order:
            if category in sorted_result:
                labels.append(category.upper())
                values.append(sorted_result[category])

        # Define figure and axis
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # Colors for the bars (matching RIASEC order)
        colors = ['#53BAD8', '#D17DD6', '#67BA48', '#BBA63A', '#CC4230', '#5999D1']
        
        # Create bar plot
        bars = ax.bar(labels, values, color=colors)
        
        # Title and labels
        plt.title('PERSONALITY ASSESSMENT', fontsize=20, fontweight='bold')
        ax.set_xlabel('')
        ax.set_ylabel('Score (%)', fontsize=18, fontweight='bold')
        
        # Setting ticks and labels size
        ax.tick_params(axis='x', labelsize=14)
        ax.tick_params(axis='y', labelsize=14)
        
        # Set y-axis limits and scale to 0-100 with intervals of 10
        ax.set_ylim(0, 105)
        ax.set_yticks(range(0, 105, 10))
        
        # Highlighting the bar with a specific value like 74%
        highlight_value = 100
        for bar, value in zip(bars, values):
            if value == highlight_value:
                bar.set_edgecolor('red')
                bar.set_linewidth(3)
            
            # Annotate bars with their values
            ax.annotate(f'{value}%', xy=(bar.get_x() + bar.get_width() / 2, value), 
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points", 
                        ha='center', va='bottom', fontsize=12, fontweight='bold')
        
        fig.subplots_adjust(bottom=0.24, top=0.88, left=0.08, right=0.98)
        # Save the image
        image_path = graph_image_path(user_name, user_ID, 'personality')
        graph_images.append(image_path)
        plt.savefig(image_path, bbox_inches='tight', pad_inches=0.3, dpi=120)
        plt.close()

    try:
        if lengths:
            # Define RIASEC order: Realistic, Investigative, Artistic, Social, Enterprising, Conventional
            riasec_order = ['Realistic', 'Investigative', 'Artistic', 'Social', 'Enterprising', 'Conventional']
            
            # Reorder labels and values according to RIASEC order
            labels = []
            values = []
            for category in riasec_order:
                if category in lengths:
                    labels.append(category.upper())
                    values.append(lengths[category])
            
            # Create the figure and axis
            fig, ax = plt.subplots(figsize=(24, 12))
            
            # Define colors for the bars (matching RIASEC order)
            colors = ['#53BAD8', '#D17DD6', '#67BA48', '#BBA63A', '#CC4230', '#5999D1']
            
            # Create bar plot
            bars = ax.bar(labels, values, color=colors)
            
            # Set title and labels
            ax.set_title('INTEREST ASSESSMENT', fontsize=25, fontweight='bold')
            ax.set_xlabel('')
            ax.set_ylabel('Score', fontsize=29, fontweight='bold')
            
            # Adjust tick parameters
            ax.tick_params(axis='x', labelsize=24)
            ax.tick_params(axis='y', labelsize=24)
            
            # Set y-axis limits and scale to 0-60 with intervals of 6
            ax.set_ylim(0, 39)
            ax.set_yticks(range(0, 39, 6))
            
            # Highlight the bar with a specific value, like 36
            highlight_value = 36
            for bar, value in zip(bars, values):
                # Highlighting the bar with the score of 36
                if value == highlight_value:
                    bar.set_edgecolor('red')
                    bar.set_linewidth(3)
                
                # Annotate bars with their values
                ax.annotate(f'{value}', xy=(bar.get_x() + bar.get_width() / 2, value), 
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points", 
                            ha='center', va='bottom', fontsize=15, fontweight='bold')
            
            # Save the image
            image_path = graph_image_path(user_name, user_ID, 'interest')
            graph_images.append(image_path)
            plt.savefig(image_path, bbox_inches='tight')  # Save image with tight layout
            plt.close()

    except Exception as e:
        logger.warning("Error creating interest assessment graph: %s", e)

    try:
        personality = test3_result.scores

        if personality:
            original_labels = list(personality.keys())
            labels = [label.split("_")[0].upper() for label in original_labels]
            values = list(personality.values())
            
            # Create the figure and axis
            fig, ax = plt.subplots(figsize=(21, 10))
            
            # Define colors for the bars
            colors = ['#53BAD8', '#D17DD6', '#67BA48', '#BBA63A', '#CC4230']
            
            # Create bar plot
            bars = ax.bar(labels, values, color=colors)
            
            # Set title and labels
            ax.set_title('APTITUDE ASSESSMENT', fontsize=29, fontweight='bold')
            ax.set_xlabel('')
            ax.set_ylabel('', fontsize=29, fontweight='bold')
            
            # Adjust tick parameters
            ax.tick_params(axis='x', labelsize=24)
            ax.tick_params(axis='y', labelsize=24)
            
            # Set y-axis limits and scale to 0-15 with increments of 3
            ax.set_ylim(0, 18)  # Set limit to 20 to create a gap above the highest tick
            ax.set_yticks(range(0, 19, 5))  # Tick marks at 0, 5, 10, 15

            # Highlight specific bars if needed
            highlight_value = 15  # Example value to highlight
            for bar, value in zip(bars, values):
                if value == highlight_value:
                    bar.set_edgecolor('red')
                    bar.set_linewidth(3)
                
                # Annotate bars with their values
                ax.annotate(f'{value}', xy=(bar.get_x() + bar.get_width() / 2, value), 
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points", 
                            ha='center', va='bottom', fontsize=15, fontweight='bold')
            
            # Save the image
            image_path = graph_image_path(user_name, user_ID, 'intelligence')
            graph_images.append(image_path)
            plt.savefig(image_path, bbox_inches='tight')  # Save image with tight layout
            plt.close()

    except Exception as e:
        logger.warning("Error creating intelligence assessment graph: %s", e)
        personality = ''

    return below, avg, above_avg, personality, min_length, max_length
     

def download_pdf(request, test_paper, _sync_generate=False):
    """
    Class 10 assessment PDF entrypoint.

    Under normal web/Locust traffic WeasyPrint runs in Celery. Pass
    ``_sync_generate=True`` only from the Celery worker (or Celery-disabled fallback).
    """
    if request.method == 'POST':
        test_paper = request.POST.get('test_paper') or test_paper
        questions = Question.objects.filter(test_paper=test_paper)

        if not questions:
            return HttpResponse("No questions found for this test.", status=404)

    # Fast path: PDF already stored — do not regenerate on the web worker.
    try:
        existing_name = class10_assessment_pdf_filename(request.user, test_paper)
        if user_pdf_exists(request.user.id, existing_name):
            return redirect('app:app_submit')
    except Exception:
        logger.exception(
            "download_pdf: exists-check failed user_id=%s test_paper=%s",
            getattr(request.user, 'id', None),
            test_paper,
        )

    # Prefer background generation so concurrent downloads do not saturate Gunicorn.
    if not _sync_generate:
        try:
            from app.task import enqueue_class10_assessment_pdf
            if enqueue_class10_assessment_pdf(
                request.user.id,
                test_paper,
                request.build_absolute_uri('/'),
            ):
                return redirect('app:app_submit')
        except Exception:
            logger.exception(
                "download_pdf: enqueue failed user_id=%s test_paper=%s; falling back to sync",
                getattr(request.user, 'id', None),
                test_paper,
            )

    top_3_categories = ""
    top_categories = []
    questions= Question.objects.all()
    score = 0

    if questions is not None:
        test1_result = Results.objects.get(user = request.user, test_paper='test1')
        sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
        for i, (category, score) in enumerate(sorted_results, start=1):
            if i > 3:
                break
            top_categories.append({
                'rank': i,
                'category': category,
                'score': f"{score:.2f}%"
            })
            
            top_3_categories += category[0]

        top_3_categories_str = "".join(top_3_categories)
        
        analysis_content = read_json_file('RIASEC.json')

        # Assume `request.user` is your user object

        below, avg, above_avg, personality, min_length, max_length = gernate_graph(request)
        # print('################## ',test_paper)
        if test_paper == 'test1':            
            template_path = 'personality-assessment-pdf.html'
        elif test_paper == 'test2':
            template_path = 'interest-assessment-pdf.html'
        elif test_paper == 'test3':            
            template_path = 'intelligence-assessment-pdf.html'
            
        else:
            template_path = 'pdf_template_final.html'
        # print('################## template_path',template_path)
        ''' ################ test complection logic###################'''
        # current_user = request.user
        # # Fetch or create TestCompletion instance for the current user
        # test_completion, created = TestCompletion.objects.get_or_create(user=current_user)
        try:
            test_completion= TestCompletion.objects.get(user=request.user)
        except:
            return HttpResponse("No User please Signup First")

        ''' ############## Ploygram Graphs #########################'''

        '''         Getting the data from the json file table Category   '''

        top_3 = top_3_categories_str.split(',')
        top_category_code = top_3[0]

        # Get the top category using the code
        top_category = Category.objects.filter(category=top_category_code).first()
        streamsubject = set()
        courseName = set()
        if top_category:
            category_id = top_category.id
            # Get streams related to this category using the category ID
            streams = Stream.objects.filter(category_id=category_id)
            # Print the details of each stream
            for stream in streams:
                streamsubject.add((stream.stream_name, stream.subjects))

            # Get courses related to this category using the category ID
            courses = Course.objects.filter(category_id=category_id)
            for course in courses:
                # Print the details of each courses
                courseName.add(course.course_name)

        else:
            logger.debug("No category found with the code: %s", top_category_code)
        
        if request.user.is_authenticated:
            user = request.user

            try:
                # Retrieve the UserProfile for the logged-in user (create if not exists)
                user_profile, created = UserProfile.objects.get_or_create(user=user)
                
            except UserProfile.DoesNotExist:
                user_profile = None

            # Get all fields from the User model for the current user
            student_name = User.objects.get(pk=user.id) 

            try:
                # Retrieve the UserProfile for the logged-in user
                user_profile = user.user_profile
                # Access attributes from the User object
                created_date = user.created

                # Access attributes from the UserProfile object
                gender = user_profile.gender
                schoolname = user_profile.schoolname
                grade = user_profile.grade

                

            except UserProfile.DoesNotExist:
                logger.debug("UserProfile does not exist.")

        else:
            logger.debug("User is not authenticated.")

        user_name = request.user
        user_ID = request.user.id

        context = {
            'score': score,
            'user_name':user_name,
            'user_ID':user_ID,
            'user_profile':user_profile,
            'student_name':student_name,
            "School_Name:": schoolname,
            'created_date':created_date,
            "Gender:": gender,
            "Grade:": grade,
            'intelligence_score':personality,
            'questions': questions,
            'top_categories':top_categories,
            'top_3_categories_str':top_3_categories_str,
            'top_category': top_category,
            'streamsubject':streamsubject,
            'courseName':courseName,
            'top_3_categories':top_3_categories,
            'test_completion': test_completion,
            'max_length': max_length,
            'min_length':min_length,
            'below':below,
            'avg':avg,
            'above_avg': above_avg,
        }

        try:
            template = get_template(template_path)
            html = template.render(context)
            # print()
            # print()
            # print("################## html", html)


            # print("HTML content generated successfully. ###################################")
            # print("Context:", html)
            # print("HTML content generated successfully Ends @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@.")

            # Configure SSL to disable verification for WeasyPrint image loading
            # This is needed because WeasyPrint tries to fetch images via HTTPS
            # and SSL certificate verification fails on the server
            # This is safe for internal requests to the same server
            import ssl
            
            # Disable SSL verification for urllib (used by WeasyPrint internally)
            original_ssl_context = ssl._create_default_https_context
            ssl._create_default_https_context = ssl._create_unverified_context
            
            try:
                # Use HTTPS with SSL verification disabled
                pdf_file = weasyprint.HTML(
                    string=html, 
                    base_url=request.build_absolute_uri('/')
                ).write_pdf()
            finally:
                # Restore original SSL context
                ssl._create_default_https_context = original_ssl_context
            response = HttpResponse(content_type='application/pdf')
            filename = class10_assessment_pdf_filename(request.user, test_paper)

            # Persist the generated PDF to media storage (S3 when enabled).
            if not save_user_pdf(request.user.id, filename, pdf_file):
                logger.warning("download_pdf: could not persist PDF for user_id=%s", request.user.id)

            return redirect('app:app_submit')
            
        except Exception as e:
            import traceback
            logger.exception("Error generating PDF: %s", e)
            traceback.print_exc()
            messages.error(request, 'Error generating PDF')
            return redirect('app:app_submit')
    else:
        messages.error(request, 'Error generating PDF')
        return redirect('app:quiz_questions')

from django.http import HttpResponse, Http404
@login_required(login_url=reverse_lazy('users:login'))
def test_1(request, test_paper):
    """
    Legacy view - redirects to new HTML report views
    """
    if test_paper == 'test1':
        return redirect('app:test1_report_html')
    elif test_paper == 'test2':
        return redirect('app:test2_report_html')
    elif test_paper == 'test3':
        return redirect('app:test3_report_html')
    else:
        return HttpResponse("Invalid test paper.", status=404)


@login_required(login_url=reverse_lazy('users:login'))
def test1_report_html(request, user_id=None):
    """
    HTML report view for Test 1 (Personality Assessment)
    """
    try:
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists (for later download/save)
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test1 is completed
        try:
            test1_result = Results.objects.get(user=target_user, test_paper='test1')
        except Results.DoesNotExist:
            resp = render(request, 'template20/app/test1_report.html', {
                'error': 'Please complete the Personality Assessment test first.',
                'no_results': True,
                'user': target_user,
                'user_ID': target_user.id if target_user else None,
                'viewing_as_admin': False
            })
            return _add_no_cache_headers(resp)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get personality data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            logger.exception(f"Error in db_results_inst_user: {e}")
            top_category = None
            streamsubject = set()
            courseName = set()
            top_categories = []
        
        # Process personality test data
        personality_data = {}
        if test1_result and test1_result.results:
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            personality_data = {
                'results': dict(sorted_results),
                'top_categories': top_categories,
                'top_category': top_category
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_personality_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                logger.warning("Error generating graph: %s", e)
                pass
        
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'personality_data': personality_data,
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'stream_career_sections': get_stream_career_sections(top_category),
            'top_categories': top_categories,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'no_results': False,
            'viewing_as_admin': user_id is not None and user_id != request.user.id
        }
        
        resp = render(request, 'template20/app/test1_report.html', context)
        return _add_no_cache_headers(resp)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.exception(f"Error in test1_report_html: {str(e)}")
        resp = render(request, 'template20/app/test1_report.html', {
            'error': f'An error occurred: {str(e)}',
            'no_results': True,
            'user': request.user,
            'user_ID': request.user.id if request.user.is_authenticated else None,
            'viewing_as_admin': False
        })
        return _add_no_cache_headers(resp)


@login_required(login_url=reverse_lazy('users:login'))
def test2_report_html(request, user_id=None):
    """
    HTML report view for Test 2 (Interest Assessment)
    """
    try:
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists (for later download/save)
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test2 is completed
        try:
            test2_result = Results.objects.get(user=target_user, test_paper='test2')
        except Results.DoesNotExist:
            resp = render(request, 'template20/app/test2_report.html', {
                'error': 'Please complete the Career Interest Assessment test first.',
                'no_results': True,
                'user': target_user,
                'user_ID': target_user.id if target_user else None,
                'viewing_as_admin': False
            })
            return _add_no_cache_headers(resp)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get interest data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            logger.exception(f"Error in db_results_inst_user: {e}")
            max_length = ''
            min_length = ''
        
        # Process interest test data
        interest_data = {}
        if test2_result and test2_result.scores:
            interest_data = {
                'scores': test2_result.scores,
                'max_category': max_length,
                'min_category': min_length
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_interest_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                logger.warning("Error generating graph: %s", e)
                pass
        
        from app.interest_report_utils import interest_report_context_fields
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'interest_data': interest_data,
            'max_length': max_length,
            'min_length': min_length,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'no_results': False,
            'viewing_as_admin': user_id is not None and user_id != request.user.id,
            **interest_report_context_fields(
                scores=test2_result.scores if test2_result else None,
                max_length=max_length,
                min_length=min_length,
            ),
        }
        
        resp = render(request, 'template20/app/test2_report.html', context)
        return _add_no_cache_headers(resp)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.exception(f"Error in test2_report_html: {str(e)}")
        resp = render(request, 'template20/app/test2_report.html', {
            'error': f'An error occurred: {str(e)}',
            'no_results': True,
            'user': request.user,
            'user_ID': request.user.id if request.user.is_authenticated else None,
            'viewing_as_admin': False
        })
        return _add_no_cache_headers(resp)


@login_required(login_url=reverse_lazy('users:login'))
def test3_report_html(request, user_id=None):
    """
    HTML report view for Test 3 (Aptitude Assessment)
    """
    try:
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists (for later download/save)
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test3 is completed
        try:
            test3_result = Results.objects.get(user=target_user, test_paper='test3')
        except Results.DoesNotExist:
            resp = render(request, 'template20/app/test3_report.html', {
                'error': 'Please complete the Aptitude Assessment test first.',
                'no_results': True,
                'user': target_user,
                'user_ID': target_user.id if target_user else None,
                'viewing_as_admin': False
            })
            return _add_no_cache_headers(resp)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get intelligence data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            logger.exception(f"Error in db_results_inst_user: {e}")
            below = []
            avg = []
            above_avg = []
        
        # Process intelligence test data
        intelligence_data = {}
        if test3_result and test3_result.scores:
            scores = {label.split("_")[0].upper(): value for label, value in test3_result.scores.items()}
            intelligence_data = {
                'scores': scores,
                'below_avg': below,
                'average': avg,
                'above_avg': above_avg
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_intelligence_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                logger.warning("Error generating graph: %s", e)
                pass
        
        from app.report_visibility import student_all_growth_areas
        from app.vocational_recommendations import vocational_guidance_context_for_below_areas

        context = {
            'user': target_user,
            'user_profile': user_profile,
            'intelligence_data': intelligence_data,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'no_results': False,
            'viewing_as_admin': user_id is not None and user_id != request.user.id,
            'stream_recommendation': recommend_streams_from_tiers(above_avg, avg, below_avg=below),
            'student_below_average': student_all_growth_areas(below, avg, above_avg),
        }
        context.update(vocational_guidance_context_for_below_areas(below, user=target_user))

        from app.aptitude_report_utils import aptitude_report_context_fields
        context.update(
            aptitude_report_context_fields(
                test3_result.scores if test3_result and test3_result.scores else None
            )
        )

        resp = render(request, 'template20/app/test3_report.html', context)
        return _add_no_cache_headers(resp)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.exception(f"Error in test3_report_html: {str(e)}")
        resp = render(request, 'template20/app/test3_report.html', {
            'error': f'An error occurred: {str(e)}',
            'no_results': True,
            'user': request.user,
            'user_ID': request.user.id if request.user.is_authenticated else None,
            'viewing_as_admin': False
        })
        return _add_no_cache_headers(resp)


def _resolve_static_urls_to_local_paths(html_content, base_url):
    """
    Replace /static/ and /media/ URLs in HTML with local file paths
    to avoid HTTP requests during PDF generation.
    This significantly speeds up PDF generation by eliminating network requests.
    """
    def replace_static(match):
        quote_char = match.group(1)  # Captured quote character (" or ')
        static_path = match.group(2)  # Path after /static/
        # Try to find the static file using Django's staticfiles finder
        found_path = finders.find(static_path)
        if found_path:
            # Normalize path separators for file:// URLs (use forward slashes)
            normalized_path = found_path.replace('\\', '/')
            # Convert to file:// URL with proper formatting
            return f'{match.group(0)[:match.start(2)-match.start()]}file:///{normalized_path}{quote_char}'
        # If not found, return original
        return match.group(0)
    
    def replace_media(match):
        quote_char = match.group(1)  # Captured quote character (" or ')
        media_path = match.group(2)  # Path after /media/
        # Construct full media file path
        media_file_path = os.path.join(settings.MEDIA_ROOT, media_path)
        if os.path.exists(media_file_path):
            # Normalize path separators for file:// URLs (use forward slashes)
            normalized_path = media_file_path.replace('\\', '/')
            # Convert to file:// URL with proper formatting
            return f'{match.group(0)[:match.start(2)-match.start()]}file:///{normalized_path}{quote_char}'
        # If not found, return original
        return match.group(0)
    
    # Replace /static/ URLs in src and href attributes (capture quote and path separately)
    html_content = re.sub(
        r'(src|href)=(["\'])/static/([^"\']+)\2',
        lambda m: f'{m.group(1)}={m.group(2)}file:///{finders.find(m.group(3)).replace(chr(92), "/")}{m.group(2)}' if finders.find(m.group(3)) else m.group(0),
        html_content
    )
    
    # Replace /media/ URLs in src and href attributes (capture quote and path separately)
    html_content = re.sub(
        r'(src|href)=(["\'])/media/([^"\']+)\2',
        lambda m: (lambda path, quote: f'{m.group(1)}={quote}file:///{path.replace(chr(92), "/")}{quote}' if os.path.exists(path) else m.group(0))(os.path.join(settings.MEDIA_ROOT, m.group(3)), m.group(2)),
        html_content
    )
    
    return html_content


@login_required(login_url=reverse_lazy('users:login'))
def test1_report_pdf(request, user_id=None, _sync_generate=False):
    """
    PDF download view for Test 1 (Personality Assessment)
    """
    try:
        import weasyprint
        from django.template.loader import get_template
        from datetime import datetime
        
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists
        ensure_user_pdf_folder(target_user.id)

        early = _try_serve_or_enqueue_web_report_pdf(
            request, target_user, 'test1', _sync_generate=_sync_generate
        )
        if early is not None:
            return early
        
        # Check if test1 is completed
        try:
            test1_result = Results.objects.get(user=target_user, test_paper='test1')
        except Results.DoesNotExist:
            return HttpResponse('Please complete the Personality Assessment test first.', status=404)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get personality data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            logger.exception(f"Error in db_results_inst_user: {e}")
            top_category = None
            streamsubject = set()
            courseName = set()
            top_categories = []
        
        # Process personality test data
        personality_data = {}
        if test1_result and test1_result.results:
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            personality_data = {
                'results': dict(sorted_results),
                'top_categories': top_categories,
                'top_category': top_category
            }
        
        # Generate graph images for PDF (always refresh so chart margins stay current)
        try:
            original_user = request.user
            request.user = target_user
            gernate_graph(request)
            request.user = original_user
        except Exception as e:
            logger.warning("Error generating graph for PDF: %s", e)
            pass
        
        # Get created_date and student_name
        created_date = test1_result.created if hasattr(test1_result, 'created') else target_user.created
        student_name = target_user.name if target_user.name else target_user.email
        
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'personality_data': personality_data,
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'stream_career_sections': get_stream_career_sections(top_category),
            'top_categories': top_categories,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'student_name': student_name,
            'created_date': created_date,
            'now': datetime.now(),
        }
        
        # Render HTML template
        template = get_template('template20/app/test1_report_pdf.html')
        html = template.render(context)
        
        # Debug: return raw HTML (?debug=true)
        if request.GET.get('debug') == 'true':
            r = HttpResponse(html, content_type='text/html; charset=utf-8')
            r['Content-Disposition'] = 'inline; filename=test1-personality-report-debug.html'
            r['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            return r
        
        # Generate PDF with optimizations
        # Keep HTTP base_url for proper static/media resolution
        # The main optimization is graph generation check (skip if exists)
        # and image optimization for smaller file size
        import ssl
        original_ssl_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            pdf_file = weasyprint.HTML(
                string=html,
                base_url=request.build_absolute_uri('/')
            ).write_pdf(optimize_images=True)
        finally:
            ssl._create_default_https_context = original_ssl_context
        
        # Create response (safe filename for Gmail/email users)
        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = class10_assessment_pdf_filename(target_user, 'test1')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Persist a copy to media storage (S3 when enabled) - best-effort.
        save_user_pdf(target_user.id, filename, pdf_file)

        return response
        
    except Exception as e:
        logger.exception("test1_report_pdf failed: %s", e)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


@login_required(login_url=reverse_lazy('users:login'))
def test2_report_pdf(request, user_id=None, _sync_generate=False):
    """
    PDF download view for Test 2 (Interest Assessment)
    """
    try:
        import weasyprint
        from django.template.loader import get_template
        from datetime import datetime
        
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists
        ensure_user_pdf_folder(target_user.id)

        early = _try_serve_or_enqueue_web_report_pdf(
            request, target_user, 'test2', _sync_generate=_sync_generate
        )
        if early is not None:
            return early
        
        # Check if test2 is completed
        try:
            test2_result = Results.objects.get(user=target_user, test_paper='test2')
        except Results.DoesNotExist:
            return HttpResponse('Please complete the Career Interest Assessment test first.', status=404)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get interest data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            logger.exception(f"Error in db_results_inst_user: {e}")
            max_length = ''
            min_length = ''
        
        # Process interest test data
        interest_data = {}
        if test2_result and test2_result.scores:
            interest_data = {
                'scores': test2_result.scores,
                'max_category': max_length,
                'min_category': min_length
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_interest_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                logger.warning("Error generating graph: %s", e)
                pass
        
        # Get created_date and student_name
        created_date = test2_result.created if hasattr(test2_result, 'created') else target_user.created
        student_name = target_user.name if target_user.name else target_user.email
        
        from app.interest_report_utils import interest_report_context_fields
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'interest_data': interest_data,
            'max_length': max_length,
            'min_length': min_length,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'student_name': student_name,
            'created_date': created_date,
            'now': datetime.now(),
            **interest_report_context_fields(
                scores=test2_result.scores if test2_result else None,
                max_length=max_length,
                min_length=min_length,
            ),
        }
        
        # Render HTML template
        template = get_template('template20/app/test2_report_pdf.html')
        html = template.render(context)
        
        # Debug: return raw HTML (?debug=true)
        if request.GET.get('debug') == 'true':
            r = HttpResponse(html, content_type='text/html; charset=utf-8')
            r['Content-Disposition'] = 'inline; filename=test2-interest-report-debug.html'
            r['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            return r
        
        # Generate PDF with optimizations
        # Keep HTTP base_url for proper static/media resolution
        # The main optimization is graph generation check (skip if exists)
        # and image optimization for smaller file size
        import ssl
        original_ssl_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            pdf_file = weasyprint.HTML(
                string=html,
                base_url=request.build_absolute_uri('/')
            ).write_pdf(optimize_images=True)
        finally:
            ssl._create_default_https_context = original_ssl_context
        
        # Create response (safe filename for Gmail/email users)
        filename = class10_assessment_pdf_filename(target_user, 'test2')
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        # Persist a copy to media storage (S3 when enabled) - best-effort.
        save_user_pdf(target_user.id, filename, pdf_file)
        return response

    except Exception as e:
        logger.exception("test2_report_pdf failed: %s", e)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


@login_required(login_url=reverse_lazy('users:login'))
def test3_report_pdf(request, user_id=None, _sync_generate=False):
    """
    PDF download view for Test 3 (Aptitude Assessment)
    """
    try:
        import weasyprint
        from django.template.loader import get_template
        from datetime import datetime
        
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists
        ensure_user_pdf_folder(target_user.id)

        early = _try_serve_or_enqueue_web_report_pdf(
            request, target_user, 'test3', _sync_generate=_sync_generate
        )
        if early is not None:
            return early
        
        # Check if test3 is completed
        try:
            test3_result = Results.objects.get(user=target_user, test_paper='test3')
        except Results.DoesNotExist:
            return HttpResponse('Please complete the Aptitude Assessment test first.', status=404)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get intelligence data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            logger.exception(f"Error in db_results_inst_user: {e}")
            below = []
            avg = []
            above_avg = []
        
        # Process intelligence test data
        intelligence_data = {}
        if test3_result and test3_result.scores:
            scores = {label.split("_")[0].upper(): value for label, value in test3_result.scores.items()}
            intelligence_data = {
                'scores': scores,
                'below_avg': below,
                'average': avg,
                'above_avg': above_avg
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_intelligence_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                logger.warning("Error generating graph: %s", e)
                pass
        
        # Get created_date and student_name
        created_date = test3_result.created if hasattr(test3_result, 'created') else target_user.created
        student_name = target_user.name if target_user.name else target_user.email
        
        from app.report_visibility import student_all_growth_areas
        from app.vocational_recommendations import vocational_guidance_context_for_below_areas

        context = {
            'user': target_user,
            'user_profile': user_profile,
            'intelligence_data': intelligence_data,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'student_name': student_name,
            'created_date': created_date,
            'now': datetime.now(),
            'stream_recommendation': recommend_streams_from_tiers(above_avg, avg, below_avg=below),
            'student_below_average': student_all_growth_areas(below, avg, above_avg),
            'show_student_info_on_cover': True,
        }
        context.update(vocational_guidance_context_for_below_areas(below, user=target_user))

        from app.aptitude_report_utils import aptitude_report_context_fields
        context.update(
            aptitude_report_context_fields(
                test3_result.scores if test3_result and test3_result.scores else None
            )
        )
        
        # Render HTML template
        template = get_template('template20/app/test3_report_pdf.html')
        html = template.render(context)
        
        # Debug: return raw HTML (?debug=true)
        if request.GET.get('debug') == 'true':
            r = HttpResponse(html, content_type='text/html; charset=utf-8')
            r['Content-Disposition'] = 'inline; filename=test3-intelligence-report-debug.html'
            r['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            return r
        
        # Generate PDF with optimizations
        # Keep HTTP base_url for proper static/media resolution
        # The main optimization is graph generation check (skip if exists)
        # and image optimization for smaller file size
        import ssl
        original_ssl_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            pdf_file = weasyprint.HTML(
                string=html,
                base_url=request.build_absolute_uri('/')
            ).write_pdf(optimize_images=True)
        finally:
            ssl._create_default_https_context = original_ssl_context
        
        # Create response (safe filename for Gmail/email users)
        filename = class10_assessment_pdf_filename(target_user, 'test3')
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        # Persist a copy to media storage (S3 when enabled) - best-effort.
        save_user_pdf(target_user.id, filename, pdf_file)
        return response

    except Exception as e:
        logger.exception("test3_report_pdf failed: %s", e)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


import json
import openpyxl
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from users.models import UserProfile
from app.models import Results, TestCompletion
from openpyxl.styles import Alignment
from openpyxl import Workbook
from .models import Results
from django.http import HttpResponse

def export_to_excel(request, email):
    # Fetch the desired number of users' data
    # results = Results.objects.all()[:num_users]

    # institute = Institute.objects.get(slug='terii-public-school-kurukshetra')
    # # institute = Institute.objects.get(slug='sggs-c-p-school')
    # stu_manage = StudentManagement.objects.filter(institute=institute)[:10]

    # user = get_object_or_404(User, email=email)

    # Create a workbook and add a worksheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "User Results"

    # Add headers for the columns (Including test1_scores)
    headers = [
        'User',
        'Test1_Scores', 'Test1_Results', 'Test1_Selected_Answers',
        'Test2_Scores', 'Test2_Results', 'Test2_Selected_Answers',
        'Test3_Scores', 'Test3_Results', 'Test3_Selected_Answers'
    ]
    ws.append(headers)

    # Dictionary to hold users' data
    users = {}

    # all_results = Results.objects.filter(user__in=[stu.student for stu in stu_manage])
    all_results = Results.objects.filter(user__email=email)
    # Populate users dictionary with test data
    for result in all_results:
        user = result.user.email

        # Initialize data structure for a new user
        if user not in users:
            users[user] = {
                'test1_scores': '',
                'test1_results': '',
                'test1_selected_answers': '',
                'test2_scores': '',
                'test2_results': '',
                'test2_selected_answers': '',
                'test3_scores': '',
                'test3_results': '',
                'test3_selected_answers': ''
            }

        # Update data based on the test paper

        if result.test_paper == 'test1':
            users[user]['test1_scores'] = json.dumps(result.scores)  # Convert dict to string
            users[user]['test1_results'] = json.dumps(result.results)
            users[user]['test1_selected_answers'] = json.dumps(result.selected_answers)
        elif result.test_paper == 'test2':
            users[user]['test2_scores'] = json.dumps(result.scores)            
            users[user]['test2_results'] = json.dumps(result.results)
            users[user]['test2_selected_answers'] = json.dumps(result.selected_answers)
        elif result.test_paper == 'test3':
            users[user]['test3_scores'] = json.dumps(result.scores)
            users[user]['test3_results'] = json.dumps(result.results)
            users[user]['test3_selected_answers'] = json.dumps(result.selected_answers)

    # Add rows to the Excel sheet
    for user, data in users.items():
        row = [user]

        # Add Test 1 data
        row += [
            data['test1_scores'],
            data['test1_results'],
            data['test1_selected_answers']
        ]

        # Add Test 2 data
        row += [
            data['test2_scores'],
            data['test2_results'],
            data['test2_selected_answers']
        ]

        # Add Test 3 data
        row += [
            data['test3_scores'],
            data['test3_results'],
            data['test3_selected_answers']
        ]

        ws.append(row)

    # Save the workbook to the response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=student_results.xlsx'
    wb.save(response)
    return response
from django.contrib.staticfiles import finders
from weasyprint import HTML
def pdf_checker(request):
    # Your HTML content
    template = get_template('test1.html')
    html = template.render()
    
    # path = finders.find('images/pcm-icon.png')
    path = finders.find('graph_images/Manishwar Singh-138_personality_Assessment.png')
    

    # Configure SSL to disable verification for WeasyPrint image loading
    import ssl
    
    # Disable SSL verification for urllib (used by WeasyPrint internally)
    original_ssl_context = ssl._create_default_https_context
    ssl._create_default_https_context = ssl._create_unverified_context
    
    try:
        # Use HTTPS with SSL verification disabled
        pdf_file = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
    finally:
        # Restore original SSL context
        ssl._create_default_https_context = original_ssl_context
    
    # Create HTTP response
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="your_filename.pdf"'  # Use 'inline' to open in browser
    
    return response


@login_required(login_url=reverse_lazy('users:login'))
def test_pdf_preview(request, test_number=1, user_id=None):
    """
    Preview PDF templates in browser for testing header and layout
    Note: @page CSS rules won't render in browser, but header structure will be visible
    """
    from django.template.loader import get_template
    from datetime import datetime
    
    # Get the target user
    if user_id:
        target_user = get_object_or_404(User, id=user_id)
    else:
        target_user = request.user
    
    # Select template based on test number
    template_map = {
        1: 'template20/app/test1_report_pdf.html',
        2: 'template20/app/test2_report_pdf.html',
        3: 'template20/app/test3_report_pdf.html',
    }
    
    template_name = template_map.get(test_number, template_map[1])
    
    # Get test result if exists
    try:
        test_result = Results.objects.get(user=target_user, test_paper=f'test{test_number}')
    except Results.DoesNotExist:
        test_result = None
    
    # Get user profile
    try:
        user_profile = target_user.user_profile
    except UserProfile.DoesNotExist:
        user_profile = None
    
    # Create minimal context for preview
    context = {
        'user': target_user,
        'user_profile': user_profile,
        'user_name': target_user.name if target_user.name else target_user.email,
        'user_ID': target_user.id,
        'student_name': target_user.name if target_user.name else target_user.email,
        'created_date': datetime.now(),
        'now': datetime.now(),
    }
    
    # Add test-specific context
    if test_number == 1:
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
            context.update({
                'personality_data': {'results': {}, 'top_categories': top_categories, 'top_category': top_category},
                'top_category': top_category,
                'streamsubject': streamsubject,
                'courseName': courseName,
                'top_categories': top_categories,
            })
        except:
            context.update({
                'personality_data': {'results': {}, 'top_categories': [], 'top_category': None},
                'top_category': None,
                'streamsubject': set(),
                'courseName': set(),
                'top_categories': [],
            })
    elif test_number == 2:
        context.update({
            'interest_data': {},
            'max_length': None,
            'min_length': None,
        })
    elif test_number == 3:
        context.update({
            'intelligence_data': {},
        })
    
    # Render template
    template = get_template(template_name)
    html = template.render(context)
    
    # Return HTML response (for browser preview)
    return HttpResponse(html, content_type='text/html')

