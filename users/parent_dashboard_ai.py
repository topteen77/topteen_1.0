from __future__ import annotations

from typing import Dict, List, Any


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, float(value)))


def normalize_scores(raw_scores: Dict[str, float], max_score: float = 100.0) -> Dict[str, float]:
    if max_score <= 0:
        max_score = 100.0
    return {k: round(_clamp((float(v) / max_score) * 100.0), 2) for k, v in raw_scores.items()}


def compare_with_benchmarks(normalized_scores: Dict[str, float], benchmarks: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    comparison: Dict[str, Dict[str, float]] = {}
    for key, score in normalized_scores.items():
        benchmark = float(benchmarks.get(key, 60.0))
        comparison[key] = {
            "score": round(score, 2),
            "benchmark": round(benchmark, 2),
            "delta": round(score - benchmark, 2),
        }
    return comparison


def process_psychometric_data(payload: Dict[str, Dict[str, float]], benchmarks: Dict[str, float] | None = None) -> Dict[str, Any]:
    """
    Returns normalized and benchmark-compared psychometric result JSON.
    payload keys expected: personality, aptitude, interest.
    """
    benchmarks = benchmarks or {}
    personality = normalize_scores(payload.get("personality", {}))
    aptitude = normalize_scores(payload.get("aptitude", {}))
    interest = normalize_scores(payload.get("interest", {}))

    merged = {}
    merged.update(personality)
    merged.update(aptitude)
    merged.update(interest)

    radar_labels = list(merged.keys())
    radar_values = [merged[x] for x in radar_labels]

    return {
        "normalized": {
            "personality": personality,
            "aptitude": aptitude,
            "interest": interest,
        },
        "benchmark_comparison": compare_with_benchmarks(merged, benchmarks),
        "radar": {
            "labels": radar_labels,
            "values": radar_values,
        },
    }


def generate_ai_insights(psychometric_data: Dict[str, Any], academic_data: Dict[str, Any]) -> Dict[str, Any]:
    all_scores = psychometric_data.get("benchmark_comparison", {})
    strengths = [k.replace("_", " ").title() for k, v in all_scores.items() if v.get("score", 0) >= 70]
    weaknesses = [k.replace("_", " ").title() for k, v in all_scores.items() if v.get("score", 0) < 45]

    math_score = float(academic_data.get("math", 0))
    science_score = float(academic_data.get("science", 0))
    english_score = float(academic_data.get("english", 0))

    career_paths: List[str] = []
    if math_score >= 70 and science_score >= 70:
        career_paths.extend(["Engineering", "Data Science"])
    if english_score >= 70:
        career_paths.extend(["Law", "Media & Communication"])
    if "Creativity" in strengths or "Openness" in strengths:
        career_paths.append("Design")
    if not career_paths:
        career_paths = ["Business Management", "Digital Marketing"]

    recommendations = []
    if math_score < 60:
        recommendations.append("Practice Math fundamentals weekly")
    if english_score < 60:
        recommendations.append("Improve communication through reading and debate club")
    if not weaknesses:
        recommendations.append("Continue with advanced career exploration modules")
    else:
        recommendations.append("Work on low-score psychometric domains using guided tasks")

    return {
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "career_paths": list(dict.fromkeys(career_paths))[:5],
        "recommendations": recommendations[:5],
    }


def build_study_abroad_options(career_paths: List[str], readiness_score: float) -> List[Dict[str, Any]]:
    base = [
        {"country": "USA", "avg_cost_usd": 45000},
        {"country": "UK", "avg_cost_usd": 38000},
        {"country": "Canada", "avg_cost_usd": 32000},
        {"country": "Australia", "avg_cost_usd": 36000},
    ]
    courses = {
        "Engineering": ["Computer Science", "Mechanical Engineering"],
        "Data Science": ["Data Analytics", "AI & ML"],
        "Design": ["UX Design", "Visual Communication"],
        "Law": ["International Law", "Public Policy"],
        "Business Management": ["BBA", "Finance"],
        "Digital Marketing": ["Marketing Analytics", "E-Commerce"],
    }
    default_courses = ["Computer Science", "Business Analytics"]
    selected = []
    for item in base:
        recommended = []
        for cp in career_paths:
            recommended.extend(courses.get(cp, []))
        if not recommended:
            recommended = default_courses
        selected.append(
            {
                "country": item["country"],
                "recommended_courses": list(dict.fromkeys(recommended))[:3],
                "estimated_cost_usd": item["avg_cost_usd"],
                "readiness_label": "High" if readiness_score >= 75 else ("Medium" if readiness_score >= 55 else "Developing"),
            }
        )
    return selected


def calculate_loan_metrics(principal: float, annual_rate_percent: float, tenure_years: float) -> Dict[str, float]:
    principal = float(principal)
    annual_rate_percent = float(annual_rate_percent)
    tenure_years = float(tenure_years)
    if principal <= 0 or annual_rate_percent <= 0 or tenure_years <= 0:
        raise ValueError("All values must be greater than zero.")

    monthly_rate = annual_rate_percent / (12 * 100)
    months = int(round(tenure_years * 12))
    emi = principal * monthly_rate * ((1 + monthly_rate) ** months) / (((1 + monthly_rate) ** months) - 1)
    total_payable = emi * months
    total_interest = total_payable - principal
    return {
        "emi": round(emi, 2),
        "total_interest": round(total_interest, 2),
        "total_payable": round(total_payable, 2),
        "months": months,
    }
