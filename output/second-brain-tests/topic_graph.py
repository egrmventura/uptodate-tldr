"""Topic-relation experiments: connect articles into a "second brain" graph.

Tests two methods of identifying topics and relating articles, entirely
offline (pure Python — no sklearn/numpy/LLM):

  Method A — VECTORS: TF-IDF document vectors + cosine similarity.
      Edges = doc pairs with cosine >= VEC_THRESHOLD (plus each doc's top-k
      neighbors). Topics emerge as connected components.

  Method B — CONCEPT NODES: each doc's top TF-IDF terms become explicit
      concept nodes; docs sharing concepts are linked through them (a
      bipartite doc–concept graph projected to doc–doc edges weighted by
      Jaccard overlap of concept sets).

Both cluster the same corpus; compare_methods() measures edge overlap and
pairwise cluster agreement, and checks temporal coherence (topic clusters
should span multiple weeks if they track a real ongoing storyline).

Run:  python3 output/second-brain-tests/topic_graph.py
In:   data/articles.json
Out:  data/nodes.json, data/edges_vector.json, data/edges_concept.json,
      data/clusters.json, data/metrics.json
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent

VEC_THRESHOLD = 0.18   # min cosine for a vector edge
VEC_TOP_K = 3          # always keep each doc's k nearest neighbors
CONCEPTS_PER_DOC = 8   # top TF-IDF terms promoted to concept nodes
CONCEPT_THRESHOLD = 0.12  # min Jaccard overlap for a concept edge

_TOKEN = re.compile(r"[a-z][a-z0-9+#.-]{2,}")
_STOP = set("""
the and for with that this from are was were has have had you your not can
will its it's our their they them then than but all any out use using used
new now get more most into over under about after before also just like one
two how what when where which who why been being does did doing don't a an
of in on at to is it as by be or we he she his her him say says said
""".split())


# ---------- corpus ----------

def load_docs() -> list[dict]:
    data = json.loads((HERE / "data" / "articles.json").read_text())
    docs = []
    for i, a in enumerate(data["articles"]):
        docs.append({
            "id": i,
            "title": a["title"],
            "url": a["url"],
            "week": a["week_start"],
            "text": f"{a['title']} {a.get('summary', '')}",
        })
    return docs


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


# ---------- tf-idf ----------

def tfidf_vectors(docs: list[dict]) -> list[dict[str, float]]:
    tokenized = [tokenize(d["text"]) for d in docs]
    df: Counter = Counter()
    for toks in tokenized:
        df.update(set(toks))
    n = len(docs)

    vectors = []
    for toks in tokenized:
        tf = Counter(toks)
        vec = {}
        for term, count in tf.items():
            if df[term] >= n * 0.6:   # near-ubiquitous terms carry no signal
                continue
            vec[term] = (1 + math.log(count)) * math.log(n / df[term])
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        vectors.append({t: w / norm for t, w in vec.items()})
    return vectors


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(b) < len(a):
        a, b = b, a
    return sum(w * b.get(t, 0.0) for t, w in a.items())


# ---------- Method A: vector edges ----------

def vector_edges(vectors: list[dict[str, float]]) -> list[tuple[int, int, float]]:
    n = len(vectors)
    sims = {}
    for i, j in combinations(range(n), 2):
        s = cosine(vectors[i], vectors[j])
        if s > 0:
            sims[(i, j)] = s

    edges = {p for p, s in sims.items() if s >= VEC_THRESHOLD}
    # guarantee top-k connectivity so no doc is stranded
    for i in range(n):
        mine = sorted(
            ((s, min(i, j), max(i, j))
             for (a, b), s in sims.items() if i in (a, b)
             for j in [(b if a == i else a)]),
            reverse=True,
        )[:VEC_TOP_K]
        for s, a, b in mine:
            if s >= VEC_THRESHOLD * 0.5:  # top-k edges still need half-threshold
                edges.add((a, b))
    return sorted((a, b, round(sims[(a, b)], 4)) for a, b in edges)


# ---------- Method B: concept-node edges ----------

def concept_nodes(vectors: list[dict[str, float]]) -> list[list[str]]:
    """Top TF-IDF terms per doc — the explicit 'concept nodes'."""
    return [
        [t for t, _ in sorted(vec.items(), key=lambda kv: kv[1], reverse=True)[:CONCEPTS_PER_DOC]]
        for vec in vectors
    ]


def concept_edges(concepts: list[list[str]]) -> list[tuple[int, int, float]]:
    by_concept: dict[str, list[int]] = defaultdict(list)
    for i, terms in enumerate(concepts):
        for t in terms:
            by_concept[t].append(i)

    weights: dict[tuple[int, int], float] = {}
    for docs_sharing in by_concept.values():
        for i, j in combinations(sorted(docs_sharing), 2):
            weights[(i, j)] = weights.get((i, j), 0) + 1

    edges = []
    for (i, j), shared in weights.items():
        union = len(set(concepts[i]) | set(concepts[j]))
        jac = shared / union
        if jac >= CONCEPT_THRESHOLD:
            edges.append((i, j, round(jac, 4)))
    return sorted(edges)


# ---------- clustering & comparison ----------

def components(n: int, edges: list[tuple[int, int, float]]) -> list[int]:
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


def cluster_label(members: list[int], concepts: list[list[str]]) -> str:
    counts = Counter(t for m in members for t in concepts[m])
    return " / ".join(t for t, c in counts.most_common(3))


def compare_methods(n: int, e_vec, e_con, c_vec, c_con, docs) -> dict:
    set_vec = {(a, b) for a, b, _ in e_vec}
    set_con = {(a, b) for a, b, _ in e_con}
    inter = set_vec & set_con
    union = set_vec | set_con

    # pairwise cluster agreement (do both methods put a pair together?)
    same_vec = {(i, j) for i, j in combinations(range(n), 2) if c_vec[i] == c_vec[j]}
    same_con = {(i, j) for i, j in combinations(range(n), 2) if c_con[i] == c_con[j]}
    all_pairs = n * (n - 1) // 2
    agree = all_pairs - len(same_vec ^ same_con)

    def temporal_span(assign: list[int]) -> float:
        """Mean number of distinct weeks per multi-doc cluster — higher means
        clusters track storylines across time, not single-week bursts."""
        weeks = defaultdict(set)
        sizes = Counter(assign)
        for i, c in enumerate(assign):
            weeks[c].add(docs[i]["week"])
        multi = [len(weeks[c]) for c, s in sizes.items() if s >= 2]
        return round(sum(multi) / len(multi), 2) if multi else 0.0

    return {
        "docs": n,
        "vector_edges": len(set_vec),
        "concept_edges": len(set_con),
        "edge_jaccard": round(len(inter) / len(union), 4) if union else 0.0,
        "pairwise_agreement": round(agree / all_pairs, 4),
        "vector_clusters_multi": sum(1 for c, s in Counter(c_vec).items() if s >= 2),
        "concept_clusters_multi": sum(1 for c, s in Counter(c_con).items() if s >= 2),
        "vector_singletons": sum(1 for c, s in Counter(c_vec).items() if s == 1),
        "concept_singletons": sum(1 for c, s in Counter(c_con).items() if s == 1),
        "vector_temporal_span_weeks": temporal_span(c_vec),
        "concept_temporal_span_weeks": temporal_span(c_con),
    }


def main() -> None:
    docs = load_docs()
    vectors = tfidf_vectors(docs)
    concepts = concept_nodes(vectors)

    e_vec = vector_edges(vectors)
    e_con = concept_edges(concepts)
    c_vec = components(len(docs), e_vec)
    c_con = components(len(docs), e_con)

    # persist graph artifacts
    (HERE / "data" / "nodes.json").write_text(json.dumps({
        "documents": [{"id": d["id"], "title": d["title"], "week": d["week"], "url": d["url"]}
                      for d in docs],
        "concepts": sorted({t for terms in concepts for t in terms}),
        "doc_concepts": {str(i): terms for i, terms in enumerate(concepts)},
    }, indent=2))
    (HERE / "data" / "edges_vector.json").write_text(json.dumps(e_vec, indent=2))
    (HERE / "data" / "edges_concept.json").write_text(json.dumps(e_con, indent=2))

    clusters = {}
    for name, assign in (("vector", c_vec), ("concept", c_con)):
        groups = defaultdict(list)
        for i, c in enumerate(assign):
            groups[c].append(i)
        clusters[name] = [
            {"label": cluster_label(members, concepts),
             "size": len(members),
             "weeks": sorted({docs[m]["week"] for m in members}),
             "titles": [docs[m]["title"] for m in members]}
            for members in sorted(groups.values(), key=len, reverse=True) if len(members) >= 2
        ]
    (HERE / "data" / "clusters.json").write_text(json.dumps(clusters, indent=2))

    metrics = compare_methods(len(docs), e_vec, e_con, c_vec, c_con, docs)
    (HERE / "data" / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print(f"\nTop vector clusters: {[c['label'] for c in clusters['vector'][:5]]}")
    print(f"Top concept clusters: {[c['label'] for c in clusters['concept'][:5]]}")


if __name__ == "__main__":
    main()
