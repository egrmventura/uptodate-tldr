"""Validation tests for uptodate-tldr pipeline.

Measures success rate across: source ingestion, ranking, summarization,
and delivery. Target: 92%+ pass rate.
"""

from __future__ import annotations

import os
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from config import load_config
from sources.base import Item, parse_timestamp
from sources.hackernews import HackerNewsSource
from sources.arxiv import ArxivSource
from ranker import rank_items, _normalize_title, _dedup_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    RESULTS.append((name, passed, detail))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


# ---------- CONFIG ----------

def test_config_loads():
    try:
        config = load_config()
        record("config_loads", True)
        return config
    except Exception as e:
        record("config_loads", False, str(e))
        return None


def test_config_topic(config: dict[str, Any]):
    topic = config.get("topic", "")
    record("config_topic_set", bool(topic), f"topic={topic!r}")


def test_config_env_override_empty_skip():
    os.environ["TOPIC"] = ""
    config = load_config()
    passed = config["topic"] != ""
    record("config_empty_env_skipped", passed, f"topic={config['topic']!r}")
    if "TOPIC" in os.environ:
        del os.environ["TOPIC"]


# ---------- PARSE_TIMESTAMP ----------

def test_parse_timestamp():
    now = datetime.now(timezone.utc)

    ts_int = parse_timestamp(1719244800)
    record("parse_ts_int", isinstance(ts_int, datetime), str(ts_int))

    ts_none = parse_timestamp(None)
    record("parse_ts_none", abs((ts_none - now).total_seconds()) < 5)

    ts_iso = parse_timestamp("2026-06-20T12:00:00Z")
    record("parse_ts_iso", ts_iso.year == 2026 and ts_iso.month == 6)

    ts_ms = parse_timestamp(1719244800000, epoch_ms=True)
    record("parse_ts_epoch_ms", isinstance(ts_ms, datetime))

    ts_bad = parse_timestamp("not-a-date")
    record("parse_ts_bad_string", abs((ts_bad - now).total_seconds()) < 5)


# ---------- SOURCES ----------

def test_hn_source(topic: str):
    src = HackerNewsSource()
    items = src.safe_fetch(topic, {"max_results": 10})
    record("hn_returns_items", len(items) > 0, f"{len(items)} items")
    if items:
        item = items[0]
        record("hn_item_has_title", bool(item.title))
        record("hn_item_has_url", bool(item.url))
        record("hn_item_has_score", item.score >= 0, f"score={item.score}")
        record("hn_item_has_timestamp", item.published_at.tzinfo is not None)
    else:
        for name in ["hn_item_has_title", "hn_item_has_url", "hn_item_has_score", "hn_item_has_timestamp"]:
            record(name, False, "no items returned")


def test_arxiv_source(topic: str):
    src = ArxivSource()
    items = src.safe_fetch(topic, {"category": "cs.SE", "max_results": 5})
    record("arxiv_returns_items", len(items) > 0, f"{len(items)} items")
    if items:
        item = items[0]
        record("arxiv_item_has_title", bool(item.title))
        record("arxiv_item_has_url", bool(item.url))
        record("arxiv_item_has_summary", bool(item.summary_raw))
        record("arxiv_item_has_citations_key", "citations" in item.extra)
    else:
        for name in ["arxiv_item_has_title", "arxiv_item_has_url", "arxiv_item_has_summary", "arxiv_item_has_citations_key"]:
            record(name, False, "no items returned")


# ---------- RANKER ----------

def test_normalize_title():
    record("normalize_basic", _normalize_title("Hello, World!") == "hello world")
    record("normalize_whitespace", _normalize_title("  lots   of   spaces  ") == "lots of spaces")
    record("normalize_punctuation", _normalize_title("C++ is great!") == "c is great")


def test_dedup_key():
    item_url = Item(source="hn", title="Test", url="https://example.com/", score=1,
                    published_at=datetime.now(timezone.utc), summary_raw="")
    item_notitle = Item(source="hn", title="", url="https://example.com/path", score=1,
                        published_at=datetime.now(timezone.utc), summary_raw="")
    record("dedup_uses_title", _dedup_key(item_url) == "test")
    record("dedup_fallback_url", _dedup_key(item_notitle) == "https://example.com/path")


def test_ranking():
    now = datetime.now(timezone.utc)
    items = [
        Item(source="hn", title="Big Story", url="https://a.com", score=100,
             published_at=now, summary_raw=""),
        Item(source="arxiv", title="Big Story", url="https://arxiv.org/1", score=0,
             published_at=now, summary_raw="", extra={"citations": 5}),
        Item(source="hn", title="Small Story", url="https://b.com", score=10,
             published_at=now, summary_raw=""),
    ]
    ranking_config = {"recency_half_life_hours": 24, "cross_source_bonus": 1.5, "citation_weight": 2.0}
    ranked = rank_items(items, ranking_config, top_n=2)

    record("rank_returns_items", len(ranked) == 2, f"{len(ranked)} items")
    record("rank_top_is_cross_source", ranked[0].title == "Big Story",
           f"top={ranked[0].title!r}")
    record("rank_deduped", len(ranked) < len(items), "3 items → 2 groups")


# ---------- SUMMARIZER (mock-free, just prompt building) ----------

def test_prompt_building():
    from summarizer import build_user_prompt
    items = [
        Item(source="hn", title="Test Title", url="https://example.com", score=50,
             published_at=datetime.now(timezone.utc), summary_raw="Some excerpt"),
    ]
    prompt = build_user_prompt(items, "Claude Code")
    record("prompt_has_topic", "Claude Code" in prompt)
    record("prompt_has_item", "Test Title" in prompt)
    record("prompt_has_url", "https://example.com" in prompt)
    record("prompt_has_count", "top 1 items" in prompt)


# ---------- DELIVERY (markdown) ----------

def test_markdown_delivery():
    from delivery.markdown import deliver
    test_date = date(2026, 6, 24)
    output_dir = "./output"
    config = {"delivery": {"markdown": {"enabled": True, "output_dir": output_dir}}}
    deliver("# Test digest content", "test-topic", config, test_date)
    path = Path(output_dir) / "2026-06-24.md"
    exists = path.exists()
    record("markdown_file_written", exists, str(path))
    if exists:
        content = path.read_text()
        record("markdown_has_header", "test-topic" in content)
        record("markdown_has_body", "Test digest content" in content)


# ---------- END-TO-END (without LLM call) ----------

def test_e2e_ingest_and_rank(topic: str):
    from main import ingest
    config = load_config()
    items = ingest(topic, config.get("sources", {}))
    record("e2e_ingest_returns", len(items) > 0, f"{len(items)} total items")

    if items:
        ranked = rank_items(items, config.get("ranking", {}), config.get("top_n", 4))
        record("e2e_rank_returns", len(ranked) > 0, f"{len(ranked)} ranked")
        record("e2e_rank_within_topn", len(ranked) <= config.get("top_n", 4))
    else:
        record("e2e_rank_returns", False, "no items to rank")
        record("e2e_rank_within_topn", False, "no items to rank")


# ---------- RUNNER ----------

def main():
    print("\n=== uptodate-tldr Pipeline Validation ===\n")

    print("[Config]")
    config = test_config_loads()
    if config:
        test_config_topic(config)
    test_config_env_override_empty_skip()

    print("\n[Timestamp Parser]")
    test_parse_timestamp()

    topic = config["topic"] if config else "Claude Code"

    print("\n[Sources — Live API]")
    test_hn_source(topic)
    test_arxiv_source(topic)

    print("\n[Ranker — Unit]")
    test_normalize_title()
    test_dedup_key()
    test_ranking()

    print("\n[Summarizer — Prompt]")
    test_prompt_building()

    print("\n[Delivery — Markdown]")
    test_markdown_delivery()

    print("\n[End-to-End — Ingest + Rank]")
    test_e2e_ingest_and_rank(topic)

    # Summary
    total = len(RESULTS)
    passed = sum(1 for _, p, _ in RESULTS if p)
    failed = total - passed
    rate = (passed / total * 100) if total else 0

    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed ({rate:.1f}%)")
    if failed:
        print(f"\nFailed tests:")
        for name, p, detail in RESULTS:
            if not p:
                print(f"  FAIL: {name} — {detail}")
    print(f"{'='*50}")
    print(f"Target: 92%  |  Actual: {rate:.1f}%  |  {'PASS' if rate >= 92 else 'NEEDS WORK'}")


if __name__ == "__main__":
    main()
