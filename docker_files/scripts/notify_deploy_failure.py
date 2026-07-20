#!/usr/bin/env python3
"""
Send deploy-failure email using the same AWS SES / SMTP settings as the website.

Loads repo-root .env (EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD,
DEFAULT_FROM_EMAIL, …) — same credentials Django uses.

Preferred (inside web container):
  python docker_files/scripts/notify_deploy_failure.py /tmp/topteen-deploy.log

Or via deploy.sh:
  ./docker_files/deploy.sh notify-failure [/path/to/log]

Env overrides:
  DEPLOY_NOTIFY_TO   recipient (default: it@canamgroup.com)
"""
from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DOCKER_FILES_DIR = SCRIPT_DIR.parent
REPO_ROOT = DOCKER_FILES_DIR.parent
ROOT_ENV = REPO_ROOT / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def _env(*keys: str, default: str = "") -> str:
    for key in keys:
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return default


def _read_log(log_path: str) -> tuple[str, str]:
    if log_path == "-":
        return sys.stdin.read(), "deploy.log"
    p = Path(log_path)
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace"), p.name
    return "", "deploy.log"


def _send_via_django(mail_to: str, subject: str, body: str, log_text: str, attachment_name: str) -> None:
    sys.path.insert(0, str(REPO_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topteens.settings")
    import django

    django.setup()
    from django.conf import settings
    from django.core.mail import EmailMessage

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or _env(
        "DEFAULT_FROM_EMAIL", default="noreply@topteen.in"
    )
    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=from_email,
        to=[mail_to],
    )
    if log_text:
        msg.attach(attachment_name, log_text, "text/plain")
    msg.send(fail_silently=False)
    print(f"Failure notification sent via Django/SES to {mail_to} (from {from_email})")


def _send_via_smtplib(mail_to: str, subject: str, body: str, log_text: str, attachment_name: str) -> None:
    host = _env("EMAIL_HOST", "SMTP_SERVER", default="email-smtp.ap-south-1.amazonaws.com")
    port = int(_env("EMAIL_PORT", "SMTP_PORT", default="587") or "587")
    user = _env("EMAIL_HOST_USER", "SMTP_USERNAME")
    password = _env("EMAIL_HOST_PASSWORD", "SMTP_PASSWORD")
    mail_from = _env("DEFAULT_FROM_EMAIL", "SMTP_FROM", "TOPTEEN_FROM_EMAIL", default="noreply@topteen.in")
    if "<" in mail_from and ">" in mail_from:
        # "Topteen <noreply@…>" → keep as-is for EmailMessage
        pass

    if not user or not password:
        raise RuntimeError(
            "EMAIL_HOST_USER / EMAIL_HOST_PASSWORD not set in repo-root .env "
            "(same SES SMTP credentials the website uses)."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content(body)
    if log_text:
        msg.add_attachment(
            log_text.encode("utf-8", errors="replace"),
            maintype="text",
            subtype="plain",
            filename=attachment_name,
        )

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if _env("EMAIL_USE_TLS", default="True").lower() in ("1", "true", "yes", "on"):
            smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)

    print(f"Failure notification sent via SES SMTP to {mail_to} (from {mail_from})")


def main() -> int:
    _load_dotenv(ROOT_ENV)
    # docker_files/.env may override DEPLOY_NOTIFY_TO only
    _load_dotenv(DOCKER_FILES_DIR / ".env")

    log_path = sys.argv[1] if len(sys.argv) > 1 else "-"
    log_text, attachment_name = _read_log(log_path)

    mail_to = _env("DEPLOY_NOTIFY_TO", default="it@canamgroup.com")
    subject = _env("DEPLOY_NOTIFY_SUBJECT", default="deploy fail")
    sha = _env("GITHUB_SHA", default="")
    ref = _env("GITHUB_REF_NAME", default="")
    body = (
        "TopTeen production Docker deploy failed.\n\n"
        f"Branch : {ref or '(unknown)'}\n"
        f"Commit : {sha or '(unknown)'}\n\n"
        "See attachment for full deploy log.\n"
        "Site email uses the same AWS SES SMTP settings as Django (EMAIL_* in .env).\n"
    )

    try:
        _send_via_django(mail_to, subject, body, log_text, attachment_name)
        return 0
    except Exception as exc:
        print(f"Django mail path failed ({exc}); trying SES SMTP fallback…", file=sys.stderr)

    try:
        _send_via_smtplib(mail_to, subject, body, log_text, attachment_name)
        return 0
    except Exception as exc:
        print(f"Failed to send deploy failure email: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
