"""P4: article freshness checker — Vercel Python serverless function.

POST /api/check  {"url": "..."} or {"text": "..."}
→ {"verdict": "current|partially_outdated|outdated|unknown",
   "summary": str, "reasons": [str], "evidence": [{title,url,date}]}

Flow: fetch/accept article → retrieve nearest corpus docs + their topic
timelines from the snapshot layer (Vercel Blob via SNAPSHOT_BASE_URL, or the
local snapshots/ dir in dev) → one Claude call judges currency against that
evidence. Reuses scraper.py, secondbrain vector math, and resilience backoff.

Env (Vercel dashboard): ANTHROPIC_API_KEY, SNAPSHOT_BASE_URL.
Guardrails: 15s scrape timeout, 40 KB text cap, top-5 evidence, JSON-only I/O.
"""

from __future__ import annotations

import json
import math
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root

MAX_TEXT_CHARS = 40_000
SCRAPE_TIMEOUT = 15
TOP_K = 5
MIN_SIM = 0.05
LLM_MAX_TOKENS = 1200
VERDICTS = {"current", "partially_outdated", "outdated", "unknown"}

_SYSTEM = """\
You are a technical currency auditor. Given a user-submitted article and a set
of recent, dated evidence items (titles, dates, and timeline analyses) about
the same topic, judge whether the article is up to date or relies on outdated
or superseded tools/claims.

Respond with valid JSON only — no prose, no markdown fences:
{"verdict": "current" | "partially_outdated" | "outdated" | "unknown",
 "summary": "<one-sentence judgement>",
 "reasons": ["<specific reason citing evidence by title/date>", ...],
 "evidence_indices": [<indices of the evidence items you relied on>]}

Rules: judge only against the provided evidence; if the evidence doesn't cover
the article's topic, verdict is "unknown". Be specific about which claims/tools
are outdated and what superseded them."""


# ---------- snapshot access (Blob in prod, local dir in dev) ----------

_CACHE: dict[str, object] = {}


def _snapshot(name: str):
    if name in _CACHE:
        return _CACHE[name]
    base = os.environ.get("SNAPSHOT_BASE_URL", "").rstrip("/")
    if base:
        with urlopen(f"{base}/{name}.json", timeout=10) as r:  # noqa: S310 (https blob url)
            data = json.loads(r.read())
    else:
        data = json.loads((Path("snapshots") / f"{name}.json").read_text())
    _CACHE[name] = data
    return data


# ---------- core (pure-ish, unit-testable) ----------

def _query_vector(text: str) -> dict[str, float]:
    from secondbrain.vectors import tokenize
    from collections import Counter
    tf = Counter(tokenize(text[:MAX_TEXT_CHARS]))
    vec = {t: 1 + math.log(c) for t, c in tf.items()}
    norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
    return {t: w / norm for t, w in vec.items()}


def retrieve_evidence(article_text: str) -> list[dict]:
    """Top-K corpus docs by cosine + their topics' timeline claims."""
    from secondbrain.vectors import cosine

    qv = _query_vector(article_text)
    index = _snapshot("search_index")
    scored = sorted(((cosine(qv, d["v"]), d) for d in index), reverse=True,
                    key=lambda p: p[0])[:TOP_K]

    timelines = _snapshot("timelines")
    topics = _snapshot("topics")
    topic_of = {u: t["label"] for t in topics for u in t["urls"]}

    evidence, seen_topics = [], set()
    for sim, d in scored:
        if sim < MIN_SIM:
            continue
        evidence.append({"title": d["t"], "url": d["u"], "date": d["d"],
                         "kind": "article", "sim": round(sim, 3)})
        label = topic_of.get(d["u"])
        if label and label not in seen_topics and label in timelines:
            seen_topics.add(label)
            for row in timelines[label][-2:]:  # most recent windows
                claims = (row["agreements"] + row["contradictions"])[:4]
                if claims:
                    evidence.append({
                        "title": f"Timeline [{label}] {row['period_start'][:10]}",
                        "url": row["sources"][0]["url"] if row["sources"] else "",
                        "date": row["period_end"][:10],
                        "kind": "timeline", "claims": claims,
                    })
    return evidence


def judge(article_text: str, evidence: list[dict]) -> dict:
    if not evidence:
        return {"verdict": "unknown",
                "summary": "The corpus has no coverage of this article's topic yet.",
                "reasons": [], "evidence": []}

    import anthropic
    from resilience import is_transient_anthropic, retry_with_backoff

    ev_block = "\n".join(
        f"{i}. [{e['date']}] {e['title']}" + (f" — claims: {'; '.join(e['claims'])}" if e.get("claims") else "")
        for i, e in enumerate(evidence)
    )
    user = (f"ARTICLE (truncated):\n{article_text[:6000]}\n\n"
            f"EVIDENCE (dated, most similar first):\n{ev_block}\n\nReturn JSON only.")

    def _call():
        client = anthropic.Anthropic()
        return client.messages.create(
            model=os.environ.get("CHECK_MODEL", "claude-sonnet-5"),
            max_tokens=LLM_MAX_TOKENS, system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )

    response = retry_with_backoff(_call, label="Checker", is_transient=is_transient_anthropic)
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(raw)

    verdict = parsed.get("verdict")
    if verdict not in VERDICTS:
        raise ValueError(f"model returned invalid verdict {verdict!r}")
    cited = [evidence[i] for i in parsed.get("evidence_indices", [])
             if isinstance(i, int) and 0 <= i < len(evidence)]
    return {
        "verdict": verdict,
        "summary": str(parsed.get("summary", ""))[:500],
        "reasons": [str(r)[:300] for r in parsed.get("reasons", [])][:6],
        "evidence": [{"title": e["title"], "url": e["url"], "date": e["date"]}
                     for e in (cited or evidence[:3])],
    }


def check(payload: dict) -> tuple[int, dict]:
    url = (payload.get("url") or "").strip()
    text = (payload.get("text") or "").strip()
    if not url and not text:
        return 400, {"error": "provide 'url' or 'text'"}
    if url and not url.startswith(("http://", "https://")):
        return 400, {"error": "url must be http(s)"}

    if url and not text:
        from scraper import scrape
        art = scrape(url, {"min_body_chars": 200, "timeout": SCRAPE_TIMEOUT})
        if art is None or not art.body:
            return 422, {"error": "could not extract article text from that URL "
                                  "(blocked/paywalled?) — paste the text instead"}
        text = f"{art.title or ''}\n{art.body}"

    try:
        evidence = retrieve_evidence(text)
        return 200, judge(text, evidence)
    except Exception as exc:  # surfaced with context, never a bare 500 page
        return 500, {"error": f"{type(exc).__name__}: {exc}"}


# ---------- Vercel handler ----------

class handler(BaseHTTPRequestHandler):  # noqa: N801 (Vercel requires this name)
    def do_POST(self):  # noqa: N802
        try:
            length = min(int(self.headers.get("Content-Length", 0)), MAX_TEXT_CHARS * 2)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            status, body = 400, {"error": "invalid JSON body"}
        else:
            status, body = check(payload)
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):  # noqa: N802 (CORS preflight)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
