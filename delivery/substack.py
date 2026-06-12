"""Substack delivery — drafts a post via Substack's unofficial API.

**This is the most fragile delivery channel in the project.** Substack has
no public API. Drafting a post requires:

1. Logging into Substack in a browser and extracting the `substack.sid`
   session cookie (DevTools -> Application -> Cookies).
2. Setting `SUBSTACK_COOKIE` to that value and `SUBSTACK_PUBLICATION_URL`
   to your publication's base URL (e.g. `https://yourname.substack.com`).
3. POSTing a draft to `<publication_url>/api/v1/drafts`.

Risks, in order of likelihood:
- The session cookie expires (Substack sessions are short-lived), silently
  breaking this channel until the cookie is refreshed manually.
- Substack changes the internal API shape with no notice or versioning,
  since it's not a contract they support.
- Logging in via automation may trip anti-bot detection; this module
  assumes you extract the cookie from a normal interactive browser
  session, not an automated login.

Given these risks, this channel is disabled by default and should be
treated as "best effort" — a failure here should not be surprising, and
should never block the markdown/email channels (see main.py, which runs
delivery channels independently and logs per-channel failures).
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15


def deliver(digest_markdown: str, topic: str, config: dict[str, Any], run_date: date) -> None:
    cookie = os.environ.get("SUBSTACK_COOKIE")
    publication_url = os.environ.get("SUBSTACK_PUBLICATION_URL") or config["delivery"][
        "substack"
    ].get("publication_url")

    if not cookie or not publication_url:
        raise RuntimeError(
            "Substack delivery is enabled but SUBSTACK_COOKIE/SUBSTACK_PUBLICATION_URL "
            "are not set"
        )

    title = f"{topic} — Daily Digest ({run_date.isoformat()})"

    response = requests.post(
        f"{publication_url.rstrip('/')}/api/v1/drafts",
        json={
            "draft_title": title,
            "draft_body": digest_markdown,
            "type": "newsletter",
        },
        cookies={"substack.sid": cookie},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    logger.info("Created Substack draft %r", title)
