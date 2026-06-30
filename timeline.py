"""Renders a topic's stored analysis history as a chronological markdown timeline.

Period labels use the article publication dates (period_start), not run dates,
so the timeline reflects when the content was written rather than when the
pipeline ran.
"""

from __future__ import annotations

import logging

from store import GroupAnalysis, Store

logger = logging.getLogger(__name__)


def _period_label(analysis: GroupAnalysis) -> str:
    start, end = analysis.period_start, analysis.period_end
    if start.year == end.year and start.month == end.month:
        return start.strftime("%b %Y")
    return f"{start.strftime('%b %Y')}–{end.strftime('%b %Y')}"


def _render_field(label: str, items: list[str]) -> str:
    if not items:
        return f"**{label}:** *(none)*"
    if len(items) == 1:
        return f"**{label}:** {items[0]}"
    bullets = "\n".join(f"  - {item}" for item in items)
    return f"**{label}:**\n{bullets}"


def render_timeline(topic: str, store: Store) -> str:
    """Return chronological markdown for all stored analyses of `topic`.

    Returns an empty string (with a log warning) if the topic has no records.
    """
    analyses = store.get_timeline(topic)
    if not analyses:
        logger.warning("Timeline: no records found for topic %r", topic)
        return ""

    header = f"# Topic Timeline: {topic}\n\n"
    sections: list[str] = []

    for analysis in analyses:
        label = _period_label(analysis)
        n = len(analysis.sources)
        body = "\n\n".join([
            _render_field("Agreement", analysis.agreements),
            _render_field("Contradictions", analysis.contradictions),
            _render_field("Debunks", analysis.debunks),
            _render_field("Unresolved", analysis.unresolved),
        ])
        sections.append(f"## {label}  ({n} source(s))\n\n{body}")

    return header + "\n\n---\n\n".join(sections) + "\n\n---\n"
