"""Renders a list of GroupAnalysis records to a structured markdown digest file.

Output path: <output_dir>/analysis-<run_date>.md — distinct from the TLDR
digest (<run_date>.md) so both pipelines can write to the same output dir.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from store import GroupAnalysis

logger = logging.getLogger(__name__)


def _render_list(items: list[str]) -> str:
    if not items:
        return "*(none)*"
    return "\n".join(f"- {item}" for item in items)


def _render_analysis(analysis: GroupAnalysis) -> str:
    start, end = analysis.period_start, analysis.period_end
    if start.date() == end.date():
        date_label = start.strftime("%b %-d, %Y")
    else:
        date_label = f"{start.strftime('%b %-d')}–{end.strftime('%b %-d, %Y')}"

    source_links = ", ".join(
        f"[{item.title}]({item.url})" for item in analysis.sources
    )

    return (
        f"## {analysis.topic}  ·  {len(analysis.sources)} source(s)  ·  {date_label}\n\n"
        f"**Agreement**\n{_render_list(analysis.agreements)}\n\n"
        f"**Contradictions**\n{_render_list(analysis.contradictions)}\n\n"
        f"**Debunks**\n{_render_list(analysis.debunks)}\n\n"
        f"**Unresolved**\n{_render_list(analysis.unresolved)}\n\n"
        f"Sources: {source_links or '*(none)*'}"
    )


def render(analyses: list[GroupAnalysis], topic: str, run_date: date) -> str:
    """Return the full markdown string for a daily analysis digest."""
    header = f"# {topic} — Analysis Digest ({run_date.isoformat()})\n"
    if not analyses:
        return header + "\n*No topic groups with 2+ sources found for this run.*\n"

    sections = ["\n---\n\n" + _render_analysis(a) + "\n" for a in analyses]
    return header + "".join(sections) + "\n---\n"


def deliver(
    analyses: list[GroupAnalysis],
    topic: str,
    config: dict[str, Any],
    run_date: date,
) -> Path:
    """Write the analysis digest to disk and return the output path."""
    output_dir = Path(
        config.get("delivery", {}).get("analysis_md", {}).get("output_dir", "./output")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"analysis-{run_date.isoformat()}.md"
    output_path.write_text(render(analyses, topic, run_date), encoding="utf-8")
    logger.info("Wrote analysis digest to %s", output_path)
    return output_path
