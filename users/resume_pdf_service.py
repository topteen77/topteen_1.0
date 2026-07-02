"""Server-side resume PDF: studio HTML templates → WeasyPrint (or wkhtmltopdf)."""

from __future__ import annotations

import base64
import logging
import mimetypes
import re

from django.http import HttpResponse
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from users.models import UserProfile
from users.pdf_utils import resume_html_to_pdf_bytes
from users.resume_guided_ai import strip_markdown_fences
from users.resume_payload import (
    ensure_studio_proto_v1_defaults_saved,
    resume_studio_prototype_payload,
    wizard_prefers_generated_pdf,
)
from users.resume_studio_pdf_html import (
    studio_pdf_template_context,
    studio_proto_pack_from_resume,
    studio_render_html_for_resume,
)

logger = logging.getLogger(__name__)

AI_DYNAMIC_GENERATED_SHELL = "mail/user/userresumepdf_gen_ai_dynamic_shell.html"


def _guess_image_mime(name: str) -> str:
    lower = (name or "").lower()
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    guessed, _ = mimetypes.guess_type(lower)
    return guessed or "image/jpeg"


def file_field_to_data_uri(file_field) -> str:
    """Read a Django FileField/ImageField into a data: URI for offline PDF rendering."""
    if not file_field or not getattr(file_field, "name", None):
        return ""
    try:
        with file_field.open("rb") as handle:
            raw = handle.read()
    except OSError as exc:
        logger.warning("Could not read image for PDF %s: %s", getattr(file_field, "name", ""), exc)
        return ""
    if not raw:
        return ""
    mime = _guess_image_mime(file_field.name)
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def file_field_to_data_uri(file_field) -> str:
    """Read a Django FileField/ImageField into a data: URI for offline PDF rendering."""
    if not file_field or not getattr(file_field, "name", None):
        return ""
    try:
        with file_field.open("rb") as handle:
            raw = handle.read()
    except OSError as exc:
        logger.warning("Could not read image for PDF %s: %s", getattr(file_field, "name", ""), exc)
        return ""
    if not raw:
        return ""
    mime = _guess_image_mime(file_field.name)
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _local_media_file_to_data_uri(path: str) -> str:
    """Read a media-relative or absolute filesystem path into a data: URI."""
    import os
    from urllib.parse import unquote, urlparse

    from django.conf import settings

    if not path:
        return ""
    norm = unquote(str(path).replace("\\", "/").strip())
    if norm.startswith(("http://", "https://")):
        norm = urlparse(norm).path or ""
    norm = norm.lstrip("/")
    if not norm:
        return ""
    candidates: list[str] = []
    media_root = str(settings.MEDIA_ROOT)
    if norm.startswith("media/"):
        candidates.append(os.path.join(media_root, norm[6:]))
    candidates.append(os.path.join(media_root, norm))
    for local in candidates:
        if os.path.isfile(local):
            try:
                with open(local, "rb") as handle:
                    raw = handle.read()
            except OSError as exc:
                logger.warning("Could not read local media for PDF %s: %s", local, exc)
                continue
            if not raw:
                continue
            mime = _guess_image_mime(local)
            encoded = base64.b64encode(raw).decode("ascii")
            return f"data:{mime};base64,{encoded}"
    return ""


def _ensure_photo_initial(payload: dict, user) -> dict:
    if (payload.get("photo") or "").strip() or (payload.get("photoInitial") or "").strip():
        return payload
    label = (getattr(user, "name", None) or getattr(user, "email", None) or "").strip()
    if not label:
        return payload
    out = dict(payload)
    out["photoInitial"] = label[0].upper()
    return out


def embed_resume_photo_data_uri(payload: dict, resume, user, request=None) -> dict:
    """Replace remote photo URLs with embedded data URIs so PDF engines need no network."""
    out = dict(payload)
    photo = (out.get("photo") or "").strip()
    if photo.startswith("data:"):
        return _ensure_photo_initial(out, user)
    for field in (getattr(resume, "image", None), getattr(user, "image", None)):
        data_uri = file_field_to_data_uri(field)
        if data_uri:
            out["photo"] = data_uri
            return _ensure_photo_initial(out, user)
    if photo:
        local_uri = _local_media_file_to_data_uri(photo)
        if local_uri:
            out["photo"] = local_uri
            return _ensure_photo_initial(out, user)
    if photo.startswith(("http://", "https://")):
        data_uri = _photo_url_to_data_uri(photo)
        if data_uri:
            out["photo"] = data_uri
            return _ensure_photo_initial(out, user)
    if request is not None and photo.startswith("/"):
        data_uri = _photo_url_to_data_uri(request.build_absolute_uri(photo))
        if data_uri:
            out["photo"] = data_uri
    return _ensure_photo_initial(out, user)


def _photo_url_to_data_uri(url: str) -> str:
    """Fetch a resume photo URL and return a data: URI for offline PDF rendering."""
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "TopTeenResumePDF/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            if not raw:
                return ""
            mime = resp.headers.get_content_type() or _guess_image_mime(url)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        logger.warning("Could not fetch resume photo URL for PDF %s: %s", url, exc)
        return ""
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _ai_shell_ctx_from_row(row):
    from users.resume_template_ai import google_font_context_for_template

    if not row:
        return {
            "ai_dynamic_css": "",
            "use_ai_dynamic_shell": False,
            "ai_google_font_url": "",
            "ai_google_font_stack": "",
        }
    css = (getattr(row, "ai_dynamic_css", None) or "").strip()
    use = bool(css)
    ctx = {"ai_dynamic_css": css if use else "", "use_ai_dynamic_shell": use}
    if use:
        ctx.update(google_font_context_for_template(row))
    else:
        ctx["ai_google_font_url"] = ""
        ctx["ai_google_font_stack"] = ""
    return ctx


def _choose_generated_mail_template(row, generated_path):
    if row and (getattr(row, "ai_dynamic_css", None) or "").strip():
        return AI_DYNAMIC_GENERATED_SHELL, AI_DYNAMIC_GENERATED_SHELL
    return generated_path, "mail/user/userresumepdf_generated.html"


def _resume_pdf_template_row_paths_and_style(user_resume, preview_template_id=None):
    del user_resume, preview_template_id
    return (
        None,
        "mail/user/userresumepdf.html",
        "mail/user/userresumepdf_generated.html",
        "v01",
        "#19718c",
    )


def _safe_pdf_filename(user) -> str:
    base = (getattr(user, "name", None) or "Student").strip() or "Student"
    safe = re.sub(r"[^\w\-. ]+", "_", base, flags=re.UNICODE).strip(" .-_") or "Student"
    return f"{safe}-resume.pdf"


def build_resume_pdf_html(
    user_resume,
    request,
    *,
    preview_template_id: str | None = None,
) -> str:
    """Render full HTML document for PDF export (studio prototype or legacy templates)."""
    from users.models import (
        UserResumeActivity,
        UserResumeCertificate,
        UserResumeInternship,
        UserResumeSkill,
        UserResumeVolunteerInvolvement,
    )

    try:
        from users.resume_v2_services import sync_studio_proto_resume_from_db
    except ImportError:
        sync_studio_proto_resume_from_db = None  # type: ignore[assignment]

    ensure_studio_proto_v1_defaults_saved(user_resume, request)
    if sync_studio_proto_resume_from_db:
        try:
            sync_studio_proto_resume_from_db(user_resume, request)
            user_resume.refresh_from_db()
        except Exception:
            logger.exception("sync_studio_proto_resume_from_db failed for resume %s", user_resume.pk)

    tpl_row, classic_path, generated_path, pdf_lv, pdf_ac = _resume_pdf_template_row_paths_and_style(
        user_resume, preview_template_id
    )
    ctx = {
        "request": request,
        "profile": UserProfile.objects.filter(user=request.user).first()
        or UserProfile.objects.create(user=request.user),
        "user_resume": user_resume,
        "pdf_layout_variant": pdf_lv,
        "pdf_accent_color": pdf_ac,
        "skills": UserResumeSkill.objects.filter(resume=user_resume),
        "certificates": UserResumeCertificate.objects.filter(resume=user_resume).order_by("issue_date"),
        "internships": UserResumeInternship.objects.filter(resume=user_resume),
        "activities": UserResumeActivity.objects.filter(resume=user_resume),
        "volunteers": UserResumeVolunteerInvolvement.objects.filter(resume=user_resume),
        "resume_contact": resume_studio_prototype_payload(user_resume, request),
    }
    ctx.update(_ai_shell_ctx_from_row(tpl_row))

    user_image = getattr(request.user, "image", None)
    if user_image:
        try:
            ctx["image_url"] = request.build_absolute_uri(user_image.url)
        except ValueError:
            ctx["image_url"] = ""
    else:
        ctx["image_url"] = ""

    studio_pack = (
        None
        if wizard_prefers_generated_pdf(user_resume)
        else studio_proto_pack_from_resume(user_resume)
    )
    if studio_pack:
        mount_html, template_id, studio_pack = studio_render_html_for_resume(
            user_resume,
            request,
            template_override=(preview_template_id or None),
        )
        pack_for_pdf = dict(studio_pack)
        resume_data = dict(pack_for_pdf.get("resume") or {})
        resume_data = embed_resume_photo_data_uri(
            resume_data, user_resume, request.user, request=request
        )
        pack_for_pdf["resume"] = resume_data
        from users.resume_studio_pdf_html import studio_proto_pack_to_mount_html

        mount_html, template_id = studio_proto_pack_to_mount_html(pack_for_pdf)
        ctx.update(studio_pdf_template_context(mount_html, template_id, pack_for_pdf))
        ctx["generated_resume_html"] = mount_html
        chosen = "mail/user/userresumepdf_studio_prototype.html"
        fallback = chosen
    elif (user_resume.generated_html or "").strip():
        ctx["generated_resume_html"] = strip_markdown_fences(user_resume.generated_html)
        chosen, fallback = _choose_generated_mail_template(tpl_row, generated_path)
    else:
        chosen = classic_path
        fallback = "mail/user/userresumepdf.html"

    try:
        template = get_template(chosen)
    except TemplateDoesNotExist:
        template = get_template(fallback)
    return template.render(ctx)


def generate_resume_pdf_bytes(
    user_resume,
    request,
    *,
    preview_template_id: str | None = None,
) -> bytes:
    html = build_resume_pdf_html(
        user_resume,
        request,
        preview_template_id=preview_template_id,
    )
    return resume_html_to_pdf_bytes(
        html,
        base_url=request.build_absolute_uri("/"),
    )


def resume_pdf_response(
    user_resume,
    request,
    *,
    inline: bool = True,
    preview_template_id: str | None = None,
) -> HttpResponse:
    """Return PDF HttpResponse; inline opens in the browser tab."""
    pdf = generate_resume_pdf_bytes(
        user_resume,
        request,
        preview_template_id=preview_template_id,
    )
    response = HttpResponse(pdf, content_type="application/pdf")
    filename = _safe_pdf_filename(request.user)
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response
