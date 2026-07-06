"""One iteration of the live scrape→summarize→group loop.

Driven on a schedule by the agent. Each run:
1. rotates through the factual search keywords (data/keywords.json),
2. fetches HN stories for 3 queries via the F1-fixed HackerNewsSource
   (explicit date window = last LOOKBACK_DAYS days),
3. dedupes by URL against the growing corpus,
4. scrapes + extractively summarizes new articles (offline summarizer),
5. assigns each to a topic group by TF-IDF cosine against group centroids
   (new group if nothing within threshold),
6. persists everything — every article record keeps its `url` for citing.

State:  live/state.json      (iteration counter, keyword cursor, started_at)
Corpus: live/corpus.json     (all articles: url, title, query, summary, group)
Groups: live/groups.json     (group id -> label, member urls)
Log:    live/loop_log.txt    (one line per iteration)

Run:  python3 output/second-brain-tests/live/loop_iteration.py
Prints exactly one summary line (context-cheap by design).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../second-brain-tests/live
SBT = HERE.parent                                # .../second-brain-tests
REPO = SBT.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SBT))

from scrape_summarize import extractive_summary  # noqa: E402
from sources.hackernews import HackerNewsSource  # noqa: E402
from scraper import scrape  # noqa: E402
from topic_graph import tokenize  # noqa: E402

QUERIES_PER_RUN = 3
LOOKBACK_DAYS = 60
GROUP_THRESHOLD = 0.15
MAX_NEW_PER_RUN = 6  # keep each iteration light


# ---------- state ----------

def _load(name: str, default):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else default


def _save(name: str, obj) -> None:
    (HERE / name).write_text(json.dumps(obj, indent=2))


# ---------- grouping ----------

def _vec(text: str) -> dict[str, float]:
    from collections import Counter
    import math
    tf = Counter(tokenize(text))
    vec = {t: 1 + math.log(c) for t, c in tf.items()}
    norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
    return {t: w / norm for t, w in vec.items()}


def _cos(a: dict[str, float], b: dict[str, float]) -> float:
    if len(b) < len(a):
        a, b = b, a
    return sum(w * b.get(t, 0.0) for t, w in a.items())


def assign_group(text: str, groups: dict) -> str:
    """Nearest group centroid by cosine, or a new group labeled by top terms."""
    v = _vec(text)
    best_id, best_sim = None, 0.0
    for gid, g in groups.items():
        sim = _cos(v, g["centroid"])
        if sim > best_sim:
            best_id, best_sim = gid, sim

    if best_id is not None and best_sim >= GROUP_THRESHOLD:
        g = groups[best_id]
        n = len(g["urls"])  # running centroid update
        g["centroid"] = {t: (g["centroid"].get(t, 0) * n + v.get(t, 0)) / (n + 1)
                         for t in set(g["centroid"]) | set(v)}
        return best_id

    gid = f"g{len(groups):03d}"
    top = sorted(v.items(), key=lambda kv: kv[1], reverse=True)[:3]
    groups[gid] = {"label": " / ".join(t for t, _ in top), "centroid": v, "urls": []}
    return gid


# ---------- iteration ----------

def main() -> None:
    now = datetime.now(timezone.utc)
    state = _load("state.json", {"started_at": now.isoformat(), "iteration": 0, "cursor": 0})
    corpus = _load("corpus.json", [])
    groups = _load("groups.json", {})
    known_urls = {a["url"] for a in corpus}

    keywords = json.loads((SBT / "data" / "keywords.json").read_text())["search_keywords"]
    src = HackerNewsSource()
    window = {
        "date_from": (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat(),
        "date_to": date.today().isoformat(),
        "max_results": 10,
    }

    picked = []
    for k in range(QUERIES_PER_RUN):
        picked.append(keywords[(state["cursor"] + k) % len(keywords)]["query"])
    state["cursor"] = (state["cursor"] + QUERIES_PER_RUN) % len(keywords)

    fetched = 0
    added = []
    for q in picked:
        for item in src.safe_fetch(q, dict(window)):
            fetched += 1
            if item.url in known_urls or len(added) >= MAX_NEW_PER_RUN:
                continue
            known_urls.add(item.url)

            art = scrape(item.url, {"min_body_chars": 200, "timeout": 10})
            body = art.body if art and art.body else (item.summary_raw or item.title)
            summary = extractive_summary(body)

            record = {
                "url": item.url,                     # kept for citing
                "hn_title": item.title,
                "query": q,
                "points": item.score,
                "published_at": item.published_at.isoformat(),
                "fetched_at": now.isoformat(),
                "scraped": bool(art and art.body),
                "summary": summary,
            }
            record["group"] = assign_group(f"{item.title} {summary}", groups)
            groups[record["group"]]["urls"].append(item.url)
            added.append(record)

    corpus.extend(added)
    state["iteration"] += 1
    _save("state.json", state)
    _save("corpus.json", corpus)
    _save("groups.json", groups)

    line = (f"iter={state['iteration']} queries={picked} fetched={fetched} "
            f"new={len(added)} corpus={len(corpus)} groups={len(groups)}")
    with (HERE / "loop_log.txt").open("a") as f:
        f.write(f"{now.isoformat()} {line}\n")
    print(line)


if __name__ == "__main__":
    main()
