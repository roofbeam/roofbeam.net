/* A Thousand Grandparents — the arithmetic of descent.
   Two kinds of number live here and they are kept apart on purpose:
     counted  — derived from census head counts by 1 - (1-p)^n
     measured — read off genotype data (Bryc 2015); never derived, only scaled  */
'use strict';

const $ = s => document.querySelector(s);
const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(n < 1e7 ? 2 : 1) + 'M'
              : n >= 1000 ? Math.round(n).toLocaleString() : Math.round(n).toLocaleString();

/* A probability this close to 1 should not print as "100%" — the whole piece
   is about the difference between "almost certainly" and "certainly". */
function pct(p) {
  if (p >= 0.9999) return '>99.99%';
  if (p >= 0.999)  return (Math.floor(p * 1e4) / 100).toFixed(2) + '%';
  if (p >= 0.99)   return (Math.floor(p * 1e3) / 10).toFixed(1) + '%';
  if (p < 0.001 && p > 0) return '<0.1%';
  return (p * 100).toFixed(1) + '%';
}
const atLeastOne = (p, n) => n <= 0 || p <= 0 ? 0 : 1 - Math.pow(1 - p, n);

const REGION_LABEL = { deep: 'Deep South', upper: 'Upper South', border: 'Border states', north: 'the North' };
const REGION_STATES = { deep: 'SC MS GA AL FL LA TX', upper: 'NC VA TN AR', border: 'KY MO MD DE DC', north: '' };

let D = null, S = { birth: 1990, share: 1, region: 'deep', pool: 'white', flow: 1 };

/* ---------------------------------------------------------------- pop model */
const GEN = () => D.meta.generation_years;
const genAt = y => Math.max(0, Math.round((S.birth - y) / GEN()));
const slotsAt = y => Math.pow(2, genAt(y));

/* log-linear interpolation between decade observations */
function popAt(year) {
  const P = D.population;
  if (year <= P[0].year) return { total: P[0].total, black: P[0].black, enslaved: P[0].black };
  if (year >= P[P.length - 1].year) { const l = P[P.length - 1]; return { total: l.total, black: l.black, enslaved: l.enslaved }; }
  for (let i = 0; i < P.length - 1; i++) {
    const a = P[i], b = P[i + 1];
    if (year >= a.year && year <= b.year) {
      const t = (year - a.year) / (b.year - a.year);
      const lg = (x, y2) => Math.exp(Math.log(Math.max(x, 1)) * (1 - t) + Math.log(Math.max(y2, 1)) * t);
      return {
        total: lg(a.total, b.total),
        black: lg(a.black, b.black),
        // before 1790 the split isn't reported; treat black as enslaved (meta note)
        enslaved: lg(a.enslaved == null ? a.black : a.enslaved, b.enslaved == null ? b.black : b.enslaved),
      };
    }
  }
  return { total: 1, black: 0, enslaved: 0 };
}
/* the endogamous pool a line actually drew from, not the whole population */
const poolAt = year => {
  const p = popAt(year);
  return Math.max(1, S.pool === 'black' ? p.black : p.total - p.black);
};

/* ------------------------------------------------------------------- model */
function model() {
  const g1860 = genAt(1860), slots = Math.pow(2, g1860), lines = Math.max(1, slots / 2);
  const here = Math.round(lines * S.share);
  const reg = D.regions[S.region], adm = D.admixture;

  let pEns, pOwn, howEns, howOwn;

  if (S.pool === 'black') {
    // counted: 89.0% of the 1860 black population was enslaved
    // 1860 alone understates it badly in the North, where the black population
    // was ~all free by then but had been enslaved two generations earlier
    // (New York to 1827, New Jersey by gradual emancipation to 1865). So walk
    // back and take the generation that binds.
    let best = { p: 0, year: 1860, n: here, share: reg.black_enslaved_share };
    for (const y of [1860, 1830, 1800, 1770, 1740]) {
      const pop = popAt(y);
      const share = y === 1860 ? reg.black_enslaved_share
                  : clamp(pop.enslaved / Math.max(pop.black, 1), 0, 1);
      const n = y === 1860 ? here : Math.max(1, Math.round((slotsAt(y) / 2) * S.share));
      const p = atLeastOne(share, n);
      if (p > best.p) best = { p, year: y, n, share };
    }
    pEns = best.p;
    howEns = best.year === 1860
      ? `counted · ${(best.share * 100).toFixed(1)}% of the Black population of ${REGION_LABEL[S.region]} was enslaved, across ${here} line${here === 1 ? '' : 's'}`
      : `counted · binds at ${best.year}, not 1860 — ${(best.share * 100).toFixed(1)}% of the Black population was enslaved then, across ${fmt(best.n)} lines`;
    // measured: European admixture in African Americans, near-entirely from slaveholding lines
    pOwn = clamp(adm.aa_share_any_european * S.flow, 0, 0.9999);
    howOwn = `measured floor · ${(adm.aa_share_any_european * 100).toFixed(1)}% carry \u22651% European ancestry, mean ${(adm.aa_mean_european * 100).toFixed(0)}%`;
  } else {
    // counted: share of free families in the region that held slaves
    const pf = reg.pct_fam / 100;
    pOwn = atLeastOne(pf, here);
    howOwn = S.region === 'north'
      ? `counted · 1860 only, when the North had abolished slavery — it had not in 1790, and this model does not reach back for you`
      : `counted · ${reg.pct_fam.toFixed(1)}% of free families in ${REGION_LABEL[S.region]} held slaves, across ${here} line${here === 1 ? '' : 's'}`;
    // measured: African ancestry among self-identified European Americans, by region
    const sts = REGION_STATES[S.region].split(' ').filter(Boolean);
    const base = sts.length
      ? sts.reduce((a, s) => a + (adm.ea_share_any_african_by_state[s] || adm.ea_share_any_african), 0) / sts.length
      : adm.ea_share_any_african * 0.3;   // North: well below the national mean
    const scaled = clamp(base * S.flow, 0, 0.999);
    pEns = S.share > 0 ? clamp(scaled * (0.35 + 0.65 * S.share), 0, 0.999) : 0;
    howEns = `measured floor · ${(base * 100).toFixed(1)}% carry \u22651% African ancestry — an ancestor 8 generations back falls under that threshold`;
  }

  if (here === 0) { pEns = 0; pOwn = 0; howEns = howOwn = 'no lines in North America in 1860'; }

  const floorEns = S.pool === 'white' && here > 0;
  const floorOwn = S.pool === 'black' && here > 0;
  const bothNote = here === 0 ? 'no lines in North America in 1860'
    : 'these are not two different groups of people';
  return { g1860, slots, lines, here, pEns, pOwn, pBoth: pEns * pOwn,
           howEns, howOwn, floorEns, floorOwn, bothNote };
}

/* crossing: the last year in which your slots still outnumber the whole pool */
function crossingYear() {
  let cross = null;
  for (let y = 1610; y <= 1860; y++) if (slotsAt(y) > poolAt(y)) cross = y;
  return cross;
}

/* ------------------------------------------------------------------ render */
function render() {
  const m = model();
  $('#v-birth').textContent = S.birth;
  $('#v-share').textContent = `${m.here} of ${m.lines}`;
  $('#v-flow').textContent = S.flow.toFixed(1) + '×';

  const set = (id, p, how, floor) => {
    const t = pct(p);
    $('#p-' + id).textContent = (floor && p > 0 && t[0] !== '<' ? '\u2265' : '') + t;
    $('#b-' + id).style.width = (clamp(p, 0, 1) * 100).toFixed(1) + '%';
    if (how) $('#sub-' + id).textContent = how;
  };
  set('ens', m.pEns, m.howEns, m.floorEns);
  set('own', m.pOwn, m.howOwn, m.floorOwn);
  set('both', m.pBoth, m.bothNote, m.floorEns || m.floorOwn);

  $('#chart-note').innerHTML =
    `Born ${S.birth}: ${m.g1860} generations back to 1860 &mdash; <b>${fmt(m.slots)} slots</b> against a US population of ` +
    `<b>${fmt(popAt(1860).total)}</b>. Generations fixed at ${GEN()} years.`;

  drawChart();
  drawDeep(m);
}

function drawDeep(m) {
  const cross = crossingYear();
  const rows = [];
  for (const y of [1860, 1790, 1700]) {
    const p = popAt(y), sl = slotsAt(y), pl = poolAt(y);
    // occupancy model: throwing `sl` balls into `pl` bins gives pedigree collapse for free
    const distinct = pl * (1 - Math.exp(-sl / pl));
    rows.push({ k: `${y} · ${genAt(y)} gens back`, v: fmt(sl) + ' slots',
      n: `${fmt(distinct)} distinct people out of ${fmt(pl)} alive in your pool &mdash; ${sl / pl > 1 ? (100 * sl / pl).toFixed(0) + '%' : (100 * sl / pl < 0.01 ? '<0.01%' : (100 * sl / pl).toFixed(2) + '%')} of it` });
  }
  if (cross) {
    rows.push({ k: 'They cross at', v: String(cross),
      n: `${fmt(slotsAt(cross))} slots vs ${fmt(poolAt(cross))} people alive. Past this line you don't descend from <i>some</i> of them.` });
  }
  $('#deep').innerHTML = rows.map(r =>
    `<div class="cell"><span class="k">${r.k}</span><span class="v">${r.v}</span><span class="n">${r.n}</span></div>`).join('');

  $('#deep-note').innerHTML = cross
    ? `Every line you have in colonial America converges on the same small founding population. By <b>${cross}</b> your ancestral slots exceed it entirely &mdash; so the question stops being <i>whether</i> an enslaved person or a slaveholder is in your tree and becomes <i>how many</i>. America had both from 1619 onward, in the same colonies, often in the same households.`
    : `With your lines arriving after 1860, the colonial collapse never applies &mdash; there is no colonial population for your tree to saturate.`;
}

/* ------------------------------------------------------------------- chart */
function drawChart() {
  const svg = $('#svg'), box = svg.getBoundingClientRect();
  const W = Math.max(320, box.width), H = Math.max(180, box.height);
  const M = { t: 12, r: 14, b: 22, l: 40 };
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('preserveAspectRatio', 'none');

  const y0 = 1610, y1 = 1860;   // last census in the pack; past it the pool line would be flat and lie
  const X = y => M.l + (y - y0) / (y1 - y0) * (W - M.l - M.r);
  const lo = Math.log10(1), hi = Math.log10(4e7);
  const Y = v => M.t + (1 - (Math.log10(Math.max(v, 1)) - lo) / (hi - lo)) * (H - M.t - M.b);

  const path = f => {
    let d = '';
    for (let y = y0; y <= y1; y += 2) d += (d ? 'L' : 'M') + X(y).toFixed(1) + ' ' + Y(f(y)).toFixed(1);
    return d;
  };
  const cross = crossingYear();
  let g = '';
  // gridlines
  const TICKS = [[10,'10'],[100,'100'],[1e3,'1K'],[1e4,'10K'],[1e5,'100K'],[1e6,'1M'],[1e7,'10M']];
  for (const [v, lab] of TICKS) {
    const yy = Y(v);
    g += `<line class="ax" x1="${M.l}" y1="${yy.toFixed(1)}" x2="${W - M.r}" y2="${yy.toFixed(1)}" opacity=".45"/>`
       + `<text class="axt" x="${M.l - 6}" y="${(yy + 3).toFixed(1)}" text-anchor="end">${lab}</text>`;
  }
  for (let y = 1650; y <= y1; y += 50)
    g += `<text class="axt" x="${X(y).toFixed(1)}" y="${H - 6}" text-anchor="middle">${y}</text>`;

  g += `<path class="ln p" d="${path(poolAt)}"/>`;
  g += `<path class="ln s" d="${path(slotsAt)}"/>`;
  if (cross) {
    const cx = X(cross), cy = Y(slotsAt(cross));
    g += `<line class="xhair" x1="${cx.toFixed(1)}" y1="${M.t}" x2="${cx.toFixed(1)}" y2="${H - M.b}"/>`
       + `<g class="cross"><circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="4.5"/>`
       + `<text x="${(cx + 9).toFixed(1)}" y="${(cy - 7).toFixed(1)}">${cross}</text></g>`;
  }
  svg.innerHTML = `<title id="chart-t">Ancestral slots versus population, log scale, 1610 to ${y1}</title>` + g;
}

/* ------------------------------------------------------------- methodology */
function drawTable() {
  const p = D.population[D.population.length - 1], r = D.regions;
  const rows = [
    ['US population', p.total, null],
    ['Enslaved', p.enslaved, p.enslaved / p.total],
    ['Free Black', p.black - p.enslaved, (p.black - p.enslaved) / p.total],
    ['Individual slaveholders', 393975, 393975 / p.total],
    ['Slaveholding families, slave states', null, r.south_all.pct_fam / 100],
    ['&nbsp;&nbsp;Deep South', null, r.deep.pct_fam / 100],
    ['&nbsp;&nbsp;Upper South', null, r.upper.pct_fam / 100],
    ['&nbsp;&nbsp;Border', null, r.border.pct_fam / 100],
  ];
  $('#mtable').innerHTML = rows.map(([k, n, s]) =>
    `<tr><td>${k}</td><td class="n">${n == null ? '' : Math.round(n).toLocaleString()}</td>` +
    `<td class="n">${s == null ? '' : (s * 100).toFixed(s < 0.02 ? 2 : 1) + '%'}</td></tr>`).join('');
}

/* -------------------------------------------------------------------- wire */
function seg(sel, key) {
  const el = $(sel);
  el.addEventListener('click', e => {
    const b = e.target.closest('button[data-v]'); if (!b) return;
    S[key] = b.dataset.v;
    el.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    render();
  });
}

fetch('descent.json').then(r => r.json()).then(d => {
  D = d;
  $('#birth').addEventListener('input', e => { S.birth = +e.target.value; render(); });
  $('#share').addEventListener('input', e => { S.share = +e.target.value / 100; render(); });
  $('#flow') .addEventListener('input', e => { S.flow  = +e.target.value / 100; render(); });
  seg('#seg-region', 'region');
  seg('#seg-pool', 'pool');
  addEventListener('resize', drawChart);
  drawTable();
  render();
}).catch(() => {
  $('#chart-note').textContent = 'Could not load descent.json — serve this directory over http, not file://';
});
