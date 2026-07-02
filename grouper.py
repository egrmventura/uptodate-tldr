"""Groups ingested items into topic clusters via LLM-assigned canonical labels.

Labels are normalized and stable across runs ("Anthropic MCP" not "Claude tool
integration") so that topic identity can be preserved in the SQLite timeline
store and matched across daily runs and backfill runs.

Singletons — items whose topic has no other matching article — are dropped by
default since they carry no comparative signal for the analysis layer.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import anthropic

from resilience import is_transient_anthropic, retry_with_backoff
from sources.base import Item

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a topic classifier for a technical news pipeline covering AI, ML, and Data Engineering.

Your task: assign each article a canonical topic label. Articles covering the same \
underlying topic, claim, or development should share an identical label.

Rules for labels:
- Be specific and stable: "Anthropic MCP" not "Claude tool integration"; \
"OpenAI o3" not "new reasoning model"
- Use the same label every time for the same topic — these labels are stored \
and matched across pipeline runs
- One label per article
- If an article does not clearly share a topic with any other article, \
assign it the label "__singleton__"

Respond with valid JSON only — no prose, no markdown fences:
{"assignments": [{"index": 0, "topic": "Canonical Topic Name"}, ...]}
"""

_USER_PROMPT_TEMPLATE = """\
Classify each article below into a canonical topic group.

{items_block}

Return JSON only.
"""


@dataclass
class TopicGroup:
    label: str
    items: list[Item] = field(default_factory=list)

    @property
    def date_range(self) -> tuple[datetime, datetime]:
        dates = [i.published_at for i in self.items]
        return (min(dates), max(dates))


def _format_items(items: list[Item]) -> str:
    lines = []
    for i, item in enumerate(items):
        excerpt = (item.summary_raw or "").replace("\n", " ")[:200]
        lines.append(f"{i}. [{item.source}] {item.title}\n   {excerpt}")
    return "\n\n".join(lines)


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _parse_assignments(raw: str, n_items: int) -> dict[int, str]:
    """Parse the LLM JSON response into an index→topic mapping.

    Returns an empty dict on any parse failure so the caller can decide
    whether to abort or return no groups.
    """
    try:
        data = json.loads(_strip_fences(raw))
        assignments = data["assignments"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Grouper: failed to parse LLM response (%s). Raw: %.300s", exc, raw)
        return {}

    result: dict[int, str] = {}
    for entry in assignments:
        idx = entry.get("index")
        topic = (entry.get("topic") or "").strip()
        if not isinstance(idx, int) or not topic or not (0 <= idx < n_items):
            continue
        result[idx] = topic
    return result


def group_items(
    items: list[Item],
    config: dict[str, Any],
    drop_singletons: bool = True,
) -> list[TopicGroup]:
    """Cluster `items` into topic groups and return them sorted by group size descending.

    Never raises — on LLM failure returns an empty list so the pipeline can
    decide whether to abort or fall back to the ranked-TLDR flow.
    """
    if not items:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("Grouper: ANTHROPIC_API_KEY not set — returning no groups")
        return []

    llm_config = config.get("llm", {})
    model = llm_config.get("model", "claude-sonnet-4-6")

    user_prompt = _USER_PROMPT_TEMPLATE.format(items_block=_format_items(items))

    def _call() -> anthropic.types.Message:
        client = anthropic.Anthropic(api_key=api_key)
        return client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

    try:
        # Rate limits/overload/5xx are retried with backoff; a still-failing
        # call keeps the documented contract: log and return no groups.
        response = retry_with_backoff(_call, label="Grouper", is_transient=is_transient_anthropic)
    except Exception:
        logger.warning("Grouper: Anthropic API call failed", exc_info=True)
        return []

    raw = "".join(block.text for block in response.content if block.type == "text")
    assignments = _parse_assignments(raw, len(items))

    if not assignments:
        return []

    buckets: dict[str, list[Item]] = {}
    for idx, topic in assignments.items():
        buckets.setdefault(topic, []).append(items[idx])

    groups: list[TopicGroup] = []
    for label, members in buckets.items():
        if drop_singletons and (label == "__singleton__" or len(members) < 2):
            logger.debug("Grouper: dropping singleton %r", label)
            continue
        groups.append(TopicGroup(label=label, items=members))

    groups.sort(key=lambda g: len(g.items), reverse=True)
    logger.info("Grouper: %d groups from %d items", len(groups), len(items))
    return groups
