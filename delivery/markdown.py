"""Markdown file delivery: writes the digest to ./output/YYYY-MM-DD.md.

This is the simplest and most reliable delivery target — no external
dependencies or credentials — and doubles as the source-of-truth artifact
that other delivery channels (email, Substack) reuse.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def deliver(digest_markdown: str, topic: str, config: dict[str, Any], run_date: date) -> Path:
    """Write `digest_markdown` to `<output_dir>/<run_date>.md` and return the path."""
    output_dir = Path(config["delivery"]["markdown"].get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{run_date.isoformat()}.md"
    header = f"# {topic} — Daily Digest ({run_date.isoformat()})\n\n"

    output_path.write_text(header + digest_markdown.strip() + "\n", encoding="utf-8")
    logger.info("Wrote digest to %s", output_path)
    return output_path
