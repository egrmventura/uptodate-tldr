"""Offline validation for the second-brain seed trial artifacts.

Run:  python3 -m pytest output/second-brain-tests/test_second_brain.py -v
(Requires the pipeline to have been run once: fetch_articles.py →
scrape_summarize.py → topic_graph.py → seed_trial.py.)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

DATA = HERE / "data"


def _articles() -> dict:
    return json.loads((DATA / "articles.json").read_text())


# ---------- corpus invariants ----------

def test_weekly_coverage():
    arts = _articles()["articles"]
    weeks = {a["week_start"] for a in arts}
    assert len(weeks) == 26, f"expected 26 weeks, got {len(weeks)}"
    by_week = {}
    for a in arts:
        by_week.setdefault(a["week_start"], []).append(a)
    for week, members in by_week.items():
        assert 1 <= len(members) <= 3, f"week {week} has {len(members)} articles"


def test_relevance_filter():
    for a in _articles()["articles"]:
        t = a["title"].lower()
        assert "claude" in t or "anthropic" in t, f"off-topic: {a['title']!r}"


def test_summaries_compact():
    for a in _articles()["articles"]:
        assert a["summary"], f"empty summary: {a['title']!r}"
        assert len(a["summary"]) <= 600, f"summary too long: {a['title']!r}"


def test_dates_within_window():
    for a in _articles()["articles"]:
        d = date.fromisoformat(a["created_at"][:10])
        assert date(2026, 1, 1) <= d <= date(2026, 6, 30), a["created_at"]


# ---------- graph invariants ----------

def test_graph_artifacts_consistent():
    nodes = json.loads((DATA / "nodes.json").read_text())
    e_vec = json.loads((DATA / "edges_vector.json").read_text())
    e_con = json.loads((DATA / "edges_concept.json").read_text())
    n = len(nodes["documents"])
    for a, b, w in e_vec + e_con:
        assert 0 <= a < b < n, f"bad edge ({a},{b})"
        assert 0 < w <= 1.0001, f"bad weight {w}"


def test_clusters_are_multidoc_and_labeled():
    clusters = json.loads((DATA / "clusters.json").read_text())
    for method in ("vector", "concept"):
        for c in clusters[method]:
            assert c["size"] >= 2
            assert c["label"].strip()
            assert len(c["titles"]) == c["size"]


def test_metrics_recorded():
    m = json.loads((DATA / "metrics.json").read_text())
    for key in ("edge_jaccard", "pairwise_agreement",
                "vector_temporal_span_weeks", "concept_temporal_span_weeks"):
        assert key in m


# ---------- seed-trial invariants (backfill correctness + idempotency) ----------

def test_seed_db_periods_use_publication_dates():
    conn = sqlite3.connect(DATA / "analyses-trial.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT topic, period_start, period_end FROM analyses").fetchall()
    conn.close()
    assert rows, "trial db is empty — run seed_trial.py first"
    for r in rows:
        start = date.fromisoformat(r["period_start"][:10])
        end = date.fromisoformat(r["period_end"][:10])
        assert start <= end
        # periods must fall inside the article window, not on the run date
        assert date(2026, 1, 1) <= start <= date(2026, 6, 30), dict(r)


def test_seed_db_unique_constraint_holds():
    conn = sqlite3.connect(DATA / "analyses-trial.db")
    dupes = conn.execute("""
        SELECT topic, period_start, period_end, COUNT(*) c FROM analyses
        GROUP BY topic, period_start, period_end HAVING c > 1
    """).fetchall()
    conn.close()
    assert dupes == [], f"duplicate (topic, period) rows: {dupes}"


def test_seed_rerun_is_idempotent():
    """Re-save the same analyses through the real Store; row count must not grow."""
    from store import Store
    from seed_trial import build_analyses, count_rows

    store = Store(DATA / "analyses-trial.db")
    before = count_rows(store)
    store.save_run(build_analyses(), date.today(), is_backfill=True)
    after = count_rows(store)
    assert after == before, f"idempotency violated: {before} -> {after}"
