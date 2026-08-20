"""Render the tracker as a static site plus pre-built Slack payloads.

GitHub Pages serves plain files, so the dashboard ships with its data inlined
rather than fetching from an API. The same run also writes the Slack slash
command responses, which lets the Cloudflare Worker stay a thin, near-zero-CPU
proxy: it verifies the request signature and returns a file built here.
"""
import json
import os
from datetime import datetime, timezone

from . import command, store, web
from .templates import CSS

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__
.banner{background:var(--chip);border:1px solid var(--line);border-radius:11px;
  padding:11px 15px;margin-bottom:16px;color:var(--muted);font-size:13px}
</style></head><body>
<header>
  <div><h1>__TITLE__</h1><div class="sub">__SUB__</div></div>
  <div class="grow"></div>
  <input type="search" id="q" placeholder="Filter by name or studio…">
</header>
<nav>
  <button data-t="chart" class="on">Chart</button>
  <button data-t="new">New releases</button>
  <button data-t="events">Signals</button>
</nav>
<main>
  <div class="banner">Updates automatically __CADENCE__. Last refreshed
    <b>__UPDATED__</b> UTC.</div>
  <div class="cards" id="cards"></div>
  <div class="panel" id="view"></div>
</main>
<script>
const DATA=__DATA__;
const $=s=>document.querySelector(s);
let TAB='chart';
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const num=n=>(n||0).toLocaleString();
const stars=r=>r?r.toFixed(2)+'★':'—';
function delta(d,isNew){
  if(isNew) return '<span class="d up">NEW</span>';
  if(d===null||d===undefined) return '<span class="d flat">—</span>';
  if(d>0) return '<span class="d up">▲ '+d+'</span>';
  if(d<0) return '<span class="d down">▼ '+Math.abs(d)+'</span>';
  return '<span class="d flat">–</span>';
}
function filtered(rows){
  const q=$('#q').value.trim().toLowerCase();
  return q?rows.filter(r=>((r.name||'')+' '+(r.artist||'')).toLowerCase().includes(q)):rows;
}
function renderCards(){
  const c=DATA.chart;
  $('#cards').innerHTML=[
    ['Tracked apps',num(DATA.stats.apps)],
    ['New in chart',c.rows.filter(r=>r.is_new_entry).length],
    ['Recent releases charting',c.rows.filter(r=>r.is_new_release).length],
    ['Snapshots',num(DATA.stats.snapshots)],
    ['Signals logged',num(DATA.stats.events)],
  ].map(([k,v])=>`<div class="card"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
}
function renderChart(){
  const rows=filtered(DATA.chart.rows);
  if(!rows.length) return '<div class="empty">No chart data.</div>';
  return `<div class="wrap"><table><thead><tr><th>#</th><th></th><th>Game</th><th>Move</th>
    <th class="num">Rating</th><th class="num">Ratings</th><th class="num">Released</th>
    <th class="num">Price</th></tr></thead><tbody>`+rows.map(r=>`<tr>
      <td class="rank">${r.rank}</td>
      <td><img class="ico" loading="lazy" src="${esc(r.icon)}" alt=""></td>
      <td><a class="nm" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>
        ${r.is_new_entry?'<span class="tag new">new</span>':''}
        ${r.is_new_release?'<span class="tag fresh">fresh</span>':''}
        <div class="by">${esc(r.artist)}</div></td>
      <td>${delta(r.delta,r.is_new_entry)}</td>
      <td class="num">${stars(r.rating)}</td><td class="num">${num(r.ratings)}</td>
      <td class="num by">${esc(r.release_date)}</td>
      <td class="num by">${esc(r.price||'—')}</td></tr>`).join('')+'</tbody></table></div>';
}
function renderNew(){
  const rows=filtered(DATA.new);
  if(!rows.length) return '<div class="empty">No recent releases.</div>';
  return `<div class="wrap"><table><thead><tr><th></th><th>Game</th>
    <th class="num">Released</th><th class="num">Rating</th><th class="num">Ratings</th>
    </tr></thead><tbody>`+rows.map(r=>`<tr>
      <td><img class="ico" loading="lazy" src="${esc(r.icon)}" alt=""></td>
      <td><a class="nm" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>
        <div class="by">${esc(r.artist)}</div></td>
      <td class="num">${esc((r.release_date||'').slice(0,10))}</td>
      <td class="num">${stars(r.avg_rating)}</td>
      <td class="num">${num(r.rating_count)}</td></tr>`).join('')+'</tbody></table></div>';
}
function renderEvents(){
  const rows=filtered(DATA.events);
  if(!rows.length) return '<div class="empty">No signals recorded yet.</div>';
  const label={new_entry:'new in chart',debut:'new release charted',exit:'dropped out',
    climb:'climbing',fall:'falling',new_release:'new release'};
  return `<div class="wrap"><table><thead><tr><th>When</th><th>Signal</th><th>Game</th>
    <th>Detail</th></tr></thead><tbody>`+rows.map(r=>`<tr>
      <td class="by">${esc((r.created_at||'').slice(0,16).replace('T',' '))}</td>
      <td><span class="ev">${esc(label[r.kind]||r.kind)}</span></td>
      <td><a class="nm" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name||r.app_id)}</a>
        <div class="by">${esc(r.artist||'')}</div></td>
      <td class="by">${esc(r.detail)}</td></tr>`).join('')+'</tbody></table></div>';
}
function render(){
  renderCards();
  $('#view').innerHTML={chart:renderChart,new:renderNew,events:renderEvents}[TAB]();
}
$('#q').addEventListener('input',render);
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); TAB=b.dataset.t; render();
});
render();
</script></body></html>
"""


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def build(conn, cfg, outdir="site"):
    """Write the static site and the Slack payloads the Worker will serve."""
    chart = web._chart_payload(conn, cfg)
    new = web._new_releases(conn, cfg)[:100]
    events = web._events(conn, days=30)[:200]
    stats = store.stats(conn)
    genre = cfg["genre"].replace("_", " ").title()
    country = cfg["country"].upper()

    data = {
        "chart": chart,
        "new": [{k: r[k] for k in ("name", "artist", "url", "icon", "release_date",
                                   "avg_rating", "rating_count")} for r in new],
        "events": events,
        "stats": stats,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    daily = cfg["slack"]["daily"]
    weekly = cfg["slack"]["weekly"]
    cadence = []
    if daily.get("enabled"):
        cadence.append(f"daily at {daily.get('time')} UTC")
    if weekly.get("enabled"):
        cadence.append(f"weekly on {weekly.get('day')}")
    title = f"Top {genre} Games — {country}"

    html = (PAGE
            .replace("__CSS__", CSS)
            .replace("__DATA__", json.dumps(data, default=str))
            .replace("__TITLE__", title)
            .replace("__SUB__", f"{cfg['chart']} · top {cfg['chart_size']} · "
                                f"{stats['apps']} apps tracked")
            .replace("__CADENCE__", " and ".join(cadence) or "on schedule")
            .replace("__UPDATED__", (chart.get("captured_at") or "never")[:16]
                                    .replace("T", " ")))

    _write(os.path.join(outdir, "index.html"), html)
    # Tells GitHub Pages to publish files and folders beginning with an underscore.
    _write(os.path.join(outdir, ".nojekyll"), "")
    _write(os.path.join(outdir, "data", "chart.json"),
           json.dumps(data, indent=1, default=str))

    # Pre-render every slash-command response so the Worker does no real work.
    payloads = {
        "top100-25": command._chart_reply(conn, cfg, 25, False),
        "top100-50": command._chart_reply(conn, cfg, 50, False),
        "top100-100": command._chart_reply(conn, cfg, cfg["chart_size"], False),
        "new": command._new_reply(conn, cfg, False),
        "signals": command._signals_reply(conn, cfg, False),
        "help": command._reply([command._section(command.HELP)], "help"),
    }
    for name, payload in payloads.items():
        _write(os.path.join(outdir, "slack", f"{name}.json"),
               json.dumps(payload, default=str))

    return {"outdir": outdir, "chart_rows": len(chart["rows"]),
            "new": len(data["new"]), "events": len(events),
            "slack_payloads": sorted(payloads)}
