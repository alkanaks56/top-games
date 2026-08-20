"""The dashboard's markup, styling and behaviour.

A market-terminal reading of the brief: dense tabular data, monospaced figures,
movement carried entirely by colour and a rank sparkline.
"""

STYLE = r"""
:root{
  --bg:#0a0c10; --surface:#0f131a; --row:#11161e; --row-hover:#151b25;
  --line:#1c222c; --line-soft:#161b24;
  --ink:#e6ebf2; --dim:#8b95a5; --faint:#5c6675;
  --up:#35d489; --down:#ff5f5f; --flat:#5c6675;
  --signal:#ffd23f; --mint:#3ddc84;
  --radius:8px;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
:focus-visible{outline:2px solid var(--mint);outline-offset:2px;border-radius:4px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}

/* ---------- top bar ---------- */
.topbar{display:flex;align-items:center;gap:26px;padding:13px 22px;
  background:var(--surface);border-bottom:1px solid var(--line);
  position:sticky;top:0;z-index:20;flex-wrap:wrap}
.brand{font-weight:800;font-size:17px;letter-spacing:.02em;white-space:nowrap}
.brand i{color:var(--mint);font-style:normal}
.brand span{font-family:var(--mono);font-size:11px;font-weight:500;color:var(--faint);
  letter-spacing:.06em;margin-left:9px}
.tabs{display:flex;gap:3px;flex-wrap:wrap}
.tabs button{font:inherit;font-size:11.5px;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;color:var(--dim);background:none;border:none;
  padding:8px 15px;border-radius:20px;cursor:pointer;transition:color .12s,background .12s}
.tabs button:hover{color:var(--ink)}
.tabs button.on{background:var(--mint);color:#06210f}
.spacer{flex:1}
.sync{font-family:var(--mono);font-size:11.5px;color:var(--faint);
  letter-spacing:.03em;display:flex;align-items:center;gap:7px;white-space:nowrap}
.dot{width:7px;height:7px;border-radius:50%;background:var(--up);
  box-shadow:0 0 0 3px rgba(53,212,137,.16)}
.btn{font:inherit;font-size:11.5px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;padding:9px 15px;border-radius:var(--radius);cursor:pointer;
  border:1px solid var(--line);background:transparent;color:var(--dim);
  transition:border-color .12s,color .12s}
.btn:hover{border-color:var(--faint);color:var(--ink)}
.btn.solid{background:#e6ebf2;border-color:#e6ebf2;color:#0a0c10}
.btn.solid:hover{background:#fff;border-color:#fff;color:#0a0c10}

/* ---------- movers ticker ---------- */
.ticker{display:flex;align-items:stretch;border-bottom:1px solid var(--line);
  background:var(--bg);overflow:hidden}
.ticker-tag{background:var(--signal);color:#241c00;font-size:11px;font-weight:800;
  letter-spacing:.11em;text-transform:uppercase;padding:12px 18px;white-space:nowrap;
  display:flex;align-items:center}
.ticker-rail{display:flex;overflow-x:auto;scrollbar-width:none}
.ticker-rail::-webkit-scrollbar{display:none}
.tick{display:flex;align-items:center;gap:9px;padding:12px 20px;white-space:nowrap;
  border-right:1px solid var(--line-soft);font-size:13px}
.tick b{font-weight:600}
.tick em{font-family:var(--mono);font-style:normal;font-size:12px;font-weight:700}
.tick .up{color:var(--up)} .tick .down{color:var(--down)} .tick .flat{color:var(--flat)}

/* ---------- hero ---------- */
main{padding:0 22px 70px}
.hero{display:flex;gap:40px;align-items:flex-end;justify-content:space-between;
  padding:34px 0 26px;flex-wrap:wrap}
h1{margin:0;font-size:clamp(28px,4.4vw,44px);font-weight:700;letter-spacing:-.028em;
  line-height:1.06}
h1 .thin{color:var(--dim);font-weight:400}
.lede{margin:11px 0 0;color:var(--dim);font-size:13.5px;max-width:62ch}
.figures{display:flex;gap:0;flex-shrink:0}
.fig{padding:0 26px;border-left:1px solid var(--line);text-align:right}
.fig:first-child{border-left:none}
.fig .n{font-family:var(--mono);font-size:31px;font-weight:600;letter-spacing:-.02em;
  line-height:1.1}
.fig .l{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);
  margin-top:5px}
.fig.up .n{color:var(--up)} .fig.down .n{color:var(--down)}

/* ---------- controls ---------- */
.controls{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:16px}
.ctl{display:flex;align-items:center;gap:8px;border:1px solid var(--line);
  border-radius:var(--radius);padding:8px 13px;background:var(--surface);font-size:12.5px;
  flex:0 0 auto}
.ctl label{color:var(--faint);font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.ctl select{font:inherit;font-size:12.5px;background:none;border:none;color:var(--ink);
  cursor:pointer;padding-right:2px;max-width:150px;text-overflow:ellipsis}
.ctl select option{background:var(--surface);color:var(--ink)}
.ctl.active{border-color:var(--mint)}
.ctl.active select,.ctl.active label{color:var(--mint)}
.seg{display:flex;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.seg button{font:inherit;font-size:11px;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;padding:9px 15px;background:none;border:none;color:var(--faint);
  cursor:pointer}
.seg button.on{background:var(--row-hover);color:var(--ink)}
.search{flex:1 1 200px;min-width:170px}
.search input{width:100%;font:inherit;font-size:12.5px;padding:9px 13px;
  border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);
  color:var(--ink)}
.search input::placeholder{color:var(--faint)}

/* ---------- table ---------- */
.panel{border:1px solid var(--line);border-radius:11px;overflow:hidden;background:var(--surface)}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:960px}
thead th{text-align:left;font-size:10px;font-weight:700;letter-spacing:.12em;
  text-transform:uppercase;color:var(--faint);padding:13px 14px;
  border-bottom:1px solid var(--line);white-space:nowrap;user-select:none}
thead th.sortable{cursor:pointer}
thead th.sortable:hover{color:var(--ink)}
thead th .ar{opacity:.35;margin-left:5px;font-size:9px}
thead th.sorted{color:var(--mint)}
thead th.sorted .ar{opacity:1}
tbody td{padding:13px 14px;border-bottom:1px solid var(--line-soft);vertical-align:middle}
tbody tr:last-child td{border-bottom:none}
tbody tr{background:var(--row);transition:background .1s}
tbody tr:hover{background:var(--row-hover)}
.c-rank{font-family:var(--mono);font-size:14px;font-weight:600;color:var(--dim);width:52px}
.c-d{width:74px}
.d{font-family:var(--mono);font-size:12.5px;font-weight:700;white-space:nowrap}
.d.up{color:var(--up)} .d.down{color:var(--down)} .d.flat{color:var(--flat)}
.game{display:flex;align-items:center;gap:13px;min-width:230px}
.ico{width:40px;height:40px;border-radius:10px;flex-shrink:0;background:var(--row-hover);
  object-fit:cover}
.g-name{font-weight:600;font-size:14px;letter-spacing:-.005em}
.g-sub{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:2px}
.tag{display:inline-block;font-family:var(--mono);font-size:9.5px;font-weight:700;
  letter-spacing:.06em;padding:2px 6px;border-radius:4px;margin-left:7px;
  text-transform:uppercase;vertical-align:1px}
.tag.new{background:rgba(61,220,132,.14);color:var(--mint)}
.tag.fresh{background:rgba(255,210,63,.14);color:var(--signal)}
.tag.count{background:var(--row-hover);color:var(--dim);border:1px solid var(--line)}
.co{font-size:13px;white-space:nowrap}
.rating{font-family:var(--mono);font-size:13.5px;font-weight:600;white-space:nowrap}
.rating .star{color:var(--signal);margin-right:4px}
.bar{height:3px;border-radius:2px;background:var(--line);margin-top:6px;width:112px;
  overflow:hidden}
.bar i{display:block;height:100%;background:var(--up);border-radius:2px}
.num{font-family:var(--mono);font-size:13px;text-align:right;white-space:nowrap}
.num.dim{color:var(--dim)}
.mono-dim{font-family:var(--mono);font-size:12.5px;color:var(--dim)}
.spark{display:flex;align-items:flex-end;gap:2px;height:26px;width:66px}
.spark i{flex:1;border-radius:1px;min-height:2px;background:var(--flat);opacity:.55}
.spark.up i{background:var(--up);opacity:.85}
.spark.down i{background:var(--down);opacity:.85}
.spark.none{color:var(--faint);font-family:var(--mono);font-size:11px;align-items:center}
.price{font-family:var(--mono);font-size:11px;color:var(--dim);border:1px solid var(--line);
  padding:3px 9px;border-radius:5px;white-space:nowrap}

/* ---------- grid view ---------- */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:12px}
.card{border:1px solid var(--line);border-radius:11px;background:var(--surface);
  padding:15px;transition:border-color .12s}
.card:hover{border-color:var(--faint)}
.card-top{display:flex;gap:12px;align-items:flex-start;margin-bottom:13px;min-height:52px}
.card .g-name{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;line-height:1.3}
.card .rk{font-family:var(--mono);font-size:12px;color:var(--faint);font-weight:600}
.card-row{display:flex;justify-content:space-between;font-size:12px;padding:4px 0;
  color:var(--dim)}
.card-row b{font-family:var(--mono);color:var(--ink);font-weight:600}

/* ---------- timeline view ---------- */
.tl-row{display:flex;align-items:center;gap:15px;padding:11px 15px;
  border-bottom:1px solid var(--line-soft)}
.tl-row:last-child{border-bottom:none}
.tl-name{width:210px;flex-shrink:0;font-size:13px;font-weight:600;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.tl-track{flex:1;height:30px;position:relative;min-width:150px}
.tl-track svg{width:100%;height:100%;overflow:visible}
.tl-end{font-family:var(--mono);font-size:12px;color:var(--dim);width:82px;text-align:right}

/* ---------- footer ---------- */
.tfoot{display:flex;justify-content:space-between;align-items:center;gap:16px;
  padding:15px 4px;font-size:12px;color:var(--faint);flex-wrap:wrap}
.pager{display:flex;gap:5px;align-items:center}
.pager button{font:inherit;font-family:var(--mono);font-size:12px;padding:5px 10px;
  border:1px solid transparent;border-radius:6px;background:none;color:var(--dim);
  cursor:pointer}
.pager button:hover:not(:disabled){border-color:var(--line);color:var(--ink)}
.pager button.on{background:var(--row-hover);color:var(--ink);border-color:var(--line)}
.pager button:disabled{opacity:.3;cursor:not-allowed}
.empty{padding:64px 20px;text-align:center;color:var(--faint)}
.note{border:1px solid var(--line);border-left:2px solid var(--signal);border-radius:8px;
  padding:13px 16px;margin-bottom:16px;color:var(--dim);font-size:12.5px;
  background:var(--surface)}
.note b{color:var(--ink);font-weight:600}
@media(max-width:760px){
  .figures{width:100%;justify-content:space-between}
  .fig{padding:0 12px}.fig .n{font-size:23px}
  .hero{padding-top:24px}
}
"""

BODY = r"""
<header class="topbar">
  <div class="brand">TOP<i>/</i>GAMES <span>__SCOPE__</span></div>
  <nav class="tabs" id="tabs">
    <button data-tab="top" class="on">Top 100</button>
    <button data-tab="new">New releases</button>
    <button data-tab="movers">Movers</button>
    <button data-tab="publishers">Publishers</button>
    <button data-tab="digest">Slack digest</button>
  </nav>
  <div class="spacer"></div>
  <div class="sync"><span class="dot"></span> synced __SYNC__ · itunes rss</div>
  <button class="btn" id="csv">Export CSV</button>
  <a class="btn solid" href="__ACTIONS__" target="_blank" rel="noopener">Send digest</a>
</header>

<div class="ticker" id="ticker"></div>

<main>
  <section class="hero">
    <div>
      <h1 id="title"></h1>
      <p class="lede" id="lede"></p>
    </div>
    <div class="figures" id="figures"></div>
  </section>
  <div id="controls"></div>
  <div id="view"></div>
  <div class="tfoot" id="tfoot"></div>
</main>
"""

SCRIPT = r"""
const D = __DATA__;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const num = n => (n || 0).toLocaleString('en-US');
const PER_PAGE = 10;

const S = { tab:'top', view:'table', sort:'rank', dir:1, page:1,
            q:'', publisher:'all', minRating:0, released:'any' };

/* The delta column can only describe the span the database actually covers. */
const spanLabel = D.span_days >= 7 ? 'Δ 7D'
                : D.span_days >= 1 ? `Δ ${D.span_days}D`
                : 'Δ TODAY';

function deltaCell(d, isNew){
  if (isNew) return '<span class="d up">NEW</span>';
  if (d === null || d === undefined) return '<span class="d flat">–</span>';
  if (d > 0) return `<span class="d up">▲ ${d}</span>`;
  if (d < 0) return `<span class="d down">▼ ${Math.abs(d)}</span>`;
  return '<span class="d flat">— 0</span>';
}

function spark(history){
  if (!history || history.length < 2)
    return '<div class="spark none">—</div>';
  const lo = Math.min(...history), hi = Math.max(...history);
  if (lo === hi){
    // Held the same rank throughout: draw a low flat run rather than full-height
    // bars, which would otherwise read as a solid block.
    return `<div class="spark">${history.map(() =>
      '<i style="height:16%"></i>').join('')}</div>`;
  }
  const range = hi - lo;
  const dir = history[history.length-1] < history[0] ? 'up'
            : history[history.length-1] > history[0] ? 'down' : '';
  // Rank 1 is best, so invert: a smaller rank must draw a taller bar.
  const bars = history.map(r =>
    `<i style="height:${Math.round(18 + (1 - (r - lo)/range) * 82)}%"></i>`).join('');
  return `<div class="spark ${dir}">${bars}</div>`;
}

function filtered(){
  let rows = D.items.slice();
  if (S.q){
    const q = S.q.toLowerCase();
    rows = rows.filter(r => (r.name + ' ' + r.artist).toLowerCase().includes(q));
  }
  if (S.publisher !== 'all') rows = rows.filter(r => r.artist === S.publisher);
  if (S.minRating) rows = rows.filter(r => r.rating >= S.minRating);
  if (S.released !== 'any'){
    const days = Number(S.released);
    const cutoff = Date.now() - days*864e5;
    rows = rows.filter(r => r.released && new Date(r.released).getTime() >= cutoff);
  }
  const key = S.sort;
  rows.sort((a,b) => {
    let x = a[key], y = b[key];
    if (key === 'delta'){ x = a.delta ?? -999; y = b.delta ?? -999; }
    if (typeof x === 'string') return x.localeCompare(y) * S.dir;
    return ((x ?? 0) - (y ?? 0)) * S.dir;
  });
  return rows;
}

function renderTicker(){
  const moving = D.movers.length > 0;
  const items = moving ? D.movers : D.items.slice(0, 12);
  $('#ticker').innerHTML =
    `<div class="ticker-tag">${moving ? "Today's movers" : 'Leading now'}</div>
     <div class="ticker-rail">` +
    items.map(m => {
      const d = m.delta;
      // Before any movement exists, showing "— 0" twelve times says nothing;
      // the current rank is the useful figure instead.
      if (!moving)
        return `<a class="tick" href="${esc(m.url)}" target="_blank" rel="noopener">
          <em class="flat">#${String(m.rank).padStart(2,'0')}</em><b>${esc(m.name)}</b></a>`;
      const cls = d > 0 ? 'up' : d < 0 ? 'down' : 'flat';
      const gl = d > 0 ? '▲' : d < 0 ? '▼' : '—';
      return `<a class="tick" href="${esc(m.url)}" target="_blank" rel="noopener">
        <b>${esc(m.name)}</b><em class="${cls}">${gl} ${Math.abs(d || 0)}</em></a>`;
    }).join('') + '</div>';
}

function renderHero(){
  const t = { top:['Top 100 free', D.stats.tracked + ' titles · ' + D.stats.publishers + ' publishers'],
              new:['New releases', 'Released in the last ' + D.new_days + ' days'],
              movers:['Biggest movers', 'Ranked by size of rank change'],
              publishers:['Publishers', 'Grouped by company across the chart'],
              digest:['Slack digest', 'What lands in your channel'] }[S.tab];
  $('#title').innerHTML = `${esc(D.genre)}, ${esc(D.country_name)} <span class="thin">— ${t[0]}</span>`;
  $('#lede').textContent =
    `Ranked from the iTunes RSS chart, enriched with the Lookup API. ${t[1]}.`;
  const f = D.stats;
  $('#figures').innerHTML = [
    ['', f.tracked, 'Tracked'],
    ['up', f.climbing, 'Climbing'],
    ['down', f.falling, 'Falling'],
    ['', f.median_rating.toFixed(2), 'Median rating'],
  ].map(([c,n,l]) =>
    `<div class="fig ${c}"><div class="n">${n}</div><div class="l">${l}</div></div>`).join('');
}

function renderControls(){
  if (S.tab === 'digest' || S.tab === 'publishers'){ $('#controls').innerHTML=''; return; }
  const pubs = [...new Set(D.items.map(i => i.artist))].sort();
  const sortActive = S.sort !== 'rank' || S.dir !== 1;
  $('#controls').innerHTML = `
   <div class="controls">
    <div class="ctl ${sortActive?'active':''}"><label>Sort</label>
      <select id="f-sort">
        <option value="rank|1">Rank, best first</option>
        <option value="delta|-1">Rank change, high → low</option>
        <option value="delta|1">Rank change, low → high</option>
        <option value="rating|-1">Rating, high → low</option>
        <option value="ratings|-1">Ratings count, high → low</option>
        <option value="released|-1">Newest release first</option>
        <option value="name|1">Title, A → Z</option>
      </select></div>
    <div class="ctl ${S.publisher!=='all'?'active':''}"><label>Publisher</label>
      <select id="f-pub"><option value="all">All</option>
      ${pubs.map(p=>`<option ${S.publisher===p?'selected':''}>${esc(p)}</option>`).join('')}
      </select></div>
    <div class="ctl ${S.minRating?'active':''}"><label>Rating</label>
      <select id="f-rating">
        <option value="0">Any</option><option value="4">4.0+</option>
        <option value="4.5">4.5+</option><option value="4.8">4.8+</option>
      </select></div>
    <div class="ctl ${S.released!=='any'?'active':''}"><label>Released</label>
      <select id="f-rel">
        <option value="any">Any time</option><option value="30">Last 30 days</option>
        <option value="90">Last 90 days</option><option value="365">Last year</option>
      </select></div>
    <div class="seg">
      ${['table','grid','timeline'].map(v =>
        `<button data-view="${v}" class="${S.view===v?'on':''}">${v}</button>`).join('')}
    </div>
    <div class="search"><input id="f-q" type="search" value="${esc(S.q)}"
      placeholder="Search title or company…"></div>
   </div>`;
  $('#f-sort').value = `${S.sort}|${S.dir}`;
  $('#f-rating').value = String(S.minRating);
  $('#f-rel').value = S.released;
  $('#f-sort').onchange = e => { const [k,d] = e.target.value.split('|');
    S.sort = k; S.dir = Number(d); S.page = 1; render(); };
  $('#f-pub').onchange = e => { S.publisher = e.target.value; S.page = 1; render(); };
  $('#f-rating').onchange = e => { S.minRating = Number(e.target.value); S.page=1; render(); };
  $('#f-rel').onchange = e => { S.released = e.target.value; S.page = 1; render(); };
  $('#f-q').oninput = e => { S.q = e.target.value; S.page = 1; renderBody(); };
  document.querySelectorAll('[data-view]').forEach(b =>
    b.onclick = () => { S.view = b.dataset.view; render(); });
}

const TH = (key,label,extra='') => {
  const on = S.sort === key;
  return `<th class="sortable ${on?'sorted':''}" data-sort="${key}" ${extra}>${label}
    <span class="ar">${on ? (S.dir===1?'▲':'▼') : '▲▼'}</span></th>`;
};

function tableFor(rows){
  return `<div class="panel"><div class="scroll"><table>
    <thead><tr>
      ${TH('rank','#')}${TH('delta',spanLabel)}${TH('name','Game')}
      ${TH('artist','Company')}${TH('rating','Rating')}${TH('ratings','Ratings')}
      ${TH('released','Released')}<th>Rank trend</th>${TH('price','Price')}
    </tr></thead><tbody>
    ${rows.map(r => `<tr>
      <td class="c-rank">${String(r.rank).padStart(2,'0')}</td>
      <td class="c-d">${deltaCell(r.delta, r.is_new_entry)}</td>
      <td><div class="game">
        <img class="ico" loading="lazy" src="${esc(r.icon)}" alt="">
        <div><div class="g-name">${esc(r.name)}${
            r.is_new_release ? '<span class="tag fresh">fresh</span>' : ''}</div>
          <div class="g-sub">${esc(r.genre)}</div></div></div></td>
      <td><div class="co">${esc(r.artist)}${
          r.titles_charting > 1 ? `<span class="tag count">×${r.titles_charting}</span>` : ''
        }</div></td>
      <td><div class="rating"><span class="star">★</span>${r.rating.toFixed(2)}</div>
        <div class="bar"><i style="width:${(r.rating/5*100).toFixed(1)}%"></i></div></td>
      <td class="num">${num(r.ratings)}</td>
      <td class="num dim">${esc(r.released)}</td>
      <td>${spark(r.history)}</td>
      <td><span class="price">${esc(r.price)}</span></td>
    </tr>`).join('')}
    </tbody></table></div></div>`;
}

function gridFor(rows){
  return `<div class="grid">${rows.map(r => `
    <a class="card" href="${esc(r.url)}" target="_blank" rel="noopener">
      <div class="card-top">
        <img class="ico" loading="lazy" src="${esc(r.icon)}" alt="">
        <div><div class="g-name">${esc(r.name)}</div>
          <div class="g-sub">${esc(r.artist)}</div></div>
      </div>
      <div class="card-row"><span class="rk">#${String(r.rank).padStart(2,'0')}</span>
        ${deltaCell(r.delta, r.is_new_entry)}</div>
      <div class="card-row"><span>Rating</span><b>${r.rating.toFixed(2)}</b></div>
      <div class="card-row"><span>Ratings</span><b>${num(r.ratings)}</b></div>
      <div class="card-row"><span>Released</span><b>${esc(r.released)}</b></div>
    </a>`).join('')}</div>`;
}

function timelineFor(rows){
  const usable = rows.filter(r => r.history.length >= 2);
  if (!usable.length)
    return `<div class="panel"><div class="empty">
      Rank history needs at least two snapshots on different days.<br>
      The timeline fills in as the scheduled job runs.</div></div>`;
  return `<div class="panel">${usable.map(r => {
    const h = r.history, lo = Math.min(...h), hi = Math.max(...h);
    const range = Math.max(hi - lo, 1);
    const pts = h.map((v,i) =>
      `${(i/(h.length-1)*100).toFixed(1)},${((v-lo)/range*100).toFixed(1)}`).join(' ');
    const dir = h[h.length-1] < h[0] ? 'var(--up)'
              : h[h.length-1] > h[0] ? 'var(--down)' : 'var(--flat)';
    return `<div class="tl-row">
      <div class="tl-name">${esc(r.name)}</div>
      <div class="tl-track"><svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <polyline points="${pts}" fill="none" stroke="${dir}" stroke-width="2.5"
          vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg></div>
      <div class="tl-end">#${h[0]} → #${h[h.length-1]}</div>
    </div>`; }).join('')}</div>`;
}

function publishersView(){
  const rows = D.publishers;
  return `<div class="panel"><div class="scroll"><table>
    <thead><tr><th>#</th><th>Company</th><th>Titles</th><th>Best rank</th>
      <th>Avg rating</th><th>Total ratings</th><th>Net change</th></tr></thead><tbody>
    ${rows.map((p,i) => `<tr>
      <td class="c-rank">${String(i+1).padStart(2,'0')}</td>
      <td><div class="g-name">${esc(p.artist)}</div></td>
      <td class="num">${p.titles}</td>
      <td class="num">#${p.best_rank}</td>
      <td class="num">${p.avg_rating.toFixed(2)}</td>
      <td class="num">${num(p.ratings_total)}</td>
      <td>${deltaCell(p.net_delta, false)}</td>
    </tr>`).join('')}</tbody></table></div></div>`;
}

function digestView(){
  const d = D.digest;
  return `<div class="note">The dashboard cannot post to Slack on its own — it is a
    static page. <b>Send digest</b> opens the scheduled job on GitHub, where you can run it
    by hand.</div>
    <div class="panel"><div class="scroll"><table>
    <thead><tr><th>Digest</th><th>When</th><th>Includes</th></tr></thead><tbody>
    <tr><td class="g-name">Daily</td><td class="mono-dim">${esc(d.daily_time)} UTC</td>
      <td class="co">${d.daily.map(k=>`<span class="tag count">${esc(k)}</span>`).join(' ')}</td></tr>
    <tr><td class="g-name">Weekly</td>
      <td class="mono-dim">${esc(d.weekly_day)} ${esc(d.weekly_time)} UTC</td>
      <td class="co">${d.weekly.map(k=>`<span class="tag count">${esc(k)}</span>`).join(' ')}</td></tr>
    </tbody></table></div></div>`;
}

function renderBody(){
  const el = $('#view'), foot = $('#tfoot');
  if (S.tab === 'digest'){ el.innerHTML = digestView(); foot.innerHTML=''; return; }
  if (S.tab === 'publishers'){ el.innerHTML = publishersView();
    foot.innerHTML = `<div>${D.publishers.length} companies in the top ${D.stats.tracked}</div>`;
    return; }

  let rows = filtered();
  if (S.tab === 'new') rows = rows.filter(r => r.is_new_release);
  if (S.tab === 'movers') rows = rows.filter(r => r.delta);

  if (!rows.length){
    el.innerHTML = `<div class="panel"><div class="empty">${
      S.tab === 'movers'
        ? 'No rank movement recorded yet. Movement appears once two snapshots exist.'
        : S.tab === 'new'
        ? 'No games in this chart were released in the last ' + D.new_days + ' days.'
        : 'Nothing matches those filters.'}</div></div>`;
    foot.innerHTML = ''; return;
  }

  const pages = Math.max(1, Math.ceil(rows.length / PER_PAGE));
  S.page = Math.min(S.page, pages);
  const show = S.view === 'table' ? rows.slice((S.page-1)*PER_PAGE, S.page*PER_PAGE) : rows;

  el.innerHTML = S.view === 'grid' ? gridFor(rows)
               : S.view === 'timeline' ? timelineFor(rows)
               : tableFor(show);

  el.querySelectorAll('th[data-sort]').forEach(th => th.onclick = () => {
    const k = th.dataset.sort;
    if (S.sort === k) S.dir *= -1; else { S.sort = k; S.dir = k === 'rank' ? 1 : -1; }
    S.page = 1; render();
  });

  const first = (S.page-1)*PER_PAGE + 1, last = Math.min(S.page*PER_PAGE, rows.length);
  foot.innerHTML = S.view === 'table'
    ? `<div>Showing ${first}–${last} of ${rows.length} · refreshed daily</div>
       <div class="pager">
        <button ${S.page===1?'disabled':''} data-p="${S.page-1}">← prev</button>
        ${Array.from({length:pages},(_,i)=>i+1)
          .filter(p => p===1 || p===pages || Math.abs(p-S.page)<=1)
          .map((p,i,a) => (i && p - a[i-1] > 1 ? '<span>…</span>' : '') +
            `<button class="${p===S.page?'on':''}" data-p="${p}">${p}</button>`).join('')}
        <button ${S.page===pages?'disabled':''} data-p="${S.page+1}">next →</button>
       </div>`
    : `<div>Showing all ${rows.length} · refreshed daily</div>`;
  foot.querySelectorAll('[data-p]').forEach(b =>
    b.onclick = () => { S.page = Number(b.dataset.p); renderBody();
      window.scrollTo({top:0, behavior:'smooth'}); });
}

function render(){ renderHero(); renderControls(); renderBody(); }

document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#tabs button').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); S.tab = b.dataset.tab; S.page = 1; render();
});

$('#csv').onclick = () => {
  const rows = filtered();
  const head = ['rank','delta','name','company','genre','rating','ratings','released','price','url'];
  const body = rows.map(r => [r.rank, r.delta ?? '', r.name, r.artist, r.genre,
    r.rating, r.ratings, r.released, r.price, r.url]
    .map(v => `"${String(v).replace(/"/g,'""')}"`).join(','));
  const blob = new Blob([[head.join(','), ...body].join('\n')], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `top-games-${D.captured_at.slice(0,10)}.csv`;
  a.click(); URL.revokeObjectURL(a.href);
};

renderTicker();
render();
"""
