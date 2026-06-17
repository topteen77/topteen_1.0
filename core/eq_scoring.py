"""Emotional Intelligence assessment scoring per ScoringEI Report."""

EQ_LEVELS = [
    {
        "code": "SA",
        "name": "Self-Awareness & Self-Esteem",
        "items": [
            {"id": "Q1", "reverse": False},
            {"id": "Q2", "reverse": False},
            {"id": "Q3", "reverse": False},
            {"id": "Q4", "reverse": False},
            {"id": "Q5", "reverse": False},
            {"id": "Q6", "reverse": True},
        ],
    },
    {
        "code": "SC",
        "name": "Self-Control & Emotional Regulation",
        "items": [
            {"id": "Q7", "reverse": False},
            {"id": "Q8", "reverse": False},
            {"id": "Q9", "reverse": False},
            {"id": "Q10", "reverse": False},
            {"id": "Q11", "reverse": False},
            {"id": "Q12", "reverse": True},
        ],
    },
    {
        "code": "EM",
        "name": "Empathy & Understanding Others",
        "items": [
            {"id": "Q13", "reverse": False},
            {"id": "Q14", "reverse": False},
            {"id": "Q15", "reverse": False},
            {"id": "Q16", "reverse": False},
            {"id": "Q17", "reverse": False},
            {"id": "Q18", "reverse": True},
        ],
    },
    {
        "code": "CR",
        "name": "Conflict Resolution & Interpersonal Skills",
        "items": [
            {"id": "Q19", "reverse": False},
            {"id": "Q20", "reverse": False},
            {"id": "Q21", "reverse": False},
            {"id": "Q22", "reverse": False},
            {"id": "Q23", "reverse": False},
            {"id": "Q24", "reverse": True},
        ],
    },
    {
        "code": "SM",
        "name": "Self-Motivation & Resilience",
        "items": [
            {"id": "Q25", "reverse": False},
            {"id": "Q26", "reverse": False},
            {"id": "Q27", "reverse": False},
            {"id": "Q28", "reverse": False},
            {"id": "Q29", "reverse": False},
            {"id": "Q30", "reverse": True},
        ],
    },
    {
        "code": "AC",
        "name": "Assertiveness & Communication",
        "items": [
            {"id": "Q31", "reverse": False},
            {"id": "Q32", "reverse": False},
            {"id": "Q33", "reverse": False},
            {"id": "Q34", "reverse": False},
            {"id": "Q35", "reverse": False},
            {"id": "Q36", "reverse": True},
        ],
    },
]

SUBSCALE_BANDS = [
    (24, 30, "Highest"),
    (18, 23, "High"),
    (12, 17, "Average"),
    (6, 11, "Growth Area"),
    (1, 5, "Growth Area"),
]

# Per ScoringEI Report (Exceptional capped at 150 in the doc; 151–180 still Exceptional for 36-item test).
TOTAL_BANDS = [
    (120, 180, "Exceptional EI", "Highly skilled in managing emotions, handling relationships, and staying motivated."),
    (90, 119, "Strong EI", "Generally good emotional awareness, but some areas may need refinement."),
    (60, 89, "Moderate EI", "Some strengths, but could benefit from emotional skill development."),
    (30, 59, "Low EI", "Likely struggles with emotional regulation, social interactions, or motivation."),
]

LOW_SUBSCALE_THRESHOLD = 12

IMPROVEMENT_TIPS = {
    "SA": [
        "Practice Self-Reflection – Keep a journal to track emotions and thoughts daily.",
        "Ask for Feedback – Request honest opinions from friends or mentors to understand how you come across.",
        "Mindfulness & Meditation – Spend 5–10 minutes daily observing thoughts without judgment.",
        "Self-Affirmations – Repeat positive affirmations like \"I am capable and worthy.\"",
        "Strength Analysis – List your top 5 strengths and use them daily.",
    ],
    "SC": [
        "Pause Before Reacting – Take deep breaths or count to 10 before responding in emotional situations.",
        "Use Healthy Outlets – Engage in physical exercise, writing, or music to release emotions.",
        "Identify Triggers – Notice patterns in what makes you angry or upset and develop coping strategies.",
        "Practice Reframing – Instead of thinking, \"This is unfair,\" say \"What can I learn from this?\"",
        "Develop a Relaxation Routine – Try yoga, listening to calming music, or progressive muscle relaxation.",
    ],
    "EM": [
        "Active Listening – Focus entirely on the speaker, nod, and paraphrase to show understanding.",
        "Put Yourself in Others' Shoes – Ask, \"How would I feel in their situation?\"",
        "Observe Non-Verbal Cues – Pay attention to body language, tone, and facial expressions.",
        "Read Fiction & Watch Dramas – These improve emotional perspective-taking.",
        "Volunteer or Help Others – Engaging in acts of kindness fosters deeper empathy.",
    ],
    "CR": [
        "Stay Calm During Disputes – Breathe deeply and maintain a neutral tone.",
        "Use \"I\" Statements – Say \"I feel concerned when deadlines are missed,\" instead of blaming.",
        "Find Common Ground – Focus on shared interests rather than differences.",
        "Practice Assertiveness – Clearly express needs while respecting others' opinions.",
        "Seek Mediation if Needed – If conflicts persist, involve a neutral third party.",
    ],
    "SM": [
        "Set Clear, Achievable Goals – Break big goals into smaller tasks for steady progress.",
        "Develop a Growth Mind-set – View failures as learning experiences.",
        "Visualize Success – Imagine achieving your goals and the feeling of accomplishment.",
        "Stay Accountable – Share goals with a friend or mentor for motivation.",
        "Celebrate Small Wins – Acknowledge progress, no matter how minor.",
    ],
    "AC": [
        "Practice Speaking Up – Start with small, everyday situations (e.g., ordering food confidently).",
        "Use Clear & Direct Language – Avoid excessive apologies or hesitations.",
        "Maintain Confident Body Language – Stand tall, make eye contact, and use a firm but respectful tone.",
        "Say \"No\" Without Guilt – Set boundaries and don't over-explain your decisions.",
        "Role-Play Assertive Conversations – Practice with a friend or in front of a mirror.",
    ],
}


def get_subscale_band(score):
    score = int(score)
    for low, high, label in SUBSCALE_BANDS:
        if low <= score <= high:
            return label
    if score >= 30:
        return "Highest"
    return "Growth Area"


def get_total_band(total):
    total = int(round(total))
    for low, high, label, description in TOTAL_BANDS:
        if low <= total <= high:
            return label, description
    if total >= 180:
        return TOTAL_BANDS[0][2], TOTAL_BANDS[0][3]
    return TOTAL_BANDS[-1][2], TOTAL_BANDS[-1][3]


def calculate_subscale_scores(responses):
    scores = {}
    for level in EQ_LEVELS:
        total = 0
        for item in level["items"]:
            raw = int(responses.get(item["id"], 0))
            if raw < 1 or raw > 5:
                continue
            total += (6 - raw) if item["reverse"] else raw
        scores[level["code"]] = total
    return scores


def calculate_eq_result(responses):
    subscale_scores = calculate_subscale_scores(responses)
    ei_total = float(sum(subscale_scores.values()))
    band_label, band_description = get_total_band(ei_total)
    subscale_bands = {code: get_subscale_band(score) for code, score in subscale_scores.items()}
    low_areas = [
        level["code"]
        for level in EQ_LEVELS
        if subscale_scores.get(level["code"], 0) < LOW_SUBSCALE_THRESHOLD
    ]
    return {
        "subscale_scores": subscale_scores,
        "subscale_bands": subscale_bands,
        "ei_total": ei_total,
        "band_label": band_label,
        "band_description": band_description,
        "low_areas": low_areas,
    }
