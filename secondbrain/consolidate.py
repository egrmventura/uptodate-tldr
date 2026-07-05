"""Batch consolidation: re-cluster the live corpus into coherent topics.

The live loop groups incrementally (cosine vs running centroids), which
fragments — the 249-article corpus ended at 83 groups, 50 of them singletons.
This pass re-clusters the *whole* corpus with the study-validated batch
method (similarity edges + connected components) and writes:

  consolidated_groups.json   the new topic groups (label, member urls, span)
  doc_vectors.json           per-article vectors — the "embeddings column";
                             consumed by retrieval, upgradeable to API
                             embeddings without schema change
  consolidation_log.jsonl    APPEND-ONLY change events (url, old_group,
                             new_group, run stamp) — the memory-revision
                             history a future dbt snapshot would consume

Run:  python3 -m secondbrain.consolidate [--corpus PATH] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from secondbrain import vectors as V

DEFAULT_CORPUS = Path("output/second-brain-tests/live/corpus.json")
DEFAULT_OLD_GROUPS = Path("output/second-brain-tests/live/groups.json")
DEFAULT_OUT = Path("output/second-brain-tests/consolidated")

# Relevance criteria — same as the trial fetcher (fetch_articles.py):
# title mentions claude/anthropic AND at least one capability-surface term.
CAPABILITY_TERMS = (
    "tool", "mcp", "code", "agent", "skill", "plugin", "api", "sdk",
    "integration", "extension", "connector", "computer use", "browser",
    "hook", "slash command", "artifact", "memory",
)
# A component larger than this is a chained blob (the clustering analog of
# the windowing study's runaway H3 window) and gets divisively re-split at
# progressively higher thresholds.
MAX_GROUP_SIZE = 12
SPLIT_FACTOR = 1.3
MAX_SPLIT_THRESHOLD = 0.6


def doc_text(article: dict) -> str:
    return f"{article.get('hn_title', article.get('title', ''))} {article.get('summary', '')}"


def is_relevant(article: dict) -> bool:
    t = (article.get("hn_title") or article.get("title") or "").lower()
    if "claude" not in t and "anthropic" not in t:
        return False
    return any(term in t for term in CAPABILITY_TERMS)


def _components_at(indices: list[int], sims: dict, threshold: float) -> list[list[int]]:
    local = {g: k for k, g in enumerate(indices)}
    edges = [
        (local[i], local[j], s)
        for (i, j), s in sims.items()
        if i in local and j in local and s >= threshold
    ]
    assign = V.connected_components(len(indices), edges)
    out: dict[int, list[int]] = {}
    for k, g in enumerate(indices):
        out.setdefault(assign[k], []).append(g)
    return list(out.values())


def _divisive(indices: list[int], sims: dict, threshold: float) -> list[list[int]]:
    """Recursively split an oversized component at increasing thresholds."""
    result: list[list[int]] = []
    for comp in _components_at(indices, sims, threshold):
        if len(comp) > MAX_GROUP_SIZE and threshold < MAX_SPLIT_THRESHOLD:
            result += _divisive(comp, sims, threshold * SPLIT_FACTOR)
        else:
            result.append(comp)
    return result


def consolidate(articles: list[dict]) -> tuple[list[dict], list[dict[str, float]]]:
    """Cluster articles; returns (groups, per-doc vectors for ALL articles).

    Nothing is dropped: off-topic articles are filed into a holding group
    (`"off_topic": true`), genuine singletons stay as size-1 groups flagged
    `"singleton": true` — a second brain forgets nothing, it files loners
    and noise separately.
    """
    from itertools import combinations

    vecs = V.vectorize_corpus([doc_text(a) for a in articles])

    rel_idx = [i for i, a in enumerate(articles) if is_relevant(a)]
    off_idx = [i for i in range(len(articles)) if i not in set(rel_idx)]

    sims = {
        (i, j): V.cosine(vecs[i], vecs[j])
        for i, j in combinations(rel_idx, 2)
    }
    # recall-friendly first pass (threshold + top-k floor), then divisive
    # re-split of anything blob-sized
    edges = [(i, j, s) for (i, j), s in sims.items() if s >= V.EDGE_THRESHOLD]
    for i in rel_idx:
        mine = sorted(
            ((s, (a, b)) for (a, b), s in sims.items() if i in (a, b)),
            reverse=True,
        )[:V.TOP_K]
        for s, (a, b) in mine:
            if s >= V.TOP_K_FLOOR:
                edges.append((a, b, s))

    local = {g: k for k, g in enumerate(rel_idx)}
    assign = V.connected_components(
        len(rel_idx), [(local[a], local[b], s) for a, b, s in edges]
    )
    first_pass: dict[int, list[int]] = {}
    for k, g in enumerate(rel_idx):
        first_pass.setdefault(assign[k], []).append(g)

    clusters: list[list[int]] = []
    for comp in first_pass.values():
        if len(comp) > MAX_GROUP_SIZE:
            clusters += _divisive(comp, sims, V.EDGE_THRESHOLD * SPLIT_FACTOR)
        else:
            clusters.append(comp)

    groups = []
    for members in sorted(clusters, key=len, reverse=True):
        dates = sorted(articles[m]["published_at"][:10] for m in members)
        groups.append({
            "label": V.label_for([vecs[m] for m in members]),
            "size": len(members),
            "singleton": len(members) == 1,
            "off_topic": False,
            "urls": [articles[m]["url"] for m in members],
            "member_indices": members,
            "period": [dates[0], dates[-1]],
        })

    if off_idx:
        dates = sorted(articles[m]["published_at"][:10] for m in off_idx)
        groups.append({
            "label": "(off-topic holding)",
            "size": len(off_idx),
            "singleton": False,
            "off_topic": True,
            "urls": [articles[m]["url"] for m in off_idx],
            "member_indices": off_idx,
            "period": [dates[0], dates[-1]],
        })
    return groups, vecs


def change_events(articles, old_groups: dict, new_groups: list[dict]) -> list[dict]:
    """One event per article whose group label changed (or that is newly filed)."""
    old_label_by_url: dict[str, str] = {}
    for g in old_groups.values():
        for url in g.get("urls", []):
            old_label_by_url[url] = g.get("label", "?")

    stamp = datetime.now(timezone.utc).isoformat()
    events = []
    for g in new_groups:
        for url in g["urls"]:
            old = old_label_by_url.get(url)
            if old != g["label"]:
                events.append({
                    "at": stamp, "url": url,
                    "old_group": old, "new_group": g["label"],
                })
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch consolidation pass")
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--old-groups", type=Path, default=DEFAULT_OLD_GROUPS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    articles = json.loads(args.corpus.read_text())
    old_groups = json.loads(args.old_groups.read_text()) if args.old_groups.exists() else {}

    groups, vecs = consolidate(articles)
    events = change_events(articles, old_groups, groups)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "consolidated_groups.json").write_text(json.dumps({
        "consolidated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_size": len(articles),
        "groups": groups,
    }, indent=2))
    (args.out / "doc_vectors.json").write_text(json.dumps(
        [{"url": a["url"], "vector": v} for a, v in zip(articles, vecs)]
    ))
    with (args.out / "consolidation_log.jsonl").open("a") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    multi = sum(1 for g in groups if not g["singleton"])
    singles = len(groups) - multi
    print(f"consolidated: {len(articles)} articles → {len(groups)} groups "
          f"({multi} multi-doc, {singles} singletons) | {len(events)} change events | "
          f"out={args.out}")


if __name__ == "__main__":
    main()
