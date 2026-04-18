"""
AI-assisted resume PDF shell generation (admin + student studio).
Uses OPENAI_API_KEY; returns scoped CSS stored on ResumePdfTemplate.ai_dynamic_css.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional, Tuple

_CSS_BAD = re.compile(
    r"(</\s*style|</\s*script|<\s*script|@import\b|expression\s*\(|javascript\s*:|\bbehavior\s*:)",
    re.I,
)


def sanitize_ai_css(css: str, max_len: int = 12000) -> str:
    if not css or not isinstance(css, str):
        return ""
    t = css.strip()
    if len(t) > max_len:
        t = t[:max_len]
    if _CSS_BAD.search(t):
        t = _CSS_BAD.sub("/*blocked*/", t)
    return t


def _dominant_hex_from_image(path: str) -> Optional[str]:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(path).convert("RGB")
        im = im.resize((48, 48))
        px = list(im.getdata())
        if not px:
            return None
        r = sum(p[0] for p in px) // len(px)
        g = sum(p[1] for p in px) // len(px)
        b = sum(p[2] for p in px) // len(px)
        return "#{:02x}{:02x}{:02x}".format(r, g, b)
    except Exception:
        return None


def _parse_ai_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```\s*$", "", raw)
    return json.loads(raw)


def generate_resume_shell_with_ai(
    requirements: str,
    colour_scheme: str = "",
    inspiration_image_path: Optional[str] = None,
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Call OpenAI; return dict with keys: accent_hex, suggested_name, category, css
    or (None, error_message).
    """
    from django.conf import settings

    req = (requirements or "").strip()
    if len(req) < 8:
        return None, "Please enter at least a short design brief (8+ characters)."

    api_key = (getattr(settings, "OPENAI_API_KEY", None) or "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY is not configured on the server."

    model = (getattr(settings, "OPENAI_MODEL", None) or getattr(settings, "AI_MODEL", None) or "gpt-4o-mini").strip()

    extra = ""
    if colour_scheme.strip():
        extra += "\nColour / palette notes from user: " + colour_scheme.strip() + "\n"
    if inspiration_image_path:
        hx = _dominant_hex_from_image(inspiration_image_path)
        if hx:
            extra += f"\nApproximate dominant colour sampled from uploaded image: {hx}\n"

    system = (
        "You are a senior print/PDF designer. You output ONLY valid JSON, no markdown, no explanation.\n"
        "The JSON object must have exactly these string keys:\n"
        '  "accent_hex" — a single #RRGGBB colour for the brand accent.\n'
        '  "suggested_name" — short catalogue name (max 80 chars).\n'
        '  "category" — one of: professional, modern, creative, simple, executive.\n'
        '  "css" — CSS rules ONLY. Every selector MUST start with .gen-wrap or .ai-shell (e.g. .gen-wrap h1, .ai-shell .gen-wrap p).\n'
        "Style headings, paragraphs, lists, links, tables for résumé content. Use var(--accent) where appropriate.\n"
        "Do NOT use @import, url(), expression(), behavior, javascript:, or any HTML.\n"
        "Keep css under 9000 characters."
    )
    user_msg = "Design brief:\n" + req[:8000] + extra

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.35,
            max_tokens=4096,
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        return None, str(exc)[:800]

    if not raw:
        return None, "Empty response from AI."

    try:
        data = _parse_ai_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return None, f"Could not parse AI JSON: {exc}"

    accent = str(data.get("accent_hex") or "").strip()
    if not re.match(r"^#[0-9A-Fa-f]{6}$", accent):
        accent = "#19718c"
    name = str(data.get("suggested_name") or "AI custom shell").strip()[:120]
    cat = str(data.get("category") or "professional").strip().lower()
    if cat not in ("professional", "modern", "creative", "simple", "executive"):
        cat = "professional"
    css = sanitize_ai_css(str(data.get("css") or ""))
    if not css:
        return None, "AI returned no usable CSS."

    return {
        "accent_hex": accent,
        "suggested_name": name,
        "category": cat,
        "css": css,
    }, None


def unique_library_slug(prefix: str = "ai") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


RESUME_LIBRARY_CLASSIC = "mail/user/userresumepdf_library.html"
RESUME_LIBRARY_GENERATED = "mail/user/userresumepdf_library_generated.html"


def write_upload_to_tempfile(uploaded_file) -> tuple[Optional[str], str]:
    """
    Write an UploadedFile to a temp path for palette sampling.
    Returns (path or None, suffix including dot for binary fallback).
    """
    import os
    import tempfile

    if not uploaded_file:
        return None, ".bin"
    suffix = ".bin"
    name = (getattr(uploaded_file, "name", "") or "").lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        if name.endswith(ext):
            suffix = ext
            break
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        for chunk in uploaded_file.chunks():
            os.write(fd, chunk)
    finally:
        os.close(fd)
    return tmp_path, suffix


def create_resumepdf_template_from_ai_payload(
    data: dict[str, Any],
    requirements_snapshot: str,
    *,
    created_by,
    is_active: bool,
    sort_order: int,
    description: str,
    slug_prefix: str,
    inspiration_upload=None,
):
    """Persist ResumePdfTemplate from generate_resume_shell_with_ai() output dict."""
    from users.models import ResumePdfTemplate

    slug = unique_library_slug(slug_prefix)
    tpl = ResumePdfTemplate.objects.create(
        name=(data.get("suggested_name") or "AI template")[:120],
        description=description[:500] if description else "",
        classic_template_path=RESUME_LIBRARY_CLASSIC,
        generated_template_path=RESUME_LIBRARY_GENERATED,
        ai_dynamic_css=data["css"],
        ai_requirements_snapshot=(requirements_snapshot or "")[:4000],
        accent_hex=data["accent_hex"],
        category=(data.get("category") or "professional")[:32],
        layout_variant="v01",
        library_slug=slug,
        is_active=is_active,
        sort_order=sort_order,
        created_by=created_by,
    )
    if inspiration_upload:
        try:
            inspiration_upload.seek(0)
            tpl.inspiration_image.save(inspiration_upload.name, inspiration_upload, save=True)
        except Exception:
            pass
    return tpl


def generate_and_create_resumepdf_template_from_post(
    request,
    *,
    created_by,
    is_active: bool,
    sort_order: int,
    description: str,
    slug_prefix: str,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Read requirements / colour_scheme / inspiration_image from POST, call OpenAI, create row.
    Returns (ResumePdfTemplate instance or None, error string or None).
    """
    import os

    requirements = (request.POST.get("requirements") or "").strip()
    colours = (request.POST.get("colour_scheme") or "").strip()
    uploaded = request.FILES.get("inspiration_image")
    tmp_path = None
    try:
        if uploaded:
            tmp_path, _ = write_upload_to_tempfile(uploaded)
        data, err = generate_resume_shell_with_ai(requirements, colours, tmp_path)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if err:
        return None, err
    if uploaded:
        try:
            uploaded.seek(0)
        except Exception:
            pass
    tpl = create_resumepdf_template_from_ai_payload(
        data,
        requirements,
        created_by=created_by,
        is_active=is_active,
        sort_order=sort_order,
        description=description,
        slug_prefix=slug_prefix,
        inspiration_upload=uploaded,
    )
    return tpl, None
