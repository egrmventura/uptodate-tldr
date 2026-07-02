"""Full metric study for the date-windowing hypotheses (HYPOTHESES.md).

Grid: H1/H2 at W ∈ {7,14,21} days, H3 at gap ∈ {3,5,7} days. Per config:
  boundary_split_rate   fraction of similarity edges cut (primary, lower=better)
  cohesion / separation mean intra- vs inter-window pairwise cosine
  anchor_churn          H2 only: pair-assignment flips when the calendar anchor
                        shifts ±1..3d (H1/H3 are anchor-free by construction)
  first_doc_churn       pair flips after dropping the chronologically first doc
                        (probes H3's "anchored off first article" fragility)
  storyline table       distinct windows each known storyline spans (intuitive
                        metric: fewer windows = storyline kept whole)

Run:  python3 experiments/date_windowing/study.py
Out:  study_results.json (FINDINGS.md narrates the results)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "output" / "second-brain-tests"))

from harness import assign_h1_sliding, assign_h2_calendar, assign_h3_gap, corpus  # noqa: E402
from topic_graph import cosine, load_docs, tfidf_vectors  # noqa: E402


def pair_sets(assign: list[int]) -> set[tuple[int, int]]:
    return {(i, j) for i, j in combinations(range(len(assign)), 2) if assign[i] == assign[j]}


def churn(base: list[int], alt: list[int], n: int) -> float:
    """Fraction of doc pairs whose same-window status flips between runs."""
    flips = len(pair_sets(base) ^ pair_sets(alt))
    return round(flips / (n * (n - 1) // 2), 4)


def cohesion_separation(assign: list[int], vectors) -> tuple[float, float]:
    intra, inter = [], []
    for i, j in combinations(range(len(assign)), 2):
        (intra if assign[i] == assign[j] else inter).append(cosine(vectors[i], vectors[j]))
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0
    return mean(intra), mean(inter)


def evaluate(name: str, assigner, docs, edges, vectors, anchor_variants=None) -> dict:
    assign = assigner(docs)
    n = len(docs)
    coh, sep = cohesion_separation(assign, vectors)
    sizes = defaultdict(int)
    for w in assign:
        sizes[w] += 1

    cut = sum(1 for i, j in edges if assign[i] != assign[j])

    # first-doc churn: drop the chronologically first doc, re-assign the rest
    first = min(range(n), key=lambda i: docs[i]["published"])
    rest = [d for k, d in enumerate(docs) if k != first]
    alt_assign = assigner(rest)
    # map back: compare pair status among surviving docs
    idx = [k for k in range(n) if k != first]
    base_pairs = {(a, b) for a, b in combinations(range(len(idx)), 2)
                  if assign[idx[a]] == assign[idx[b]]}
    alt_pairs = pair_sets(alt_assign)
    fd_churn = round(len(base_pairs ^ alt_pairs) / (len(idx) * (len(idx) - 1) // 2), 4)

    result = {
        "config": name,
        "windows": len(sizes),
        "max_window_docs": max(sizes.values()),
        "boundary_split_rate": round(cut / len(edges), 4),
        "cohesion": coh,
        "separation": sep,
        "cohesion_ratio": round(coh / sep, 2) if sep else None,
        "first_doc_churn": fd_churn,
    }

    if anchor_variants:  # H2 anchor sensitivity
        churns = [churn(assign, anchor_variants[d](docs), n) for d in anchor_variants]
        result["anchor_churn_mean"] = round(sum(churns) / len(churns), 4)
    else:
        result["anchor_churn_mean"] = 0.0  # anchor-free by construction
    return result


def storyline_table(docs, configs: dict[str, list[int]]) -> list[dict]:
    clusters = json.loads(
        (REPO / "output" / "second-brain-tests" / "data" / "clusters.json").read_text()
    )["vector"]
    title_to_idx = {d["title"]: d["id"] for d in docs}
    rows = []
    for c in clusters:
        if c["size"] < 4:
            continue
        members = [title_to_idx[t] for t in c["titles"]]
        row = {"storyline": c["label"], "docs": c["size"],
               "weeks_span": len(c["weeks"])}
        for name, assign in configs.items():
            row[name] = len({assign[m] for m in members})
        rows.append(row)
    return rows


def main() -> None:
    docs, edges = corpus()
    vectors = tfidf_vectors(load_docs())

    grid = {
        "H1-sliding-7d":  lambda ds: assign_h1_sliding(ds, 7),
        "H1-sliding-14d": lambda ds: assign_h1_sliding(ds, 14),
        "H1-sliding-21d": lambda ds: assign_h1_sliding(ds, 21),
        "H2-calendar-7d":  lambda ds: assign_h2_calendar(ds, 7),
        "H2-calendar-14d": lambda ds: assign_h2_calendar(ds, 14),
        "H2-calendar-21d": lambda ds: assign_h2_calendar(ds, 21),
        "H3-gap-3d": lambda ds: assign_h3_gap(ds, 3),
        "H3-gap-5d": lambda ds: assign_h3_gap(ds, 5),
        "H3-gap-7d": lambda ds: assign_h3_gap(ds, 7),
    }

    results = []
    for name, fn in grid.items():
        anchors = None
        if name.startswith("H2"):
            w = int(name.split("-")[-1].rstrip("d"))
            anchors = {
                d: (lambda ds, _d=d, _w=w: assign_h2_calendar(
                    ds, _w, anchor=date(2026, 1, 1) + timedelta(days=_d)))
                for d in (-3, -1, 1, 3)
            }
        results.append(evaluate(name, fn, docs, edges, vectors, anchors))

    table = storyline_table(docs, {name: fn(docs) for name, fn in grid.items()})

    out = {"grid": results, "storylines": table,
           "corpus": {"docs": len(docs), "edges": len(edges)}}
    (HERE / "study_results.json").write_text(json.dumps(out, indent=2))

    hdr = ["config", "windows", "boundary_split_rate", "cohesion_ratio",
           "anchor_churn_mean", "first_doc_churn", "max_window_docs"]
    print("\t".join(hdr))
    for r in results:
        print("\t".join(str(r[h]) for h in hdr))
    print("\nstorylines (windows spanned per config → fewer = kept whole):")
    print(json.dumps(table, indent=1))


if __name__ == "__main__":
    main()
