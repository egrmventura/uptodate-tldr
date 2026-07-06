"""Harness skeleton for the date-windowing study (see HYPOTHESES.md).

Implements the three window-assignment schemes over the second-brain trial
corpus and computes the primary metric (boundary_split_rate) for each, so the
study starts from a running end-to-end baseline.

Run:  python3 experiments/date_windowing/harness.py
      (requires output/second-brain-tests/data/articles.json from the trial;
       refetch support and the full metric suite are follow-up work)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "output" / "second-brain-tests"))

from topic_graph import load_docs, tfidf_vectors, vector_edges  # noqa: E402


# ---------- corpus ----------

def corpus() -> tuple[list[dict], list[tuple[int, int]]]:
    """Docs (with pub dates) + the similarity edges every scheme must try
    not to cut."""
    docs = load_docs()
    data = json.loads(
        (REPO / "output" / "second-brain-tests" / "data" / "articles.json").read_text()
    )["articles"]
    for d, a in zip(docs, data):
        d["published"] = date.fromisoformat(a["created_at"][:10])

    vectors = tfidf_vectors(docs)
    # same edge builder as the trial (threshold + top-k floor, 25 edges)
    edges = [(a, b) for a, b, _ in vector_edges(vectors)]
    return docs, edges


# ---------- the three schemes (doc -> window id) ----------

def assign_h1_sliding(docs: list[dict], window_days: int = 7) -> list[int]:
    """H1 — dynamic position, static magnitude: a new window opens at the
    first unassigned article (chronologically) and covers the next W days."""
    order = sorted(range(len(docs)), key=lambda i: docs[i]["published"])
    assign = [-1] * len(docs)
    window_id = -1
    window_end: date | None = None
    for i in order:
        d = docs[i]["published"]
        if window_end is None or d > window_end:
            window_id += 1
            window_end = d + timedelta(days=window_days - 1)
        assign[i] = window_id
    return assign


def assign_h2_calendar(docs: list[dict], window_days: int = 7,
                       anchor: date = date(2026, 1, 1)) -> list[int]:
    """H2 — static ranges: fixed buckets of W days from a calendar anchor."""
    return [ (d["published"] - anchor).days // window_days for d in docs ]


def assign_h3_gap(docs: list[dict], gap_days: int = 5) -> list[int]:
    """H3 — dynamic magnitude off the first article: a window stays open
    while articles keep arriving within `gap_days` of the last one; a quiet
    gap closes it. (Corpus-global skeleton; per-storyline anchoring is the
    follow-up refinement.)"""
    order = sorted(range(len(docs)), key=lambda i: docs[i]["published"])
    assign = [-1] * len(docs)
    window_id = 0
    last: date | None = None
    for i in order:
        d = docs[i]["published"]
        if last is not None and (d - last).days > gap_days:
            window_id += 1
        assign[i] = window_id
        last = d
    return assign


# ---------- primary metric ----------

def boundary_split_rate(assign: list[int], edges: list[tuple[int, int]]) -> float:
    """Fraction of similarity edges cut by a window boundary. Lower is better."""
    if not edges:
        return 0.0
    cut = sum(1 for i, j in edges if assign[i] != assign[j])
    return round(cut / len(edges), 4)


def describe(name: str, assign: list[int], edges) -> dict:
    sizes = defaultdict(int)
    for w in assign:
        sizes[w] += 1
    return {
        "scheme": name,
        "windows": len(sizes),
        "max_window_docs": max(sizes.values()),
        "boundary_split_rate": boundary_split_rate(assign, edges),
    }


def main() -> None:
    docs, edges = corpus()
    results = [
        describe("H1 sliding-7d", assign_h1_sliding(docs, 7), edges),
        describe("H2 calendar-7d", assign_h2_calendar(docs, 7), edges),
        describe("H3 gap-5d", assign_h3_gap(docs, 5), edges),
    ]
    print(f"corpus: {len(docs)} docs, {len(edges)} similarity edges (trial edge builder)\n")
    for r in results:
        print(json.dumps(r))
    (HERE / "baseline_results.json").write_text(json.dumps(results, indent=2))
    print(f"\nWrote {HERE / 'baseline_results.json'}")


if __name__ == "__main__":
    main()
