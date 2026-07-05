"""M5: HTTP API for the second brain — stdlib only, serves the daily artifacts.

Endpoints (JSON):
  GET /health                     {"status": "ok", "docs": N, "topics": N}
  GET /topics                     consolidated storylines (label, size, period)
  GET /timeline?topic=LABEL       stored GroupAnalysis rows for a topic
  GET /search?q=QUERY&k=5         cited retrieval hits
  GET /digest                     latest run's analyses

Run:  python3 -m secondbrain.serve [--port 8787]
The routing core (`handle_path`) is a pure function so tests exercise it
without binding a socket.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

GROUPS_PATH = Path("output/second-brain-tests/consolidated/consolidated_groups.json")


class Api:
    """Lazy-loading facade over store + retriever; one instance per process."""

    def __init__(self) -> None:
        self._retriever = None
        self._store = None

    @property
    def retriever(self):
        if self._retriever is None:
            from secondbrain.retrieval import Retriever
            self._retriever = Retriever()
        return self._retriever

    @property
    def store(self):
        if self._store is None:
            from store import Store
            self._store = Store()
        return self._store

    # ---- endpoint bodies ----

    def health(self) -> dict:
        topics = self.store.topics()
        return {"status": "ok", "docs": len(self.retriever), "topics": len(topics)}

    def topics(self) -> list[dict]:
        groups = json.loads(GROUPS_PATH.read_text())["groups"]
        return [
            {"label": g["label"], "size": g["size"], "period": g["period"]}
            for g in groups
            if not g["singleton"] and not g["off_topic"]
        ]

    def timeline(self, topic: str) -> list[dict]:
        return [
            {
                "period_start": a.period_start.isoformat(),
                "period_end": a.period_end.isoformat(),
                "agreements": a.agreements,
                "contradictions": a.contradictions,
                "debunks": a.debunks,
                "unresolved": a.unresolved,
                "sources": [{"title": i.title, "url": i.url} for i in a.sources],
            }
            for a in self.store.get_timeline(topic)
        ]

    def digest(self) -> list[dict]:
        # Latest run *with content* — idempotent re-runs create empty runs
        # (all rows deduped), which would otherwise blank the digest.
        run_id = self.store.latest_run_id()
        rows = []
        while run_id and run_id > 0:
            rows = self.store.get_run(run_id)
            if rows:
                break
            run_id -= 1
        return [
            {"topic": a.topic,
             "period_start": a.period_start.isoformat(),
             "agreements": a.agreements, "contradictions": a.contradictions,
             "sources": [{"title": i.title, "url": i.url} for i in a.sources]}
            for a in rows
        ]

    def search(self, query: str, k: int) -> list[dict]:
        return [vars(h) for h in self.retriever.search(query, top_k=k)]


def handle_path(api: Api, path: str) -> tuple[int, dict | list]:
    """Route a request path to (status, json-serializable body)."""
    parsed = urlparse(path)
    qs = parse_qs(parsed.query)
    route = parsed.path.rstrip("/") or "/"

    try:
        if route in ("/", "/health"):
            return 200, api.health()
        if route == "/topics":
            return 200, api.topics()
        if route == "/timeline":
            topic = (qs.get("topic") or [""])[0]
            if not topic:
                return 400, {"error": "missing ?topic="}
            rows = api.timeline(topic)
            return (200, rows) if rows else (404, {"error": f"no timeline for {topic!r}"})
        if route == "/search":
            q = (qs.get("q") or [""])[0]
            if not q:
                return 400, {"error": "missing ?q="}
            k = min(int((qs.get("k") or ["5"])[0]), 25)
            return 200, api.search(q, k)
        if route == "/digest":
            return 200, api.digest()
        return 404, {"error": f"no route {route!r}"}
    except FileNotFoundError as exc:
        return 503, {"error": f"artifact missing — run the refresh: {exc}"}
    except Exception as exc:  # surfaced, never swallowed silently
        logger.warning("API error on %s", path, exc_info=True)
        return 500, {"error": str(exc)}


def main() -> None:
    import argparse
    from http.server import BaseHTTPRequestHandler, HTTPServer

    ap = argparse.ArgumentParser(description="second-brain API")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()

    api = Api()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (stdlib name)
            status, body = handle_path(api, self.path)
            payload = json.dumps(body, indent=2).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *fmt_args):
            logger.info("%s " + fmt, self.client_address[0], *fmt_args)

    logging.basicConfig(level=logging.INFO)
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    logger.info("second-brain API on http://127.0.0.1:%d", args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
