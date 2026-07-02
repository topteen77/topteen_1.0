"""Build template context for Class 10 psychometric dashboard."""
from __future__ import annotations

from typing import Any, Dict


def build_psychometric_dashboard_context(request, target_user, *, embed_mode: bool = False) -> Dict[str, Any]:
    from app.models import Results, TestCompletion
    from app.riasec_report_utils import get_stream_career_sections
    from users.models import UserProfile

    original_user = request.user
    request.user = target_user
    try:
        from app.views import (
            UserHasNotAttemptedTestException,
            _build_stream_questionnaire_options,
            db_results,
        )
        from app.aptitude_stream_selection import (
            premium_career_groups_from_recommendation,
            recommend_streams_from_tiers,
            streamsubject_from_recommendation,
            suitable_combinations_from_recommendation,
        )

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
        context['parent_inline_mode'] = False
        return context
    finally:
        request.user = original_user
