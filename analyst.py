"""Produces a structured compare-and-contrast analysis for one topic group.

Takes a TopicGroup (2+ articles on the same topic) and returns a GroupAnalysis
with four fields — agreements, contradictions, debunks, unresolved — by asking
the LLM to reason across the sources rather than summarize them individually.

The persona from config.yaml shapes the analytical voice. Failures return None
so the pipeline can skip a bad group rather than abort the run.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

import anthropic

from resilience import is_transient_anthropic, retry_with_backoff
from grouper import TopicGroup
from store import GroupAnalysis

logger = logging.getLogger(__name__)

_SYSTEM_TEMPLATE = """\
{persona}

You are performing comparative source analysis. Your job is not to summarize \
each article — it is to reason across them and surface where they agree, \
where they conflict, and what remains unresolved.

Definitions:
- agreements: claims that two or more sources make consistently
- contradictions: cases where sources make directly conflicting factual claims
- debunks: cases where one source explicitly refutes or disproves a claim made by another
- unresolved: tensions or open questions the available sources do not resolve

Be specific. Name the sources. Quote or closely paraphrase the conflicting claims. \
Empty lists are fine if a category genuinely has nothing to report.

Respond with valid JSON only — no prose, no markdown fences:
{{"agreements": [...], "contradictions": [...], "debunks": [...], "unresolved": [...]}}
"""

_USER_PROMPT_TEMPLATE = """\
Topic: {topic}

Analyze the following {count} sources and produce a structured compare-and-contrast.

{items_block}

Return JSON only.
"""


def _format_items(group: TopicGroup) -> str:
    lines = []
    for i, item in enumerate(group.items):
        excerpt = (item.summary_raw or "").replace("\n", " ")[:300]
        lines.append(
            f"{i + 1}. [{item.source}] {item.title}\n"
            f"   URL: {item.url}\n"
            f"   Excerpt: {excerpt or '(no excerpt)'}"
        )
    return "\n\n".join(lines)


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences the model sometimes adds despite instructions."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _parse_response(raw: str) -> dict[str, list[str]] | None:
    """Parse the LLM JSON response into the four analysis fields.

    Returns None on any parse failure so the caller can skip the group.
    """
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        logger.warning("Analyst: JSON parse failed (%s). Raw: %.300s", exc, raw)
        return None

    result: dict[str, list[str]] = {}
    for key in ("agreements", "contradictions", "debunks", "unresolved"):
        value = data.get(key)
        if not isinstance(value, list):
            logger.warning("Analyst: missing or invalid field %r in response", key)
            return None
        result[key] = [str(v) for v in value if v]

    return result


def analyze(group: TopicGroup, config: dict[str, Any]) -> GroupAnalysis | None:
    """Call the Anthropic API to produce a structured analysis for one topic group.

    Returns None on API failure or unparseable response — callers should log
    and skip rather than abort the run.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("Analyst: ANTHROPIC_API_KEY not set")
        return None

    persona = config.get("persona", {}).get("prompt", "You are a sharp technical analyst.")
    llm_config = config.get("llm", {})
    model = llm_config.get("model", "claude-sonnet-4-6")

    system_prompt = _SYSTEM_TEMPLATE.format(persona=persona.strip())
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        topic=group.label,
        count=len(group.items),
        items_block=_format_items(group),
    )

    n_items = len(group.items)
    # Scale token budget with group size; large groups need room for verbose JSON.
    dynamic_max_tokens = min(1500 + (n_items * 300), 3000)

    def _call() -> anthropic.types.Message:
        client = anthropic.Anthropic(api_key=api_key)
        return client.messages.create(
            model=model,
            max_tokens=dynamic_max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

    try:
        # Rate limits/overload/5xx are retried with backoff; a still-failing
        # call keeps the documented contract: log and skip this group (None).
        response = retry_with_backoff(_call, label="Analyst", is_transient=is_transient_anthropic)
    except Exception:
        logger.warning("Analyst: Anthropic API call failed for topic %r", group.label, exc_info=True)
        return None

    raw = "".join(block.text for block in response.content if block.type == "text")
    fields = _parse_response(raw)
    if fields is None:
        return None

    period_start, period_end = group.date_range

    analysis = GroupAnalysis(
        topic=group.label,
        run_date=date.today(),
        period_start=period_start,
        period_end=period_end,
        agreements=fields["agreements"],
        contradictions=fields["contradictions"],
        debunks=fields["debunks"],
        unresolved=fields["unresolved"],
        sources=group.items,
    )

    logger.info(
        "Analyst: %r → %d agreements, %d contradictions, %d debunks, %d unresolved",
        group.label,
        len(analysis.agreements),
        len(analysis.contradictions),
        len(analysis.debunks),
        len(analysis.unresolved),
    )
    return analysis


def analyze_all(groups: list[TopicGroup], config: dict[str, Any]) -> list[GroupAnalysis]:
    """Analyze every group; skip and log any that fail."""
    results: list[GroupAnalysis] = []
    for group in groups:
        result = analyze(group, config)
        if result is not None:
            results.append(result)
        else:
            logger.warning("Analyst: skipped group %r (analyze returned None)", group.label)
    return results
