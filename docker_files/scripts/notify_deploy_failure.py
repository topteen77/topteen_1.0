#!/usr/bin/env python3
"""
Send deploy-failure email (used by CI or manual runs).

Environment:
  DEPLOY_NOTIFY_TO     Recipient (default: it@canamgroup.com)
  SMTP_SERVER / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD / SMTP_FROM
  Or Django-style: EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD

Usage:
  python docker_files/scripts/notify_deploy_failure.py deploy.log
  cat deploy.log | python docker_files/scripts/notify_deploy_failure.py -
"""
from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


def _env(*keys: str, default: str = "") -> str:
    for key in keys:
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return default


def main() -> int:
    log_path = sys.argv[1] if len(sys.argv) > 1 else "-"
    if log_path == "-":
        log_text = sys.stdin.read()
        attachment_name = "deploy.log"
    else:
        p = Path(log_path)
        log_text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        attachment_name = p.name or "deploy.log"

    host = _env("SMTP_SERVER", "EMAIL_HOST")
    port = int(_env("SMTP_PORT", "EMAIL_PORT", default="587") or "587")
    user = _env("SMTP_USERNAME", "EMAIL_HOST_USER")
    password = _env("SMTP_PASSWORD", "EMAIL_HOST_PASSWORD")
    mail_from = _env("SMTP_FROM", default="noreply@topteen.in")
    mail_to = _env("DEPLOY_NOTIFY_TO", default="it@canamgroup.com")

    if not host or not user or not password:
        print("SMTP not configured (set SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD)", file=sys.stderr)
        return 2

    msg = EmailMessage()
    msg["Subject"] = "deploy fail"
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content(
        "TopTeen production deploy failed.\n\n"
        "See attachment for full deploy log.\n"
    )
    if log_text:
        msg.add_attachment(
            log_text.encode("utf-8", errors="replace"),
            maintype="text",
            subtype="plain",
            filename=attachment_name,
        )

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)

    print(f"Failure notification sent to {mail_to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
