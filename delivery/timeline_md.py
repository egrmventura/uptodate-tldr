"""Writes a rendered topic timeline to <output_dir>/timeline-<slug>.md."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from store import Store
from timeline import render_timeline

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^\w]+")


def _slugify(topic: str) -> str:
    return _SLUG_RE.sub("-", topic.lower()).strip("-")


def deliver(topic: str, store: Store, config: dict[str, Any]) -> Path | None:
    """Render and write the timeline for `topic`; return the path or None if empty."""
    content = render_timeline(topic, store)
    if not content:
        return None

    output_dir = Path(
        config.get("delivery", {}).get("analysis_md", {}).get("output_dir", "./output")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(topic)
    output_path = output_dir / f"timeline-{slug}.md"
    output_path.write_text(content, encoding="utf-8")
    logger.info("Wrote timeline for %r to %s", topic, output_path)
    return output_path
