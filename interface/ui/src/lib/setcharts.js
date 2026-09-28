/* ===========================================================================
   setcharts.js — the combined book's figures: several videos held side by side.

   Every mark is placed by a number the pipeline computed
   (pipeline/analyst_sweep_facts.py); nothing is estimated in the browser.
   Each builder returns markup whose resting state is the finished drawing,
   and each carries its own words for a screen reader.

   ONE KEY FOR THE WHOLE BOOK.

     a video      its number, 01 to 05, the same as on the contents page;
                  every mark that belongs to video 3 carries data-vid="3", so
                  pointing at it anywhere lights that video up on the spread
     the reviewer a circle, in the transcript's colour
     the audience a square, in the audience's colour
     a reading    solid positive, tinted neutral, hatched negative

   so nothing is told by colour alone. `--tear` still means one thing, a
   flagged conflict.

   Motion is the book's own (charts.js animateIn): lines draw, bars grow,
   marks pop, once, on the first opening of a spread, and never under
   reduced motion. A figure is never counted up.
   ======================================================================== */

import { esc, score } from "./format.js";
import { clamp, finite, hatch, uid, signed } from "./charts.js";

/** A video's number as the book prints it: 01, 02, ... */
export const nn = (n) => String(n).padStart(2, "0");

export const CALL_WORD = {
  positive: "leans positive", balanced: "balanced", negative: "leans negative", unknown: "not readable",
};

const ciOf = (s) => (s && finite(s.se) ? 1.96 * s.se : 0);

/** A symmetric lean domain wide enough for every mark and its interval, in quarters, never under 0.5. */
function leanDomain(sides) {
  /* The floor used to be applied before the 0.02 margin, so 0.5 always became
     0.75: every set in this library was drawn on +-0.75 or wider, and the S27
     readers of the final user evaluation (24 Sep 2026) found five marks
     "squashed into a tiny bit in the middle". The margin now goes on the data. */
  const reach = Math.max(0, ...sides.filter((s) => s && finite(s.lean))
    .map((s) => Math.abs(s.lean) + ciOf(s)));
  return Math.min(1, Math.max(0.5, Math.ceil((reach + 0.02) * 4) / 4));
}

/* ------------------------------------------------------ the call ribbon -- */

export function consensusWords(c) {
  if (!c || c.label === "too_few") return "Too few videos to call";
  const word = { positive: "lean positive", balanced: "are balanced", negative: "lean negative" }[c.call];
  if (c.label === "all") return `All ${c.of} ${word}`;
  if (c.label === "all_but_one") return `${c.count} of ${c.of} ${word}`;
  return c.call ? `Split: ${c.count} of ${c.of} ${word}` : `Split: no reading is shared by more than ${c.count}`;
}

/**
 * Every video's call, reviewers above audiences, one tile each. The set is
 * read at a glance: a row of one shade agrees, a mixed row does not.
 */
export function callRibbon(rows, set) {
  const analysed = rows.filter((r) => r.analysed);
  const line = (who, key, cons) => `
    <div class="rb__row" data-who="${key}">
      <p class="rb__who"><i class="k ${key === "reviewer" ? "k--r" : "k--a"}" aria-hidden="true"></i>${who}
        <span class="rb__sum">${consensusWords(cons)}</span></p>
      <ol class="rb__tiles" style="--cols:${Math.max(analysed.length, 1)}">${analysed.map((r) => `
        <li class="rb__tile" data-call="${esc(r[key].call)}" data-vid="${r.n}" data-pop>
          <b class="t-read">${nn(r.n)}</b><span class="sr-only">Video ${r.n}:</span>
          <span class="rb__w">${CALL_WORD[r[key].call] || ""}</span></li>`).join("")}</ol>
    </div>`;
  return `<figure class="rb">${line("Reviewers' words", "reviewer", set.reviewer_consensus)}
    ${line("Audiences", "audience", set.audience_consensus)}</figure>`;
}

/* ------------------------------------------------------ a lean, small ---- */

/** One lean on a -1..+1 rule, with its 95% interval: the table's cell. */
export function leanMini(side, who) {
  if (!side || !finite(side.lean)) return `<span class="lmn lmn--none">not readable</span>`;
  const W = 120, L = 5, R = 115, Y = 9;
  const x = (v) => L + ((clamp(v, -1, 1) + 1) / 2) * (R - L);
  const ci = ciOf(side)
    ? `<line class="lmn__ci" x1="${x(side.lean - ciOf(side)).toFixed(1)}" y1="${Y}" x2="${x(side.lean + ciOf(side)).toFixed(1)}" y2="${Y}" data-grow-c/>`
    : "";
  const mark = who === "reviewer"
    ? `<circle class="lmn__r" cx="${x(side.lean).toFixed(1)}" cy="${Y}" r="4.6" data-pop/>`
    : `<rect class="lmn__a" x="${(x(side.lean) - 4.2).toFixed(1)}" y="${Y - 4.2}" width="8.4" height="8.4" data-pop/>`;
  return `<span class="lmn"><svg class="lmn__svg" viewBox="0 0 ${W} 18" aria-hidden="true">
      <line class="lmn__axis" x1="${L}" y1="${Y}" x2="${R}" y2="${Y}"/>
      <line class="lmn__zero" x1="${(L + R) / 2}" y1="${Y - 5}" x2="${(L + R) / 2}" y2="${Y + 5}"/>${ci}${mark}</svg>
    <span class="lmn__v t-read">${signed(side.lean)}</span></span>`;
}

/* ------------------------------------------------------ the quadrant ----- */

/**
 * Each video's reviewer (across) against its audience (up), on one square
 * scale, so the diagonal is exactly where the two lean the same way by the
 * same amount. A mark is filled when one side was measurably warmer, open
 * when no clear difference was found; its cross is the two 95% intervals.
 */
export function quadrant(rows) {
  const pts = rows.filter((r) => r.analysed && finite(r.reviewer.lean) && finite(r.audience.lean));
  if (!pts.length) return "";
  const W = 470, H = 452, L = 64, R = 452, T = 16, B = 404;
  const dom = leanDomain(pts.flatMap((p) => [p.reviewer, p.audience]));
  const x = (v) => L + ((clamp(v, -dom, dom) + dom) / (2 * dom)) * (R - L);
  const y = (v) => B - ((clamp(v, -dom, dom) + dom) / (2 * dom)) * (B - T);
  const ticks = [];
  for (let t = -dom; t <= dom + 1e-9; t += 0.25) ticks.push(Math.round(t * 100) / 100);
  const grid = ticks.map((t) => `
    <line class="qd__grid${t === 0 ? " qd__grid--zero" : ""}" x1="${x(t)}" y1="${T}" x2="${x(t)}" y2="${B}"/>
    <line class="qd__grid${t === 0 ? " qd__grid--zero" : ""}" x1="${L}" y1="${y(t)}" x2="${R}" y2="${y(t)}"/>
    <text class="qd__tick" x="${x(t)}" y="${B + 18}" text-anchor="middle">${signed(t)}</text>
    <text class="qd__tick" x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${signed(t)}</text>`).join("");

  /* Two marks closer than a disc apart are drawn side by side, each with a
     hairline back to where it really is, rather than one on top of the other.
     Every video's interval lines are drawn before any video's disc, so no
     disc sits under another video's lines (a reader found 02 "half hidden
     under its own lines", 24 Sep 2026). */
  const R_DISC = 12.5;
  const placed = [];
  const lines = [];
  const discs = [];
  for (const p of [...pts].sort((a, b) => a.n - b.n)) {
    const tx = x(p.reviewer.lean), ty = y(p.audience.lean);
    let dx = tx;
    const dy = ty;
    while (placed.some((q) => Math.hypot(q[0] - dx, q[1] - dy) < 2 * R_DISC + 1)) dx += 2 * R_DISC + 2;
    placed.push([dx, dy]);
    const clear = p.agreement.call === "reviewer_warmer" || p.agreement.call === "audience_warmer";
    const cr = ciOf(p.reviewer), ca = ciOf(p.audience);
    lines.push(`<g class="qd__pt${clear ? " is-clear" : ""}" data-vid="${p.n}">
      ${cr ? `<line class="qd__ci" x1="${x(p.reviewer.lean - cr).toFixed(1)}" y1="${ty.toFixed(1)}" x2="${x(p.reviewer.lean + cr).toFixed(1)}" y2="${ty.toFixed(1)}" data-grow-c/>` : ""}
      ${ca ? `<line class="qd__ci" x1="${tx.toFixed(1)}" y1="${y(p.audience.lean - ca).toFixed(1)}" x2="${tx.toFixed(1)}" y2="${y(p.audience.lean + ca).toFixed(1)}"/>` : ""}
      ${dx !== tx ? `<line class="qd__lead" x1="${tx.toFixed(1)}" y1="${ty.toFixed(1)}" x2="${dx.toFixed(1)}" y2="${dy.toFixed(1)}"/>
        <circle class="qd__true" cx="${tx.toFixed(1)}" cy="${ty.toFixed(1)}" r="2.4"/>` : ""}
    </g>`);
    discs.push(`<g class="qd__pt${clear ? " is-clear" : ""}" data-vid="${p.n}">
      <g data-pop><circle class="qd__disc" cx="${dx.toFixed(1)}" cy="${dy.toFixed(1)}" r="${R_DISC}"/>
      <text class="qd__n" x="${dx.toFixed(1)}" y="${(dy + 4).toFixed(1)}" text-anchor="middle">${nn(p.n)}</text></g>
    </g>`);
  }
  const marks = lines.join("") + discs.join("");
  /* Each side of the diagonal in its own channel's colour, faintly: the book's
     one key gives the reviewer the transcript's colour and the audience the
     audience's, so the half a mark falls in says who is warmer before the
     corner words are read (asked for by two readers, 24 Sep 2026). */
  const halves = `
    <polygon class="qd__half qd__half--a" points="${x(-dom)},${y(-dom)} ${x(-dom)},${y(dom)} ${x(dom)},${y(dom)}"/>
    <polygon class="qd__half qd__half--r" points="${x(-dom)},${y(-dom)} ${x(dom)},${y(-dom)} ${x(dom)},${y(dom)}"/>`;

  const words = pts.map((p) => `video ${p.n}: reviewer ${signed(p.reviewer.lean)}, audience ${signed(p.audience.lean)}`).join("; ");
  return `<svg class="qd" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="${esc(`Each video's reviewer lean across and audience lean up, from ${signed(-dom)} to ${signed(dom)}. ${words}.`)}">
    ${halves}
    ${grid}
    <line class="qd__diag" x1="${x(-dom)}" y1="${y(-dom)}" x2="${x(dom)}" y2="${y(dom)}" data-draw/>
    <text class="qd__cap qd__cap--a" x="${x(-dom) + 10}" y="${T + 18}">Audience warmer</text>
    <text class="qd__cap qd__cap--r" x="${R - 10}" y="${B - 10}" text-anchor="end">Reviewer warmer</text>
    <text class="qd__axis" x="${(L + R) / 2}" y="${H - 6}" text-anchor="middle">The reviewer's words, lean</text>
    <text class="qd__axis" x="14" y="${(T + B) / 2}" text-anchor="middle" transform="rotate(-90 14 ${(T + B) / 2})">The audience, lean</text>
    ${marks}
  </svg>`;
}

/* ------------------------------------------------------ one lean, all videos */

/**
 * Every video's lean on one rule, the odd one drawn large with its interval
 * and the others' median marked: the picture of the odd-one-out rule.
 */
export function oddStrip(rows, who, odd) {
  const pts = rows.filter((r) => r.analysed && finite(r[who].lean));
  if (!pts.length) return "";
  const W = 560, H = 76, L = 16, R = 544, Y = 46;
  const x = (v) => L + ((clamp(v, -1, 1) + 1) / 2) * (R - L);
  const focus = odd && odd.dimension === who ? odd : null;
  const levels = [];
  const marks = [...pts].sort((a, b) => a[who].lean - b[who].lean).map((p) => {
    const px = x(p[who].lean);
    let lv = 0;
    while (levels.some(([qx, ql]) => ql === lv && Math.abs(qx - px) < 17)) lv += 1;
    levels.push([px, lv]);
    const big = focus && focus.n === p.n;
    const py = Y - lv * 17;
    const shape = who === "reviewer"
      ? `<circle class="os__m${big ? " is-odd" : ""}" cx="${px.toFixed(1)}" cy="${py}" r="${big ? 10 : 8}"/>`
      : `<rect class="os__m${big ? " is-odd" : ""}" x="${(px - (big ? 10 : 8)).toFixed(1)}" y="${py - (big ? 10 : 8)}" width="${big ? 20 : 16}" height="${big ? 20 : 16}"/>`;
    return `<g data-vid="${p.n}" data-pop>${big && finite(p[who].se)
      ? `<line class="os__ci" x1="${x(p[who].lean - ciOf(p[who])).toFixed(1)}" y1="${py}" x2="${x(p[who].lean + ciOf(p[who])).toFixed(1)}" y2="${py}"/>` : ""}
      ${shape}<text class="os__n${big ? " is-odd" : ""}" x="${px.toFixed(1)}" y="${py + 3.5}" text-anchor="middle">${nn(p.n)}</text></g>`;
  }).join("");
  const med = focus ? `<line class="os__med" x1="${x(focus.others_median)}" y1="${Y - 30}" x2="${x(focus.others_median)}" y2="${Y + 14}"/>
    <text class="os__lab" x="${x(focus.others_median)}" y="${Y + 28}" text-anchor="middle">others' median ${signed(focus.others_median)}</text>` : "";
  return `<svg class="os${focus ? " is-focus" : ""}" viewBox="0 0 ${W} ${H + 8}" aria-hidden="true">
    <line class="os__axis" x1="${L}" y1="${Y}" x2="${R}" y2="${Y}"/>
    <line class="os__zero" x1="${x(0)}" y1="${Y - 6}" x2="${x(0)}" y2="${Y + 6}"/>
    <text class="os__end" x="${L}" y="${H + 4}">−1</text><text class="os__end" x="${R}" y="${H + 4}" text-anchor="end">+1</text>
    ${med}${marks}</svg>`;
}

/* ------------------------------------------------------ five tone lines -- */

/**
 * One review's tone on a percent-of-video axis, so five reviews of different
 * lengths share one scale: solid above the line, hatched below, a gap where
 * the words were not read, turning points marked, and the video's most
 * contested moment ticked (in the conflict colour only when it was flagged).
 */
export function toneMini(row, dom = 1) {
  const W = 1000, H = 70, T = 6, B = 64, mid = (T + B) / 2, half = (B - T) / 2;
  const x = (p) => (clamp(p, 0, 100) / 100) * W;
  const y = (v) => mid - (clamp(v, -dom, dom) / dom) * half;
  const pts = (row.tone && row.tone.points) || [];
  const runs = [];
  let run = [];
  for (const p of pts) {
    if (!finite(p.v) || !finite(p.p)) { if (run.length) runs.push(run); run = []; continue; }
    run.push(p);
  }
  if (run.length) runs.push(run);
  if (!runs.length) return `<p class="tm__none">The words of this video could not be read.</p>`;
  const line = runs.map((r) => r.map((p, i) => `${i ? "L" : "M"}${x(p.p).toFixed(1)},${y(p.v).toFixed(1)}`).join("")).join("");
  const area = runs.map((r) => {
    const top = r.map((p, i) => `${i ? "L" : "M"}${x(p.p).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    return `${top}L${x(r[r.length - 1].p).toFixed(1)},${mid}L${x(r[0].p).toFixed(1)},${mid}Z`;
  }).join("");
  const above = uid("tm-a"), below = uid("tm-b"), pat = uid("tm-h");
  const dur = row.tone.duration_s || 0;
  const m = row.moment;
  const tick = m && dur ? `<rect class="tm__mom${m.flagged ? " is-flagged" : ""}" x="${x((100 * m.start) / dur).toFixed(1)}" y="${B - 4}" width="4" height="8" data-pop>
      <title>${esc(`Most contested moment, ${m.time}${m.flagged ? ", flagged" : ""}`)}</title></rect>` : "";
  const turns = ((row.tone && row.tone.turns) || []).filter((t) => finite(t.p) && finite(t.v)).map((t) =>
    `<circle class="tm__turn" cx="${x(t.p).toFixed(1)}" cy="${y(t.v).toFixed(1)}" r="3.5" data-pop/>`).join("");
  return `<svg class="tm" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
    <defs><clipPath id="${above}"><rect x="0" y="0" width="${W}" height="${mid}"/></clipPath>
      <clipPath id="${below}"><rect x="0" y="${mid}" width="${W}" height="${H - mid}"/></clipPath>
      ${hatch(pat, "ta__hatch")}</defs>
    <line class="ta__zero" x1="0" y1="${mid}" x2="${W}" y2="${mid}" vector-effect="non-scaling-stroke"/>
    <path class="ta__pos" d="${area}" clip-path="url(#${above})" data-fade/>
    <path class="ta__neg" d="${area}" clip-path="url(#${below})" fill="url(#${pat})" data-fade/>
    <path class="ta__line" d="${line}" vector-effect="non-scaling-stroke" data-draw/>
    ${turns}${tick}
  </svg>`;
}

/**
 * One scale for every tone line of a set: the largest swing any of them made,
 * in quarters, never less than a quarter. Shared, so a flat review and a
 * lively one look flat and lively beside each other.
 */
export function toneDomain(rows) {
  const vs = rows.flatMap((r) => ((r.tone && r.tone.points) || []).map((p) => p.v)).filter(finite);
  const reach = vs.length ? Math.max(...vs.map(Math.abs)) : 1;
  return Math.min(1, Math.max(0.25, Math.ceil(reach * 4) / 4));
}

/* ------------------------------------------------------ the signs grid --- */

const SIGN_GLYPH = { present: "Present", absent: "Absent", not_checked: "Not checked" };

/** Five signs down, the videos across: present, absent, or not checked. */
export function signGrid(signs, rows) {
  const vids = rows.filter((r) => r.analysed);
  return `<table class="sgx">
    <caption class="sr-only">Each sign of a commercial interest, for each video</caption>
    <thead><tr><th scope="col"><span class="sr-only">Sign</span></th>
      ${vids.map((r) => `<th scope="col" class="sgx__vid" data-vid="${r.n}"><span class="t-read">${nn(r.n)}</span></th>`).join("")}
      <th scope="col" class="sgx__tot">Present in</th></tr></thead>
    <tbody>${signs.signs.map((s) => `
      <tr><th scope="row" class="sgx__name">${esc(s.name || s.id)}
          <span class="sg__kind">${s.kind === "fact" ? "fact" : "inference"}</span></th>
        ${vids.map((r) => {
          const st = s.states[r.n] || "not_checked";
          return `<td data-vid="${r.n}"><button class="sgx__dot" type="button" data-state="${st}"
            data-sign="${esc(s.id)}" data-n="${r.n}" data-pop
            aria-label="${esc(`${s.name}, video ${r.n}: ${SIGN_GLYPH[st]}`)}"></button></td>`;
        }).join("")}
        <td class="sgx__tot t-read">${vids.length - s.not_checked
          ? `${s.present} of ${vids.length - s.not_checked}${s.not_checked ? `<span class="sgx__nc">${s.not_checked} not checked</span>` : ""}`
          : `<span class="sgx__nc">not checked</span>`}</td></tr>`).join("")}
    </tbody></table>`;
}

/* ------------------------------------------------------ the matrix ------- */

const STANCE_WORD = {
  praise: "praised", criticism: "criticised", mixed: "mixed", neutral: "neutral", silent: "not discussed",
};
const AUD_WORD = { positive: "comments lean positive", negative: "comments lean negative",
  balanced: "comments balanced", unknown: "too few comments" };

function cellGlyph(cell, ids) {
  if (cell.status === "not_written") {
    return `<svg class="mx__g" viewBox="0 0 40 40" aria-hidden="true"><line class="mx__nw" x1="12" y1="20" x2="28" y2="20"/></svg>`;
  }
  const a = cell.audience || {};
  const ring = !a.comments ? ""
    : `<circle class="mx__ring" data-aud="${esc(a.call)}" cx="20" cy="20" r="16"/>`;
  const st = cell.stance;
  const disc = st === "silent" ? `<circle class="mx__dot" cx="20" cy="20" r="2.6"/>`
    : st === "criticism" ? `<circle class="mx__disc" data-stance="criticism" cx="20" cy="20" r="10" fill="url(#${ids.hatch})"/>`
    : st === "mixed" ? `<circle class="mx__disc" data-stance="mixed-o" cx="20" cy="20" r="10"/>
        <path class="mx__disc" data-stance="mixed" d="M20,10 A10,10 0 0 0 20,30 Z"/>`
    : st === "neutral" ? `<circle class="mx__disc" data-stance="neutral" cx="20" cy="20" r="10"/>
        <line class="mx__neu" x1="14.5" y1="20" x2="25.5" y2="20"/>`
    : `<circle class="mx__disc" data-stance="${esc(st)}" cx="20" cy="20" r="10"/>`;
  return `<svg class="mx__g" viewBox="0 0 40 40" aria-hidden="true">${ring}${disc}</svg>`;
}

/** The row's own count as one bar of one segment per video, in video order. */
export function consensusBar(cells) {
  return `<span class="cb" aria-hidden="true">${cells.map((c) => {
    const st = c.status === "not_written" ? "not_written" : c.stance;
    return `<i class="cb__s" data-stance="${st}" data-vid="${c.n}"></i>`;
  }).join("")}</span>`;
}

export function rowWords(t) {
  const r = t.reviewer;
  if (r.label === "agreed") return `${r.side === "praise" ? "Praised" : "Criticised"} in ${Math.max(r.praise_in, r.criticism_in)} of ${r.talked}`;
  if (r.label === "mostly") return `${r.side === "praise" ? "Praised" : "Criticised"} in ${Math.max(r.praise_in, r.criticism_in)} of ${r.talked}, one dissent`;
  if (r.label === "split") return `Split: praised in ${r.praise_in}, criticised in ${r.criticism_in}`;
  if (r.label === "neutral") return `Discussed in ${r.talked}, no side taken`;
  return r.talked ? `Discussed in ${r.talked}, too few sides to call` : "Not discussed";
}

/**
 * Themes down, videos across. The disc is the reviewer: filled for praise,
 * hatched for criticism, half for mixed, tinted for neutral, a dot when the
 * video did not discuss it. The ring is the audience on that theme: solid
 * when its comments lean positive, broken when they lean negative, thin when
 * balanced, absent with no comments. Cells are buttons: a roving tab stop,
 * arrow keys between them.
 */
export function matrix(themes, rows, groups) {
  const vids = rows.filter((r) => r.analysed);
  const ids = { hatch: uid("mx-h") };
  const productOf = new Map();
  for (const g of groups || []) for (const n of g.videos) productOf.set(n, g.product);
  const ordered = groups && groups.length
    ? [...vids].sort((a, b) => {
      const ga = groups.findIndex((g) => g.videos.includes(a.n));
      const gb = groups.findIndex((g) => g.videos.includes(b.n));
      return (ga < 0 ? 99 : ga) - (gb < 0 ? 99 : gb) || a.n - b.n;
    }) : vids;
  const head = groups && groups.length ? `<tr class="mx__groups"><td></td>${(() => {
    const out = [];
    for (let i = 0; i < ordered.length;) {
      const p = productOf.get(ordered[i].n) || "";
      let span = 1;
      while (i + span < ordered.length && (productOf.get(ordered[i + span].n) || "") === p) span += 1;
      out.push(`<th scope="colgroup" colspan="${span}" class="mx__prod">${p ? esc(p) : "No single product"}</th>`);
      i += span;
    }
    return out.join("");
  })()}<td></td></tr>` : "";
  const cellOf = (t, n) => t.cells.find((c) => c.n === n) || { n, stance: "silent", audience: {} };
  let first = true;
  const body = themes.map((t) => `
    <tr class="mx__row" data-theme="${esc(t.id)}" id="theme-${esc(t.id)}">
      <th scope="row" class="mx__name"><span class="mx__tn">${esc(t.name)}</span>
        ${t.aspects && t.aspects.length ? `<span class="mx__asp">${esc(t.aspects.slice(0, 4).join(", "))}</span>` : ""}</th>
      ${ordered.map((r) => {
        const c = cellOf(t, r.n);
        const label = c.status === "not_written"
          ? `${t.name}, video ${r.n}: not written yet`
          : `${t.name}, video ${r.n}: ${STANCE_WORD[c.stance]}; ${c.audience && c.audience.comments ? `${c.audience.comments} comments, ${AUD_WORD[c.audience.call] || ""}` : "no comments on it"}`;
        const tab = first ? "0" : "-1";
        first = false;
        return `<td data-vid="${r.n}"><button class="mx__cell" type="button" tabindex="${tab}"
          data-cell="${esc(t.id)}:${r.n}" data-vid="${r.n}" data-pop aria-label="${esc(label)}">${cellGlyph(c, ids)}</button></td>`;
      }).join("")}
      <td class="mx__sum">${consensusBar(ordered.map((r) => cellOf(t, r.n)))}
        <span class="mx__words" data-label="${esc(t.reviewer.label)}">${rowWords(t)}</span></td>
    </tr>`).join("");
  return `<table class="mx" role="grid" aria-label="Themes by video: the reviewer's stance and the audience's lean">
    <thead>${head}<tr><td class="mx__corner">
      <svg width="0" height="0" class="mx__defs" aria-hidden="true" focusable="false"><defs>${hatch(ids.hatch, "mx__hatch")}</defs></svg></td>
      ${ordered.map((r) => `<th scope="col" class="mx__vid" data-vid="${r.n}"><span class="t-read">${nn(r.n)}</span>
        <span class="mx__vt">${esc(String(r.title || "").split(/\s+/).slice(0, 4).join(" "))}</span></th>`).join("")}
      <th scope="col" class="mx__sumh">Across the videos</th></tr></thead>
    <tbody>${body}</tbody></table>`;
}

/* ------------------------------------------------------ periods ---------- */

function scoreDomain(values) {
  const lo = Math.max(0, Math.floor((Math.min(...values) - 5) / 10) * 10);
  const hi = Math.min(100, Math.ceil((Math.max(...values) + 5) / 10) * 10);
  return hi - lo < 20 ? [Math.max(0, lo - 10), Math.min(100, hi + 10)] : [lo, hi];
}

const MEASURE_NAME = { reviewer: "The reviewers' words", audience: "The audiences",
  authenticity: "Authenticity", brand_health: "Brand health" };

/**
 * One measure in two periods: every video's value in each, the medians joined
 * by the line that draws on, and -- where the same video is in both -- a
 * hairline from its first reading to its second.
 */
export function slope(m, labels) {
  const all = [...m.a, ...m.b].map((p) => p.v).filter(finite);
  if (!all.length) return "";
  const W = 300, H = 196, T = 30, B = 176, XA = 84, XB = 238;
  let lo, hi;
  if (m.kind === "lean") {
    const dom = leanDomain(all.map((v) => ({ lean: v, se: null })));
    lo = -dom; hi = dom;
  } else [lo, hi] = scoreDomain(all);
  const y = (v) => B - ((clamp(v, lo, hi) - lo) / (hi - lo || 1)) * (B - T);
  const fmt = m.kind === "lean" ? signed : (v) => String(Math.round(v));
  const col = (pts, cx) => pts.map((p, i) => {
    const off = (i % 3 - 1) * 7;
    return `<circle class="sl__pt" cx="${cx + off}" cy="${y(p.v).toFixed(1)}" r="4" data-vid="${p.n}" data-pop>
      <title>${esc(`Video ${p.n}: ${m.kind === "lean" ? signed(p.v) : score(p.v)}`)}</title></circle>`;
  }).join("");
  const same = m.a.filter((p) => p.video_id && m.b.some((q) => q.video_id === p.video_id)).map((p) => {
    const q = m.b.find((z) => z.video_id === p.video_id);
    return `<line class="sl__twice" x1="${XA}" y1="${y(p.v).toFixed(1)}" x2="${XB}" y2="${y(q.v).toFixed(1)}"/>`;
  }).join("");
  const ma = m.a_range.median, mb = m.b_range.median;
  const med = finite(ma) && finite(mb) ? `
    <line class="sl__band" x1="${XA}" y1="${y(m.a_range.min)}" x2="${XA}" y2="${y(m.a_range.max)}"/>
    <line class="sl__band" x1="${XB}" y1="${y(m.b_range.min)}" x2="${XB}" y2="${y(m.b_range.max)}"/>
    <line class="sl__med" x1="${XA}" y1="${y(ma).toFixed(1)}" x2="${XB}" y2="${y(mb).toFixed(1)}" data-draw/>
    <text class="sl__v" x="${XA - 14}" y="${(y(ma) + 4).toFixed(1)}" text-anchor="end">${fmt(ma)}</text>
    <text class="sl__v" x="${XB + 14}" y="${(y(mb) + 4).toFixed(1)}">${fmt(mb)}</text>` : "";
  const call = { moved: "moved: the two ranges do not overlap", within_spread: "within the spread",
    too_few: "too few videos to call" }[m.call] || "";
  return `<figure class="sl" data-call="${esc(m.call)}">
    <figcaption class="sl__cap"><b>${MEASURE_NAME[m.key] || esc(m.key)}</b><span class="sl__call">${call}</span></figcaption>
    <svg class="sl__svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(`${MEASURE_NAME[m.key]}: median ${finite(ma) ? fmt(ma) : "none"} in ${labels[0]} and ${finite(mb) ? fmt(mb) : "none"} in ${labels[1]}; ${call}.`)}">
      <text class="sl__col" x="${XA}" y="14" text-anchor="middle">${esc(labels[0])}</text>
      <text class="sl__col" x="${XB}" y="14" text-anchor="middle">${esc(labels[1])}</text>
      <line class="sl__axis" x1="${XA}" y1="${T - 6}" x2="${XA}" y2="${B + 6}"/>
      <line class="sl__axis" x1="${XB}" y1="${T - 6}" x2="${XB}" y2="${B + 6}"/>
      <text class="sl__tick" x="${XA - 30}" y="${T + 4}" text-anchor="end">${fmt(hi)}</text>
      <text class="sl__tick" x="${XA - 30}" y="${B + 4}" text-anchor="end">${fmt(lo)}</text>
      ${same}${med}${col(m.a, XA)}${col(m.b, XB)}
    </svg></figure>`;
}

/** One measure of one video read twice: the first reading open, the second filled. */
export function twiceBell(a, b, kind) {
  if (!finite(a) || !finite(b)) return `<span class="tw__none">not readable</span>`;
  const W = 200, L = 6, R = 194, Y = 10;
  const [lo, hi] = kind === "lean" ? [-1, 1] : [0, 100];
  const x = (v) => L + ((clamp(v, lo, hi) - lo) / (hi - lo)) * (R - L);
  const fmt = kind === "lean" ? signed : score;
  return `<span class="tw"><svg class="tw__svg" viewBox="0 0 ${W} 20" aria-hidden="true">
      <line class="tw__axis" x1="${L}" y1="${Y}" x2="${R}" y2="${Y}"/>
      <line class="tw__gap" x1="${x(a).toFixed(1)}" y1="${Y}" x2="${x(b).toFixed(1)}" y2="${Y}" data-grow/>
      <circle class="tw__a" cx="${x(a).toFixed(1)}" cy="${Y}" r="4.5"/>
      <circle class="tw__b" cx="${x(b).toFixed(1)}" cy="${Y}" r="4.5" data-pop/></svg>
    <span class="tw__v t-read">${fmt(a)} <span class="tw__then">then</span> ${fmt(b)}</span></span>`;
}

