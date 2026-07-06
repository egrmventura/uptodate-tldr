"""Scrape each fetched article and produce a compact extractive summary.

Uses the repo's scraper.scrape() (never raises; paywalled/blocked → None —
the HN discussion excerpt is kept as fallback text). Summarization is
extractive and offline (no LLM): sentences are scored by position + keyword
density and the top ones are kept, capped at SUMMARY_CHARS. This keeps the
trial reproducible, free, and context-cheap.

Run:  python3 output/second-brain-tests/scrape_summarize.py
In:   data/articles_raw.json
Out:  data/articles.json   (adds: body_chars, scraped, summary)
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from scraper import scrape  # noqa: E402

SUMMARY_CHARS = 600
SUMMARY_SENTENCES = 4
_KEYWORDS = (
    "claude", "anthropic", "mcp", "tool", "agent", "code", "api", "skill",
    "plugin", "sdk", "integration", "model", "release", "feature",
)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 20]


def extractive_summary(body: str, n: int = SUMMARY_SENTENCES) -> str:
    """Position + keyword-density sentence scoring; returns top sentences in
    original order, capped at SUMMARY_CHARS."""
    sents = split_sentences(body)
    if not sents:
        return body[:SUMMARY_CHARS]

    scored = []
    for i, s in enumerate(sents):
        low = s.lower()
        kw = sum(low.count(k) for k in _KEYWORDS)
        position = 1.5 if i < 3 else (1.0 if i < 10 else 0.5)  # lead bias
        length_penalty = 0.5 if len(s) > 400 else 1.0
        scored.append((kw * position * length_penalty, i, s))

    top = sorted(scored, key=lambda t: t[0], reverse=True)[:n]
    ordered = [s for _, _, s in sorted(top, key=lambda t: t[1])]
    out = " ".join(ordered)
    return out[:SUMMARY_CHARS]


def enrich(article: dict) -> dict:
    result = scrape(article["url"], {"min_body_chars": 200, "timeout": 10})
    if result is not None and result.body:
        article["scraped"] = True
        article["body_chars"] = len(result.body)
        article["summary"] = extractive_summary(result.body)
        if result.author:
            article["author"] = result.author
    else:
        article["scraped"] = False
        article["body_chars"] = 0
        # fallback: HN story text or just the title
        article["summary"] = (article.get("story_text") or article["title"])[:SUMMARY_CHARS]
    return article


def main() -> None:
    raw = json.loads((HERE / "data" / "articles_raw.json").read_text())
    articles = raw["articles"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        articles = list(pool.map(enrich, articles))

    ok = sum(1 for a in articles if a["scraped"])
    raw["articles"] = articles
    out = HERE / "data" / "articles.json"
    out.write_text(json.dumps(raw, indent=2))
    print(f"Scraped {ok}/{len(articles)} articles successfully "
          f"(rest fell back to HN excerpt/title). Wrote {out}")


if __name__ == "__main__":
    main()
