"""P1: export derived JSON snapshots — the data plane the site/checker read.

SQLite (output/analyses.db) stays the private system of record; these snapshots
are the rebuildable, HTTP-hostable derivatives (Vercel Blob in production, a
local snapshots/ dir for preview):

  topics.json        storylines: label, size, period, category, urls
  timelines.json     per-topic GroupAnalysis rows (all claims + source URLs)
  search_index.json  per-doc top-term vectors + url/title/date (checker + search)
  meta.json          refreshed_at + counts (the deploy heartbeat)

Run:  python3 -m secondbrain.export_snapshots [--out snapshots]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

GROUPS_PATH = Path("output/second-brain-tests/consolidated/consolidated_groups.json")
VECTORS_PATH = Path("output/second-brain-tests/consolidated/doc_vectors.json")
CORPUS_PATH = Path("output/second-brain-tests/live/corpus.json")
DEFAULT_OUT = Path("snapshots")

INDEX_TERMS_PER_DOC = 20
DEFAULT_CATEGORY = "AI Tools"


def export(out: Path) -> dict:
    from store import Store

    corpus = json.loads(CORPUS_PATH.read_text())
    by_url = {a["url"]: a for a in corpus}
    groups = json.loads(GROUPS_PATH.read_text())["groups"]
    vec_rows = json.loads(VECTORS_PATH.read_text())

    # topics: multi-doc, on-topic storylines
    topics = [
        {
            "label": g["label"],
            "size": g["size"],
            "period": g["period"],
            "category": _group_category(g, by_url),
            "urls": g["urls"],
        }
        for g in groups
        if not g["singleton"] and not g["off_topic"]
    ]

    # timelines: every stored analysis, keyed by topic
    store = Store()
    timelines: dict[str, list[dict]] = {}
    for topic in store.topics():
        timelines[topic] = [
            {
                "period_start": a.period_start.isoformat(),
                "period_end": a.period_end.isoformat(),
                "agreements": a.agreements,
                "contradictions": a.contradictions,
                "debunks": a.debunks,
                "unresolved": a.unresolved,
                "sources": [{"title": i.title, "url": i.url} for i in a.sources],
            }
            for a in store.get_timeline(topic)
        ]

    index = [
        {
            "u": r["url"],
            "t": (by_url.get(r["url"], {}).get("hn_title") or "?")[:110],
            "d": (by_url.get(r["url"], {}).get("published_at") or "")[:10],
            "c": by_url.get(r["url"], {}).get("category", DEFAULT_CATEGORY),
            "v": dict(sorted(r["vector"].items(), key=lambda kv: kv[1],
                             reverse=True)[:INDEX_TERMS_PER_DOC]),
        }
        for r in vec_rows
    ]

    meta = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "articles": len(index),
        "storylines": len(topics),
        "analyses": sum(len(v) for v in timelines.values()),
        "categories": sorted({t["category"] for t in topics}),
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "topics.json").write_text(json.dumps(topics, separators=(",", ":")))
    (out / "timelines.json").write_text(json.dumps(timelines, separators=(",", ":")))
    (out / "search_index.json").write_text(json.dumps(index, separators=(",", ":")))
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def _group_category(group: dict, by_url: dict) -> str:
    """Majority category among a group's members (collect.py tags records;
    untagged legacy records fall back to the default)."""
    from collections import Counter
    votes = Counter(
        by_url.get(u, {}).get("category", DEFAULT_CATEGORY) for u in group["urls"]
    )
    return votes.most_common(1)[0][0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Export site/checker snapshots")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    meta = export(args.out)
    print(f"snapshots → {args.out}: {json.dumps(meta)}")


if __name__ == "__main__":
    main()
