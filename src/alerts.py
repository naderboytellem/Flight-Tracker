"""
Two free alert channels:

- Email via plain SMTP (works with a Gmail/Outlook/etc "app password", or
  any SMTP relay).
- Push via ntfy.sh (https://ntfy.sh) - no account needed, just a shared
  topic name your phone/computer subscribes to.

Both are best-effort: if the env vars for a channel aren't set, that
channel is silently skipped (so you can start with just one).
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.text import MIMEText

import requests


def send_email(subject: str, body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    to_addr = os.environ.get("ALERT_EMAIL_TO", user)
    port = int(os.environ.get("SMTP_PORT", "587"))

    if not (host and user and password and to_addr):
        print("[alerts] email not configured, skipping")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        print(f"[alerts] email sent: {subject}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[alerts] email FAILED: {exc}")
        return False


def send_push(title: str, message: str, url: str | None = None) -> bool:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("[alerts] ntfy not configured, skipping")
        return False

    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
    headers = {
        "Title": title.encode("utf-8"),
        "Priority": "default",
        "Tags": "airplane,moneybag",
    }
    if url:
        headers["Click"] = url

    try:
        resp = requests.post(f"{server}/{topic}", data=message.encode("utf-8"), headers=headers, timeout=15)
        resp.raise_for_status()
        print(f"[alerts] push sent: {title}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[alerts] push FAILED: {exc}")
        return False


def fire(subject_line: str, body: str, url: str | None = None) -> None:
    send_email(subject_line, body)
    send_push(subject_line, body, url=url)
