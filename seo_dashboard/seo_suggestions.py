"""
Generate professional, marketing-driven SEO suggestions (title, description, keywords)
and page improvement tips for Google ranking. Used by the Edit SEO page.
"""
import re


# Page-type patterns and default labels for fallback
PAGE_TEMPLATES = {
    "terms": {
        "title": "Terms and Conditions | TopTeen Career Guidance",
        "description": "Read TopTeen's terms and conditions. Trusted career guidance and college counselling for students in India. Clear policies for using our services.",
        "keywords": "terms and conditions, TopTeen, career guidance terms, student counselling policy, India",
        "improvements": [
            "Keep the first paragraph under 2–3 lines for snippet clarity.",
            "Use bullet points for key obligations to improve scannability.",
            "Add a last-updated date near the top for trust and freshness.",
        ],
    },
    "privacy": {
        "title": "Privacy Policy | How TopTeen Uses Your Data",
        "description": "TopTeen's privacy policy: how we collect, use and protect your data. Compliant career and college counselling for students and parents in India.",
        "keywords": "privacy policy, TopTeen, data protection, student data, career counselling privacy, India",
        "improvements": [
            "Include a short summary (2–3 sentences) at the top for quick scanning.",
            "Mention GDPR/Indian data laws if applicable to build trust.",
            "Link to contact or support for privacy questions.",
        ],
    },
    "about": {
        "title": "About TopTeen | Career Guidance for Students in India",
        "description": "TopTeen helps Indian students choose the right stream, career and college. Expert career counselling, psychometric assessments and college guidance for classes 9–12.",
        "keywords": "about TopTeen, career guidance India, student counselling, stream selection, college guidance, class 9 10 11 12",
        "improvements": [
            "Lead with one clear value proposition in the first 50 words.",
            "Add stats (e.g. students helped, partners) if available for E-E-A-T.",
            "Include a clear call-to-action (e.g. Explore careers, Take assessment).",
        ],
    },
    "contact": {
        "title": "Contact TopTeen | Career & College Counselling Support",
        "description": "Contact TopTeen for career guidance and college counselling. Get in touch for students and parents. We're here to help you plan the right career path.",
        "keywords": "contact TopTeen, career counselling contact, student support, college guidance help, India",
        "improvements": [
            "Add expected response time (e.g. within 24 hours) to set expectations.",
            "Offer at least two contact methods (form + email or phone).",
            "Briefly state what you help with (career, stream, college) above the form.",
        ],
    },
    "career_planning": {
        "title": "Career Planning for Students | Stream & College Guidance",
        "description": "Step-by-step career planning for Indian students. Choose the right stream after 10th, explore careers and colleges. Free resources and expert guidance from TopTeen.",
        "keywords": "career planning, stream selection, career guidance for students, after 10th, college planning, India",
        "improvements": [
            "Use one H1 that includes the main keyword (e.g. Career Planning for Students).",
            "Break content into steps or sections with H2s for featured snippets.",
            "Add internal links to career lists, assessments and college pages.",
        ],
    },
    "career_planning_4_year": {
        "title": "4-Year Career Plan | Class 9 to 12 Roadmap | TopTeen",
        "description": "Build your 4-year career plan from class 9 to 12. Year-wise goals, stream selection and college prep. Free career planning guide for Indian students.",
        "keywords": "4 year career plan, class 9 to 12, stream selection, career roadmap, student planning, India",
        "improvements": [
            "Use a year-wise or class-wise structure (H2 per year) for clarity.",
            "Add a downloadable or printable summary for parents and students.",
            "Link to psychometric tests and career explore pages.",
        ],
    },
    "career_planning_class_9": {
        "title": "Career Planning Class 9 | Start Early with TopTeen",
        "description": "Career planning tips for class 9 students in India. Explore interests, subjects and streams. Start your career journey with TopTeen's free guidance.",
        "keywords": "career planning class 9, stream selection class 9, career guidance for class 9, India",
        "improvements": [
            "Address both students and parents in the first paragraph.",
            "Include 3–5 actionable tips (e.g. explore subjects, try assessments).",
            "Link to career exploration and stream comparison tools.",
        ],
    },
    "career_planning_class_10": {
        "title": "Career Planning After Class 10 | Stream Selection Guide",
        "description": "Choosing stream after class 10? TopTeen's career planning guide helps you pick Science, Commerce or Arts with confidence. Expert tips for students and parents.",
        "keywords": "career after class 10, stream selection after 10th, science commerce arts, career guidance class 10, India",
        "improvements": [
            "Compare streams (Science, Commerce, Arts) in a simple table or list.",
            "Mention common careers per stream to support decision-making.",
            "Add CTA to psychometric test or career explorer.",
        ],
    },
    "career_planning_class_11": {
        "title": "Career Planning Class 11 | Subject & College Prep",
        "description": "Class 11 career planning: choose subjects, explore careers and start college prep. TopTeen's guide for Indian students in class 11.",
        "keywords": "career planning class 11, subject selection class 11, college preparation, stream class 11, India",
        "improvements": [
            "Focus on subject-choice impact on future courses and careers.",
            "Add a timeline (e.g. when to start entrance prep, when to shortlist colleges).",
            "Link to college search and career profiles.",
        ],
    },
    "career_planning_class_12": {
        "title": "Career Planning Class 12 | College & Course Selection",
        "description": "Class 12 career guide: college applications, course selection and entrance exams. TopTeen helps you plan the next step after class 12 in India.",
        "keywords": "career planning class 12, college selection, course after 12th, entrance exams, India",
        "improvements": [
            "List key entrance exams and deadlines in a clear format.",
            "Include 2–3 next steps (e.g. shortlist colleges, apply, prepare for exams).",
            "Link to college listings and course pages.",
        ],
    },
    "emotional_intelligences": {
        "title": "Emotional Intelligence Test for Students | Free EQ Assessment",
        "description": "Take a free emotional intelligence (EQ) test for students. Understand your strengths and improve soft skills. Part of TopTeen's career guidance toolkit.",
        "keywords": "emotional intelligence test, EQ test for students, soft skills assessment, career readiness, India",
        "improvements": [
            "Explain what EQ is and why it matters for careers in the first 100 words.",
            "Add a clear 'Start test' or CTA above the fold.",
            "Link to career planning and stream selection pages.",
        ],
    },
    "multiple_intelligences": {
        "title": "Multiple Intelligence Test | Find Your Strengths | TopTeen",
        "description": "Free multiple intelligence test for students. Discover your learning style and strengths. Use results for stream and career choices. Trusted by TopTeen.",
        "keywords": "multiple intelligence test, MI test students, learning style, career choice, stream selection, India",
        "improvements": [
            "Briefly list the types of intelligence (e.g. logical, verbal) for SEO.",
            "State how long the test takes and what the result includes.",
            "Link to career explorer and psychometric assessments.",
        ],
    },
    "four_pillars": {
        "title": "Four Pillars of Learning | TopTeen Career Framework",
        "description": "Explore the four pillars of learning that shape career success. TopTeen's framework for students and parents. Build a strong foundation for stream and career choice.",
        "keywords": "four pillars of learning, career framework, student development, TopTeen, India",
        "improvements": [
            "Use one H1 and four H2s (one per pillar) for clear structure.",
            "Add one paragraph per pillar with a practical tip.",
            "Link to assessments and career planning pages.",
        ],
    },
    "all-faq": {
        "title": "Career & College FAQs | TopTeen Answers",
        "description": "Frequently asked questions on career guidance, stream selection and college admissions in India. Expert answers from TopTeen for students and parents.",
        "keywords": "career FAQ, college admission FAQ, stream selection questions, TopTeen, India",
        "improvements": [
            "Use FAQ schema (JSON-LD) for rich results in Google.",
            "Keep each answer 2–4 sentences where possible.",
            "Add internal links to relevant career or college pages.",
        ],
    },
    "ebooks": {
        "title": "Free Career E-Books for Students | TopTeen",
        "description": "Download free career and college guidance e-books for Indian students. Expert tips on stream selection, careers and planning. From TopTeen.",
        "keywords": "career e-books, free e-books students, college guidance PDF, stream selection guide, India",
        "improvements": [
            "List e-books with clear titles and one-line descriptions.",
            "Add a visible download or read CTA for each book.",
            "Link to career planning and assessments.",
        ],
    },
    "searchand-explore": {
        "title": "Search Careers & Colleges | Explore Options | TopTeen",
        "description": "Search and explore careers and colleges in India. Filter by stream, interest and course. TopTeen helps you find the right career and college fit.",
        "keywords": "search careers, search colleges, explore careers India, college search, stream wise careers",
        "improvements": [
            "Use a clear H1 like 'Search Careers and Colleges'.",
            "Ensure filters are visible and work on mobile.",
            "Add trending or popular searches to reduce bounce.",
        ],
    },
    "blogs": {
        "title": "Career & College Blog | Tips for Students | TopTeen",
        "description": "TopTeen's blog: career tips, stream selection advice and college guidance for Indian students. Expert articles for class 9–12 and parents.",
        "keywords": "career blog, student blog, college guidance blog, stream selection tips, TopTeen, India",
        "improvements": [
            "Use one H1 per post that includes the main topic.",
            "Keep intro under 100 words and add a clear takeaway.",
            "Add 2–3 internal links to careers, colleges or assessments.",
        ],
    },
    "careers": {
        "title": "Explore Careers | Stream-wise Career List | TopTeen",
        "description": "Explore careers by stream and interest. Science, Commerce, Arts career options for Indian students. Detailed career profiles and guidance from TopTeen.",
        "keywords": "career list, careers by stream, science commerce arts careers, career options India, TopTeen",
        "improvements": [
            "Use H1 like 'Explore Careers' or 'Careers by Stream'.",
            "Add filters (stream, interest) and show result count.",
            "Link to career planning and psychometric tests.",
        ],
    },
    "colleges": {
        "title": "Colleges in India | Search & Compare | TopTeen",
        "description": "Search and compare colleges in India. Find courses, fees and admission info. TopTeen helps students and parents shortlist the right college.",
        "keywords": "colleges in India, college search, compare colleges, admission, courses, TopTeen",
        "improvements": [
            "Use a clear H1 (e.g. Search Colleges in India).",
            "Show key filters (course, location, stream) above results.",
            "Add internal links to career and course guidance.",
        ],
    },
    "skilllabcourse": {
        "title": "Skill Development Courses for Students | TopTeen",
        "description": "Skill development and learning courses for Indian students. Build skills for career success. Explore courses on TopTeen.",
        "keywords": "skill courses, student courses, skill development, career skills, TopTeen, India",
        "improvements": [
            "Use one H1 and separate H2s per course category.",
            "Add duration and level (e.g. class 9+) where relevant.",
            "Link to career planning and assessments.",
        ],
    },
    "psychometrictest": {
        "title": "Psychometric Tests for Students | Career & Stream Fit | TopTeen",
        "description": "Free psychometric tests for Indian students. Discover career fit, stream recommendation and interests. Trusted assessments from TopTeen.",
        "keywords": "psychometric test, career test students, stream recommendation test, interest test, India",
        "improvements": [
            "State what the test measures and how long it takes.",
            "Add a prominent 'Start test' or 'Take assessment' CTA.",
            "Link to career explorer and stream selection pages.",
        ],
    },
    "testprep": {
        "title": "Entrance Exam Prep & Test Prep | TopTeen",
        "description": "Entrance exam and test preparation resources for Indian students. JEE, NEET, CUET and more. TopTeen supports your exam journey.",
        "keywords": "entrance exam prep, JEE NEET CUET, test preparation, exam guidance, India",
        "improvements": [
            "List major exams with short descriptions and links.",
            "Add a timeline or checklist (e.g. when to start prep).",
            "Link to college search and course pages.",
        ],
    },
    "home": {
        "title": "TopTeen | Career Guidance & College Counselling for Students",
        "description": "TopTeen helps Indian students choose the right stream, career and college. Free career assessments, expert guidance and college search. Start your career journey.",
        "keywords": "career guidance, college counselling, stream selection, career for students, class 9 10 11 12, India, TopTeen",
        "improvements": [
            "Use one main H1 that includes your primary keyword.",
            "Above the fold: one value proposition + one clear CTA.",
            "Link to key pages: careers, colleges, assessments, blog.",
        ],
    },
}

# Fallback for unknown pages (generic, marketing-driven)
DEFAULT_TEMPLATE = {
    "title": "Career & College Guidance | TopTeen for Students",
    "description": "TopTeen offers career guidance and college counselling for Indian students. Explore careers, streams and colleges. Trusted by students and parents.",
    "keywords": "career guidance, college counselling, students India, stream selection, TopTeen",
    "improvements": [
        "Use a single, clear H1 that matches the page topic.",
        "Keep meta description between 150–160 characters for best display in search.",
        "Add 2–3 internal links to related careers, colleges or assessments.",
        "Include a clear call-to-action (e.g. Explore, Take test, Contact).",
    ],
}


def _truncate(s, max_len):
    if not s:
        return ""
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rsplit(" ", 1)[0] + "…" if " " in s[: max_len - 3] else s[: max_len - 3] + "…"


def _detect_page_type(url_key):
    """Return a page type key used for PAGE_TEMPLATES."""
    if not url_key:
        return "home"
    key = (url_key or "").strip().lower()
    if key in PAGE_TEMPLATES:
        return key
    if key.startswith("blogs/"):
        return "blogs"
    if key.startswith("careers/"):
        return "careers"
    if key.startswith("colleges/"):
        return "colleges"
    if key.startswith("skilllabcourse/"):
        return "skilllabcourse"
    if key.startswith("psychometrictest/"):
        return "psychometrictest"
    if key.startswith("testprep/"):
        return "testprep"
    if key == "searchand-explore" or key == "searchand-explore/":
        return "searchand-explore"
    if key == "all-faq" or "faq" in key:
        return "all-faq"
    if key == "ebooks" or key.startswith("ebooks/"):
        return "ebooks"
    # Static keys with underscores
    for static in ("terms", "privacy", "about", "contact", "career_planning", "career_planning_4_year",
                   "career_planning_class_9", "career_planning_class_10", "career_planning_class_11", "career_planning_class_12",
                   "emotional_intelligences", "multiple_intelligences", "four_pillars"):
        if key == static or key.replace("-", "_") == static:
            return static
    return None


def get_seo_suggestions(url_key, current_title="", current_description="", page_label=None):
    """
    Return suggested title, description, keywords and improvements for a page.
    Optimized for Google (title ≤70 chars, description 150–160 chars) and marketing-driven.
    """
    page_type = _detect_page_type(url_key)
    template = PAGE_TEMPLATES.get(page_type or "", DEFAULT_TEMPLATE.copy())
    if not template:
        template = DEFAULT_TEMPLATE.copy()

    title = (template.get("title") or DEFAULT_TEMPLATE["title"]).strip()
    description = (template.get("description") or DEFAULT_TEMPLATE["description"]).strip()
    keywords = (template.get("keywords") or DEFAULT_TEMPLATE["keywords"]).strip()
    improvements = list(template.get("improvements") or DEFAULT_TEMPLATE["improvements"])

    # If we have a blog slug, optionally use page_label as topic in title/description
    if page_type == "blogs" and page_label:
        clean_label = _truncate(re.sub(r"<[^>]+>", "", str(page_label)), 40)
        if clean_label:
            title = "{} | Career Blog | TopTeen".format(_truncate(clean_label, 50))
            description = "{} – Expert career and college tips for Indian students. TopTeen blog.".format(_truncate(clean_label, 120))

    # If we have a career slug (e.g. careers/software-engineer), use page_label
    if page_type == "careers" and page_label:
        clean_label = _truncate(re.sub(r"<[^>]+>", "", str(page_label)), 40)
        if clean_label:
            title = "{} | Career Guide | TopTeen".format(_truncate(clean_label, 50))
            description = "{} – Career scope, courses and skills. Career guidance for Indian students from TopTeen.".format(_truncate(clean_label, 110))

    # Enforce length for Google
    title = _truncate(title, 70)
    description = _truncate(description, 160)
    if len(description) < 120 and not current_description:
        description = description.strip()
    elif current_description and len(current_description) >= 120:
        description = _truncate(current_description, 160)

    return {
        "title": title,
        "description": description,
        "keywords": keywords,
        "improvements": improvements,
    }
