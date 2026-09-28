/* ===========================================================================
   charts.js — the written report's figures, drawn from the facts it carries.

   Every mark here is placed by a number the pipeline computed
   (pipeline/analyst_facts.py); nothing is estimated in the browser. Each
   builder returns markup whose resting state is the finished drawing, so a
   figure is complete with scripting slow, with reduced motion, or in a
   thumbnail, and each carries its own words for a screen reader.

   The encoding is the book's own, set on the audience band in codex.css and
   repeated here so the two can be read against each other:

     positive   the channel's colour, solid
     neutral    the same colour, tinted into the paper
     negative   the same colour, hatched

   so a reading is never told by colour alone. The reviewer is drawn in the
   transcript's colour, the audience in the audience's, because those are the
   two channels the reading comes from. `--tear` is kept for what it means
   everywhere else in the build: a flagged conflict.

   MOTION. One orchestrated draw-on, the first time a spread is opened: lines
   draw, bars grow from their baseline, marks arrive. Geometry only. A figure
   is never counted up, because a count-up walks a measured number through
   values it never held. Bars carry their true width in the markup and the
   tween only scales from zero, so the honest state is the default.
   ======================================================================== */

import { gsap, reduced } from "./motion.js";
import { esc, mmss } from "./format.js";

let serial = 0;
/* Shared with setcharts.js, the combined book's figures, so both draw with
   one set of helpers. */
export const uid = (prefix) => `${prefix}${(serial += 1)}`;
export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
export const finite = (v) => typeof v === "number" && Number.isFinite(v);

/** A lean on the -1..+1 scale, signed, to two places. */
export function signed(v) {
  if (!finite(v)) return "not readable";
  const s = Math.abs(v).toFixed(2);
  return v > 0.004 ? `+${s}` : v < -0.004 ? `−${s}` : "0.00";
}

/** The three-way encoding as a class suffix. */
export const KIND = { POSITIVE: "pos", NEUTRAL: "neu", NEGATIVE: "neg" };

/** A hatch pattern for negative readings, in the given channel colour class. */
export function hatch(id, cls) {
  return `<pattern id="${id}" width="5" height="5" patternUnits="userSpaceOnUse"
    patternTransform="rotate(45)"><rect width="5" height="5" class="ch-bg"/>
    <line x1="0" y1="0" x2="0" y2="5" class="${cls}" stroke-width="2.2"/></pattern>`;
}

/* ------------------------------------------------------- the tug bar ---- */

/**
 * Reviewer against audience on one -1..+1 axis, each with its 95% interval.
 * `agreement.call` decides how the gap between them is drawn: a dashed line
 * when no clear difference was found, a solid one when one side is
 * measurably warmer.
 */
export function tugBar({ reviewer, audience, agreement }) {
  const W = 520, L = 86, R = 434, AX = 52;
  const x = (v) => L + ((clamp(v, -1, 1) + 1) / 2) * (R - L);
  const ok = (s) => s && finite(s.lean);
  const whisker = (s, y) => (ok(s) && finite(s.se)
    ? `<line class="tug__ci" x1="${x(s.lean - 1.96 * s.se).toFixed(1)}" y1="${y}"
        x2="${x(s.lean + 1.96 * s.se).toFixed(1)}" y2="${y}" data-grow-c/>` : "");
  const label = (s, y, who) => {
    if (!ok(s)) return `<text class="tug__lab" x="${(L + R) / 2}" y="${y}" text-anchor="middle">${who}: not readable</text>`;
    const px = clamp(x(s.lean), L + 34, R - 34);
    return `<text class="tug__lab" x="${px.toFixed(1)}" y="${y}" text-anchor="middle">${who} ${signed(s.lean)}</text>`;
  };
  const clear = agreement && (agreement.call === "reviewer_warmer" || agreement.call === "audience_warmer");
  const gap = ok(reviewer) && ok(audience)
    ? `<line class="tug__gap${clear ? " is-clear" : ""}" x1="${x(reviewer.lean).toFixed(1)}" y1="30"
        x2="${x(audience.lean).toFixed(1)}" y2="74"/>` : "";
  const words = [
    ok(reviewer) ? `The reviewer's words lean ${signed(reviewer.lean)}` : "The reviewer's words could not be read",
    ok(audience) ? `the comments lean ${signed(audience.lean)}` : "the comments could not be read",
  ].join("; ");
  return `<svg class="tug" viewBox="0 0 ${W} 104" role="img"
      aria-label="${esc(`${words}, on a scale from minus one, all negative, to plus one, all positive.`)}">
    <line class="tug__axis" x1="${L}" y1="${AX}" x2="${R}" y2="${AX}"/>
    <line class="tug__tick" x1="${L}" y1="${AX - 5}" x2="${L}" y2="${AX + 5}"/>
    <line class="tug__tick tug__tick--zero" x1="${(L + R) / 2}" y1="${AX - 9}" x2="${(L + R) / 2}" y2="${AX + 9}"/>
    <line class="tug__tick" x1="${R}" y1="${AX - 5}" x2="${R}" y2="${AX + 5}"/>
    <text class="tug__end" x="${L - 10}" y="${AX + 4}" text-anchor="end">negative</text>
    <text class="tug__end" x="${R + 10}" y="${AX + 4}" text-anchor="start">positive</text>
    ${gap}
    ${whisker(reviewer, 30)}${whisker(audience, 74)}
    ${ok(reviewer) ? `<circle class="tug__r" cx="${x(reviewer.lean).toFixed(1)}" cy="30" r="6.5" data-pop/>` : ""}
    ${ok(audience) ? `<rect class="tug__a" x="${(x(audience.lean) - 6).toFixed(1)}" y="68" width="12" height="12" data-pop/>` : ""}
    ${label(reviewer, 14, "Reviewer")}${label(audience, 99, "Audience")}
  </svg>`;
}

/* ------------------------------------------------------- the tone line -- */

/**
 * The reviewer's smoothed tone across the whole video, split at zero: solid
 * above, hatched below. A segment the transcript could not read breaks the
 * line rather than being joined across. Flagged moments are ticked in the
 * conflict colour on the time axis; turning points are pinned and labelled.
 */
export function toneArc({ points = [], turns = [], flagged = [], duration = 0, labels = {},
  compact = false }) {
  const W = compact ? 480 : 960;
  const H = compact ? 132 : 300;
  const L = compact ? 8 : 64, R = W - (compact ? 8 : 20);
  const T = compact ? 10 : 58, B = H - (compact ? 22 : 44);
  const mid = (T + B) / 2, half = (B - T) / 2;
  const dur = duration > 0 ? duration : Math.max(1, ...points.map((p) => p.end || 0));
  const x = (t) => L + (clamp(t, 0, dur) / dur) * (R - L);
  const y = (v) => mid - clamp(v, -1, 1) * half;

  const runs = [];
  let run = [];
  for (const p of points) {
    if (!finite(p.smooth)) { if (run.length) runs.push(run); run = []; continue; }
    run.push(p);
  }
  if (run.length) runs.push(run);

  const line = runs.map((r) => (r.length === 1
    ? `M${x(r[0].start).toFixed(1)},${y(r[0].smooth).toFixed(1)}H${x(r[0].end).toFixed(1)}`
    : r.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.smooth).toFixed(1)}`).join(""))).join("");
  const area = runs.map((r) => {
    const pts = r.length === 1 ? [{ t: r[0].start, smooth: r[0].smooth }, { t: r[0].end, smooth: r[0].smooth }] : r;
    const top = pts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.smooth).toFixed(1)}`).join("");
    return `${top}L${x(pts[pts.length - 1].t).toFixed(1)},${mid}L${x(pts[0].t).toFixed(1)},${mid}Z`;
  }).join("");

  const above = uid("ta-a"), below = uid("ta-b"), pat = uid("ta-h");
  const ticks = compact ? [] : [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const tx = L + f * (R - L);
    const anchor = f === 0 ? "start" : f === 1 ? "end" : "middle";
    return `<line class="ta__grid" x1="${tx.toFixed(1)}" y1="${T}" x2="${tx.toFixed(1)}" y2="${B}"/>
      <text class="ta__time" x="${tx.toFixed(1)}" y="${B + 30}" text-anchor="${anchor}">${mmss(f * dur)}</text>`;
  }).join("");
  const flags = flagged.map((s) => `<rect class="ta__flag" x="${x(s.start_s).toFixed(1)}" y="${B + 6}"
      width="${Math.max(3, x(s.end_s) - x(s.start_s)).toFixed(1)}" height="7" data-pop>
      <title>${esc(`Flagged at ${mmss(s.start_s)}`)}</title></rect>`).join("");

  /* THE LABELS SIT ON A RAIL ABOVE THE PLOT, never on the line. Placed
     beside their points, the labels of two dips near the floor ran into each
     other and into the curve (Nike, 23 Sep 2026). Each label is centred over
     its point where it fits, pushed in from the edges, and dropped to a second
     row when it would overlap its neighbour; a hairline runs down to the
     point it names. Widths are estimated from the character count at the
     label's size, with room to spare. */
  const pins = compact ? "" : (() => {
    const CHAR = 7.2, PAD = 18;
    const placed = [];
    const rowEnds = [-Infinity, -Infinity];
    const sorted = turns.map((turn, i) => ({ turn, i })).sort((a, b) => a.turn.t - b.turn.t);
    for (const { turn, i } of sorted) {
      const text = `${i + 1} ${labels[turn.seg] || (turn.kind === "peak" ? "Peak" : "Dip")}`;
      const w = text.length * CHAR;
      const px = x(turn.t);
      const cx = clamp(px, L + w / 2, R - w / 2);
      let row = rowEnds.findIndex((end) => cx - w / 2 >= end + PAD);
      if (row < 0) row = rowEnds[0] <= rowEnds[1] ? 0 : 1;
      rowEnds[row] = cx + w / 2;
      placed.push({ turn, i, text, cx, row, px });
    }
    return placed.map(({ turn, i, text, cx, row, px }) => {
      const ly = row === 0 ? 14 : 34;
      const py = y(turn.smooth);
      return `<g class="ta__pin" data-pop>
        <line class="ta__stem" x1="${px.toFixed(1)}" y1="${ly + 6}" x2="${px.toFixed(1)}" y2="${(py - 5).toFixed(1)}"/>
        <circle class="ta__dot" cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="4.5"/>
        <text class="ta__lab" x="${cx.toFixed(1)}" y="${ly}" text-anchor="middle"><tspan class="ta__n">${i + 1}</tspan>${esc(text.slice(String(i + 1).length))}</text>
      </g>`;
    }).join("");
  })();

  const summary = `The reviewer's tone across ${mmss(dur)}, smoothed over a minute. `
    + (turns.length ? `${turns.length} turning point${turns.length > 1 ? "s" : ""} are marked. ` : "")
    + (flagged.length ? `${flagged.length} flagged moment${flagged.length > 1 ? "s" : ""} are ticked on the time axis.` : "");
  return `<svg class="ta${compact ? " ta--compact" : ""}" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="${esc(summary)}">
    <defs>
      <clipPath id="${above}"><rect x="0" y="0" width="${W}" height="${mid}"/></clipPath>
      <clipPath id="${below}"><rect x="0" y="${mid}" width="${W}" height="${H - mid}"/></clipPath>
      ${hatch(pat, "ta__hatch")}
    </defs>
    ${ticks}
    ${compact ? "" : `<text class="ta__axis" x="${L - 10}" y="${T + 4}" text-anchor="end">positive</text>
      <text class="ta__axis" x="${L - 10}" y="${B + 4}" text-anchor="end">negative</text>`}
    <line class="ta__zero" x1="${L}" y1="${mid}" x2="${R}" y2="${mid}"/>
    <path class="ta__pos" d="${area}" clip-path="url(#${above})" data-fade/>
    <path class="ta__neg" d="${area}" clip-path="url(#${below})" fill="url(#${pat})" data-fade/>
    <path class="ta__line" d="${line}" data-draw/>
    ${flags}${pins}
  </svg>`;
}

/* ------------------------------------------------------- bars ----------- */

/**
 * Where the reviewer's time went, by topic: one bar per topic, split by the
 * transcript's reading of those seconds. Widths are shares of the longest
 * topic, written into the markup.
 */
export function timeBars(topics) {
  const rows = topics.filter((t) => t.reviewer && t.reviewer.claims);
  if (!rows.length) return "";
  const total = (t) => Object.values(t.reviewer.seconds).reduce((a, b) => a + b, 0);
  const max = Math.max(...rows.map(total), 1);
  return `<ol class="tb" role="list">${rows.map((t) => {
    const s = t.reviewer.seconds;
    const all = total(t);
    const seg = (k) => (s[k] > 0 ? `<i class="tb__seg tb__seg--${KIND[k]}" style="width:${((s[k] / all) * 100).toFixed(2)}%"></i>` : "");
    return `<li class="tb__row">
      <span class="tb__name">${esc(t.name)}</span>
      <span class="tb__track"><span class="tb__bar" style="width:${((all / max) * 100).toFixed(2)}%" data-grow
        role="img" aria-label="${esc(`${t.name}: ${mmss(all)} of talk, ${mmss(s.POSITIVE)} read positive, ${mmss(s.NEUTRAL)} neutral, ${mmss(s.NEGATIVE)} negative`)}">
        ${seg("POSITIVE")}${seg("NEUTRAL")}${seg("NEGATIVE")}</span></span>
      <span class="tb__n t-read">${mmss(all)}</span>
    </li>`;
  }).join("")}</ol>`;
}

/**
 * How the audience talks about each topic: complaints to the left of the
 * centre line, praise to the right, neutral as a count. Lengths are shares of
 * the largest side across all topics.
 */
export function themeBars(topics) {
  const rows = topics.filter((t) => t.audience && t.audience.comments);
  if (!rows.length) return "";
  const max = Math.max(1, ...rows.flatMap((t) => [t.audience.counts.POSITIVE, t.audience.counts.NEGATIVE]));
  return `<ol class="th" role="list">${rows.map((t) => {
    const c = t.audience.counts;
    return `<li class="th__row">
      <span class="th__name">${esc(t.name)}</span>
      <span class="th__neg"><i style="width:${((c.NEGATIVE / max) * 100).toFixed(2)}%" data-grow-left></i>
        <b class="t-read">${c.NEGATIVE || ""}</b></span>
      <span class="th__pos"><i style="width:${((c.POSITIVE / max) * 100).toFixed(2)}%" data-grow></i>
        <b class="t-read">${c.POSITIVE || ""}</b></span>
      <span class="th__neu">${c.NEUTRAL ? `${c.NEUTRAL} neutral` : ""}</span>
      <span class="sr-only">${esc(`${t.name}: ${c.POSITIVE} positive, ${c.NEUTRAL} neutral, ${c.NEGATIVE} negative comments`)}</span>
    </li>`;
  }).join("")}</ol>`;
}

/**
 * Reviewer against audience, topic by topic, on the same -1..+1 axis as the
 * tug bar. A side with nothing to say about a topic is left out and named.
 */
export function dumbbells(topics) {
  const rows = topics.filter((t) => (t.reviewer && finite(t.reviewer.lean)) || (t.audience && finite(t.audience.lean)));
  if (!rows.length) return "";
  const W = 240, L = 10, R = 230;
  const x = (v) => L + ((clamp(v, -1, 1) + 1) / 2) * (R - L);
  return `<ol class="db" role="list">${rows.map((t) => {
    const r = t.reviewer && finite(t.reviewer.lean) ? t.reviewer.lean : null;
    const a = t.audience && finite(t.audience.lean) ? t.audience.lean : null;
    const call = t.agreement && t.agreement.call;
    const note = r == null ? "no claims from the reviewer"
      : a == null ? "no comments on it"
      : call === "reviewer_warmer" ? "reviewer warmer"
      : call === "audience_warmer" ? "audience warmer"
      : "no clear difference";
    return `<li class="db__row">
      <span class="db__name">${esc(t.name)}</span>
      <svg class="db__svg" viewBox="0 0 ${W} 22" aria-hidden="true">
        <line class="db__axis" x1="${L}" y1="11" x2="${R}" y2="11"/>
        <line class="db__zero" x1="${(L + R) / 2}" y1="4" x2="${(L + R) / 2}" y2="18"/>
        ${r != null && a != null ? `<line class="db__gap" x1="${x(r).toFixed(1)}" y1="11" x2="${x(a).toFixed(1)}" y2="11"/>` : ""}
        ${r != null ? `<circle class="db__r" cx="${x(r).toFixed(1)}" cy="11" r="5" data-pop/>` : ""}
        ${a != null ? `<rect class="db__a" x="${(x(a) - 4.5).toFixed(1)}" y="6.5" width="9" height="9" data-pop/>` : ""}
      </svg>
      <span class="db__note">${note}</span>
      <span class="sr-only">${esc(`${t.name}: reviewer ${r == null ? "no claims" : signed(r)}, audience ${a == null ? "no comments" : signed(a)}, ${note}.`)}</span>
    </li>`;
  }).join("")}</ol>`;
}

/* ------------------------------------------------------- motion --------- */

/**
 * The draw-on for one spread, the first time it is opened. Consults reduced()
 * first: with reduced motion the finished drawing is simply what is there.
 */
export function animateIn(root) {
  if (!root || reduced() || root.dataset.drawn === "yes") return;
  root.dataset.drawn = "yes";
  const ease = "power2.out";
  for (const path of root.querySelectorAll("[data-draw]")) {
    if (typeof path.getTotalLength !== "function") continue;
    const len = path.getTotalLength();
    if (!len) continue;
    gsap.fromTo(path, { strokeDasharray: len, strokeDashoffset: len },
      { strokeDashoffset: 0, duration: 1.1, ease, clearProps: "strokeDasharray,strokeDashoffset" });
  }
  const grow = root.querySelectorAll("[data-grow]");
  if (grow.length) gsap.from(grow, { scaleX: 0, transformOrigin: "0% 50%", duration: 0.7, ease, stagger: 0.035, clearProps: "transform" });
  const left = root.querySelectorAll("[data-grow-left]");
  if (left.length) gsap.from(left, { scaleX: 0, transformOrigin: "100% 50%", duration: 0.7, ease, stagger: 0.035, clearProps: "transform" });
  const ci = root.querySelectorAll("[data-grow-c]");
  if (ci.length) gsap.from(ci, { scaleX: 0, transformOrigin: "50% 50%", duration: 0.6, ease, delay: 0.25, clearProps: "transform" });
  /* A matrix can hold forty marks: past twenty they share one short window
     rather than queueing for over a second. */
  const pop = root.querySelectorAll("[data-pop]");
  if (pop.length) gsap.from(pop, { scale: 0, transformOrigin: "50% 50%", duration: 0.45, ease: "back.out(1.6)",
    stagger: pop.length > 20 ? { amount: 0.6 } : 0.03, delay: 0.2, clearProps: "transform" });
  const fade = root.querySelectorAll("[data-fade]");
  if (fade.length) gsap.from(fade, { opacity: 0, duration: 0.9, ease, delay: 0.3, clearProps: "opacity" });
}
