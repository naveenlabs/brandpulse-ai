/* ===========================================================================
   combined.js — the combined book's written pages: several videos, one report.

   The combined written report (pipeline/analyst_sweep.py) reads every video's
   own report together. This module prints it. As in written.js, two kinds of
   thing arrive and are printed differently on purpose:

     facts     computed by code (analyst_sweep_facts.py): every call, count,
               rank and rule. Always present, even before any model has run,
               so every combined book on this machine has its table, its
               quadrant, its odd one out, its tone lines, its trust and its
               signs from the start.
     written   the model's sentences, each checked against the set before it
               was kept. Marked as the model's; a sentence code built where
               the model's did not pass is marked as that.

   The themes (what the videos agree and split on) need every video's own
   written report first; until then those pages say so and give the command.

   Every sentence of the model's carries its evidence: a video number goes to
   its row in the table, a moment or a comment opens that video's own book at
   it, a theme goes to its row in the matrix.
   ======================================================================== */

import { count, esc, mmss, score, confidence } from "./format.js";
import { signed, themeBars } from "./charts.js";
import { cut, source, notYet, levelPill, readingsSentence, CODE_READINGS, inShortBlock } from "./written.js";
import {
  nn, CALL_WORD, callRibbon, leanMini, quadrant, oddStrip, toneMini, toneDomain, signGrid, matrix,
  consensusBar, rowWords, slope, twiceBell,
} from "./setcharts.js";

const LEVEL = {
  well_covered: { word: "Well covered", dots: 3 },
  partly_covered: { word: "Partly covered", dots: 2 },
  thinly_covered: { word: "Thinly covered", dots: 1 },
  unknown: { word: "Coverage unknown", dots: 0 },
};

const AGREE_WORD = {
  reviewer_warmer: "Reviewer warmer", audience_warmer: "Audience warmer",
  no_clear_difference: "No clear difference", unknown: "Cannot compare",
};

/* ------------------------------------------------------- the context ---- */

/**
 * What every page of one combined book needs: the analysis, its rows by
 * video number, its themes by id, and where each video's own book is.
 */
export function makeContext(record, analysis) {
  const facts = analysis.facts;
  const rows = facts.videos || [];
  const byN = new Map(rows.map((r) => [r.n, r]));
  const themes = (analysis.reading && analysis.reading.themes) || [];
  const byTheme = new Map(themes.map((t) => [t.id, t]));
  const times = new Map();
  for (const t of themes) {
    for (const c of t.cells) if (c.quote) times.set(`${c.n}:${c.quote.seg}`, c.quote.time);
  }
  const sweepId = record.sweep_id;
  return {
    record, a: analysis, facts, rows, byN, themes, byTheme, times,
    written: analysis.written || null,
    reading: analysis.reading || null,
    command: `python write_analysis.py --sweep ${sweepId}`,
    href: (n, query = "") => {
      const r = byN.get(n);
      return r && r.analysed
        ? `/brand/${encodeURIComponent(sweepId)}/${encodeURIComponent(r.video_id)}${query}` : null;
    },
  };
}

/** Evidence as buttons and links: a video, a moment of it, a comment on it, a theme. */
export function setChips(ids, ctx) {
  const out = (ids || []).map((raw) => {
    const m = String(raw).match(/^(?:V(\d{1,2})(?::([SC])(\d{1,5}))?|H(\d{1,2}))$/);
    if (!m) return "";
    const [, v, kind, num, h] = m;
    if (h !== undefined) {
      const t = ctx.byTheme.get(`H${h}`);
      return t ? `<button class="ev ev--t" type="button" data-evh="H${h}">${esc(t.name)}</button>` : "";
    }
    const n = Number(v);
    if (!ctx.byN.has(n)) return "";
    if (!kind) {
      return `<button class="ev" type="button" data-evv="${n}" aria-label="Video ${n} in the table">${nn(n)}</button>`;
    }
    const href = ctx.href(n, kind === "S" ? `?at=${num}` : `?c=${num}`);
    if (!href) return "";
    if (kind === "S") {
      const time = ctx.times.get(`${n}:${num}`);
      return `<a class="ev" href="${href}" aria-label="Open video ${n}${time ? ` at ${time}` : ""}">${nn(n)}${time ? ` at ${esc(time)}` : ", moment"}</a>`;
    }
    return `<a class="ev ev--c" href="${href}" aria-label="Read comment ${Number(num) + 1} on video ${n}">${nn(n)}, comment ${Number(num) + 1}</a>`;
  }).filter(Boolean);
  return out.length ? `<span class="evs">${out.join("")}</span>` : "";
}

/** A sentence and its evidence, marked by who wrote it. */
function said(item, ctx, cls = "cx-text") {
  if (!item || !item.text) return "";
  return `<p class="${cls}">${esc(item.text)} ${source(item)}</p>${setChips(item.evidence, ctx)}`;
}

/* ------------------------------------------------------- code's words ---- */

function joinWords(parts) {
  const p = parts.filter(Boolean);
  return p.length <= 1 ? p.join("") : `${p.slice(0, -1).join(", ")} and ${p[p.length - 1]}`;
}

/** The set's calls in a sentence, built from the counts: true by construction. */
export function codeVerdict(facts) {
  const s = facts.set;
  const counted = (calls, noun) => {
    const bits = [["positive", "lean positive"], ["balanced", "are balanced"], ["negative", "lean negative"],
      ["unknown", "could not be read"]].filter(([k]) => calls[k]).map(([k, w]) => `${w} in ${calls[k]}`);
    return bits.length ? `${noun} ${joinWords(bits)}` : "";
  };
  const parts = [counted(s.reviewer_calls, "the reviewers' words"), counted(s.audience_calls, "the audiences")]
    .filter(Boolean);
  return `Across ${s.analysed} video${s.analysed === 1 ? "" : "s"}, ${parts.join("; ")}.`;
}

export function codeAgreement(facts) {
  const g = facts.set.agreement_calls;
  const bits = [];
  if (g.reviewer_warmer) bits.push(`the reviewer is measurably warmer than the audience in ${g.reviewer_warmer}`);
  if (g.audience_warmer) bits.push(`the audience is measurably warmer than the reviewer in ${g.audience_warmer}`);
  if (g.no_clear_difference) bits.push(`there is no clear difference in ${g.no_clear_difference}`);
  if (g.unknown) bits.push(`the two cannot be compared in ${g.unknown}`);
  return bits.length ? `Of ${facts.set.analysed} videos, ${joinWords(bits)}.` : "No video could be compared.";
}

/**
 * The set's plain line for its title page (24 Sep 2026; see inShort in
 * written.js): how much evidence the set rests on, which videos declared a
 * paid promotion -- three of five people in the final user evaluation wanted
 * that at the top rather than on the signs page -- and that no reviewer's
 * honesty can be read from it. Facts only; no model writes this.
 */
const SET_COVER = {
  well_covered: "Plenty of evidence behind this set.",
  partly_covered: "Some of the evidence behind this set is thin.",
  thinly_covered: "The evidence behind this set is thin.",
  unknown: "How much evidence is behind this set is unknown.",
};
export function setInShort(ctx) {
  const f = ctx && ctx.facts;
  if (!f) return "";
  const n = f.set.analysed;
  const s1 = ((f.signs && f.signs.signs) || []).find((s) => s.id === "S1");
  const states = Object.values((s1 && s1.states) || {});
  const declared = ((s1 && s1.present_in) || []).slice().sort((x, y) => x - y);
  const unchecked = states.filter((s) => s === "not_checked").length;
  let paid;
  if (!s1) {
    paid = "Whether any video declared a paid promotion could not be checked.";
  } else if (declared.length) {
    const who = `${declared.length === 1 ? "Video" : "Videos"} ${joinWords(declared.map(nn))}`;
    const rest = n - declared.length - unchecked;
    paid = `${who} declared a paid promotion${rest > 0 ? `; the other ${count(rest)} did not` : ""}${unchecked ? `; for ${count(unchecked)} it could not be checked` : ""}.`;
  } else {
    paid = unchecked === n ? "Whether any video declared a paid promotion could not be checked."
      : `None of the ${count(n - unchecked)} videos checked declared a paid promotion.`;
  }
  return inShortBlock(`${SET_COVER[f.coverage && f.coverage.level] || SET_COVER.unknown} ${paid} It cannot say whether any reviewer is honest.`);
}

/** A combined report written before the sweep, or a video's own report, changed. */
function staleNote(ctx) {
  if (!ctx.a.stale) return "";
  const byVid = new Map(ctx.rows.map((r) => [r.video_id, r.n]));
  const changed = (ctx.a.stale_members || []).map((v) => byVid.get(v)).filter(Boolean).sort((x, y) => x - y);
  return `<p class="rdx__stale" role="note">Written before ${changed.length
    ? `the own report of video ${changed.map(nn).join(", ")} changed` : "this sweep changed"}. Every figure
    is current; the themes and the words are from when it was written.
    <code>${esc(ctx.command)} --combined-only</code></p>`;
}

/* ------------------------------------------------------- overview -------- */

export function readingPage(ctx) {
  const f = ctx.facts;
  const w = ctx.written;
  const v = w && w.verdict;
  const verdict = v && v.source === "model"
    ? `<p class="vd">${esc(v.text)}</p>${setChips(v.evidence, ctx)}`
    : v && v.source === "code"
      ? `<p class="vd">${esc(v.text)}</p>${setChips(v.evidence, ctx)}
         <p class="vd__src">Summarised from the figures by code; the advice further on is the local model's.</p>`
      : `<p class="vd vd--code">${esc(v ? v.text : codeVerdict(f))}</p>
         <p class="vd__src">${w ? "Written by code from the figures: the fact checks set the local model's own summary aside."
           : "Summarised from the figures. The combined written report has not been run for this set."}</p>`;
  return `<section class="rd rdx" aria-labelledby="rdx-h">
    <div class="rd__head"><p class="cx-kicker" id="rdx-h">The reading across ${count(f.set.analysed)} video${f.set.analysed === 1 ? "" : "s"}</p>
      ${levelPill(f.coverage.level, "#trust")}</div>
    ${staleNote(ctx)}
    ${verdict}
    ${callRibbon(f.videos, f.set)}
    <div class="rdx__agree"><p class="ag__k">Do reviewers and audiences agree?</p>
      <p class="rdx__words">${esc((w && w.agreement_words && w.agreement_words.text) || codeAgreement(f))}</p></div>
    <p class="cx-note">Each tile is one video, numbered as in the contents. A reviewer is read from the words
      (the transcript model), an audience from its comments (the comment model); a lean is called only when its
      95% interval leaves zero. ${esc(f.rules.consensus)}</p>
  </section>`;
}

export function setTakeaways(ctx) {
  const w = ctx.written;
  const items = (w && w.takeaways) || [];
  const dropped = w ? (((ctx.a.verifier || {}).by_field || {}).takeaway || {}).dropped || 0 : 0;
  return `<section class="tk" aria-labelledby="tkx-h">
    <h2 id="tkx-h" class="cx-h">What to take from the set</h2>
    ${!w ? notYet("Three takeaways across the videos", ctx.command) : items.length ? `
    <ol class="tk__list">${items.map((t, i) => {
      const theme = ctx.byTheme.get((t.evidence || []).find((id) => id.startsWith("H")));
      return `
      <li class="tk__item"><span class="tk__n" aria-hidden="true">${i + 1}</span>
        <div><p class="tk__text">${esc(t.text)}</p>
          ${theme ? `<p class="tk__basis">${esc(theme.name)}: ${rowWords(theme).toLowerCase()}</p>` : ""}
          ${setChips(t.evidence, ctx)}</div></li>`;
    }).join("")}
    </ol>` : `<p class="cx-note">None of the model's takeaways passed the checks, so none is printed.</p>`}
    ${w && dropped ? `<p class="cx-note tk__dropped">${dropped} further ${dropped === 1 ? "takeaway was" : "takeaways were"}
      written and dropped because ${dropped === 1 ? "it" : "they"} did not hold up against the set.</p>` : ""}
    <p class="cx-note">The advice is the local model's, checked against every video's own report before it was
      kept; the figures under each are code's, read off the matrix.</p>
  </section>`;
}

/** Where a Brand health score rests on a near-tie of comments: one short paragraph. */
export function nearTieNote(ctx) {
  const ties = ctx.rows.filter((r) => r.analysed && r.near_tie && r.near_tie.near_tie);
  if (!ties.length) return "";
  const each = ties.map((r) => {
    const t = r.near_tie;
    return `<span class="t-read">${nn(r.n)}</span> ${count(t.top[1])} against ${count(t.second[1])}${Number.isFinite(t.swing)
      ? `, ${score(t.swing)} points at stake` : ""}`;
  });
  return `<div class="nt" data-vid-list>
    <p class="nt__p"><b>Near-ties.</b> ${each.join("; ")}. The comment label is a majority vote, and Brand health gives
      it 60% of its weight, so a handful of comments can swing it: one video read twice on this machine, days apart,
      went from 79.29 to 15.96 (23 Sep 2026). The leans above have no such cliff.</p>
  </div>`;
}

/* ------------------------------------------------------- the videos ----- */

function coverageDots(level) {
  const l = LEVEL[level] || LEVEL.unknown;
  return `<span class="vt__cov"><span class="lvl__dots" aria-hidden="true">${[1, 2, 3].map((i) =>
    `<i${i <= l.dots ? " data-on" : ""}></i>`).join("")}</span><span>${l.word}</span></span>`;
}

function signDots(r) {
  const s = r.signs || { signs: [] };
  return `<span class="vt__signs"><span class="vt__sd" aria-hidden="true">${s.signs.map((x) =>
    `<i data-state="${esc(x.state)}"></i>`).join("")}</span>
    <span class="t-read">${s.present} of ${s.checked}</span></span>`;
}

const WARMER = { reviewer_warmer: "Reviewer", audience_warmer: "Audience",
  no_clear_difference: "Neither clearly", unknown: "Cannot tell" };

export function tablePage(ctx) {
  const rows = ctx.rows;
  const cov = { well_covered: 3, partly_covered: 2, thinly_covered: 1, unknown: 0 };
  const num = (v) => (Number.isFinite(v) ? v : "");
  const tr = (r) => {
    if (!r.analysed) {
      return `<tr class="vt__row is-failed" data-vid="${r.n}" data-sort-n="${r.n}">
        <td class="vt__n t-read">${nn(r.n)}</td>
        <td class="vt__video"><span class="vt__title">${esc(r.title || r.video_id)}</span></td>
        <td colspan="8" class="vt__failed">Not analysed. ${esc(r.reason || "No reason was recorded.")}</td></tr>`;
    }
    const nt = r.near_tie && r.near_tie.near_tie;
    const lv = LEVEL[r.coverage] || LEVEL.unknown;
    return `<tr class="vt__row" data-vid="${r.n}" data-sort-n="${r.n}"
        data-sort-reviewer="${num(r.reviewer.lean)}" data-sort-audience="${num(r.audience.lean)}"
        data-sort-gap="${num(r.agreement.gap)}" data-sort-coverage="${cov[r.coverage] ?? 0}"
        data-sort-signs="${r.signs.present}" data-sort-authenticity="${num(r.scores.authenticity)}"
        data-sort-brand_health="${num(r.scores.brand_health)}">
      <td class="vt__n t-read">${nn(r.n)}</td>
      <td class="vt__video"><a class="vt__title" href="${ctx.href(r.n)}">${esc(cut(r.title || r.video_id, 7))}</a>
        <span class="vt__ch">${[r.channel ? esc(r.channel) : "", r.duration_s ? mmss(r.duration_s) : ""].filter(Boolean).join(", ")}</span></td>
      <td class="vt__vd">${r.verdict ? `${esc(cut(r.verdict.text, 12))}${r.verdict.source === "template" ? ` ${source(r.verdict)}` : ""}`
        : `<span class="vt__none">Not written yet</span>`}</td>
      <td>${leanMini(r.reviewer, "reviewer")}</td>
      <td>${leanMini(r.audience, "audience")}</td>
      <td class="vt__ag" data-call="${esc(r.agreement.call)}">${WARMER[r.agreement.call] || ""}</td>
      <td><span class="lvl__dots" aria-hidden="true" title="${lv.word}">${[1, 2, 3].map((i) => `<i${i <= lv.dots ? " data-on" : ""}></i>`).join("")}</span>
        <span class="sr-only">${lv.word}</span></td>
      <td>${signDots(r)}</td>
      <td class="t-read vt__sc">${score(r.scores.authenticity)}</td>
      <td class="t-read vt__sc">${score(r.scores.brand_health)}${nt ? `<span class="vt__nt" aria-hidden="true">&asymp;</span><span class="sr-only">, resting on a near-tie of comments</span>` : ""}</td></tr>`;
  };
  const th = (key, label) => `<th scope="col"${key === "n" ? ' aria-sort="ascending"' : ""}>
    <button class="vt__sort" type="button" data-sort="${key}">${label}</button></th>`;
  return `<section class="vt" aria-labelledby="vt-h">
    <div class="vt__head">
      <h2 id="vt-h" class="cx-h">The videos, side by side</h2>
      <p class="cx-lede">Every video on the same measures: a heading sorts by it, a title opens that video's own book.</p>
    </div>
    <div class="vt__wrap"><table class="vt__t">
      <caption class="sr-only">The videos in this set, compared</caption>
      <thead><tr>${th("n", "No.")}<th scope="col">Video</th><th scope="col">Verdict</th>
        ${th("reviewer", '<i class="k k--r" aria-hidden="true"></i>Reviewer\'s words')}
        ${th("audience", '<i class="k k--a" aria-hidden="true"></i>Audience')}
        ${th("gap", "Warmer")}${th("coverage", "Covered")}${th("signs", "Signs")}
        ${th("authenticity", "Authenticity&dagger;")}${th("brand_health", "Brand health&dagger;")}</tr></thead>
      <tbody data-vt-body>${rows.map(tr).join("")}</tbody>
    </table></div>
    <p class="cx-note vt__key">Leans run from &minus;1 (all negative) to +1 (all positive), with 95% intervals.
      Warmer: the side measurably warmer. Signs: present of the five checked on the Trust pages.
      <span class="vt__nt">&asymp;</span> a near-tie of comments. Brand health gives a video's comments one
      majority label; where that label is negative, however narrowly, the comments add nothing and Brand health
      is 0.4&nbsp;&times;&nbsp;Authenticity, so compare videos on the leans.</p>
    ${ctx.record.bias_caveat ? `<p class="cav vt__fn"><span aria-hidden="true">&dagger;</span> ${esc(ctx.record.bias_caveat)}</p>` : ""}
  </section>`;
}

export function quadrantPage(ctx) {
  const f = ctx.facts;
  return `<section class="qdx" aria-labelledby="qdx-h">
    <h2 id="qdx-h" class="cx-h">Reviewers against their audiences</h2>
    <p class="cx-lede">Each video once: how its reviewer's words lean, across, and how its comments lean, up.
      On the diagonal the two lean alike; above it the audience is warmer, below it the reviewer.</p>
    <figure class="qdx__fig">${quadrant(ctx.rows)}</figure>
    <p class="qdx__key" aria-hidden="true"><span><i class="qdx__k is-clear"></i>one side measurably warmer</span>
      <span><i class="qdx__k"></i>no clear difference</span><span><i class="qdx__kci"></i>95% intervals</span></p>
    <p class="rdx__words">${esc((ctx.written && ctx.written.agreement_words && ctx.written.agreement_words.text) || codeAgreement(f))}</p>
  </section>`;
}

export function oddPage(ctx, frameOf) {
  const f = ctx.facts;
  const odd = f.odd_one_out;
  const w = ctx.written;
  const minority = ctx.themes.filter((t) => t.odd).map((t) => {
    const r = ctx.byN.get(t.odd.n);
    return `<li data-vid="${t.odd.n}"><span class="t-read">${nn(t.odd.n)}</span> The only video to
      ${t.odd.stance === "criticism" ? "criticise" : "praise"} <b>${esc(t.name)}</b>, which the others
      ${t.odd.stance === "criticism" ? "praise" : "criticise"}.${r ? ` <span class="od__t">${esc(cut(r.title, 8))}</span>` : ""}</li>`;
  });
  let head;
  if (odd) {
    const r = ctx.byN.get(odd.n) || {};
    const img = frameOf(r);
    const who = odd.dimension === "reviewer" ? "reviewer's words" : "audience";
    head = `<article class="od__card" data-vid="${odd.n}">
      <div class="od__frame">${img ? `<img src="${img}" alt="" loading="lazy" decoding="async">` : ""}<span class="mem__n t-read">${nn(odd.n)}</span></div>
      <div class="od__body"><p class="od__title"><a href="${ctx.href(odd.n)}">${esc(r.title || "")}</a></p>
        <p class="od__fact">Its ${who} ${odd.lean > odd.others_median ? "lean warmer" : "lean cooler"} than the rest:
          <span class="t-read">${signed(odd.lean)}</span>, where the others' median is <span class="t-read">${signed(odd.others_median)}</span>.</p>
        ${w && w.odd_words ? said(w.odd_words, ctx, "od__words") : ""}</div>
    </article>`;
  } else {
    head = `<p class="cx-text">No video stands apart, by this rule. Every video's leans sit within a quarter of
      the scale of the others', or too close for their intervals to tell apart.</p>`;
  }
  return `<section class="od" aria-labelledby="od-h">
    <h2 id="od-h" class="cx-h">The odd one out</h2>
    ${head}
    <figure class="od__strips">
      <figcaption class="od__cap"><i class="k k--r" aria-hidden="true"></i>The reviewers' words</figcaption>${oddStrip(ctx.rows, "reviewer", odd)}
      <figcaption class="od__cap"><i class="k k--a" aria-hidden="true"></i>The audiences</figcaption>${oddStrip(ctx.rows, "audience", odd)}
    </figure>
    ${minority.length ? `<div class="od__themes"><p class="ag__k">Alone on a theme</p><ul class="od__list">${minority.join("")}</ul></div>` : ""}
    <p class="cx-note">${esc(f.rules.odd)}</p>
  </section>`;
}

export function tonesPage(ctx) {
  const rows = ctx.rows.filter((r) => r.analysed);
  const dom = toneDomain(rows);
  return `<section class="tmx" aria-labelledby="tmx-h">
    <div class="tmx__head">
      <h2 id="tmx-h" class="cx-h">How each review moved</h2>
      <p class="cx-lede">Each reviewer's tone from first second to last, on one scale of the video's length and one
        scale of tone (${signed(-dom)} to ${signed(dom)}): solid above the line, hatched below, a dot at each turn,
        a tick at the most contested moment, pink when it was flagged.</p>
    </div>
    <ol class="tmx__list">${rows.map((r) => `
      <li class="tmx__row" data-vid="${r.n}">
        <p class="tmx__who"><span class="t-read tmx__n">${nn(r.n)}</span>
          <a class="tmx__t" href="${ctx.href(r.n)}">${esc(cut(r.title, 9))}</a>
          <span class="tmx__len t-read">${mmss(r.tone.duration_s)}</span></p>
        ${toneMini(r, dom)}
        <span class="sr-only">${esc(`Video ${r.n}: reviewer ${CALL_WORD[r.reviewer.call]}, ${r.tone.turns.length} turning points.`)}</span>
      </li>`).join("")}</ol>
    <p class="tmx__axis" aria-hidden="true"><span>start</span><span>half way</span><span>end</span></p>
  </section>`;
}

const READS = { transcript: "words", facial: "face", vocal: "voice", comment: "comments" };

export function momentsPage(ctx, frameOf) {
  const rows = ctx.rows.filter((r) => r.analysed);
  const card = (r) => {
    const m = r.moment;
    if (!m) {
      return `<article class="omc" data-vid="${r.n}"><p class="omc__who"><span class="t-read">${nn(r.n)}</span></p>
        <p class="cx-note">No moment of this video scored any conflict.</p></article>`;
    }
    const img = frameOf(r);
    return `<article class="omc" data-vid="${r.n}" aria-label="${esc(`Video ${r.n}, the moment at ${m.time}`)}">
      <div class="om__frame">${img ? `<img src="${img}" alt="" loading="lazy" decoding="async">` : `<span class="om__none">No frame for this second</span>`}
        <span class="mem__n t-read">${nn(r.n)}</span></div>
      <p class="om__when"><span class="t-time">${esc(m.time)}</span>
        <span class="om__c${m.flagged ? " is-flagged" : ""}">conflict ${confidence(m.conflict)}${m.flagged ? ", flagged" : ""}</span></p>
      <blockquote class="om__said">&ldquo;${esc(cut(m.text, 16))}&rdquo;</blockquote>
      <ul class="om__reads">${["transcript", "facial", "vocal", "comment"].map((k) => {
        const v = m.valences[k];
        return `<li data-v="${v ? esc(v.toLowerCase()) : "none"}"><span class="om__ch">${READS[k]}</span>
          <span class="om__v">${v ? esc(v.toLowerCase()) : "no reading"}</span></li>`;
      }).join("")}</ul>
      ${m.note ? `<p class="om__note">${esc(cut(m.note, 22))}</p>`
        : `<p class="om__note">${esc(readingsSentence(m.valences))} ${CODE_READINGS}</p>`}
      <a class="cx-btn" href="${ctx.href(r.n, `?at=${m.seg}`)}">Open this moment</a>
    </article>`;
  };
  return `<section class="omx" aria-labelledby="omy-h">
    <div class="omx__head">
      <h2 id="omy-h" class="cx-h">One moment per video that does not add up</h2>
      <p class="cx-lede">The second of each video where its four readings disagreed most: what was said, what each
        channel read, and a note on it: the video's own report's where it passed the checks, otherwise the readings in words.</p>
    </div>
    <div class="omy__grid">${rows.map(card).join("")}</div>
  </section>`;
}

/* ------------------------------------------------------- consensus ------- */

function themesNotYet(ctx) {
  const s = ctx.facts.set.written;
  return notYet("The themes the videos share", ctx.command)
    + `<p class="cx-note">Themes are built from each video's own written report, grouped across the set by the
      local model. ${count(s.complete + s.partial)} of ${count(ctx.facts.set.analysed)} videos have one so far.</p>`;
}

export function matrixPage(ctx, groups) {
  if (!ctx.reading || !ctx.themes.length) {
    return `<section class="mxp" aria-labelledby="mxp-h">
      <h2 id="mxp-h" class="cx-h">What they agree on, theme by theme</h2>${themesNotYet(ctx)}</section>`;
  }
  const unplaced = (ctx.reading.unplaced || []).length;
  const missing = ctx.facts.set.analysed - (ctx.reading.members_written || []).length;
  return `<section class="mxp" aria-labelledby="mxp-h">
    <div class="mxp__head">
      <h2 id="mxp-h" class="cx-h">What they agree on, theme by theme</h2>
      <p class="cx-lede">Themes down, videos across. The disc is the reviewer, the ring around it the audience on that
        theme. Point at a cell, or move with the arrow keys, to read what was said.</p>
    </div>
    <div class="mxp__body">
      <div class="mxp__grid">${matrix(ctx.themes, ctx.rows, groups)}</div>
      <aside class="mxd">
        <p class="mxp__key" aria-hidden="true">
          <span><i class="mk mk--praise"></i>praised</span><span><i class="mk mk--criticism"></i>criticised</span>
          <span><i class="mk mk--mixed"></i>mixed</span><span><i class="mk mk--neutral"></i>neutral</span>
          <span><i class="mk mk--silent"></i>not discussed</span>
          <span><i class="mr mr--positive"></i>comments positive</span><span><i class="mr mr--negative"></i>negative</span>
          <span><i class="mr mr--balanced"></i>balanced</span></p>
        <div class="mxd__detail" data-mx-detail aria-live="polite">
          <p class="mxd__hint">Point at a cell to read what the reviewer said about that theme, and what the
            comments said.</p>
        </div>
        <p class="cx-note">${esc(ctx.facts.rules.theme)}${unplaced ? ` ${count(unplaced)} topic${unplaced === 1 ? "" : "s"} raised by one video only ${unplaced === 1 ? "is" : "are"} in no theme.` : ""}${missing > 0 ? ` ${count(missing)} video${missing === 1 ? " has" : "s have"} no written report of ${missing === 1 ? "its" : "their"} own yet, and ${missing === 1 ? "its column is" : "their columns are"} marked with a dash.` : ""}</p>
      </aside>
    </div>
  </section>`;
}

/** The words shown when a matrix cell is pointed at or focused. */
export function cellDetail(ctx, themeId, n) {
  const t = ctx.byTheme.get(themeId);
  const r = ctx.byN.get(n);
  if (!t || !r) return "";
  const c = t.cells.find((x) => x.n === n);
  const head = `<p class="mxd__who"><span class="t-read">${nn(n)}</span> ${esc(cut(r.title, 10))}</p>
    <p class="mxd__theme">${esc(t.name)}</p>`;
  if (!c || c.status === "not_written") {
    return `${head}<p class="cx-note">This video has no written report of its own yet.</p>`;
  }
  const stance = { praise: "praised it", criticism: "criticised it", mixed: "was mixed about it",
    neutral: "mentioned it without taking a side", silent: "did not discuss it" }[c.stance];
  const q = c.quote;
  const a = c.audience;
  return `${head}
    <p class="mxd__k"><i class="k k--r" aria-hidden="true"></i>The reviewer ${stance}</p>
    ${q ? `<blockquote class="mxd__q">&ldquo;${esc(cut(q.quote, 30))}&rdquo;</blockquote>
      <a class="ev" href="${ctx.href(n, `?at=${q.seg}`)}">Open ${esc(q.time)}</a>` : ""}
    <p class="mxd__k"><i class="k k--a" aria-hidden="true"></i>${a.comments
      ? `${count(a.comments)} comment${a.comments === 1 ? "" : "s"}: ${count(a.counts.POSITIVE)} positive,
         ${count(a.counts.NEUTRAL)} neutral, ${count(a.counts.NEGATIVE)} negative` : "No comments on it"}</p>
    ${a.example ? `<blockquote class="mxd__q mxd__q--c">&ldquo;${esc(cut(a.example.quote, 26))}&rdquo;</blockquote>
      <a class="ev ev--c" href="${ctx.href(n, `?c=${a.example.i}`)}">Comment ${a.example.i + 1}</a>` : ""}
    ${c.pushback ? `<p class="mxd__push">The reviewer and the comments pull opposite ways here.</p>` : ""}`;
}

function themeQuote(ctx, t, stance) {
  const c = t.cells.find((x) => x.stance === stance && x.quote);
  if (!c) return "";
  return `<blockquote class="ag__q" data-vid="${c.n}">&ldquo;${esc(cut(c.quote.quote, 22))}&rdquo;
    <a class="ev" href="${ctx.href(c.n, `?at=${c.quote.seg}`)}">${nn(c.n)} at ${esc(c.quote.time)}</a></blockquote>`;
}

export function agreedPage(ctx) {
  const w = ctx.written;
  if (!ctx.reading || !ctx.themes.length) {
    return `<section class="agx" aria-labelledby="agx-h"><h2 id="agx-h" class="cx-h">Praised and criticised across the set</h2>
      ${themesNotYet(ctx)}</section>`;
  }
  const side = (want) => ctx.themes.filter((t) => ["agreed", "mostly"].includes(t.reviewer.label) && t.reviewer.side === want);
  const list = (items, stance, empty) => (items.length ? `<ol class="agx__list">${items.map((t) => `
    <li class="agx__item"><p class="agx__name"><button class="ev ev--t" type="button" data-evh="${esc(t.id)}">${esc(t.name)}</button>
      <span class="agx__count">${rowWords(t)}</span></p>
      ${consensusBar(t.cells)}${themeQuote(ctx, t, stance)}</li>`).join("")}</ol>`
    : `<p class="cx-note">${empty}</p>`);
  return `<section class="agx" aria-labelledby="agx-h">
    <h2 id="agx-h" class="cx-h">Praised and criticised across the set</h2>
    ${w && w.consensus_words ? said(w.consensus_words, ctx, "agx__words") : ""}
    <div class="agx__cols">
      <div><p class="ag__k"><i class="mk mk--praise" aria-hidden="true"></i>Praised</p>
        ${list(side("praise"), "praise", "No theme was praised by two or more reviewers without a dissent.")}</div>
      <div><p class="ag__k"><i class="mk mk--criticism" aria-hidden="true"></i>Criticised</p>
        ${list(side("criticism"), "criticism", "No theme was criticised by two or more reviewers without a dissent.")}</div>
    </div>
  </section>`;
}

export function splitPage(ctx) {
  const w = ctx.written;
  if (!ctx.reading || !ctx.themes.length) {
    return `<section class="spx" aria-labelledby="spx-h"><h2 id="spx-h" class="cx-h">Where they split</h2>
      <p class="cx-note">The themes come with the combined written report.</p></section>`;
  }
  const split = ctx.themes.filter((t) => t.reviewer.label === "split");
  const push = ctx.themes.filter((t) => t.pushback.length);
  return `<section class="spx" aria-labelledby="spx-h">
    <h2 id="spx-h" class="cx-h">Where they split</h2>
    ${w && w.split_words ? said(w.split_words, ctx, "agx__words") : ""}
    ${split.length ? `<ol class="spx__list">${split.slice(0, 3).map((t) => `
      <li class="spx__item"><p class="agx__name"><button class="ev ev--t" type="button" data-evh="${esc(t.id)}">${esc(t.name)}</button>
        <span class="agx__count">${rowWords(t)}</span></p>
        <div class="spx__voices"><div><p class="spx__k">For</p>${themeQuote(ctx, t, "praise")}</div>
          <div><p class="spx__k">Against</p>${themeQuote(ctx, t, "criticism")}</div></div></li>`).join("")}</ol>`
      : `<p class="cx-note">No theme split the reviewers: wherever two or more took a side, they took the same one,
        or only one dissented.</p>`}
    ${push.length ? `<div class="spx__push"><p class="ag__k">Where audiences push back</p><ul class="od__list">${push.map((t) =>
      t.pushback.map((n) => {
        const c = t.cells.find((x) => x.n === n);
        return `<li data-vid="${n}"><span class="t-read">${nn(n)}</span> The reviewer ${c.stance === "praise" ? "praises" : "criticises"}
          <b>${esc(t.name)}</b>; its ${count(c.audience.comments)} comments on it lean ${c.audience.call}.</li>`;
      }).join("")).join("")}</ul></div>` : ""}
  </section>`;
}

/* ------------------------------------------------------- products -------- */

export function lineupPage(ctx) {
  const groups = (ctx.reading && ctx.reading.product_groups) || [];
  return `<section class="lu" aria-labelledby="lu-h">
    <h2 id="lu-h" class="cx-h">The products these videos cover</h2>
    <p class="cx-lede">Each product as its videos' titles name it, with how each of its reviewers and audiences
      lean.</p>
    <ol class="lu__list">${groups.map((g) => `
      <li class="lu__item"><p class="lu__name">${esc(g.product)}</p>
        <p class="lu__vids">${g.videos.map((n) => `<span data-vid="${n}" class="t-read">${nn(n)}</span>`).join(" ")}</p>
        <ul class="lu__rows">${g.videos.map((n) => {
          const r = ctx.byN.get(n);
          return r && r.analysed ? `<li data-vid="${n}"><span class="t-read">${nn(n)}</span>
            ${leanMini(r.reviewer, "reviewer")}${leanMini(r.audience, "audience")}</li>` : "";
        }).join("")}</ul></li>`).join("")}</ol>
  </section>`;
}

export function productsWordsPage(ctx) {
  const w = ctx.written;
  const groups = (ctx.reading && ctx.reading.product_groups) || [];
  const best = (n, stance) => ctx.themes.filter((t) => t.cells.some((c) => c.n === n && c.stance === stance)).map((t) => t.name);
  return `<section class="lu" aria-labelledby="lu2-h">
    <h2 id="lu2-h" class="cx-h">What they say about each</h2>
    ${w && w.lineup_words ? said(w.lineup_words, ctx, "agx__words") : ""}
    <table class="lu__t"><caption class="sr-only">Themes praised and criticised, by product</caption>
      <thead><tr><th scope="col">Product</th><th scope="col">Praised</th><th scope="col">Criticised</th></tr></thead>
      <tbody>${groups.map((g) => {
        const p = [...new Set(g.videos.flatMap((n) => best(n, "praise")))];
        const c = [...new Set(g.videos.flatMap((n) => best(n, "criticism")))];
        return `<tr><th scope="row">${esc(g.product)}</th><td>${p.length ? esc(p.join(", ")) : "none"}</td>
          <td>${c.length ? esc(c.join(", ")) : "none"}</td></tr>`;
      }).join("")}</tbody></table>
    <p class="cx-note">Product names are copied from each video's title by the local model and checked against
      it; videos naming the same product are grouped.</p>
  </section>`;
}

/* ------------------------------------------------------- audience -------- */

export function talkSetPage(ctx) {
  const f = ctx.facts;
  const w = ctx.written;
  const c = f.audience.counts;
  const pooled = ctx.themes.map((t) => {
    const counts = { POSITIVE: 0, NEUTRAL: 0, NEGATIVE: 0 };
    for (const cell of t.cells) {
      for (const k of Object.keys(counts)) counts[k] += ((cell.audience || {}).counts || {})[k] || 0;
    }
    return { name: t.name, audience: { comments: t.audience.comments, counts } };
  }).filter((t) => t.audience.comments);
  const about = f.about_reviewers || [];
  return `<section class="tl" aria-labelledby="tlx-h">
    <h2 id="tlx-h" class="cx-h">How people talk about it</h2>
    ${w && w.brand_health_words ? said(w.brand_health_words, ctx, "tl__words")
      : `<p class="tl__words">Across ${count(f.audience.comments)} comments on ${count(f.set.analysed)} videos,
        ${count(c.POSITIVE)} read positive, ${count(c.NEUTRAL)} neutral and ${count(c.NEGATIVE)} negative.</p>`}
    ${pooled.length ? `${themeBars(pooled)}
      <p class="tt__key" aria-hidden="true"><span class="th__keyl">complaints</span><span class="th__keyr">praise</span></p>
      <p class="cx-note">Every audience's comments on each theme, counted together. Which comments belong to which
        theme is the local model's reading; whether each is positive or negative is the benched comment model's.</p>`
      : ctx.reading ? "" : themesNotYet(ctx)}
    ${about.length ? `<div class="abx"><p class="ag__k">About the reviewers themselves</p>
      <ul class="od__list">${about.slice(0, 3).map((x) => `<li data-vid="${x.n}"><span class="t-read">${nn(x.n)}</span>
        ${count(x.comments)} comments${x.example ? `, such as &ldquo;${esc(cut(x.example.quote, 10))}&rdquo;` : ""}</li>`).join("")}</ul></div>` : ""}
  </section>`;
}

const SENTIMENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"];

export function eachAudienceSet(ctx) {
  const rows = ctx.rows.filter((r) => r.analysed);
  const W = 240, L = 6, R = 234, Y = 10;
  const x = (v) => L + ((Math.max(-1, Math.min(1, v)) + 1) / 2) * (R - L);
  return `<section class="ea" aria-labelledby="eax-h">
    <h2 id="eax-h" class="cx-h">Each audience on its own</h2>
    <p class="cx-lede">The pooled figure can hide an audience that said the opposite of the rest, so each is drawn
      on one scale: its lean with a 95% interval, and its comments by label.</p>
    <ul class="eax">${rows.map((r) => {
      const d = r.comments.distribution || {};
      const total = SENTIMENTS.reduce((s, k) => s + (d[k] || 0), 0);
      const a = r.audience;
      const ok = Number.isFinite(a.lean);
      const ci = ok && Number.isFinite(a.se) ? 1.96 * a.se : 0;
      const nt = r.near_tie && r.near_tie.near_tie;
      return `<li class="eax__row" data-vid="${r.n}">
        <span class="eax__n t-read">${nn(r.n)}</span>
        <div class="eax__lean"><svg class="lr__svg" viewBox="0 0 ${W} 20" aria-hidden="true">
            <line class="lr__axis" x1="${L}" y1="${Y}" x2="${R}" y2="${Y}"/>
            <line class="lr__zero" x1="${x(0)}" y1="${Y - 6}" x2="${x(0)}" y2="${Y + 6}"/>
            ${ci ? `<line class="lr__ci" x1="${x(a.lean - ci).toFixed(1)}" y1="${Y}" x2="${x(a.lean + ci).toFixed(1)}" y2="${Y}" data-grow-c/>` : ""}
            ${ok ? `<rect class="lr__a" x="${(x(a.lean) - 4.5).toFixed(1)}" y="${Y - 4.5}" width="9" height="9" data-pop/>` : ""}
          </svg><span class="t-read eax__v">${ok ? signed(a.lean) : "not readable"}</span></div>
        <div class="eax__band">${total ? `<div class="au__band" role="img" aria-label="${esc(`Video ${r.n}: ${SENTIMENTS.map((k) => `${d[k] || 0} ${k.toLowerCase()}`).join(", ")}`)}">
            ${SENTIMENTS.map((k) => `<i data-k="${k}" style="--n:${d[k] || 0}"></i>`).join("")}</div>
          <p class="each__v">${SENTIMENTS.map((k) => `${count(d[k] || 0)} ${k.toLowerCase()}`).join(", ")}${nt ? ", a near-tie" : ""}</p>`
          : `<p class="each__v is-absent">No comment distribution was recorded.</p>`}</div>
      </li>`;
    }).join("")}</ul>
    ${nearTieNote(ctx)}
  </section>`;
}

/** The first question of each audience, then the rest in order, up to `k`. */
function pickQuestions(qs, k) {
  const first = [];
  const seen = new Set();
  for (const q of qs) if (!seen.has(q.n)) { seen.add(q.n); first.push(q); }
  return [...first, ...qs.filter((q) => !first.includes(q))].slice(0, k);
}

export function asksSetPage(ctx) {
  const qs = ctx.facts.questions || [];
  return `<section class="ak" aria-labelledby="akx-h">
    <h2 id="akx-h" class="cx-h">What the audiences ask</h2>
    <p class="cx-lede">The questions each audience asked most, the most-liked first: what people still want to
      know after watching.</p>
    ${qs.length ? `<ul class="ak__qs akx__qs">${pickQuestions(qs, 6).map((q) => `
      <li data-vid="${q.n}"><p class="ak__q"><span class="t-read akx__n">${nn(q.n)}</span>&ldquo;${esc(cut(q.quote, 18))}&rdquo;
        <a class="ev ev--c" href="${ctx.href(q.n, `?c=${q.i}`)}">comment ${q.i + 1}</a></p></li>`).join("")}</ul>`
      : `<p class="cx-note">Nobody asked a question in the comments that were read.</p>`}
    <p class="cx-note">Usernames and links are removed before any comment is quoted.</p>
  </section>`;
}

/* ------------------------------------------------------- trust ----------- */

export function trustSetPage(ctx) {
  const c = ctx.facts.coverage;
  const l = LEVEL[c.level] || LEVEL.unknown;
  const need = (k) => (k.id === "none_thin" ? "none" : `at least ${count(k.target)}`);
  return `<section class="tr" aria-labelledby="trx-h">
    <h2 id="trx-h" class="cx-h">How far to trust this set</h2>
    <div class="tr__level" data-lvl="${esc(c.level)}">
      <span class="lvl__dots lvl__dots--big" aria-hidden="true">${[1, 2, 3].map((i) => `<i${i <= l.dots ? " data-on" : ""}></i>`).join("")}</span>
      <p class="tr__word">${l.word}</p>
    </div>
    <p class="cx-text">${esc(c.means_not)}</p>
    <table class="tr__checks">
      <thead><tr><th scope="col">Check</th><th scope="col">This set</th><th scope="col">Needs</th><th scope="col"><span class="sr-only">Result</span></th></tr></thead>
      <tbody>${c.checks.map((k) => `
        <tr data-pass="${k.passed === true ? "yes" : k.passed === false ? "no" : "unknown"}">
          <th scope="row">${esc(k.label)}</th><td class="t-read">${count(k.value)}</td><td>${need(k)}</td>
          <td class="tr__res">${k.passed === true ? "met" : k.passed === false ? "not met" : "unknown"}</td></tr>`).join("")}
      </tbody></table>
    <ul class="trx__vids">${c.videos.map((v) => {
      const lv = LEVEL[v.level] || LEVEL.unknown;
      return `<li data-vid="${v.n}"><span class="t-read">${nn(v.n)}</span>
        <span class="lvl__dots" aria-hidden="true">${[1, 2, 3].map((i) => `<i${i <= lv.dots ? " data-on" : ""}></i>`).join("")}</span>
        <span>${lv.word}${v.failed.length ? `: ${esc(v.failed.join("; ").toLowerCase())}` : ""}</span></li>`;
    }).join("")}</ul>
    <div class="tr__ceiling"><p class="ag__k">What no report here can promise</p>
      <p class="cx-note">${esc(c.ceiling.text)}</p></div>
  </section>`;
}

export function signsSetPage(ctx) {
  const s = ctx.facts.signs;
  const notChecked = s.signs.filter((x) => x.not_checked).length;
  return `<section class="sg" aria-labelledby="sgx-h">
    <h2 id="sgx-h" class="cx-h">Could any of this be paid?</h2>
    <p class="cx-lede">Five signs of a commercial interest, checked on every video. A filled dot is present, an
      open one absent, a dashed one not checked. Point at a filled dot for what was found.</p>
    ${signGrid(s, ctx.rows)}
    <p class="sgx__ev" data-sg-detail aria-live="polite"></p>
    <p class="sg__disc">${esc(s.disclaimer)}</p>
    ${notChecked ? `<p class="cx-note">Signs 1 and 3 need each video's own details from YouTube, which are fetched
      when its written report is run; until then they are not checked.</p>` : ""}
  </section>`;
}

/** What a present sign found, in one line, for the grid's detail line. */
export function signEvidence(ctx, signId, n) {
  const r = ctx.byN.get(n);
  const sign = r && r.signs && r.signs.signs.find((x) => x.id === signId);
  if (!sign) return "";
  const e = sign.evidence || {};
  const lead = `Video ${nn(n)}, ${sign.name.toLowerCase()}: ${sign.state.replace("_", " ")}.`;
  if (sign.state !== "present") return lead;
  if (signId === "S1") {
    return `${lead} ${e.label === true ? "The creator ticked YouTube's paid-promotion box." : ""}
      ${(e.description || []).slice(0, 1).map((h) => `Description: &ldquo;${esc(cut(h.context, 14))}&rdquo;`).join("")}`;
  }
  if (signId === "S2") return `${lead} ${(e.speech || []).map((h) => `&ldquo;${esc(h.match)}&rdquo; at ${esc(h.time)}`).join("; ")}`;
  if (signId === "S3") return `${lead} ${(e.description || []).map((h) => `&ldquo;${esc(cut(h.context, 12))}&rdquo;`).join("; ")}`;
  if (signId === "S4") {
    const g = e.agreement || {};
    return `${lead} Gap ${signed(g.gap)}, 95% interval ${signed(g.low)} to ${signed(g.high)}.`;
  }
  if (signId === "S5") {
    const k = new Set([...(e.positive_flagged || []), ...(e.controller_flag || [])]).size;
    return `${lead} ${k} flagged moment${k === 1 ? "" : "s"} where the words read positive.`;
  }
  return lead;
}

/* ------------------------------------------------------- another period -- */

const MEASURE_ORDER = ["reviewer", "audience", "authenticity", "brand_health"];

export function periodChecks(pf, labels) {
  const o = pf.overlap || {};
  const sh = pf.shared || { n: 0 };
  const row = (ok, title, text) => `<li class="pc__row" data-ok="${ok ? "yes" : "no"}">
    <span class="pc__mark" aria-hidden="true"></span><div><p class="pc__t">${title}</p><p class="cx-note">${text}</p></div></li>`;
  return `<div class="pc">
    <h3 class="cx-h3">Can these two be compared?</h3>
    <ol class="pc__list">
      ${row(true, "The same subject, scored by the same controller",
        `Both were scored by <code>${esc(pf.a.controller || "an unrecorded model")}</code>.`)}
      ${row(o.known ? o.disjoint : false, o.known && o.disjoint ? "The periods do not overlap" : "The periods overlap",
        !o.known ? "The dates of one of them were not recorded."
          : o.disjoint ? `${esc(labels[0])} and ${esc(labels[1])} share no days.`
          : `${o.nested ? "One period sits inside the other" : "The periods share days"}: about ${count(Math.round(o.overlap_days))} days
            in common. A difference here is partly the same stretch of time counted twice.`)}
      ${row(sh.n === 0, sh.n ? `${count(sh.n)} ${sh.n === 1 ? "video is" : "videos are"} in both` : "No video is in both",
        sh.n ? `Read twice, days apart. They are the measure of how much this system moves when nothing about the
          video has changed, and they are drawn on the next spread.` : "Every video in one period is different from every video in the other.")}
    </ol>
  </div>`;
}

export function periodSlopes(pf, labels) {
  const ms = MEASURE_ORDER.map((k) => pf.measures.find((m) => m.key === k)).filter(Boolean);
  return `<section class="slx" aria-labelledby="slx-h">
    <h2 id="slx-h" class="cx-h">What moved between them</h2>
    <p class="cx-lede">Every video's value in each period, the medians joined, a hairline for a video read in both.
      ${esc(pf.rule)}</p>
    <div class="slx__grid">${ms.map((m) => slope(m, labels)).join("")}</div>
  </section>`;
}

export function twicePage(pf, labels) {
  const sh = pf.shared;
  if (!sh || !sh.n) {
    return `<section class="twx" aria-labelledby="twx-h"><h2 id="twx-h" class="cx-h">The same video, read twice</h2>
      <p class="cx-text">No video is in both periods, so nothing here was read twice.</p></section>`;
  }
  const md = sh.max_delta;
  return `<section class="twx" aria-labelledby="twx-h">
    <h2 id="twx-h" class="cx-h">The same video, read twice</h2>
    <p class="cx-lede">${count(sh.n)} ${sh.n === 1 ? "video is" : "videos are"} in both periods, analysed again days
      apart. The leans kept their calls in ${count(sh.calls_unchanged)} of ${count(sh.n)}; the largest moves were
      <b>${md.reviewer == null ? "none" : signed(md.reviewer).replace("+", "")}</b> in a reviewer's lean,
      <b>${md.audience == null ? "none" : signed(md.audience).replace("+", "")}</b> in an audience's,
      and <b>${score(md.brand_health)}</b> points of Brand health.</p>
    <ol class="twx__list">${sh.videos.map((v) => `
      <li class="twx__item">
        <p class="twx__t">${esc(cut(v.title, 10))}${v.label_changed ? ` <span class="twx__flip">comment label changed</span>` : ""}</p>
        <dl class="twx__grid">
          <div><dt><i class="k k--r" aria-hidden="true"></i>Reviewer</dt><dd>${twiceBell(v.a.reviewer, v.b.reviewer, "lean")}</dd></div>
          <div><dt><i class="k k--a" aria-hidden="true"></i>Audience</dt><dd>${twiceBell(v.a.audience, v.b.audience, "lean")}</dd></div>
          <div><dt>Authenticity</dt><dd>${twiceBell(v.a.authenticity, v.b.authenticity, "score")}</dd></div>
          <div><dt>Brand health</dt><dd>${twiceBell(v.a.brand_health, v.b.brand_health, "score")}</dd></div>
        </dl>
        ${v.label_changed ? `<p class="twx__why">Comments read ${esc(String(v.a.label).toLowerCase())}, then
          ${esc(String(v.b.label).toLowerCase())}${v.a.near_tie || v.b.near_tie ? ", on a near-tie" : ""}.</p>` : ""}
      </li>`).join("")}</ol>
    <p class="cx-note">Open mark: the reading in ${esc(labels[0])}; filled: in ${esc(labels[1])}. A change between
      periods smaller than these is not a change in the videos.</p>
  </section>`;
}

export function themeChanges(pf, labels, commands) {
  const th = pf.themes;
  if (!th) {
    return `<section class="thx" aria-labelledby="thx-h"><h2 id="thx-h" class="cx-h">What changed by theme</h2>
      <div class="ny" role="note"><p class="ny__h">Themes in both periods</p>
        <p class="ny__p">Needs the combined written report of both periods, which the local model writes after
          each video's own. Every figure on the facing page is already here.</p>
        ${commands.map((c) => `<p class="ny__cmd"><code>${esc(c)}</code></p>`).join("")}</div></section>`;
  }
  const bar = (t) => `<span class="thx__v t-read">${count(t.praise_in)} praised, ${count(t.criticism_in)} criticised of ${count(t.talked)}</span>`;
  return `<section class="thx" aria-labelledby="thx-h">
    <h2 id="thx-h" class="cx-h">What changed by theme</h2>
    <p class="cx-lede">Themes matched by name, or by the aspects they cover.</p>
    <table class="thx__t"><caption class="sr-only">Each theme in both periods</caption>
      <thead><tr><th scope="col">Theme</th><th scope="col">${esc(labels[0])}</th><th scope="col">${esc(labels[1])}</th></tr></thead>
      <tbody>${th.matched.map((m) => `<tr><th scope="row">${esc(m.a.name)}</th><td>${bar(m.a)}</td><td>${bar(m.b)}</td></tr>`).join("")}
      ${th.only_a.map((t) => `<tr><th scope="row">${esc(t.name)}</th><td>${bar(t)}</td><td class="thx__none">not discussed</td></tr>`).join("")}
      ${th.only_b.map((t) => `<tr><th scope="row">${esc(t.name)}</th><td class="thx__none">not discussed</td><td>${bar(t)}</td></tr>`).join("")}
      </tbody></table>
  </section>`;
}

/** The search that gives this set its clean other half, pre-filled. A window
    may end at most one window back (sweep.py offset_problem, 24 Sep 2026), so
    a set ending today is paired with the period just before it, and a set that
    already ends earlier with the one ending today. Nothing else is offered:
    the Analyse page would refuse it. */
export function earlierLinks(record, windowDays) {
  if (!windowDays) return "";
  const base = new URLSearchParams({ subject: record.subject || "", kind: record.subject_kind || "",
    window: record.window || "month" });
  const off = Number(record.offset_days || 0);
  const [target, words] = off === 0 ? [windowDays, "the period just before this one"]
    : [0, "the same length, ending today"];
  const shared = Math.max(0, windowDays - Math.abs(off - target));
  const q = new URLSearchParams(base);
  q.set("offset", String(target));
  return `<div class="pe">
    <p class="ag__k">A cleaner comparison</p>
    <p class="cx-note">The same search over an equal window ${off === 0 ? "ending one window earlier" : "ending today"}
      ${shared ? `shares ${shared} of its ${windowDays} days with this one` : "shares no days with this one"}. It is a
      new search (100 quota units), sent only when you start it.</p>
    <p class="pe__links"><a class="cx-btn" href="/run?${esc(q.toString())}">Search ${words}</a></p>
  </div>`;
}
