"""Email delivery via SMTP.

Uses `smtplib` with the env vars in .env.example (SMTP_HOST, SMTP_PORT,
SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO). SMTP is chosen over a
provider SDK (e.g. SendGrid) to avoid an extra dependency and account setup
for the common case of sending through an existing Gmail/Workspace/etc.
account; if you'd rather use SendGrid, replace the body of `deliver` with a
call to their HTTP API using `SENDGRID_API_KEY` — the function signature
(markdown in, nothing out) doesn't need to change.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import date
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)


def deliver(digest_markdown: str, topic: str, config: dict[str, Any], run_date: date) -> None:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("EMAIL_FROM") or config["delivery"]["email"].get("from")
    recipient = os.environ.get("EMAIL_TO") or config["delivery"]["email"].get("to")

    if not all([host, sender, recipient]):
        raise RuntimeError(
            "Email delivery is enabled but SMTP_HOST/EMAIL_FROM/EMAIL_TO are not fully set"
        )

    message = EmailMessage()
    message["Subject"] = f"{topic} — Daily Digest ({run_date.isoformat()})"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(digest_markdown)

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)

    logger.info("Sent digest email to %s", recipient)
