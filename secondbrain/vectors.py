"""Document vectors for the second brain — pure-Python TF-IDF.

This is the corpus-wide vector representation validated by the topic-relation
study (vectors win recall; concept terms win labels). It deliberately has no
heavy dependencies; swap `vectorize_corpus` for an embedding-API call later
without touching consumers (consolidate, retrieval) — they only rely on
"dict[str, float] per doc + cosine".
"""

from __future__ import annotations

import math
import re
from collections import Counter
from itertools import combinations

_TOKEN = re.compile(r"[a-z][a-z0-9+#.-]{2,}")
_STOP = set("""
the and for with that this from are was were has have had you your not can
will its it's our their they them then than but all any out use using used
new now get more most into over under about after before also just like one
two how what when where which who why been being does did doing don't a an
of in on at to is it as by be or we he she his her him say says said its
x2f amp quot nbsp https http www href nofollow noopener noreferrer
""".split())

# Study-validated relation parameters (output/second-brain-tests/topic_graph.py)
EDGE_THRESHOLD = 0.18
TOP_K = 3
TOP_K_FLOOR = EDGE_THRESHOLD * 0.5
LABEL_TERMS = 3


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def vectorize_corpus(texts: list[str]) -> list[dict[str, float]]:
    """L2-normalized TF-IDF vectors; near-ubiquitous terms (df >= 60%) dropped."""
    tokenized = [tokenize(t) for t in texts]
    df: Counter = Counter()
    for toks in tokenized:
        df.update(set(toks))
    n = max(len(texts), 1)

    vectors: list[dict[str, float]] = []
    for toks in tokenized:
        tf = Counter(toks)
        vec = {
            term: (1 + math.log(c)) * math.log(n / df[term])
            for term, c in tf.items()
            if df[term] < n * 0.6
        }
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        vectors.append({t: w / norm for t, w in vec.items()})
    return vectors


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(b) < len(a):
        a, b = b, a
    return sum(w * b.get(t, 0.0) for t, w in a.items())


def similarity_edges(vectors: list[dict[str, float]]) -> list[tuple[int, int, float]]:
    """Edges = pairs above EDGE_THRESHOLD, plus each doc's TOP_K neighbors at
    half-threshold (so weakly-connected docs still attach somewhere)."""
    n = len(vectors)
    sims: dict[tuple[int, int], float] = {}
    for i, j in combinations(range(n), 2):
        s = cosine(vectors[i], vectors[j])
        if s > 0:
            sims[(i, j)] = s

    edges = {p for p, s in sims.items() if s >= EDGE_THRESHOLD}
    for i in range(n):
        mine = sorted(
            ((s, (a, b)) for (a, b), s in sims.items() if i in (a, b)),
            reverse=True,
        )[:TOP_K]
        for s, pair in mine:
            if s >= TOP_K_FLOOR:
                edges.add(pair)
    return sorted((a, b, round(sims[(a, b)], 4)) for a, b in edges)


def connected_components(n: int, edges: list[tuple[int, int, float]]) -> list[int]:
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _ in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return [find(i) for i in range(n)]


def label_for(member_vectors: list[dict[str, float]], k: int = LABEL_TERMS) -> str:
    """Concept-node style label: top shared TF-IDF terms across members."""
    counts: Counter = Counter()
    for vec in member_vectors:
        for term, w in sorted(vec.items(), key=lambda kv: kv[1], reverse=True)[:8]:
            counts[term] += w
    return " / ".join(t for t, _ in counts.most_common(k)) or "(unlabeled)"
