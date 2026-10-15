/* The Open Classical Chinese Character Atlas — the reading room.
 *
 * Ported from the Tao Te Ching's original atlas and extended to any number of
 * texts. Every character has its own address (BASE + 常 + /), so the grid is
 * made of links and the URL always names what the card shows.
 *
 * Two kinds of page load this script:
 *   <body data-page="atlas" [data-char="常"]>   the grid and the card
 *   <body data-page="entry" data-chars="無為">   a glossary entry; the card only
 */
(async function () {
const BASE = document.querySelector('meta[name="atlas-base"]').content;
const DATA_URL = document.querySelector('meta[name="atlas-data"]').content;
const PAGE = document.body.dataset.page;
const el = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, m =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const charUrl = c => BASE + encodeURIComponent(c) + '/';
const entryUrl = (tid, slug) => BASE + 'glossary/' + tid + '/' + encodeURIComponent(slug) + '/';
const SITE = 'Open Classical Chinese Character Atlas & Glossary';
if (PAGE === 'glossary') return glossaryPage();
if (PAGE !== 'atlas' && PAGE !== 'entry') return;   // index pages need no data
const D = await (await fetch(DATA_URL)).json();

const TEXTS = D.texts, TX = Object.fromEntries(TEXTS.map(t => [t.id, t]));
const CH = D.chars, G = D.glyphs, BUILT = D.built;
const byChar = Object.fromEntries(CH.map(c => [c.c, c]));

// ---------------------------------------------------------------- per-text view
// A character carries one record per text it appears in (c.t[tid]). The grid
// shows either one text or all of them; this folds the records into one row.
// The tab in force: 'all', or one text's id. It rides in the URL (?text=),
// so a shared link keeps its context.
const TAB_IDS = [...document.querySelectorAll('[role="tab"]')].map(b => b.dataset.text);
let tf = new URLSearchParams(location.search).get('text') || 'all';
if (!TAB_IDS.includes(tf)) tf = 'all';
const scopeQS = () => tf === 'all' ? '' : '?text=' + encodeURIComponent(tf);
function view(c){
  const ids = (tf === 'all' ? TEXTS.map(t => t.id) : [tf]).filter(id => c.t[id]);
  if (!ids.length) return null;
  const rs = ids.map(id => c.t[id]);
  return {
    ids, n: rs.reduce((a, r) => a + r.n, 0),
    cent: Math.max(...rs.map(r => r.cent || 0)),
    lock: rs.some(r => r.lock), fw: rs.every(r => r.fw),
    g: (rs.find(r => r.g) || {}).g || '', r: (rs.find(r => r.r) || {}).r || '',
  };
}

// ---------------------------------------------------------------- heat colour
// Each heat cell's number is black or white, whichever reads better on that
// cell's own blend of vermilion over the sunk surface. Fixed colours cannot
// reach 4.5:1 across the whole ramp; the better of the two always does.
function rgb(v){
  v = v.trim();
  if (v.startsWith('#')) return [1,3,5].map(i => parseInt(v.slice(i, i+2), 16));
  return v.split(',').map(Number);
}
function lum(c){
  const f = x => { x /= 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; };
  return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]);
}
function textOn(alpha){
  const cs = getComputedStyle(document.documentElement);
  const sem = rgb(cs.getPropertyValue('--heat-rgb')), base = rgb(cs.getPropertyValue('--sunk'));
  const bg = sem.map((s, i) => s * alpha + base[i] * (1 - alpha));
  const L = lum(bg);
  return (1.05 / (L + .05)) >= ((L + .05) / .05) ? '#fff' : '#000';
}

// ---------------------------------------------------------------- the card
let occLimit = 6, unitFilter = null, wOn = false;
// The part the grid is filtered to (a "Built from" tile), or null.
let compSel = null;

function partBtn(ch, role, link){
  const g = G[ch] || [null, null];
  const known = !!g[1];
  const meaning = role === 'sem' ? (g[1] || 'not yet glossed')
                                 : 'sound only — carries no meaning here';
  const tag = link ? 'a' : 'button';
  const on = !link && compSel === ch;
  const attr = link ? `href="${BASE}?built=${encodeURIComponent(ch)}"`
                    : `type="button" data-comp="${esc(ch)}" aria-pressed="${on}"`;
  return `<${tag} class="part ${role}" ${attr}
      title="${on ? 'Showing every character built from ' + esc(ch) + ' — click to reset'
                  : 'Show every character built from ' + esc(ch)}" style="text-decoration:none">
      <span class="pg">${esc(ch)}</span>
      <span class="pt">${g[0] ? `<b>${esc(g[0])}</b>` : ''}
      <span${known || role === 'pho' ? '' : ' class="gap"'}>${esc(meaning)}</span></span>
    </${tag}>`;
}

// The way into the argument. Each text with an entry for this character gets
// one prominent button, directly under the character; an entry the character
// only takes part in (無 inside 無為) is a quieter link beneath it.
function glossaryButtons(c, texts){
  let h = '';
  const many = texts.filter(t => (c.t[t.id].entries || []).length).length > 1;
  for (const t of texts){
    const slugs = c.t[t.id].entries || [];
    if (!slugs.length) continue;
    const E = D.entries[t.id] || {};
    const main = slugs.find(s => E[s] && E[s].term === c.c) || slugs[0];
    const e = E[main];
    h += `<a class="gbtn" href="${entryUrl(t.id, main)}">
      <span><span class="k">${many ? esc(t.title) + ' · ' : ''}Read the glossary entry${
        e.status === 'open' ? ' · open' : ''}</span>
      <span class="t"><span class="zh">${esc(e.term)}</span> ${esc(e.pinyin)} — ${esc(e.render)}</span></span>
      <span class="arrow" aria-hidden="true">→</span></a>`;
    const rest = slugs.filter(s => s !== main && E[s]);
    if (rest.length)
      h += `<p class="also">Also in ${rest.map(s => `<a href="${entryUrl(t.id, s)}"><span class="zh">${
        esc(E[s].term)}</span> ${esc(E[s].pinyin)}</a>`).join(', ')}</p>`;
  }
  return h ? `<div class="gwrap">${h}</div>` : '';
}

function heatSection(c, t, mode){
  const full = mode !== 'summary';
  const r = c.t[t.id], U = D.units[t.id] || {}, N = t.units;
  const occ = D.where[t.id][c.c] || [];
  const per = new Array(N + 1).fill(0);
  for (const [k, n] of occ) per[+k.split('.')[0]] += n;
  const peak = Math.max(1, ...per);
  const unit = t.unit, Unit = unit[0].toUpperCase() + unit.slice(1);
  // Scaled against this character's own peak, not the text's. The question the
  // map answers is where *this* character concentrates; a global scale would
  // flatten every term that is not the commonest into an even wash.
  const shade = n => n === 0 ? 0 : 0.18 + 0.82 * (n / peak);
  const W = t.witness;
  let wChars = 0, allChars = 0, wUses = 0;
  if (W) for (let n = 1; n <= N; n++){
    const m = U[n] || [], size = m[4] || 0;
    allChars += size; if (m[3]){ wChars += size; wUses += per[n]; }
  }
  const wShare = allChars ? Math.round(100 * wChars / allChars) : 0;
  const useShare = r.n ? Math.round(100 * wUses / r.n) : 0;
  const on = full && W && wOn;

  let h = `<section class="blk">${full ? `
    <span class="lab" style="display:flex;justify-content:space-between;
      align-items:center;gap:10px">Where it appears
      ${W ? `<button class="wtog" type="button" aria-pressed="${on}"
        title="${esc(W.name)}, ${esc(W.date)} — the oldest surviving copy of this text. A witness is a copy that testifies to what the text said at some point; it is not a source the text came from."
        style="padding:3px 8px;font-size:10px">Oldest witness</button>` : ''}</span>` : ''}
    <p class="legend" style="margin:0 0 10px">${r.n}&times;
      across ${r.chs.length} of ${N} ${unit}s${
        peak > 1 ? `, most often in ${unit} ${per.indexOf(peak)} (${peak}&times;)` : ''}</p>
    <div class="heat" style="grid-template-columns:repeat(${t.cols},1fr)">`;
  for (let n = 1; n <= N; n++){
    const k = per[n], gd = U[n] && U[n][3];
    const faded = on && !gd;
    // A unit outside the witness keeps a readable number: its fill is lightened
    // rather than the whole cell, so the text still meets contrast.
    const a = k ? shade(k) * (faded ? .35 : 1) : 0;
    const title = `${Unit} ${n}${U[n] && U[n][2] ? ' — ' + U[n][2] : ''}` +
      ` · ${k === 0 ? 'does not appear' : k + (k === 1 ? ' time' : ' times')}` +
      (on ? (gd ? ` · in ${W.name}, ${W.date}` : ` · not in ${W.name}`) : '');
    const cls = 'hc' + (k ? '' : ' void') + (on && gd ? ' gd' : '') + (faded ? ' faded' : '');
    const pressed = unitFilter && unitFilter[0] === t.id && unitFilter[1] === n;
    h += `<button class="${cls}" type="button" data-tid="${t.id}" data-u="${n}"
      ${k ? '' : 'tabindex="-1" aria-disabled="true"'} aria-pressed="${!!pressed}"
      style="background:${k ? `rgba(var(--heat-rgb),${a.toFixed(3)})` : 'var(--sunk)'};${
        k ? `color:${textOn(a)};` : ''}"
      title="${esc(title)}">${n}</button>`;
  }
  h += `</div>
    <div class="hkey">
      <span class="lab">none</span>
      <span class="hramp">${[0, .25, .5, .75, 1].map(x =>
        `<i style="background:${x ? `rgba(var(--heat-rgb),${(0.18 + 0.82 * x).toFixed(2)})`
          : 'var(--sunk)'}"></i>`).join('')}</span>
      <span class="lab">${peak}&times; in one ${unit}</span>
    </div>`;
  if (!full){
    h += `</section><button class="txgo" type="button" data-go="${t.id}">
      Read its ${occ.length} line${occ.length === 1 ? '' : 's'} in the ${esc(t.title)} →</button>`;
    return h;
  }
  if (!on)
    h += `<p class="legend" style="margin-top:8px">
      All ${N} ${unit}s are shown, so the gaps count too. Deeper red means more
      uses of ${esc(c.c)} there. Click a ${unit} to read only its lines.</p>`;
  else
    h += `<p class="legend" style="margin-top:8px">
      Dashed ${unit}s are missing from <b>${esc(W.name)}</b> (${esc(W.date)}), the
      oldest surviving copy of this text. It is a <i>witness</i>, not a source: it
      testifies to what the text said, but the later text does not descend from
      it. It carries ${W.carries} of the ${N} ${unit}s and ${wShare}% of the
      text&rsquo;s characters.
      <b>${wUses} of ${esc(c.c)}&rsquo;s ${r.n} uses &mdash; ${useShare}% &mdash;
      fall inside it.</b>
      ${r.n < 10
        ? `Too few uses to read anything into that. With ${r.n}, a split this far
           from ${wShare}% is ordinary chance.`
        : useShare === 0
        ? `Absent from the oldest witness entirely &mdash; across ${r.n} uses that
           is unlikely to be chance, and worth asking whether ${esc(c.c)} belongs
           to a later layer.`
        : Math.abs(useShare - wShare) < 10
        ? `Within range of the ${wShare}% an even spread would give, so this says
           nothing either way.`
        : useShare < wShare
        ? `Below the ${wShare}% an even spread would give: it leans toward the
           ${unit}s the oldest witness lacks.`
        : `Above the ${wShare}% an even spread would give: it leans toward the
           oldest stratum.`}
      Weak evidence at best: the witness is a selection, not an earlier edition,
      and absence from it is not proof of lateness.</p>`;
  h += `</section>`;

  const lines = D.lines[t.id];
  const shown = unitFilter && unitFilter[0] === t.id
    ? occ.filter(e => +e[0].split('.')[0] === unitFilter[1]) : occ;
  h += `<section class="blk"><span class="lab">In the text</span>`;
  if (unitFilter && unitFilter[0] === t.id)
    h += `<p class="legend" style="margin:0 0 9px">${Unit} ${unitFilter[1]} only —
      <button class="allu" type="button" style="padding:2px 7px">show all
      ${occ.length} lines</button></p>`;
  h += `<div class="occ">`;
  for (const [key, times] of shown.slice(0, occLimit)){
    const L = lines[key]; if (!L) continue;
    const [u, seq] = key.split('.');
    const zh = esc(L[0]).split(c.c).join(`<mark>${esc(c.c)}</mark>`);
    h += `<div class="oc">
      <div class="ref">${esc(t.abbr)} ${u} · LINE ${seq}${
        times > 1 ? `<span class="times">${times}× in this line</span>` : ''}</div>
      <div class="zh">${zh}</div>
      <div class="py2">${esc(L[1] || '')}</div>
      <div class="en">${esc(L[2] || '—')}</div>
      ${L[3] ? '' : '<div class="approx">line pairing approximate</div>'}
    </div>`;
  }
  h += `</div>`;
  if (shown.length > occLimit)
    h += `<button class="more" type="button">Show more
          (${shown.length - occLimit} more line${shown.length - occLimit === 1 ? '' : 's'})</button>`;
  h += `</section>`;
  return h;
}

function cardHtml(chr, compact){
  const c = byChar[chr];
  if (!c) return '';
  // Layer 1 is shared by every text: the character, its parts, 說文. Layer 2 is
  // how each text in scope reads it, each line labelled with its text. Layer 3
  // is one section per text: its glossary, its map, its lines.
  const scope = TEXTS.filter(t => compact || tf === 'all' || tf === t.id);
  const present = scope.filter(t => c.t[t.id]);
  const tags = [];
  if (c.kind) tags.push(`<span class="tag">${esc(c.kind.replace(/-/g, ' '))}</span>`);
  if (c.rad) tags.push(`<span class="tag">filed under ${esc(c.rad)}</span>`);

  let meta = `<div class="pin">${esc(c.p || '')}</div>`;
  for (const t of present){
    const r = c.t[t.id], t2 = [];
    if (r.lock) t2.push('<span class="tag lock">settled rendering</span>');
    if (r.tier && r.tier !== 'locked') t2.push(`<span class="tag">${esc(r.tier)}</span>`);
    meta += `<div class="by"><span class="lab">${esc(t.title)}</span>
      <div class="gloss">${esc(r.g || 'not yet glossed')}</div>
      ${r.r && r.r !== r.g ? `<div class="render">rendered “${esc(r.r)}”</div>` : ''}
      ${t2.length ? `<div class="tags">${t2.join('')}</div>` : ''}</div>`;
  }
  if (!present.length && tf !== 'all' && TX[tf])
    meta += `<p class="legend">${esc(c.c)} does not appear in the ${esc(TX[tf].title)}.</p>`;
  if (tags.length) meta += `<div class="tags shared">${tags.join('')}</div>`;
  let h = `<div class="hero"><div class="big">${esc(c.c)}</div>
    <div class="meta">${meta}</div></div>`;
  if (!compact) h += glossaryButtons(c, present);

  if (c.sem.length || c.pho.length){
    h += `<section class="blk"><span class="lab">Built from</span>
      <div class="parts">
        ${c.sem.map(x => `<div class="pcol">${partBtn(x, 'sem', compact)}
          <p class="pcap">Carries meaning</p></div>`).join('')}
        ${c.pho.map(x => `<div class="pcol">${partBtn(x, 'pho', compact)}
          <p class="pcap">Borrowed for sound alone</p></div>`).join('')}
      </div>`;
    if (!compact && compSel){
      const n = (BUILT[compSel] || []).filter(x => byChar[x[0]] && view(byChar[x[0]])).length;
      h += `<p class="legend resetrow">The grid shows only the ${n} character${n === 1 ? '' : 's'} built from <span class="zh">${esc(compSel)}</span>.<button class="resetcomp" type="button">Reset</button></p>`;
    }
    h += `</section>`;
  } else if (c.kind === 'pictograph'){
    h += `<section class="blk"><span class="lab">Built from</span>
      <p class="legend">This is a pictograph, not an assembly of parts.</p>
      </section>`;
  }

  /* HIDDEN, 2026-10-14 — Shalom's call. The 說文解字 block (Xu Shen's definition,
     c. 100 CE) is commented out until it is accessible to readers who do not
     read Chinese. 795 of 798 lines are untranslated, so for this atlas's reader
     the box was Chinese they could not use, in the most prominent place on the
     card. Revisit by 2026-12-14 (.github/workflows/revisit-shuowen.yml opens
     an issue that day; README.md → Deferred). The data is still in data.json
     (c.def, c.defen, c.hw, c.fq), so restoring it is uncommenting this block.

  // if (c.def){
  //   h += `<section class="blk"><span class="lab">說文解字 · c. 100 CE</span>
  //     <div class="swz">${esc(c.def)}</div>`;
  //   // The English is hand-made, from a glossary entry; where no entry has
  //   // translated the line yet, the Chinese stands alone.
  //   if (c.defen) h += `<p class="swen">${esc(c.defen)}</p>`;
  //   const facts = (c.hw && c.hw !== c.c ? `Filed under the older graph ${esc(c.hw)}. ` : '') +
  //     (c.fq ? `Middle Chinese spelling ${esc(c.fq)}.` : '');
  //   if (facts) h += `<p class="note">${facts.trim()}</p>`;
  //   h += `</section>`;
  // }
  */

  if (compact){
    h += `<a class="open" href="${charUrl(c.c)}">Open ${esc(c.c)} in the atlas →</a>`;
    return h;
  }

  // All texts: a comparison. Each text the character appears in gets a short
  // summary (its map, and the way into its own view), and none of them takes
  // over the card. One text's tab: that text's full map and its lines.
  if (tf === 'all'){
    if (present.length){
      h += `<div class="txs"><span class="lab txs-lab">In the texts</span>`;
      for (const t of present)
        h += `<div class="tx"><div class="txhead">${esc(t.title)}
          <span class="zh">${esc(t.title_zh)}</span></div>${heatSection(c, t, 'summary')}</div>`;
      h += `</div>`;
    }
  } else {
    for (const t of present) h += heatSection(c, t, 'full');
  }
  return h;
}

function wireCard(card, chr, rerender){
  card.querySelectorAll('[data-comp]').forEach(b => b.onclick = () => {
    if (compSel === b.dataset.comp) return resetComp();   // a second click resets
    setComp(b.dataset.comp);
    window.scrollTo({top: 0, behavior: 'smooth'});
  });
  card.querySelectorAll('.resetcomp').forEach(b => b.onclick = resetComp);
  card.querySelectorAll('.hc').forEach(b => b.onclick = () => {
    const tid = b.dataset.tid, n = +b.dataset.u;
    if (b.classList.contains('void')) return;
    if (tf === 'all'){                   // a summary map opens that text's view
      setTab(tid, true); unitFilter = [tid, n]; occLimit = 6; show(sel); return;
    }
    unitFilter = unitFilter && unitFilter[0] === tid && unitFilter[1] === n ? null : [tid, n];
    occLimit = 6; rerender();
  });
  card.querySelectorAll('[data-go]').forEach(b => b.onclick = () => {
    setTab(b.dataset.go, true);
    card.scrollTop = 0;
  });
  card.querySelectorAll('.wtog').forEach(b => b.onclick = () => { wOn = !wOn; rerender(); });
  card.querySelectorAll('.allu').forEach(b => b.onclick = () => {
    unitFilter = null; occLimit = 6; rerender(); });
  card.querySelectorAll('.more').forEach(b => b.onclick = () => { occLimit += 12; rerender(); });
}

// ---------------------------------------------------------------- entry pages
if (PAGE === 'entry'){
  const chars = [...document.body.dataset.chars].filter(c => byChar[c]);
  const card = el('card'), chips = el('chips');
  let cur = chars[0];
  const render = () => {
    card.innerHTML = cardHtml(cur, true);
    if (chips && chars.length > 1){
      chips.innerHTML = chars.map(c => `<button type="button" aria-pressed="${c === cur}"
        data-c="${esc(c)}">${esc(c)}</button>`).join('');
      chips.querySelectorAll('button').forEach(b => b.onclick = () => { cur = b.dataset.c; render(); });
    }
  };
  if (cur) render();
  return;
}

// ---------------------------------------------------------------- the atlas
const grid = el('grid'), card = el('card'), status = el('status');
let sel = null, sort = 'freq';
const filter = {q: '', lock: false, real: true, comp: null};

function counts(){
  const ready = tf === 'all' || TX[tf];
  const inScope = ready ? CH.filter(c => view(c)) : [];
  const names = new Set(inScope.map(c => c.c));
  const parts = Object.entries(BUILT).filter(([, m]) => m.some(x => names.has(x[0]))).length;
  el('k-ch').textContent = ready ? inScope.length.toLocaleString() : '—';
  el('k-oc').textContent = ready ? inScope.reduce((a, c) => a + view(c).n, 0).toLocaleString() : '—';
  el('k-pt').textContent = ready ? parts.toLocaleString() : '—';
  el('k-parts').disabled = !ready;
  if (!ready) openParts(false);
}

function visible(){
  let out = CH.map(c => [c, view(c)]).filter(([, v]) => v);
  if (filter.comp){
    const set = new Set((BUILT[filter.comp] || []).map(x => x[0]));
    out = out.filter(([c]) => set.has(c.c));
  }
  if (filter.lock) out = out.filter(([, v]) => v.lock);
  if (filter.real) out = out.filter(([, v]) => !v.fw);
  const q = filter.q.trim().toLowerCase();
  if (q) out = out.filter(([c, v]) =>
    c.c.includes(q) || (c.p || '').toLowerCase().includes(q) ||
    v.g.toLowerCase().includes(q) || v.r.toLowerCase().includes(q));
  out.sort(sort === 'cent' ? (a, b) => b[1].cent - a[1].cent : (a, b) => b[1].n - a[1].n);
  return out;
}

function draw(){
  const list = visible();
  grid.innerHTML = '';
  if (!list.length)
    grid.innerHTML = '<p class="empty" style="grid-column:1/-1">' +
      'Nothing matches. Try a different word, or clear the filter.</p>';
  const frag = document.createDocumentFragment();
  for (const [c, v] of list){
    const a = document.createElement('a');
    a.className = 'cell' + (v.lock ? ' locked' : '');
    a.href = charUrl(c.c) + scopeQS();
    a.setAttribute('aria-current', sel === c.c ? 'true' : 'false');
    a.title = `${c.c} ${c.p || ''} — ${v.g || 'not yet glossed'} · ${v.n}×`;
    a.innerHTML = `<span class="gl">${esc(c.c)}</span><span class="py">${esc(c.p || '')}</span>`;
    a.onclick = e => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
      e.preventDefault(); go(c.c, true);
    };
    frag.appendChild(a);
  }
  grid.appendChild(frag);
  const total = CH.filter(c => view(c)).length;
  let s = `${list.length} of ${total} characters`;
  if (filter.comp){
    const g = G[filter.comp] || [];
    s += ` built from ${filter.comp}` + (g[1] ? ` (${g[1]})` : '');
  }
  status.textContent = s;
  drawParts();
  el('key').hidden = !list.some(([, v]) => v.lock);
  el('clear').hidden = !filter.comp;
}

function show(chr){
  card.innerHTML = cardHtml(chr, false);
  wireCard(card, chr, () => show(chr));
}

function go(chr, push){
  if (!chr || !byChar[chr]) return;
  sel = chr; occLimit = 6; unitFilter = null;
  draw(); show(chr);
  const c = byChar[chr], v = view(c) || {};
  document.title = `${chr} ${c.p || ''} — ${v.g || 'not yet glossed'} · ${SITE}`;
  if (push) history.pushState({c: chr}, '', charUrl(chr) + scopeQS());
  if (window.innerWidth <= 980 && push) card.scrollIntoView({behavior: 'smooth', block: 'start'});
}
window.addEventListener('popstate', e => go((e.state && e.state.c) || START, false));

el('q').oninput = e => { filter.q = e.target.value; draw(); };
function toggle(id, key){
  el(id).onclick = () => {
    filter[key] = !filter[key];
    el(id).setAttribute('aria-pressed', String(filter[key])); draw();
  };
}
toggle('f-lock', 'lock'); toggle('f-real', 'real');
el('s-freq').onclick = () => { sort = 'freq';
  el('s-freq').setAttribute('aria-pressed', 'true');
  el('s-cent').setAttribute('aria-pressed', 'false'); draw(); };
el('s-cent').onclick = () => { sort = 'cent';
  el('s-cent').setAttribute('aria-pressed', 'true');
  el('s-freq').setAttribute('aria-pressed', 'false'); draw(); };
// Filtering by a part turns "hide grammar" off (a part's family includes its
// grammar words); resetting puts back whatever the reader had chosen.
let realBefore = true;
function setComp(comp){
  if (!compSel) realBefore = filter.real;
  compSel = filter.comp = comp;
  filter.q = ''; el('q').value = '';
  filter.real = false; el('f-real').setAttribute('aria-pressed', 'false');
  draw(); if (sel) show(sel);
}
function resetComp(){
  compSel = filter.comp = null;
  filter.real = realBefore;
  el('f-real').setAttribute('aria-pressed', String(filter.real));
  draw(); if (sel) show(sel);
}
el('clear').onclick = resetComp;

// ---------------------------------------------------------------- the parts
// The "parts" count opens a strip of every part in scope, the most-used first.
// Picking one is the same filter as a "Built from" tile on the card.
const PARTS_FIRST = 48;
let partsAll = false;
function partsInScope(){
  return Object.entries(BUILT)
    .map(([p, m]) => [p, m.filter(x => byChar[x[0]] && view(byChar[x[0]])).length])
    .filter(([, n]) => n)
    .sort((a, b) => b[1] - a[1]);
}
function drawParts(){
  if (el('parts').hidden) return;
  const ps = partsInScope();
  el('pgrid').innerHTML = (partsAll ? ps : ps.slice(0, PARTS_FIRST)).map(([p, n]) => {
    const g = G[p] || [];
    const title = `${p}${g[0] ? ' ' + g[0] : ''}${g[1] ? ' — ' + g[1] : ''}` +
      ` · builds ${n} character${n === 1 ? '' : 's'}`;
    return `<button type="button" class="pc" data-comp="${esc(p)}"
      aria-pressed="${compSel === p}" title="${esc(title)}"><span
      class="pg">${esc(p)}</span><span class="py">${esc(g[0] || '')}</span></button>`;
  }).join('');
  const more = el('parts-more');
  more.hidden = ps.length <= PARTS_FIRST;
  more.textContent = partsAll ? `Show the first ${PARTS_FIRST}` : `Show all ${ps.length}`;
}
function openParts(open){
  el('parts').hidden = !open;
  el('k-parts').setAttribute('aria-expanded', String(open));
  drawParts();
}
el('k-parts').onclick = () => openParts(el('parts').hidden);
el('parts-close').onclick = () => { openParts(false); el('k-parts').focus(); };
el('parts-more').onclick = () => { partsAll = !partsAll; drawParts(); };
el('pgrid').onclick = e => {
  const b = e.target.closest('[data-comp]');
  if (b) b.dataset.comp === compSel ? resetComp() : setComp(b.dataset.comp);
};
const TABS = [...document.querySelectorAll('[role="tab"]')];
function setTab(id, push){
  tf = id;
  for (const b of TABS){
    const on = b.dataset.text === id;
    b.setAttribute('aria-selected', String(on));
    b.tabIndex = on ? 0 : -1;
  }
  const ready = id === 'all' || !!TX[id];
  document.querySelectorAll('.soon').forEach(p => p.hidden = p.id !== 'soon-' + id);
  document.querySelector('.controls').hidden = !ready;
  document.querySelector('.room').hidden = !ready;
  counts();
  if (!ready){
    if (push) history.replaceState(history.state, '', location.pathname + scopeQS());
    return;
  }
  // Keep the character if this text has it; otherwise open on the text's
  // commonest character, so the card always has something to say.
  if (!sel || !view(byChar[sel])){
    const first = visible()[0];
    if (first) sel = first[0].c;
  }
  if (push) history.replaceState({c: sel}, '', (sel ? charUrl(sel) : location.pathname) + scopeQS());
  go(sel, false);
}
TABS.forEach((b, i) => {
  b.onclick = () => setTab(b.dataset.text, true);
  b.onkeydown = e => {
    const k = {ArrowRight: 1, ArrowLeft: -1}[e.key];
    if (!k) return;
    const nb = TABS[(i + k + TABS.length) % TABS.length];
    nb.focus(); setTab(nb.dataset.text, true);
  };
});

// ?built=巾 arrives from a component tile on an entry page.
const built = new URLSearchParams(location.search).get('built');
if (built && BUILT[built]){
  compSel = filter.comp = built; filter.real = false;
  el('f-real').setAttribute('aria-pressed', 'false');
}
const START = document.body.dataset.char || '道';
history.replaceState({c: START}, '', location.href);
sel = START;
setTab(tf, false);

// ---------------------------------------------------------------- the glossary
// One glossary for every translation. Each entry keeps its text's label; the
// tabs scope it, as they scope the atlas. Search reaches the words a ruling
// sets aside, so "eternal" finds 常 and says why it is not there.
async function glossaryPage(){
  const G2 = await (await fetch(document.querySelector('meta[name="atlas-glossary"]').content)).json();
  const SERVE = [...document.querySelectorAll('[role="tab"]')];
  const TITLES = Object.fromEntries(SERVE.map(b => [b.dataset.text,
    b.childNodes[0].textContent.trim()]));
  const fold = x => (x || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const P = new URLSearchParams(location.search);
  const st = {
    text: P.get('text') || 'all', q: P.get('q') || '', status: P.get('status') || 'all',
    form: P.get('form') || 'all', ch: P.get('ch') || '', sort: P.get('sort') || 'az',
    sel: P.get('sel') || '',
  };
  if (!SERVE.some(b => b.dataset.text === st.text)) st.text = 'all';
  const ready = id => id === 'all' || G2.some(r => r.tid === id);
  const list = el('glist'), prev = el('gprev');
  el('gq').value = st.q; el('gform').value = st.form; el('gsort').value = st.sort;

  function chapterOptions(){
    const sel = el('gch');
    const recs = G2.filter(r => st.text === 'all' || r.tid === st.text);
    const max = Math.max(0, ...recs.flatMap(r => r.chapters));
    sel.hidden = st.text === 'all' || !max;
    sel.innerHTML = '<option value="">Any chapter</option>' +
      Array.from({length: max}, (_, k) => `<option value="${k + 1}">Chapter ${k + 1}</option>`).join('');
    sel.value = st.ch;
  }

  function matches(){
    const q = fold(st.q.trim());
    let out = G2.filter(r => st.text === 'all' || r.tid === st.text);
    const scoped = out;
    if (st.status !== 'all') out = out.filter(r => (st.status === 'locked') === (r.status === 'locked'));
    if (st.form !== 'all') out = out.filter(r => r.form === st.form);
    if (st.ch) out = out.filter(r => r.chapters.includes(+st.ch));
    out = out.map(r => {
      if (!q) return [r, null];
      const hit = r.term.includes(st.q.trim()) || fold(r.pinyin).includes(q) ||
        fold(r.render).includes(q) || r.slug.includes(q);
      const aside = r.aside.find(w => fold(w).includes(q));
      return hit || aside ? [r, hit ? null : aside] : null;
    }).filter(Boolean);
    if (st.sort === 'reach') out.sort((a, b) => b[0].chapters.length - a[0].chapters.length);
    return [out, scoped];
  }

  function url(){
    const p = new URLSearchParams();
    for (const [k, v, d] of [['text', st.text, 'all'], ['q', st.q, ''], ['status', st.status, 'all'],
      ['form', st.form, 'all'], ['ch', st.ch, ''], ['sort', st.sort, 'az'], ['sel', st.sel, '']])
      if (v && v !== d) p.set(k, v);
    history.replaceState(null, '', location.pathname + (p.toString() ? '?' + p : ''));
  }

  function preview(r){
    if (!r){ prev.innerHTML = '<p class="legend">Nothing matches. Try another word, or clear a filter.</p>'; return; }
    const single = r.chars.length === 1;
    prev.innerHTML = `<div class="hero gp-hero"><div class="big">${esc(r.term)}</div>
      <div class="meta"><div class="pin">${esc(r.pinyin)}</div>
      <span class="lab">${esc(TITLES[r.tid] || r.tid)}</span>
      <div class="gloss">${esc(r.render)}</div>
      <div class="tags">${r.status === 'locked' ? '<span class="tag lock">settled</span>'
        : `<span class="tag">${esc(r.status)}</span>`}<span class="tag">${esc(r.form)}</span>${
        r.chapters.length ? `<span class="tag">${r.chapters.length} chapter${r.chapters.length === 1 ? '' : 's'}</span>` : ''}</div>
      </div></div>
      <a class="gbtn" href="${entryUrl(r.tid, r.slug)}"><span><span class="k">Read the full entry</span>
        <span class="t"><span class="zh">${esc(r.term)}</span> ${esc(r.pinyin)} — ${esc(r.render)}</span></span>
        <span class="arrow" aria-hidden="true">→</span></a>
      ${r.aside.length ? `<section class="blk"><span class="lab">Set aside</span>
        <div class="asides">${r.aside.map(w => `<span class="aside">${esc(w)}</span>`).join('')}</div></section>` : ''}
      <section class="blk gp-prose prose">${r.lock}${r.lead}</section>
      ${single ? `<a class="open" href="${charUrl(r.chars[0])}">Open ${esc(r.chars[0])} in the atlas →</a>` : ''}`;
  }

  function draw(){
    const isReady = ready(st.text);
    document.querySelectorAll('.soon').forEach(p => p.hidden = p.id !== 'soon-' + st.text);
    document.querySelector('.gcontrols').hidden = !isReady;
    document.querySelector('.groom').hidden = !isReady;
    const [out, scoped] = matches();
    el('g-n').textContent = isReady ? scoped.length : '—';
    el('g-set').textContent = isReady ? scoped.filter(r => r.status === 'locked').length : '—';
    el('g-open').textContent = isReady ? scoped.filter(r => r.status !== 'locked').length : '—';
    if (!isReady){ url(); return; }
    el('gstatus').textContent = `${out.length} of ${scoped.length} entries`;
    if (!out.some(([r]) => r.tid + '/' + r.slug === st.sel)) st.sel = out.length ? out[0][0].tid + '/' + out[0][0].slug : '';
    list.innerHTML = out.length ? out.map(([r, aside]) => {
      const k = r.tid + '/' + r.slug;
      return `<a class="grow" href="${entryUrl(r.tid, r.slug)}" data-k="${esc(k)}" aria-current="${k === st.sel}">
        <span class="term">${esc(r.term)}</span>
        <span class="gmid"><span class="py">${esc(r.pinyin)}</span>
          <span class="r">${esc(r.render)}</span>
          ${aside ? `<span class="setaside">Sets aside “${esc(aside)}”</span>` : ''}</span>
        <span class="gend">${st.text === 'all' ? `<span class="lab">${esc(TITLES[r.tid] || r.tid)}</span>` : ''}
          ${r.status === 'locked' ? '<span class="tag lock">settled</span>' : `<span class="tag">${esc(r.status)}</span>`}</span>
      </a>`;
    }).join('') : '<p class="empty">Nothing matches. Try another word, or clear a filter.</p>';
    list.querySelectorAll('.grow').forEach(a => a.onclick = ev => {
      if (window.innerWidth <= 980 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button) return;
      ev.preventDefault(); st.sel = a.dataset.k; draw();
    });
    preview((out.find(([r]) => r.tid + '/' + r.slug === st.sel) || [])[0]);
    url();
  }

  SERVE.forEach((b, i) => {
    const on = () => {
      st.text = b.dataset.text; st.ch = '';
      SERVE.forEach(x => { x.setAttribute('aria-selected', String(x === b)); x.tabIndex = x === b ? 0 : -1; });
      chapterOptions(); draw();
    };
    b.onclick = on;
    b.onkeydown = e => {
      const k = {ArrowRight: 1, ArrowLeft: -1}[e.key]; if (!k) return;
      const nb = SERVE[(i + k + SERVE.length) % SERVE.length]; nb.focus(); nb.click();
    };
    if (b.dataset.text === st.text){ b.setAttribute('aria-selected', 'true'); b.tabIndex = 0; }
    else { b.setAttribute('aria-selected', 'false'); b.tabIndex = -1; }
  });
  document.querySelectorAll('[data-status]').forEach(b => {
    b.setAttribute('aria-pressed', String(b.dataset.status === st.status));
    b.onclick = () => { st.status = b.dataset.status;
      document.querySelectorAll('[data-status]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      draw(); };
  });
  el('gq').oninput = e => { st.q = e.target.value; draw(); };
  el('gform').onchange = e => { st.form = e.target.value; draw(); };
  el('gch').onchange = e => { st.ch = e.target.value; draw(); };
  el('gsort').onchange = e => { st.sort = e.target.value; draw(); };
  chapterOptions(); draw();
}
})();
