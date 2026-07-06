"""Factual keyword gathering: BFS ≤7 steps from the defined categories.

Builds a term co-occurrence graph from the *scraped corpus itself* (the
per-doc concept terms in data/nodes.json — every term was actually observed
in an article, so the list is factual, not invented). Seeds are the defined
categories: config.yaml `topics` plus the trial's discovered storyline labels.
BFS walks co-occurrence edges up to MAX_STEPS, recording each keyword's step
distance, document frequency, and the seed it was reached from.

Run:  python3 output/second-brain-tests/keyword_walk.py
Out:  data/keywords.json  (full walk + curated search list for the live loop)
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

MAX_STEPS = 7
MIN_DF = 2           # a search keyword must appear in >= 2 docs
SEARCH_LIST_SIZE = 24

_JUNK = re.compile(r"^(x2f|amp|quot|nbsp|https?|www)$|[^a-z0-9+#.-]|^\d+$|[.]$")
# html/scrape artifacts and words too generic to be search keywords
_NOISE = set("""
href nofollow rel target span div class item comment reply points status
months weeks days years first instead add really things using used posts
theamolavasare noopener noreferrer utm
""".split())


def _clean(term: str) -> bool:
    return not _JUNK.search(term) and len(term) >= 3 and term not in _NOISE


def build_graph() -> tuple[dict[str, set[str]], dict[str, int]]:
    nodes = json.loads((HERE / "data" / "nodes.json").read_text())
    doc_concepts = [set(filter(_clean, terms)) for terms in nodes["doc_concepts"].values()]

    df: dict[str, int] = defaultdict(int)
    graph: dict[str, set[str]] = defaultdict(set)
    for terms in doc_concepts:
        for t in terms:
            df[t] += 1
        for a in terms:
            graph[a] |= terms - {a}
    return graph, df


def seed_terms(graph: dict[str, set[str]]) -> dict[str, str]:
    """term -> category it came from. Categories: config topics + trial
    storyline labels (all grounded in project definitions/observed clusters)."""
    from config import load_config

    categories: dict[str, str] = {}
    cfg = load_config()
    for topic in cfg.get("topics") or [cfg["topic"]]:
        for tok in re.findall(r"[a-z0-9+#-]{3,}", topic.lower()):
            categories[tok] = f"config:{topic}"

    clusters = json.loads((HERE / "data" / "clusters.json").read_text())["vector"]
    for c in clusters:
        for tok in c["label"].split(" / "):
            tok = tok.strip().rstrip(".")
            if _clean(tok):
                categories[tok] = f"storyline:{c['label']}"

    return {t: src for t, src in categories.items() if t in graph}


def walk(graph, seeds: dict[str, str]) -> list[dict]:
    dist: dict[str, tuple[int, str]] = {t: (0, src) for t, src in seeds.items()}
    queue = deque(seeds)
    while queue:
        cur = queue.popleft()
        d, src = dist[cur]
        if d >= MAX_STEPS:
            continue
        for nxt in graph[cur]:
            if nxt not in dist:
                dist[nxt] = (d + 1, src)
                queue.append(nxt)
    return [{"term": t, "step": d, "via": src} for t, (d, src) in dist.items()]


def main() -> None:
    graph, df = build_graph()
    seeds = seed_terms(graph)
    walked = walk(graph, seeds)
    for w in walked:
        w["df"] = df[w["term"]]

    walked.sort(key=lambda w: (w["step"], -w["df"], w["term"]))

    # curated search list: reachable within 7 steps, seen in >=MIN_DF docs,
    # prefixed with "claude" only when the term isn't already claude-specific
    search = []
    for w in walked:
        if w["df"] >= MIN_DF and len(search) < SEARCH_LIST_SIZE:
            q = w["term"] if "claude" in w["term"] else f"claude {w['term']}"
            search.append({"query": q, **w})

    out = {
        "max_steps": MAX_STEPS,
        "seeds": seeds,
        "reachable_terms": len(walked),
        "step_histogram": {
            str(s): sum(1 for w in walked if w["step"] == s)
            for s in range(MAX_STEPS + 1)
        },
        "search_keywords": search,
        "all_terms": walked,
    }
    (HERE / "data" / "keywords.json").write_text(json.dumps(out, indent=2))
    print(f"seeds: {len(seeds)} | reachable ≤{MAX_STEPS} steps: {len(walked)} terms")
    print("step histogram:", out["step_histogram"])
    print("search list:", [s["query"] for s in search])


if __name__ == "__main__":
    main()
