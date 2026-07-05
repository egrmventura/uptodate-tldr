"""M4: cited retrieval over the consolidated corpus.

Cosine search over the stored per-document vectors (doc_vectors.json — the
consolidation pass's "embeddings column"). Every hit carries its source URL,
title, date, and group, so answers are citable by construction. Pure Python:
at corpus scale (hundreds–thousands of docs) brute-force cosine is
milliseconds; swap the vector source for API embeddings + an ANN index when
the corpus outgrows that, without changing this interface.

Run:  python3 -m secondbrain.retrieval "claude memory skills"
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from secondbrain import vectors as V

VECTORS_PATH = Path("output/second-brain-tests/consolidated/doc_vectors.json")
CORPUS_PATH = Path("output/second-brain-tests/live/corpus.json")
GROUPS_PATH = Path("output/second-brain-tests/consolidated/consolidated_groups.json")

DEFAULT_TOP_K = 5
MIN_SCORE = 0.05  # below this, a hit is noise, not evidence


@dataclass
class Hit:
    url: str
    title: str
    published: str
    score: float
    group: str
    summary: str


class Retriever:
    def __init__(
        self,
        vectors_path: Path = VECTORS_PATH,
        corpus_path: Path = CORPUS_PATH,
        groups_path: Path = GROUPS_PATH,
    ) -> None:
        vec_rows = json.loads(Path(vectors_path).read_text())
        self._vectors = {r["url"]: r["vector"] for r in vec_rows}

        self._articles = {a["url"]: a for a in json.loads(Path(corpus_path).read_text())}

        self._group_of: dict[str, str] = {}
        if Path(groups_path).exists():
            for g in json.loads(Path(groups_path).read_text())["groups"]:
                for url in g["urls"]:
                    self._group_of[url] = g["label"]

    def __len__(self) -> int:
        return len(self._vectors)

    def query_vector(self, query: str) -> dict[str, float]:
        """Query text → unit vector in the corpus's term space (IDF-free —
        query terms are few; TF weighting suffices)."""
        import math
        toks = V.tokenize(query)
        if not toks:
            return {}
        from collections import Counter
        tf = Counter(toks)
        vec = {t: 1 + math.log(c) for t, c in tf.items()}
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        return {t: w / norm for t, w in vec.items()}

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[Hit]:
        qv = self.query_vector(query)
        if not qv:
            return []
        scored = sorted(
            ((V.cosine(qv, vec), url) for url, vec in self._vectors.items()),
            reverse=True,
        )[:top_k]

        hits = []
        for score, url in scored:
            if score < MIN_SCORE:
                continue
            a = self._articles.get(url, {})
            hits.append(Hit(
                url=url,
                title=a.get("hn_title") or a.get("title") or "?",
                published=(a.get("published_at") or "")[:10],
                score=round(score, 4),
                group=self._group_of.get(url, "(unfiled)"),
                summary=(a.get("summary") or "")[:240],
            ))
        return hits


def main() -> None:
    import sys
    query = " ".join(sys.argv[1:]) or "claude memory"
    r = Retriever()
    print(f"corpus: {len(r)} docs | query: {query!r}\n")
    for h in r.search(query):
        print(f"{h.score:.3f}  [{h.published}] {h.title[:70]}\n       {h.url}  ({h.group})")


if __name__ == "__main__":
    main()
