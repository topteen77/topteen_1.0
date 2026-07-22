"""
AI-powered SEO generator for the SEO dashboard.
Uses OpenAI (or configured AI provider) to generate title, description, and keywords
from current SEO + optional page content. Requires OPENAI_API_KEY in settings.
"""
import re


def get_page_content_for_seo(url_key):
    """
    Return plain-text content for the given url_key (for AI context).
    Static pages: first ~2000 chars of content_html (stripped).
    Blogs: summary + first part of content (~2000 chars).
    Others: empty string.
    """
    from core.utils import clean_html
    text_parts = []
    max_len = 2000

    if not url_key or not isinstance(url_key, str):
        return ""

    # Static page
    from core.models import StaticPage
    sp = StaticPage.objects.filter(url_key=url_key).first()
    if sp and getattr(sp, "content_html", None):
        plain = clean_html(sp.content_html or "")
        if plain:
            text_parts.append(plain[:max_len])
        if sp.title:
            text_parts.insert(0, sp.title)

    # Blog: url_key like "blogs/my-slug"
    if url_key.startswith("blogs/") and len(text_parts) == 0:
        try:
            from blog.models import Blog
            from core import choices
            slug = url_key[6:].strip("/")
            blog = Blog.get_published_objects().filter(slug=slug).first()
            if blog:
                if blog.title:
                    text_parts.append(blog.title)
                if blog.summary:
                    text_parts.append(blog.summary)
                if getattr(blog, "content", None) or getattr(blog, "content_html", None):
                    content = getattr(blog, "content_html", None) or getattr(blog, "content", None) or ""
                    text_parts.append(clean_html(content)[:max_len])
        except Exception:
            pass

    return "\n\n".join(text_parts).strip()[:4000]


def generate_seo_with_ai(
    url_key,
    current_title="",
    current_description="",
    current_keywords="",
    page_content=None,
    user=None,
):
    """
    Call AI to generate SEO title (≤70 chars), description (≤160 chars), keywords.
    page_content: optional plain text for context. If None and url_key given, fetched via get_page_content_for_seo.
    Returns dict: { "title", "description", "keywords" } or { "error": "..." }.
    """
    from django.conf import settings
    api_key = (getattr(settings, "OPENAI_API_KEY", None) or "").strip()
    if not api_key:
        return {"error": "AI is not configured. Set OPENAI_API_KEY in environment."}

    try:
        from core.llm_quota import LLMQuotaExceeded, ensure_can_use_llm

        ensure_can_use_llm(user, feature="seo")
    except LLMQuotaExceeded as exc:
        pay = exc.payload or {}
        return {
            "error": pay.get("message") or "AI token limit reached",
            "quota_exceeded": True,
            "cta_url": pay.get("cta_url"),
            "shop_url": pay.get("shop_url"),
        }

    model = getattr(settings, "OPENAI_MODEL", None) or getattr(settings, "AI_MODEL", "gpt-4o-mini")

    if page_content is None and url_key:
        page_content = get_page_content_for_seo(url_key)
    page_content = (page_content or "").strip()[:4000]

    current_title = (current_title or "").strip()
    current_description = (current_description or "").strip()
    current_keywords = (current_keywords or "").strip()

    safe_title = (current_title or "(none)").replace("---", "")
    safe_desc = (current_description or "(none)").replace("---", "")
    safe_kw = (current_keywords or "(none)").replace("---", "")
    prompt = """You are an SEO expert for "Top Teen", a career guidance and college counselling platform for students in India (classes 9–12).

Generate meta title, meta description, and meta keywords for a web page. Rules:
- Title: max 70 characters, include main keyword and "Top Teen" or the site context where natural.
- Description: max 160 characters, compelling for search snippets, include a call-to-action or value proposition.
- Keywords: comma-separated, 5–12 relevant keywords/phrases (e.g. career guidance, stream selection, India, students).

Current SEO (user may leave these empty):
- Title: {}
- Description: {}
- Keywords: {}
""".format(safe_title, safe_desc, safe_kw)

    if page_content:
        prompt += "\nPage content (for context; use to align SEO with actual content):\n---\n{}\n---\n".format(page_content[:3500])
    else:
        prompt += "\nNo page content was provided; base suggestions on the current SEO and Top Teen's focus (career, stream, college, India, students).\n"

    prompt += """
Reply with exactly three lines, no labels or bullets:
Line 1: The meta title (max 70 chars).
Line 2: The meta description (max 160 chars).
Line 3: Comma-separated keywords.
"""

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=400,
        )
        try:
            from core.llm_billing import log_openai_response
            log_openai_response(
                feature="seo",
                response=response,
                model=model,
                call_type="chat",
                user=user,
                consume=True,
                metadata={"source": "seo_dashboard.generate_seo_with_ai"},
            )
        except Exception:
            pass
        raw = (response.choices[0].message.content or "").strip()
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        title = (lines[0] if len(lines) > 0 else "")[:70]
        description = (lines[1] if len(lines) > 1 else "")[:160]
        keywords = (lines[2] if len(lines) > 2 else "")[:500]
        # Normalize keywords: single line, comma-separated
        keywords = re.sub(r"\s*,\s*", ", ", keywords).strip()
        return {"title": title, "description": description, "keywords": keywords}
    except ImportError:
        return {"error": "OpenAI package not installed. Run: pip install openai"}
    except Exception as e:
        return {"error": str(e)}
