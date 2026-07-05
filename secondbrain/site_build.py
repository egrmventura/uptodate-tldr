"""M5: build the self-contained second-brain site (single HTML file).

Deterministic template over the daily artifacts:
- storylines (consolidated multi-doc groups) with their analyzed timelines
  (agreements / contradictions / unresolved, every source URL-linked)
- client-side cited search: a compact per-doc term index (top terms only)
  is embedded and queried with cosine in vanilla JS — no backend needed,
  so the page works as a static URL

Run:  python3 -m secondbrain.site_build [--out output/second-brain-tests/site/index.html]
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import date
from pathlib import Path

GROUPS_PATH = Path("output/second-brain-tests/consolidated/consolidated_groups.json")
VECTORS_PATH = Path("output/second-brain-tests/consolidated/doc_vectors.json")
CORPUS_PATH = Path("output/second-brain-tests/live/corpus.json")
DEFAULT_OUT = Path("output/second-brain-tests/site/index.html")

INDEX_TERMS_PER_DOC = 20
E = html.escape


def load_data() -> dict:
    groups = json.loads(GROUPS_PATH.read_text())["groups"]
    corpus = {a["url"]: a for a in json.loads(CORPUS_PATH.read_text())}
    vec_rows = json.loads(VECTORS_PATH.read_text())

    from store import Store
    store = Store()
    timelines = {t: store.get_timeline(t) for t in store.topics()}

    index = [
        {
            "u": r["url"],
            "t": (corpus.get(r["url"], {}).get("hn_title") or "?")[:110],
            "d": (corpus.get(r["url"], {}).get("published_at") or "")[:10],
            "v": dict(sorted(r["vector"].items(), key=lambda kv: kv[1],
                             reverse=True)[:INDEX_TERMS_PER_DOC]),
        }
        for r in vec_rows
    ]
    return {"groups": groups, "corpus": corpus, "timelines": timelines, "index": index}


def _render_list(label: str, entries: list[str]) -> str:
    if not entries:
        return ""
    items = "".join(f"<li>{E(x)}</li>" for x in entries)
    return f'<p class="fl">{E(label)}</p><ul>{items}</ul>'


def _render_storyline(g: dict, timelines: dict, corpus: dict) -> str:
    arts = "".join(
        f'<li><a href="{E(u)}" rel="noopener">{E((corpus.get(u, {}).get("hn_title") or u)[:90])}</a>'
        f' <span class="dt">{E((corpus.get(u, {}).get("published_at") or "")[:10])}</span></li>'
        for u in g["urls"]
    )
    analysis_html = ""
    for a in timelines.get(g["label"], []):
        span = f'{a.period_start.date().isoformat()} → {a.period_end.date().isoformat()}'
        analysis_html += (
            f'<div class="win"><p class="dt">{E(span)}</p>'
            + _render_list("Agreements", a.agreements)
            + _render_list("Contradictions", a.contradictions)
            + _render_list("Debunks", a.debunks)
            + _render_list("Unresolved", a.unresolved)
            + "</div>"
        )
    return (
        f'<details class="story"><summary><b>{E(g["label"])}</b>'
        f' <span class="dt">{g["size"]} articles · {E(g["period"][0])} → {E(g["period"][1])}</span></summary>'
        f'{analysis_html or "<p class=dt>No comparative analysis yet (next refresh).</p>"}'
        f'<p class="fl">Sources</p><ul class="src">{arts}</ul></details>'
    )


def build(out: Path) -> Path:
    d = load_data()
    multi = [g for g in d["groups"] if not g["singleton"] and not g["off_topic"]]
    n_analyses = sum(len(v) for v in d["timelines"].values())
    today = date.today().isoformat()

    stories = "".join(_render_storyline(g, d["timelines"], d["corpus"]) for g in multi)
    index_json = json.dumps(d["index"], separators=(",", ":"))

    page = f"""<title>Claude Tools — Second Brain</title>
<style>
:root{{--paper:#f7f8f6;--ink:#141a1e;--ink2:#5a6570;--ink3:#8a949c;--hair:#dde2e2;--card:#fdfdfc;--acc:#2a78d6}}
@media(prefers-color-scheme:dark){{:root{{--paper:#181a19;--ink:#f2f3f1;--ink2:#b5bdc3;--ink3:#7d868d;--hair:#32373a;--card:#1f2221;--acc:#3987e5}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 Seravek,'Gill Sans',Calibri,system-ui,sans-serif}}
.wrap{{max-width:860px;margin:0 auto;padding:36px 20px 80px}}
h1{{font-family:'Avenir Next Condensed','Arial Narrow',sans-serif;font-weight:600;font-size:1.9rem;margin:0 0 2px}}
.sub{{color:var(--ink2);margin:0 0 22px;max-width:64ch}}
.eyebrow{{font-family:ui-monospace,Menlo,monospace;font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink3);margin:26px 0 8px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap}}
.stat{{background:var(--card);border:1px solid var(--hair);border-radius:6px;padding:8px 14px;font-family:ui-monospace,Menlo,monospace;font-size:.85rem}}
.stat b{{font-size:1.2rem}}
input{{width:100%;padding:11px 14px;border:1px solid var(--hair);border-radius:6px;background:var(--card);color:var(--ink);font:inherit}}
input:focus{{outline:2px solid var(--acc)}}
#res .hit{{background:var(--card);border:1px solid var(--hair);border-radius:6px;padding:10px 14px;margin:8px 0}}
.hit a{{color:var(--acc);text-decoration:none}}.hit a:hover{{text-decoration:underline}}
.dt{{color:var(--ink3);font-size:.8rem;font-family:ui-monospace,Menlo,monospace}}
.story{{background:var(--card);border:1px solid var(--hair);border-radius:6px;padding:12px 16px;margin:10px 0}}
.story summary{{cursor:pointer}}
.fl{{font-family:ui-monospace,Menlo,monospace;font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);margin:12px 0 4px}}
ul{{margin:4px 0;padding-left:20px}}li{{margin:3px 0}}
.src a{{color:var(--acc);text-decoration:none}}.src a:hover{{text-decoration:underline}}
.win{{border-left:2px solid var(--hair);padding-left:12px;margin:10px 0}}
footer{{margin-top:40px;color:var(--ink3);font-size:.78rem}}
</style>
<div class="wrap">
<p class="eyebrow">uptodate-tldr · second brain · refreshed {today}</p>
<h1>Claude Tools — Second Brain</h1>
<p class="sub">A self-updating research memory over Hacker News coverage of Claude tool
expansion. Storylines are clustered from article similarity, analyzed for agreements and
contradictions across sources, and fully cited — every claim links to where it came from.</p>
<div class="stats">
<span class="stat"><b>{len(d["index"])}</b> articles</span>
<span class="stat"><b>{len(multi)}</b> storylines</span>
<span class="stat"><b>{n_analyses}</b> analyses</span>
<span class="stat"><b>{today}</b> last refresh</span>
</div>
<p class="eyebrow">search the corpus</p>
<input id="q" type="search" placeholder="e.g. memory skills, mcp server, microsoft copilot…" aria-label="Search articles">
<div id="res"></div>
<p class="eyebrow">storylines</p>
{stories}
<footer>Built by the uptodate-tldr pipeline · sources: Hacker News (Algolia) · all article
credit belongs to the linked authors.</footer>
</div>
<script>
const IDX={index_json};
const STOP=new Set("the and for with that this from are was were has have had you your not can will its our their they them than but all any out use using new now get more most into over under about after also just like one two how what when where which who why been does did don of in on at to is it as by be or we".split(" "));
const toks=s=>(s.toLowerCase().match(/[a-z][a-z0-9+#.-]{{2,}}/g)||[]).filter(t=>!STOP.has(t));
function qvec(s){{const c={{}};toks(s).forEach(t=>c[t]=(c[t]||0)+1);let n=0;for(const t in c){{c[t]=1+Math.log(c[t]);n+=c[t]*c[t]}}n=Math.sqrt(n)||1;for(const t in c)c[t]/=n;return c}}
function cos(q,v){{let s=0;for(const t in q)if(v[t])s+=q[t]*v[t];return s}}
const res=document.getElementById('res');
document.getElementById('q').addEventListener('input',e=>{{
 const q=qvec(e.target.value);
 if(!Object.keys(q).length){{res.innerHTML='';return}}
 const hits=IDX.map(d=>[cos(q,d.v),d]).filter(([s])=>s>0.05).sort((a,b)=>b[0]-a[0]).slice(0,6);
 res.innerHTML=hits.map(([s,d])=>`<div class="hit"><a href="${{d.u}}" rel="noopener">${{d.t.replace(/</g,'&lt;')}}</a> <span class="dt">${{d.d}} · ${{s.toFixed(3)}}</span></div>`).join('')||'<p class="dt">no matches above the noise floor</p>';
}});
</script>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print(f"site built: {out} ({out.stat().st_size // 1024} KB, "
          f"{len(d['index'])} docs indexed, {len(multi)} storylines, {n_analyses} analyses)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the second-brain static site")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
