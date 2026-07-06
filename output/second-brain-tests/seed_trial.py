"""Real-data seed trial: persist topic clusters into a Store timeline db.

Takes the vector-method clusters from topic_graph.py and seeds them into a
GroupAnalysis timeline using the repo's real Store (SQLite, same schema as
output/analyses.db — but a separate trial db so production data stays clean).

For each multi-doc cluster (a topic) and each week it appears in, one
GroupAnalysis row is written whose period_start/period_end come from the
articles' real publication dates — the backfill-correctness rule. The trial
runs the seed TWICE and asserts the row count is identical (idempotency via
UNIQUE(topic, period_start, period_end) + INSERT OR IGNORE), then renders
the chronological timeline for the biggest topic.

Run:  python3 output/second-brain-tests/seed_trial.py
In:   data/articles.json, data/clusters.json
Out:  data/analyses-trial.db, data/timeline-<topic>.md
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from sources.base import Item, parse_timestamp  # noqa: E402
from store import GroupAnalysis, Store  # noqa: E402
from timeline import render_timeline  # noqa: E402

DB_PATH = HERE / "data" / "analyses-trial.db"


def build_analyses() -> list[GroupAnalysis]:
    articles = json.loads((HERE / "data" / "articles.json").read_text())["articles"]
    clusters = json.loads((HERE / "data" / "clusters.json").read_text())["vector"]

    by_title = {a["title"]: a for a in articles}
    analyses: list[GroupAnalysis] = []

    for cluster in clusters:
        topic = f"Claude tools: {cluster['label']}"
        # bucket the cluster's articles by week window
        weekly: dict[str, list[dict]] = defaultdict(list)
        for title in cluster["titles"]:
            a = by_title[title]
            weekly[a["week_start"]].append(a)

        for week, members in sorted(weekly.items()):
            published = [parse_timestamp(m["created_at"]) for m in members]
            items = [
                Item(
                    source="hackernews",
                    title=m["title"],
                    url=m["url"],
                    score=m["points"],
                    published_at=parse_timestamp(m["created_at"]),
                    summary_raw=m["summary"][:300],
                    extra={"week": m["week_start"], "scraped": m["scraped"]},
                )
                for m in members
            ]
            analyses.append(GroupAnalysis(
                topic=topic,
                run_date=date.today(),
                period_start=min(published),   # real publication dates,
                period_end=max(published),     # never the run date
                agreements=[f"{m['title']} ({m['points']} pts)" for m in members],
                contradictions=[],
                debunks=[],
                unresolved=[],
                sources=items,
            ))
    return analyses


def count_rows(store: Store) -> int:
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    finally:
        conn.close()


def main() -> None:
    DB_PATH.unlink(missing_ok=True)  # fresh trial each invocation
    store = Store(DB_PATH)
    analyses = build_analyses()

    store.save_run(analyses, date.today(), is_backfill=True)
    first = count_rows(store)

    store.save_run(analyses, date.today(), is_backfill=True)  # identical re-run
    second = count_rows(store)

    assert first == second, f"idempotency violated: {first} -> {second}"
    print(f"Seeded {first} analysis rows across {len(store.topics())} topics; "
          f"re-run added {second - first} rows (idempotent ✓)")

    # chronological ordering check + rendered timeline for the biggest topic
    biggest = max(store.topics(), key=lambda t: len(store.get_timeline(t)))
    timeline = store.get_timeline(biggest)
    starts = [a.period_start for a in timeline]
    assert starts == sorted(starts), "timeline not chronological"
    print(f"Biggest topic: {biggest!r} — {len(timeline)} periods, chronological ✓")

    md = render_timeline(biggest, store)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in biggest)[:60]
    out = HERE / "data" / f"timeline-{safe}.md"
    out.write_text(md)
    print(f"Rendered timeline → {out}")


if __name__ == "__main__":
    main()
