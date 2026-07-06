"""Tests for the secondbrain layer (milestones M1–M4 of the launch plan).

Offline throughout — no network, no LLM. Run:
    python3 -m pytest test_secondbrain.py -v
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sources.base import Item


def _item(day: int, title: str = "t", month: int = 1) -> Item:
    return Item(source="hn", title=title, url=f"https://x/{month}-{day}-{title}",
                score=1, published_at=datetime(2026, month, day, tzinfo=timezone.utc),
                summary_raw="s")


# ---------- M1: H1 sliding windowing ----------

def test_sliding_windows_basic():
    from secondbrain.windowing import sliding_windows
    items = [_item(1), _item(5), _item(14), _item(15), _item(29)]
    buckets = sliding_windows(items, 14)
    # window 1 opens Jan 1, spans through Jan 14 → items 1,5,14
    # window 2 opens Jan 15 → item 15 (Jan 29 is beyond Jan 15+13=Jan 28)
    # window 3 opens Jan 29
    assert [len(b) for b in buckets] == [3, 1, 1]


def test_sliding_windows_anchor_free():
    """Shifting every date by the same offset must shift windows identically —
    the anchor-invariance property that won H1 the study."""
    from secondbrain.windowing import sliding_windows
    base = [_item(d) for d in (1, 5, 14, 15, 29)]
    shifted = [Item(source=i.source, title=i.title, url=i.url, score=i.score,
                    published_at=i.published_at + timedelta(days=3),
                    summary_raw=i.summary_raw) for i in base]
    shape = lambda items: [len(b) for b in sliding_windows(items, 14)]
    assert shape(base) == shape(shifted)


def test_sliding_windows_edges():
    from secondbrain.windowing import sliding_windows
    assert sliding_windows([], 14) == []
    one = [_item(7)]
    assert [len(b) for b in sliding_windows(one, 14)] == [1]
    try:
        sliding_windows(one, 0)
        assert False, "window_days=0 must raise"
    except ValueError:
        pass


def test_window_bounds_from_publication_dates():
    from secondbrain.windowing import sliding_windows, window_bounds
    items = [_item(3), _item(1), _item(9)]
    (bucket,) = sliding_windows(items, 14)
    start, end = window_bounds(bucket)
    assert start == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 9, tzinfo=timezone.utc)


# ---------- M2: consolidation ----------

def _fake_article(i: int, title: str, summary: str, day: int = 1) -> dict:
    return {"url": f"https://x/{i}", "hn_title": title, "summary": summary,
            "published_at": f"2026-06-{day:02d}T00:00:00+00:00"}


def _synthetic_corpus() -> list[dict]:
    a = [_fake_article(i, f"Claude Code memory tools update {i}",
                       "claude memory skills persistence recall notes vault", day=i + 1)
         for i in range(3)]
    b = [_fake_article(10 + i, f"Claude MCP plugin server release {i}",
                       "mcp server plugin protocol transport integration release", day=i + 1)
         for i in range(3)]
    noise = [_fake_article(20, "Rapunzel story generator hits front page",
                           "fairy tale hair tower story generator", day=9)]
    lone = [_fake_article(30, "Claude Code quota changes announced",
                          "quota limits billing tokens usage caps", day=12)]
    return a + b + noise + lone


def test_consolidate_clusters_and_files_everything():
    from secondbrain.consolidate import consolidate
    corpus = _synthetic_corpus()
    groups, vecs = consolidate(corpus)

    # every article filed exactly once
    filed = [u for g in groups for u in g["urls"]]
    assert sorted(filed) == sorted(a["url"] for a in corpus)
    assert len(vecs) == len(corpus)

    multi = [g for g in groups if not g["singleton"] and not g["off_topic"]]
    assert len(multi) == 2, [g["label"] for g in multi]
    sizes = sorted(g["size"] for g in multi)
    assert sizes == [3, 3]

    # the noise article (no claude in title) is in the off-topic holding group
    off = [g for g in groups if g["off_topic"]]
    assert len(off) == 1 and "https://x/20" in off[0]["urls"]

    # the lone relevant article survives as a flagged singleton
    singles = [g for g in groups if g["singleton"]]
    assert any("https://x/30" in g["urls"] for g in singles)


def test_consolidate_no_runaway_groups():
    from secondbrain.consolidate import MAX_GROUP_SIZE, consolidate
    corpus = _synthetic_corpus()
    groups, _ = consolidate(corpus)
    for g in groups:
        if not g["off_topic"]:
            assert g["size"] <= MAX_GROUP_SIZE, f"runaway group: {g['label']} ({g['size']})"


def test_consolidate_change_events():
    from secondbrain.consolidate import change_events, consolidate
    corpus = _synthetic_corpus()
    groups, _ = consolidate(corpus)
    old = {"g0": {"label": "old-label", "urls": [corpus[0]["url"]]}}
    events = change_events(corpus, old, groups)
    # article 0 moved from old-label to its new cluster label → event exists
    moved = [e for e in events if e["url"] == corpus[0]["url"]]
    assert len(moved) == 1 and moved[0]["old_group"] == "old-label"
    # events are append-only records with the required keys
    for e in events:
        assert set(e) == {"at", "url", "old_group", "new_group"}


# ---------- M4: retrieval ----------

def _retriever(tmp_path: Path):
    import json
    from secondbrain.consolidate import consolidate
    from secondbrain.retrieval import Retriever

    corpus = _synthetic_corpus()
    groups, vecs = consolidate(corpus)

    (tmp_path / "corpus.json").write_text(json.dumps(corpus))
    (tmp_path / "vectors.json").write_text(json.dumps(
        [{"url": a["url"], "vector": v} for a, v in zip(corpus, vecs)]))
    (tmp_path / "groups.json").write_text(json.dumps({"groups": groups}))
    return Retriever(tmp_path / "vectors.json", tmp_path / "corpus.json",
                     tmp_path / "groups.json")


def test_retrieval_relevant_and_cited(tmp_path):
    r = _retriever(tmp_path)
    hits = r.search("memory skills persistence")
    assert hits, "no hits for an on-corpus query"
    # top hit is from the memory cluster, and every hit is fully cited
    assert "memory" in hits[0].title.lower()
    for h in hits:
        assert h.url.startswith("https://")
        assert h.published and h.score > 0 and h.group


def test_retrieval_ranking_and_noise_floor(tmp_path):
    r = _retriever(tmp_path)
    hits = r.search("mcp plugin server protocol")
    assert hits and "mcp" in hits[0].title.lower()
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    # nonsense query yields nothing above the noise floor
    assert r.search("zzqx qqzz vvxx") == []


# ---------- P2: category-driven collection ----------

def test_collect_category_tagging_dedupe_rotation():
    from unittest.mock import patch
    from secondbrain.collect import collect_category

    now = datetime.now(timezone.utc)

    def fake_ingest(query, sources_config):
        return [
            Item(source="hn", title=f"{query} story", url=f"https://x/{query}",
                 score=5, published_at=now, summary_raw="raw excerpt"),
            Item(source="rss", title="duplicate", url="https://x/known",
                 score=0, published_at=now, summary_raw="dup"),
        ]

    known = {"https://x/known"}
    with patch("main.ingest", side_effect=fake_ingest), \
         patch("scraper.scrape", return_value=None):
        records, cursor = collect_category(
            category="Data Engineering",
            queries=["dbt", "spark", "airflow"],
            cursor=1,
            known_urls=known,
            sources_config={},
            max_new=8,
            fetched_at=now.isoformat(),
        )

    # rotation: cursor 1 picks queries[1], queries[2]; advances to 0 (mod 3)
    assert [r["query"] for r in records] == ["spark", "airflow"]
    assert cursor == 0
    # tagging + citation fields on every record
    for r in records:
        assert r["category"] == "Data Engineering"
        assert r["url"].startswith("https://")
        assert r["summary"]  # scrape=None → falls back to excerpt
        assert r["scraped"] is False
    # dedupe: the known URL was skipped both times
    assert all(r["url"] != "https://x/known" for r in records)


def test_collect_respects_max_new_cap():
    from unittest.mock import patch
    from secondbrain.collect import collect_category

    now = datetime.now(timezone.utc)

    def flood(query, sources_config):
        return [Item(source="hn", title=f"s{i}", url=f"https://x/{query}/{i}",
                     score=1, published_at=now, summary_raw="e") for i in range(20)]

    with patch("main.ingest", side_effect=flood), \
         patch("scraper.scrape", return_value=None):
        records, _ = collect_category("C", ["q1", "q2"], 0, set(), {}, 5, now.isoformat())
    assert len(records) == 5


# ---------- P4: freshness checker ----------

def test_check_input_validation():
    import importlib
    check_mod = importlib.import_module("api.check")
    assert check_mod.check({})[0] == 400
    assert check_mod.check({"url": "ftp://nope"})[0] == 400


def test_check_retrieval_and_mocked_verdict():
    import importlib
    import pytest
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    if not Path("snapshots/search_index.json").exists():
        pytest.skip("snapshots not present")
    check_mod = importlib.import_module("api.check")

    article = ("Claude Code memory skills persistence: how to configure the "
               "memory vault and session recall for daily driver workflows.")
    evidence = check_mod.retrieve_evidence(article)
    assert evidence, "expected on-topic evidence for a memory/skills article"
    assert all(e["url"] or e["kind"] == "timeline" for e in evidence)

    good = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps({
        "verdict": "partially_outdated",
        "summary": "Some claims superseded.",
        "reasons": ["Newer memory tooling exists per evidence 0"],
        "evidence_indices": [0],
    }))])
    client = MagicMock()
    client.messages.create.return_value = good
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("anthropic.Anthropic", return_value=client):
        status, body = check_mod.check({"text": article})
    assert status == 200
    assert body["verdict"] == "partially_outdated"
    assert body["evidence"] and body["evidence"][0]["url"]


def test_check_unknown_when_no_coverage():
    import importlib
    import pytest
    if not Path("snapshots/search_index.json").exists():
        pytest.skip("snapshots not present")
    check_mod = importlib.import_module("api.check")
    status, body = check_mod.check({"text": "zzqx qqzz vvxx nothing relevant here at all"})
    assert status == 200 and body["verdict"] == "unknown"


def test_check_rejects_invalid_model_verdict():
    import importlib
    import pytest
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch
    if not Path("snapshots/search_index.json").exists():
        pytest.skip("snapshots not present")
    check_mod = importlib.import_module("api.check")

    bad = SimpleNamespace(content=[SimpleNamespace(type="text",
                                                   text='{"verdict": "sideways"}')])
    client = MagicMock()
    client.messages.create.return_value = bad
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("anthropic.Anthropic", return_value=client):
        status, body = check_mod.check({"text": "claude code memory skills tools"})
    assert status == 500 and "verdict" in body["error"]


# ---------- M5: serving + site ----------

def test_api_routes():
    """Route handling: param validation and 404s never require live data;
    data-backed routes are exercised when artifacts exist."""
    import pytest
    from secondbrain.serve import Api, handle_path
    api = Api()

    status, body = handle_path(api, "/timeline")
    assert (status, body["error"]) == (400, "missing ?topic=")
    status, _ = handle_path(api, "/search")
    assert status == 400
    status, _ = handle_path(api, "/definitely-not-a-route")
    assert status == 404

    if not Path("output/second-brain-tests/consolidated/doc_vectors.json").exists():
        pytest.skip("live artifacts not present for data-backed routes")
    status, body = handle_path(api, "/health")
    assert status == 200 and body["status"] == "ok" and body["docs"] > 0
    status, hits = handle_path(api, "/search?q=claude+memory&k=3")
    assert status == 200 and len(hits) <= 3
    for h in hits:
        assert h["url"].startswith("http")


def test_site_builds_embedded_and_dataurl(tmp_path):
    import pytest
    if not Path("snapshots/meta.json").exists():
        pytest.skip("snapshots not present — run export_snapshots first")
    from secondbrain.site_build import build

    # embedded mode: snapshots inlined, citations everywhere
    out = build(tmp_path / "embedded.html")
    page = out.read_text()
    assert "<title>UpToDate — AI & Data Engineering Timelines</title>" in page
    assert "const EMBEDDED={" in page
    assert page.count("https://") > 50
    for marker in ('id="q"', 'id="checker"', 'id="tabs"', "/api/check"):
        assert marker in page, f"missing {marker}"

    # data-url mode: small page, no embedded data, fetches the base URL
    out2 = build(tmp_path / "remote.html", data_url="https://blob.example/snap/")
    page2 = out2.read_text()
    assert 'const DATA_URL="https://blob.example/snap"' in page2
    assert "const EMBEDDED=null" in page2
    assert out2.stat().st_size < 30_000, "data-url page should be small"


def test_snapshot_export_schema(tmp_path):
    import pytest
    if not Path("output/second-brain-tests/consolidated/doc_vectors.json").exists():
        pytest.skip("live artifacts not present")
    import json
    from secondbrain.export_snapshots import export
    meta = export(tmp_path)
    for name in ("topics", "timelines", "search_index", "meta"):
        assert (tmp_path / f"{name}.json").exists()
    topics = json.loads((tmp_path / "topics.json").read_text())
    assert meta["storylines"] == len(topics) > 0
    for t in topics:
        assert set(t) == {"label", "size", "period", "category", "urls"}
    index = json.loads((tmp_path / "search_index.json").read_text())
    assert meta["articles"] == len(index)
    for row in index[:5]:
        assert row["u"].startswith("http") and row["v"]
    timelines = json.loads((tmp_path / "timelines.json").read_text())
    assert meta["analyses"] == sum(len(v) for v in timelines.values())


def test_consolidated_artifacts_on_disk():
    """Integration check against the real consolidated corpus (skips if the
    consolidation pass hasn't been run in this checkout)."""
    import pytest
    out = Path("output/second-brain-tests/consolidated/consolidated_groups.json")
    if not out.exists():
        pytest.skip("consolidation artifacts not present")
    import json
    data = json.loads(out.read_text())
    groups = data["groups"]
    filed = [u for g in groups for u in g["urls"]]
    assert len(filed) == len(set(filed)) == data["corpus_size"]
    from secondbrain.consolidate import MAX_GROUP_SIZE
    for g in groups:
        if not g["off_topic"]:
            assert g["size"] <= MAX_GROUP_SIZE
