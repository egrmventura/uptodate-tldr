"""Offline extractive summarization (productized from the trial scripts).

Position + keyword-density sentence scoring; no LLM. Study finding F5: this
is sufficient for *relating* articles — save LLM budget for the analysis
stage, which extractive methods can't do.
"""

from __future__ import annotations

import re

SUMMARY_CHARS = 600
SUMMARY_SENTENCES = 4
_KEYWORDS = (
    "claude", "anthropic", "mcp", "tool", "agent", "code", "api", "skill",
    "plugin", "sdk", "integration", "model", "release", "feature",
    "pipeline", "warehouse", "dbt", "spark", "airflow", "data", "embedding",
    "memory", "retrieval", "rag",
)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 20]


def extractive_summary(body: str, n: int = SUMMARY_SENTENCES) -> str:
    """Top-n sentences by keyword density with lead bias, original order,
    capped at SUMMARY_CHARS."""
    sents = split_sentences(body)
    if not sents:
        return body[:SUMMARY_CHARS]

    scored = []
    for i, s in enumerate(sents):
        low = s.lower()
        kw = sum(low.count(k) for k in _KEYWORDS)
        position = 1.5 if i < 3 else (1.0 if i < 10 else 0.5)
        length_penalty = 0.5 if len(s) > 400 else 1.0
        scored.append((kw * position * length_penalty, i, s))

    top = sorted(scored, key=lambda t: t[0], reverse=True)[:n]
    ordered = [s for _, _, s in sorted(top, key=lambda t: t[1])]
    return " ".join(ordered)[:SUMMARY_CHARS]
