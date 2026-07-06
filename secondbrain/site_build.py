"""Build the timeline site (single HTML file, client-side rendered).

Two data modes, one render path:
  embedded (default)   snapshots inlined into the page — zero-infra local preview
  --data-url BASE      page fetch()es {BASE}/topics.json, timelines.json,
                       search_index.json, meta.json at load — the production
                       mode against Vercel Blob; page stays ~15 KB

The page renders: category tabs → storylines → expandable timeline cards
(agreements / contradictions / debunks / unresolved, every claim's sources
linked), plus client-side cited search and the article freshness checker panel
(calls /api/check; hidden automatically if the endpoint is absent).

Run:  python3 -m secondbrain.site_build [--out site/index.html]
                                        [--data-url https://…blob…/snapshots]
      (embedded mode requires snapshots/ to exist — run export_snapshots first)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SNAPSHOTS = Path("snapshots")
DEFAULT_OUT = Path("site/index.html")  # Vercel root: site/


def build(out: Path, data_url: str | None = None) -> Path:
    if data_url:
        boot = f'const DATA_URL={json.dumps(data_url.rstrip("/"))};const EMBEDDED=null;'
    else:
        embedded = {
            name: json.loads((SNAPSHOTS / f"{name}.json").read_text())
            for name in ("topics", "timelines", "search_index", "meta")
        }
        boot = f"const DATA_URL=null;const EMBEDDED={json.dumps(embedded, separators=(',', ':'))};"

    page = _TEMPLATE.replace("/*__BOOT__*/", boot)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    mode = f"data-url={data_url}" if data_url else "embedded"
    print(f"site built: {out} ({out.stat().st_size // 1024} KB, {mode})")
    return out


_TEMPLATE = r"""<title>UpToDate — AI & Data Engineering Timelines</title>
<style>
:root{--paper:#f7f8f6;--ink:#141a1e;--ink2:#5a6570;--ink3:#8a949c;--hair:#dde2e2;--card:#fdfdfc;--acc:#2a78d6;
--ok:#1baf7a;--warn:#eda100;--bad:#e34948}
@media(prefers-color-scheme:dark){:root{--paper:#181a19;--ink:#f2f3f1;--ink2:#b5bdc3;--ink3:#7d868d;--hair:#32373a;--card:#1f2221;--acc:#3987e5;
--ok:#199e70;--warn:#c98500;--bad:#e66767}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 Seravek,'Gill Sans',Calibri,system-ui,sans-serif}
.wrap{max-width:880px;margin:0 auto;padding:36px 20px 80px}
h1{font-family:'Avenir Next Condensed','Arial Narrow',sans-serif;font-weight:600;font-size:1.9rem;margin:0 0 2px}
.sub{color:var(--ink2);margin:0 0 20px;max-width:66ch}
.eyebrow{font-family:ui-monospace,Menlo,monospace;font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink3);margin:28px 0 8px}
.mono{font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
.stats{display:flex;gap:10px;flex-wrap:wrap}
.stat{background:var(--card);border:1px solid var(--hair);border-radius:6px;padding:8px 14px;font-family:ui-monospace,Menlo,monospace;font-size:.85rem}
.stat b{font-size:1.15rem}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.tab{border:1px solid var(--hair);background:var(--card);color:var(--ink2);border-radius:99px;padding:6px 14px;font:inherit;font-size:.86rem;cursor:pointer}
.tab[aria-selected=true]{background:var(--acc);border-color:var(--acc);color:#fff}
input,textarea{width:100%;padding:11px 14px;border:1px solid var(--hair);border-radius:6px;background:var(--card);color:var(--ink);font:inherit}
input:focus,textarea:focus{outline:2px solid var(--acc)}
button.go{margin-top:8px;border:0;background:var(--acc);color:#fff;border-radius:6px;padding:10px 18px;font:inherit;cursor:pointer}
button.go:disabled{opacity:.5;cursor:wait}
.hit,.story{background:var(--card);border:1px solid var(--hair);border-radius:6px;padding:10px 14px;margin:8px 0}
.story{padding:12px 16px;margin:10px 0}
.story summary{cursor:pointer}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.dt{color:var(--ink3);font-size:.8rem;font-family:ui-monospace,Menlo,monospace}
.fl{font-family:ui-monospace,Menlo,monospace;font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);margin:12px 0 4px}
ul{margin:4px 0;padding-left:20px}li{margin:3px 0}
.win{border-left:2px solid var(--hair);padding-left:12px;margin:10px 0}
.verdict{border-radius:6px;padding:12px 16px;margin:12px 0;border:1px solid var(--hair);background:var(--card)}
.verdict .tag{font-family:ui-monospace,Menlo,monospace;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#fff;border-radius:99px;padding:3px 10px}
.tag.current{background:var(--ok)}.tag.partially_outdated{background:var(--warn)}.tag.outdated{background:var(--bad)}.tag.unknown{background:var(--ink3)}
footer{margin-top:40px;color:var(--ink3);font-size:.76rem}
#loading{color:var(--ink3);font-family:ui-monospace,Menlo,monospace}
@media(prefers-reduced-motion:no-preference){.story{transition:border-color .15s}.story:hover{border-color:var(--acc)}}
</style>
<div class="wrap">
<p class="eyebrow">uptodate · timelines refreshed <span id="refreshed" class="mono">…</span></p>
<h1>Is that article still true?</h1>
<p class="sub">Living timelines of AI, ML, and Data Engineering topics, distilled from
multiple sources and cross-examined for agreements and contradictions — every claim cited.
Paste an article below to check it against the current state of its topic.</p>
<div class="stats" id="stats"><span id="loading">loading data…</span></div>

<p class="eyebrow" id="check-eyebrow">check an article</p>
<div id="checker">
  <input id="check-url" type="url" placeholder="https://… (or paste the article text below)" aria-label="Article URL">
  <textarea id="check-text" rows="3" placeholder="…or paste article text here" aria-label="Article text" style="margin-top:8px"></textarea>
  <button class="go" id="check-go">Check freshness</button>
  <div id="check-result"></div>
</div>

<p class="eyebrow">search the corpus</p>
<input id="q" type="search" placeholder="e.g. mcp server, dbt, claude memory…" aria-label="Search articles">
<div id="res"></div>

<p class="eyebrow">timelines</p>
<div class="tabs" id="tabs" role="tablist"></div>
<div id="stories"></div>

<footer>Built by the uptodate-tldr pipeline · sources: Hacker News, arXiv, curated RSS ·
all article credit belongs to the linked authors.</footer>
</div>
<script>
/*__BOOT__*/
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let DATA={};

async function load(){
  if(EMBEDDED){DATA=EMBEDDED;}
  else{
    const names=["topics","timelines","search_index","meta"];
    const got=await Promise.all(names.map(n=>fetch(`${DATA_URL}/${n}.json`).then(r=>{
      if(!r.ok)throw new Error(`${n}: HTTP ${r.status}`);return r.json();})));
    names.forEach((n,i)=>DATA[n]=got[i]);
  }
  render();
}

function render(){
  const m=DATA.meta;
  $("refreshed").textContent=(m.refreshed_at||"").slice(0,10);
  $("stats").innerHTML=`
    <span class="stat"><b>${m.articles}</b> articles</span>
    <span class="stat"><b>${m.storylines}</b> storylines</span>
    <span class="stat"><b>${m.analyses}</b> analyses</span>
    <span class="stat"><b>${m.categories.length}</b> categories</span>`;
  const cats=["All",...m.categories];
  $("tabs").innerHTML=cats.map((c,i)=>
    `<button class="tab" role="tab" aria-selected="${i===0}" data-cat="${esc(c)}">${esc(c)}</button>`).join("");
  $("tabs").addEventListener("click",e=>{
    const b=e.target.closest(".tab");if(!b)return;
    document.querySelectorAll(".tab").forEach(t=>t.setAttribute("aria-selected",t===b));
    stories(b.dataset.cat);
  });
  stories("All");
}

function renderList(label,items){
  if(!items||!items.length)return "";
  return `<p class="fl">${label}</p><ul>${items.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
}

function stories(cat){
  const groups=DATA.topics.filter(t=>cat==="All"||t.category===cat);
  $("stories").innerHTML=groups.map(t=>{
    const wins=(DATA.timelines[t.label]||[]).map(a=>
      `<div class="win"><p class="dt">${a.period_start.slice(0,10)} → ${a.period_end.slice(0,10)}</p>`
      +renderList("Agreements",a.agreements)+renderList("Contradictions",a.contradictions)
      +renderList("Debunks",a.debunks)+renderList("Unresolved",a.unresolved)
      +`<p class="fl">Sources</p><ul>${a.sources.map(s=>
         `<li><a href="${esc(s.url)}" rel="noopener">${esc(s.title.slice(0,90))}</a></li>`).join("")}</ul></div>`
    ).join("")||`<p class="dt">No comparative analysis yet (next refresh).</p>`;
    return `<details class="story"><summary><b>${esc(t.label)}</b>
      <span class="dt">${t.size} articles · ${esc(t.period[0])} → ${esc(t.period[1])} · ${esc(t.category)}</span></summary>
      ${wins}</details>`;
  }).join("")||`<p class="dt">no storylines in this category yet</p>`;
}

/* search */
const STOP=new Set("the and for with that this from are was were has have had you your not can will its our their they them than but all any out use using new now get more most into over under about after also just like one two how what when where which who why been does did don of in on at to is it as by be or we".split(" "));
const toks=s=>(s.toLowerCase().match(/[a-z][a-z0-9+#.-]{2,}/g)||[]).filter(t=>!STOP.has(t));
function qvec(s){const c={};toks(s).forEach(t=>c[t]=(c[t]||0)+1);let n=0;
  for(const t in c){c[t]=1+Math.log(c[t]);n+=c[t]*c[t]}n=Math.sqrt(n)||1;
  for(const t in c)c[t]/=n;return c}
const cos=(q,v)=>{let s=0;for(const t in q)if(v[t])s+=q[t]*v[t];return s};
$("q").addEventListener("input",e=>{
  const q=qvec(e.target.value);
  if(!Object.keys(q).length){$("res").innerHTML="";return}
  const hits=DATA.search_index.map(d=>[cos(q,d.v),d]).filter(([s])=>s>0.05)
    .sort((a,b)=>b[0]-a[0]).slice(0,6);
  $("res").innerHTML=hits.map(([s,d])=>
    `<div class="hit"><a href="${esc(d.u)}" rel="noopener">${esc(d.t)}</a>
     <span class="dt">${esc(d.d)} · ${s.toFixed(3)}</span></div>`).join("")
    ||'<p class="dt">no matches above the noise floor</p>';
});

/* freshness checker */
$("check-go").addEventListener("click",async()=>{
  const url=$("check-url").value.trim(),text=$("check-text").value.trim();
  const out=$("check-result");
  if(!url&&!text){out.innerHTML='<p class="dt">give me a URL or some text first</p>';return}
  $("check-go").disabled=true;
  out.innerHTML='<p class="dt">checking against the timeline…</p>';
  try{
    const r=await fetch("/api/check",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(url?{url}:{text})});
    const v=await r.json();
    if(!r.ok)throw new Error(v.error||`HTTP ${r.status}`);
    out.innerHTML=`<div class="verdict">
      <span class="tag ${esc(v.verdict)}">${esc(v.verdict.replace("_"," "))}</span>
      <p>${esc(v.summary||"")}</p>
      ${renderList("Reasons",v.reasons)}
      ${v.evidence&&v.evidence.length?`<p class="fl">Evidence</p><ul>${v.evidence.map(e=>
        `<li><a href="${esc(e.url)}" rel="noopener">${esc(e.title)}</a> <span class="dt">${esc(e.date||"")}</span></li>`).join("")}</ul>`:""}
    </div>`;
  }catch(err){
    out.innerHTML=`<div class="verdict"><span class="tag unknown">unavailable</span>
      <p class="dt">${esc(err.message)} — the checker API may not be deployed on this host.</p></div>`;
  }finally{$("check-go").disabled=false}
});

load().catch(err=>{$("loading").textContent=`failed to load data: ${err.message}`});
</script>"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the timeline site")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--data-url", default=None,
                    help="Snapshot base URL (e.g. Vercel Blob); omit to embed")
    args = ap.parse_args()
    build(args.out, args.data_url)


if __name__ == "__main__":
    main()
