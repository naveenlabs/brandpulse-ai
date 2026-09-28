/* ===========================================================================
   sweep.js — several videos about one subject, bound as one volume.

   THE RANGE IS THE FINDING, NOT THE AVERAGE.

   A mean of five videos is the least interesting number here and the easiest
   one to over-read, so it is not the headline. The headline is the SPREAD:
   every video's score drawn on one axis with the mean marked among them, so a
   reader sees how far apart they actually were before they see what they
   average to. `summary.spread_verdict` is the system's own words for that and
   it opens the findings page.

   THE BOOK IS COMPOSED FOR WHAT A SWEEP HOLDS, NOT FOR WHAT A VIDEO HOLDS.
   These are its chapters before the combined written report exists; the book
   with it is laid out in main() (THE COMBINED WRITTEN REPORT'S BOOK).

     1  Overview        a title page in the cover's own cloth and serif, with a
                        contents list of the videos and the pages they are on,
                        facing the combined findings: the verdict, the range,
                        what the mean is not
     2  The videos      each video with its own frame, its trace on one shared
                        clock, its two scores, and the way into its own book;
                        carried over as many spreads as the videos need
     3  Channels        what each channel managed to read across the set,
                        facing what limits the reading
     4  Audience        every audience pooled, facing each one separately
     5  Another period  only when one exists: two sweeps of the same subject
                        held against each other, or refused with reasons
     6  Provenance      how the videos were chosen and which were refused, and
                        which channels the controller named in conflict

   Nothing here generalises past the videos analysed. Every page that reports a
   combined figure says how many videos it is combined from, and the pages
   carry the pipeline's own statement of what the combined score is not.
   ======================================================================== */

import "../styles/tokens.css";
import "../styles/chassis.css";
import "../styles/transport.css";
/* The book is made of paper, and the paper's tokens live here. Without them
   --leaf, --leaf-rule and --lf-shade are all undefined and the spread paints
   as nothing: a book with no pages. */
import "../styles/leaf.css";
import "../styles/codex.css";
import "../styles/sweep.css";
import "../styles/analysis.css";
import "../styles/combined.css";

import { mountAll } from "../lib/chrome.js";
import { mountAnnouncer, announce } from "../lib/announce.js";
import { getSweep, listSweeps, getSweepMember, getSweepAnalysis, compareSweeps } from "../lib/api.js";
import { animateIn } from "../lib/charts.js";
import * as C from "../lib/combined.js";
import { CHANNELS, CHANNEL_META, segmentValences, coverage, toValence,
         disagreementPairs, aggregateIsNearTie } from "../lib/contract.js";
import { count, esc, mmss, pct, score, confidence, savedOn } from "../lib/format.js";
import { createClock, mountTransport } from "../lib/transport.js";
import { stashFlip, Flip, reduced } from "../lib/motion.js";
import { takeVolume, stashReturn } from "../lib/leaf.js";
import { chapter, codexShell, openBook, spread, titleLength, wireClose, wireCodex } from "../lib/codex.js";
import { manifest, plateFor, videoIdOf } from "../lib/frames.js";

const root = document.querySelector("[data-sweep]");

const PERIODS = {
  week: "the last week", month: "the last month",
  half: "the last six months", year: "the last year",
};

const KINDS = { brand: "A brand", product: "A product" };

function idFromPath() {
  const match = decodeURIComponent(window.location.pathname)
    .match(/^\/brand\/([^/]+)\/?$/);
  return match ? match[1] : null;
}

function fail(tag, heading, body, extra = "") {
  root.innerHTML = `
    <section class="state${tag === "Unreachable" ? " state--error" : ""}">
      <p class="t-label state__tag">${esc(tag)}</p>
      <h1 class="t-l">${esc(heading)}</h1>
      <p class="t-body">${body}</p>${extra}
    </section>`;
  delete document.documentElement.dataset.carrying;
  clearTimeout(window.__bpFallback);
}

/* --- 1. the title page ---------------------------------------------------- */

function titlePage(record, ctx = null) {
  const summary = record.summary || {};
  const members = record.members || [];
  const failed = record.failed || [];
  const finished = savedOn(Number(record.finished_at));
  const kind = KINDS[record.subject_kind] || "A subject";

  return `
  <section class="ti ti--sweep" aria-labelledby="ti-h">
    <div class="ti__board cx-bleed">
      <p class="ti__bk">${kind}, ${count(summary.video_count)} video${summary.video_count === 1 ? "" : "s"} combined</p>
      <h1 id="ti-h" class="ti__title cx-display" data-len="${titleLength(record.subject)}">${esc(record.subject || "Untitled sweep")}</h1>
      <span class="ti__brule" aria-hidden="true"></span>
      ${record.window ? `<p class="ti__bsub">from ${esc(periodLabel(record))}</p>` : ""}
    </div>
    <div class="ti__block">
      <dl class="ti__facts">
        <div><dt>Videos analysed</dt><dd class="t-read">${count(summary.video_count)}</dd></div>
        <div><dt>Segments</dt><dd class="t-read">${count(summary.segments_total)}</dd></div>
        <div><dt>Comments read</dt><dd class="t-read">${count(summary.comments_total)}</dd></div>
      </dl>
      <p class="cx-note">${record.controller ? `Scored by <code>${esc(record.controller)}</code>` : "Controller not recorded"}${finished ? `, finished ${esc(finished)}` : ""}.</p>
      ${ctx ? C.setInShort(ctx) : ""}
      ${record.status === "partial" && failed.length ? `
        <p class="sp__partial cx-note">
          This sweep finished partly: ${count(failed.length)} of
          ${count((summary.video_count || 0) + failed.length)} videos could not be
          analysed, and every figure here covers the ${count(summary.video_count)} that were.
          Why, on <button class="cx-xref" type="button" data-cx-xref="prov-failed">page
          <span data-cx-xref-page></span></button>.
        </p>` : ""}
    </div>
    <nav class="toc" aria-label="The videos in this volume">
      <p class="cx-h3">Contents</p>
      <ol class="toc__list">
        ${members.map((m, i) => `
          <li${m.analysed === false ? ' class="is-failed"' : ""}>
            <span class="toc__n t-read">${String(i + 1).padStart(2, "0")}</span>
            <button class="toc__t" type="button" data-cx-xref="mem-${esc(m.video_id)}">${esc(m.title || m.video_id)}</button>
            <span class="toc__pg t-read" data-cx-xref="mem-${esc(m.video_id)}"><span data-cx-xref-page></span></span>
          </li>`).join("")}
      </ol>
    </nav>
  </section>`;
}

/* --- 1. the combined findings --------------------------------------------- */

/* One mark per video on a real axis, with the observed range drawn as a band
   and the mean as a rule among the points rather than above them. A mark is
   numbered with its video's place in the contents only when the summary's
   values can be shown to be those videos' own scores in the same order;
   otherwise it is drawn unnumbered rather than labelled by a guess. Two
   videos with nearly the same score are stacked, never drawn as one mark. */
function spreadPlot(values, stat, label, numbers) {
  if (!values || values.length < 2) return "";
  const lo = Math.min(...values, stat.min ?? Infinity);
  const hi = Math.max(...values, stat.max ?? -Infinity);
  const pad = Math.max(4, (hi - lo) * 0.12);
  const from = Math.max(0, lo - pad);
  const to = Math.min(100, hi + pad);
  const span = to - from || 1;
  const at = (v) => ((v - from) / span) * 100;

  const order = values.map((v, i) => ({ v, i })).sort((a, b) => a.v - b.v);
  const level = new Array(values.length).fill(0);
  order.forEach((p, k) => {
    if (k && at(p.v) - at(order[k - 1].v) < 3.2) level[p.i] = level[order[k - 1].i] + 1;
  });

  return `
  <figure class="spr">
    <figcaption class="spr__cap"><b>${esc(label)}</b>, one mark per video</figcaption>
    <div class="spr__axis">
      <span class="spr__band"
            style="left:${at(stat.min).toFixed(3)}%;width:${(at(stat.max) - at(stat.min)).toFixed(3)}%"></span>
      <span class="spr__mean" style="left:${at(stat.mean).toFixed(3)}%"></span>
      ${values.map((v, i) => `
        <span class="spr__pt" style="left:${at(v).toFixed(3)}%;--lv:${level[i]}">${
          numbers ? `<b aria-hidden="true">${numbers[i]}</b>` : ""}<span class="sr-only">${
          numbers ? `Video ${numbers[i]}, ` : ""}${score(v)}</span></span>`).join("")}
    </div>
    <div class="spr__ends"><span>${score(from)}</span><span>${score(to)}</span></div>
    <dl class="spr__key">
      <div><dt>Lowest</dt><dd class="t-read">${score(stat.min)}</dd></div>
      <div class="is-mean"><dt>Mean</dt><dd class="t-read">${score(stat.mean)}</dd></div>
      <div><dt>Highest</dt><dd class="t-read">${score(stat.max)}</dd></div>
      <div><dt>Range</dt><dd class="t-read">${score(stat.spread)}</dd></div>
      <div><dt>Standard deviation</dt><dd class="t-read">${score(stat.stdev)}</dd></div>
    </dl>
  </figure>`;
}

function findingsPage(record, ctx = null) {
  const summary = record.summary || {};
  const auth = summary.authenticity || {};
  const health = summary.brand_health || {};
  const analysed = (record.members || [])
    .map((m, i) => ({ m, n: String(i + 1).padStart(2, "0") }))
    .filter(({ m }) => m.analysed !== false);
  const same = (values, key) => Array.isArray(values) && values.length === analysed.length
    && values.every((v, i) => analysed[i].m[key] === v);
  const numbers = (values, key) => (same(values, key) ? analysed.map((a) => a.n) : null);

  return `
  <section class="sf" data-act="spread" aria-labelledby="sf-h">
    <h2 id="sf-h" class="sr-only">What the videos found together</h2>
    ${summary.spread_verdict ? `<p class="sf__verdict">${esc(summary.spread_verdict)}.</p>` : ""}
    <p class="cx-lede">
      The average is the least informative number here. The range says how far
      apart the videos actually were.
    </p>
    <div class="sf__plots">
      ${spreadPlot(auth.values, auth, "Authenticity", numbers(auth.values, "authenticity_score"))}
      ${spreadPlot(health.values, health, "Brand health", numbers(health.values, "brand_health_score"))}
    </div>
    <p class="sf__not cx-note">${[summary.note, summary.means_not].filter(Boolean).map(esc).join(" ")}</p>

    ${record.bias_caveat
      ? `<p class="sf__fn cav"><span aria-hidden="true">&dagger;</span> ${esc(record.bias_caveat)}</p>`
      : `<p class="sf__fn cav">This sweep carries no caveat text of its own, which
           is unusual and is stated rather than passed over.</p>`}
  </section>`;
}

/* --- 2. the videos -------------------------------------------------------- */

function membersShell(record) {
  const members = record.members || [];
  const analysed = members.filter((m) => m.analysed !== false);

  return `
  <div class="mem__head" data-act="members">
    <h2 class="cx-h">The ${count(analysed.length)} videos, on one clock</h2>
    <p class="cx-lede">
      Every trace is drawn against the same clock, so a shorter video stops where
      it actually stops. The frame is each video&rsquo;s most contested moment.
      A title opens that video&rsquo;s own book.
    </p>
  </div>
  <ul class="mem" data-members data-cx-flow>
    ${members.map((m, i) => {
      const ok = m.analysed !== false;
      return `
      <li class="mem__one${ok ? "" : " is-failed"}" id="mem-${esc(m.video_id)}" data-video="${esc(m.video_id)}">
        <div class="mem__plate" data-plate="${esc(m.video_id)}">
          <span class="mem__n t-read">${String(i + 1).padStart(2, "0")}</span>
        </div>
        <div class="mem__body">
          <h3 class="mem__t">${ok
            ? `<a href="/brand/${encodeURIComponent(record.sweep_id)}/${encodeURIComponent(m.video_id)}"
                  data-open-member>${esc(m.title || m.video_id)}</a>`
            : esc(m.title || m.video_id)}</h3>
          <p class="mem__meta">
            ${[m.channel ? esc(m.channel) : "", m.duration_s ? mmss(m.duration_s) : "",
               m.comment_count ? `${count(m.comment_count)} comments` : ""]
              .filter(Boolean).join('<span class="mem__sep" aria-hidden="true"></span>')}
          </p>
          ${ok ? `
            <div class="mem__trace" data-trace="${esc(m.video_id)}">
              <p class="mem__loading">Reading this video&rsquo;s run</p>
            </div>
            <dl class="mem__nums">
              <div><dt>Authenticity</dt><dd class="t-read">${score(m.authenticity_score)}</dd></div>
              <div><dt>Brand health</dt><dd class="t-read">${score(m.brand_health_score)}</dd></div>
            </dl>`
          : `<p class="mem__failed">Not analysed. ${esc(
              (record.failed || []).find((f) => f.video_id === m.video_id)?.reason
              || "No reason was recorded.")}</p>`}
        </div>
      </li>`;
    }).join("")}
  </ul>`;
}

/* --- 3. channels ---------------------------------------------------------- */

function channelsPanel(record, collected) {
  if (!collected.length) {
    return `<p class="cx-note">No video in this sweep could be read, so there is
      nothing to count per channel.</p>`;
  }

  /* Counted across every segment of every member that could be read, using
     the pipeline's own channel labels rather than the controller's
     attribution. */
  const tallies = Object.fromEntries(CHANNELS.map((c) => [c, { read: 0, total: 0 }]));
  let disagreeing = 0;
  let comparable = 0;

  for (const { report, segments } of collected) {
    const cov = coverage(segments, report.comment_sentiment);
    for (const channel of CHANNELS) {
      tallies[channel].read += cov[channel].read;
      tallies[channel].total += cov[channel].total;
    }
    for (const segment of segments) {
      const v = Object.values(segmentValences(segment, report.comment_sentiment));
      if (v.length >= 2) {
        comparable += 1;
        if (new Set(v).size > 1) disagreeing += 1;
      }
    }
  }

  return `
    <ul class="cvx">
      ${CHANNELS.map((channel) => {
        const t = tallies[channel];
        const share = t.total ? (t.read / t.total) * 100 : 0;
        const meta = CHANNEL_META[channel];
        return `
        <li class="cvx__row" data-channel="${channel}" style="--ch:var(--ch-${channel})">
          <p class="cvx__name"><i class="mo__mark" data-mark="${channel}" aria-hidden="true"></i>${esc(meta.label)}
            <span>${esc(meta.reads)}</span></p>
          <span class="cvx__track" aria-hidden="true"><i style="--to:${share.toFixed(2)}%"></i></span>
          <p class="cvx__v"><span class="t-read">${pct(share, 1)}</span>
            ${count(t.read)} of ${count(t.total)} segments</p>
        </li>`;
      }).join("")}
    </ul>
    <p class="sp__count cx-text">
      Across ${count(comparable)} segments where at least two channels returned a
      reading, ${count(disagreeing)}
      (${pct(comparable ? (disagreeing / comparable) * 100 : 0, 1)}) had the
      channels disagreeing with one another. That is the raw rate of
      disagreement, before the controller scored any of it.
    </p>`;
}

/* --- which channels the controller named together ------------------------

   The project's own thesis counted: which channels the controller said were
   in conflict, read off the orchestrator's audit trail. A pair that never
   disagreed is kept at zero rather than dropped, because an absence is a
   finding and removing the row would make the grid look denser than the
   data. */
function pairsPanel(collected) {
  const all = collected.flatMap(({ segments }) => segments);
  if (!all.length) return "";
  const grid = disagreementPairs(all);

  if (!grid.attributed) {
    return `
    <div class="pairs pairs--none">
      <h3 class="cx-h3">Which channels the controller named</h3>
      <p class="cx-note">
        On none of the ${count(grid.total)} segments in this sweep did the
        controller name which channels it thought were in conflict. That is a
        measured property of the model rather than a gap in this page. The
        down-weighting that depends on knowing which channel dissented runs off
        the pipeline&rsquo;s own channel labels instead, which need no model
        compliance.
      </p>
    </div>`;
  }

  const most = Math.max(...grid.pairs.map((p) => p.count), 1);
  return `
  <div class="pairs">
    <h3 class="cx-h3">Which channels the controller named together</h3>
    <p class="cx-note">
      Counted on the ${count(grid.attributed)} of ${count(grid.total)} segments
      where the controller named any channel at all.
      ${grid.unknown ? `${count(grid.unknown)} names it used were not recognised
        and are counted as unattributable rather than dropped into a bucket.` : ""}
    </p>
    <ul class="pairs__list">
      ${grid.pairs.map((pair) => `
        <li>
          <span class="pairs__who">
            <i style="--ch:var(--ch-${pair.a})"></i><i style="--ch:var(--ch-${pair.b})"></i>
            ${esc(CHANNEL_META[pair.a].short)} and ${esc(CHANNEL_META[pair.b].short)}
          </span>
          <span class="pairs__track" aria-hidden="true">
            <i style="--to:${((pair.count / most) * 100).toFixed(2)}%"></i></span>
          <span class="t-read">${count(pair.count)}</span>
          <span class="pairs__share">${pct(pair.share * 100, 1)}</span>
        </li>`).join("")}
    </ul>
  </div>`;
}

/* --- 3. the caveats -------------------------------------------------------

   A combined score is an average of several facial-derived ones, so
   the bias-caveat rule (README, "Engineering rules") applies here exactly as it does to a single report. */
function caveats(record, extra = "") {
  const list = [record.bias_caveat, record.vocal_caveat].filter(Boolean);
  if (!list.length) {
    return `
    <section class="lm" data-act="caveats">
      <h2 class="cx-h">What limits the reading</h2>
      <p class="cav">This sweep carries no caveat text of its own, which
        is unusual and is stated rather than passed over.</p>
    </section>`;
  }
  return `
  <section class="lm" data-act="caveats" aria-labelledby="cv-h">
    <h2 id="cv-h" class="cx-h">What limits the reading</h2>
    <ol class="lm__notes">
      ${list.map((text, i) => `
        <li class="lm__note">
          <p class="lm__k"><span class="lm__n">${i + 1}</span>${text === record.bias_caveat
            ? "Facial emotion" : "Vocal prosody"}</p>
          <p class="cav">${esc(text)}</p>
        </li>`).join("")}
    </ol>
    ${extra}
  </section>`;
}

/* --- 4. the audience, pooled ---------------------------------------------- */

const SENTIMENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"];

function band(dist, total, label) {
  return `
  <div class="au__band" role="img" aria-label="${label}: ${SENTIMENTS.map((k) =>
    `${count(dist[k] || 0)} ${k.toLowerCase()}`).join(", ")}, of ${count(total)} comments">
    ${SENTIMENTS.map((k) => `<i data-k="${k}" style="--n:${dist[k] || 0}"></i>`).join("")}
  </div>`;
}

function audiencePanel(record, extra = "") {
  const summary = record.summary || {};
  const dist = summary.comment_distribution || {};
  const total = Object.values(dist).reduce((a, b) => a + b, 0);
  const tie = aggregateIsNearTie(dist);

  return `
  <section class="au" data-act="audience" aria-labelledby="au-h">
    <h2 id="au-h" class="cx-h">Every audience, pooled</h2>
    <p class="cx-lede">
      ${count(total)} comments across ${count(summary.video_count)} videos,
      classified one at a time and counted together. No author identifier was
      stored at any point. Comments are one reading per video, not per moment.
    </p>
    ${total ? `
    <figure class="au__fig">
      ${band(dist, total, "Every audience pooled")}
      <dl class="au__nums">
        ${SENTIMENTS.map((k) => `
          <div data-k="${k}"><dt><i class="cm__glyph" aria-hidden="true"></i>${k.toLowerCase()}</dt>
            <dd class="t-read">${count(dist[k] || 0)}</dd>
            <dd class="au__pct">${pct(((dist[k] || 0) / total) * 100, 1)}</dd></div>`).join("")}
      </dl>
    </figure>` : `<p class="cx-note">No comment distribution was recorded for this sweep.</p>`}
    ${tie && tie.nearTie ? `
      <p class="pool__tie cx-note">
        The top two are within ${pct(tie.margin * 100, 1)} of each other across the
        whole pool. Reporting the leading label as the audience verdict would
        overstate it, so the counts are given rather than one word.
      </p>` : ""}
    ${extra}
  </section>`;
}

/* Each audience on its own, filled once the members have been read: the
   pooled figure can hide a video whose room said the opposite of the rest. */
function eachAudience(record, collected) {
  if (!collected.length) {
    return `<p class="cx-note">No video in this sweep could be read.</p>`;
  }
  const byId = new Map(collected.map((c) => [c.videoId, c]));
  const members = (record.members || []).filter((m) => m.analysed !== false);
  return `
    <ul class="each">
      ${members.map((m) => {
        const i = (record.members || []).indexOf(m);
        const c = byId.get(m.video_id);
        const cs = c ? c.report.comment_sentiment || {} : {};
        const dist = cs.distribution || {};
        const total = Object.values(dist).reduce((a, b) => a + b, 0);
        return `
        <li class="each__one">
          <p class="each__t"><span class="t-read">${String(i + 1).padStart(2, "0")}</span>${esc(m.title || m.video_id)}</p>
          ${total ? `${band(dist, total, `Video ${i + 1}`)}
            <p class="each__v">${SENTIMENTS.map((k) => `${count(dist[k] || 0)} ${k.toLowerCase()}`).join(", ")}${
              cs.label ? `; classified <b>${esc(String(cs.label).toLowerCase())}</b>` : ""}</p>`
          : `<p class="each__v is-absent">No comment distribution was recorded.</p>`}
        </li>`;
      }).join("")}
    </ul>`;
}

/* --- 5. holding two periods against each other ---------------------------

   Two states of one subject on one shared scale, with a divider you drag.
   Whether the two CAN be compared is checked first and stated plainly:
   swapping only the controller model moved mean Authenticity across this
   project's corpus by 49.08 points, so two sweeps scored by different
   controllers are not measuring the same thing. */

function separable(left, right) {
  const reasons = [];
  if ((left.subject || "").trim().toLowerCase() !== (right.subject || "").trim().toLowerCase()) {
    reasons.push("They are about different subjects, so any difference between "
      + "them is a difference between two things rather than a change in one.");
  }
  if (left.controller && right.controller && left.controller !== right.controller) {
    reasons.push(`They were scored by different controller models `
      + `(${left.controller} and ${right.controller}). Swapping only the `
      + `controller moved mean Authenticity across this project's corpus by `
      + `49.08 points, so these two numbers are not measuring the same thing.`);
  }
  const lv = ((left.summary || {}).authenticity || {}).values || [];
  const rv = ((right.summary || {}).authenticity || {}).values || [];
  if (lv.length < 2 || rv.length < 2) {
    reasons.push("One of them has fewer than two analysed videos, so it has no "
      + "range to compare against.");
  }
  if (left.window === right.window && left.offset_days === right.offset_days) {
    reasons.push("They cover the same period, so there is no before and after "
      + "between them.");
  }
  return reasons;
}

function periodLabel(record) {
  const base = PERIODS[record.window] || record.window || "an unrecorded period";
  return record.offset_days && Number(record.offset_days)
    ? `${base}, ending ${count(Number(record.offset_days))} days ago`
    : base;
}

function comparePanel(record, siblings, measured = false) {
  return `
  <section class="cpp" data-act="compare" aria-labelledby="cp-h">
    <h2 id="cp-h" class="cx-h">Hold this against another period</h2>
    <p class="cx-lede">
      ${count(siblings.length)} other sweep${siblings.length === 1 ? "" : "s"} on
      this machine ${siblings.length === 1 ? "covers" : "cover"} the same
      subject. ${measured
        ? "Choosing one holds the two against each other measure by measure, and video by video where the same video is in both, or says why they cannot be compared."
        : "Choosing one puts both on a single scale with a divider you can drag between them, or says why the two cannot be compared."}
    </p>
    <p class="cx-note">This volume covers ${esc(periodLabel(record))}.</p>
    <div class="cp__pick">
      ${siblings.map((s) => `
        <button class="chip" type="button" data-sib="${esc(s.sweep_id)}"
                aria-pressed="false">${esc(periodLabel(s))}
          <span class="chip__n t-read">${score((s.summary?.authenticity || {}).mean ?? s.authenticity)}</span>
        </button>`).join("")}
    </div>
  </section>`;
}

function comparisonBody(left, right) {
  const reasons = separable(left, right);
  if (reasons.length) {
    /* The refusal is a designed page, not an error. It says what would have
       to be true for the comparison to mean anything. */
    return `
    <div class="cp__refuse">
      <h3 class="cx-h">These two cannot honestly be compared</h3>
      <ol class="cp__why">
        ${reasons.map((r) => `<li class="cx-text">${esc(r)}</li>`).join("")}
      </ol>
      <p class="cx-note">
        Both are still readable on their own, and each one&rsquo;s range is on
        its own page. What is refused here is putting them on one axis and
        calling the difference a change.
      </p>
    </div>`;
  }

  const la = (left.summary || {}).authenticity || {};
  const ra = (right.summary || {}).authenticity || {};
  const lh = (left.summary || {}).brand_health || {};
  const rh = (right.summary || {}).brand_health || {};

  const rows = [
    ["Authenticity", la.mean, ra.mean],
    ["Lowest video", la.min, ra.min],
    ["Highest video", la.max, ra.max],
    ["Range", la.spread, ra.spread],
    ["Brand health", lh.mean, rh.mean],
  ];

  return `
  <div class="cp" data-cp style="--split:50%">
    <div class="cp__heads">
      <p class="cx-h3">${esc(periodLabel(left))}</p>
      <p class="cx-h3 cp__right">${esc(periodLabel(right))}</p>
    </div>

    <div class="cp__stage">
      <div class="cp__side cp__side--a">
        ${rows.map(([label, v]) => `
          <div class="cp__row">
            <span class="cp__k">${esc(label)}</span>
            <b class="t-read">${score(v)}</b>
          </div>`).join("")}
      </div>
      <div class="cp__side cp__side--b" aria-hidden="true">
        ${rows.map(([label, , v]) => `
          <div class="cp__row">
            <span class="cp__k">${esc(label)}</span>
            <b class="t-read">${score(v)}</b>
          </div>`).join("")}
      </div>

      <input class="cp__handle" type="range" min="0" max="100" value="50" step="0.5"
             aria-label="Drag between the two periods"
             data-split>
      <span class="cp__line" aria-hidden="true"></span>
    </div>

    <table class="cp__table">
      <caption class="sr-only">Both periods, and the difference between them</caption>
      <thead>
        <tr><th scope="col">Measure</th>
            <th scope="col">${esc(periodLabel(left))}</th>
            <th scope="col">${esc(periodLabel(right))}</th>
            <th scope="col">Change</th></tr>
      </thead>
      <tbody>
        ${rows.map(([label, a, b]) => {
          const delta = (typeof a === "number" && typeof b === "number") ? b - a : null;
          return `
          <tr>
            <th scope="row">${esc(label)}</th>
            <td class="t-read">${score(a)}</td>
            <td class="t-read">${score(b)}</td>
            <td class="t-read${delta != null && Math.abs(delta) >= 5 ? " is-tear" : ""}">${
              delta == null ? "&mdash;"
              : `${delta > 0 ? "+" : ""}${delta.toFixed(2)}`}</td>
          </tr>`;
        }).join("")}
      </tbody>
    </table>

    <p class="cx-note">
      Both sweeps were scored by <code>${esc(left.controller || "an unrecorded model")}</code>.
      A change here is a change in what these videos about this subject did, not a
      measurement of the subject itself, and a handful of videos is too few to generalise from.
    </p>
  </div>`;
}

/* --- 6. provenance -------------------------------------------------------- */

function provenancePanel(record, pairs = true) {
  const sel = record.selection || {};
  const rejected = sel.rejected || [];
  const failed = record.failed || [];

  return `
  <section class="prv" data-act="provenance" aria-labelledby="pr-h">
    <h2 id="pr-h" class="cx-h">Where these videos came from</h2>
    <dl class="prov">
      <div><dt>Searched as</dt><dd><code>${esc(sel.query_used || "not recorded")}</code></dd></div>
      <div><dt>Published after</dt><dd>${esc(sel.published_after || "not recorded")}</dd></div>
      ${sel.published_before
        ? `<div><dt>Published before</dt><dd>${esc(sel.published_before)}</dd></div>` : ""}
      <div><dt>Considered</dt><dd>${count(sel.considered)} videos</dd></div>
      <div><dt>Refused</dt><dd>${count(rejected.length)} videos</dd></div>
      <div><dt>Controller</dt><dd><code>${esc(record.controller || "not recorded")}</code></dd></div>
    </dl>

    ${failed.length ? `
      <div class="prov__failed" id="prov-failed" tabindex="-1">
        <h3 class="cx-h3">Selected, then could not be analysed</h3>
        <ul class="prov__list">
          ${failed.map((f) => `
            <li><b>${esc(f.title || f.video_id || "A video")}</b>
              <span>${esc(f.reason || "no reason recorded")}</span></li>`).join("")}
        </ul>
      </div>` : ""}

    ${pairs ? "<div data-pairs></div>" : ""}
  </section>`;
}

function refusedHead(record) {
  const rejected = ((record.selection || {}).rejected || []);
  return `
  <div class="ref__head">
    <h3 class="cx-h3">${rejected.length ? `The ${count(rejected.length)} that were refused, and why`
      : "Nothing was refused"}</h3>
    <p class="ref__range" data-ref-range></p>
  </div>
  <ul class="prov__list ref__list" data-cx-flow>
    ${rejected.map((r) => `
      <li><b>${esc(r.title || r.video_id || "A video")}</b>
        <span>${esc(r.verdict || r.reason || "no reason recorded")}</span></li>`).join("")}
  </ul>
  ${rejected.length ? "" : `<p class="cx-note">Every video the search considered and
    selected was taken; none was turned away by the selection rules.</p>`}`;
}

/* --- painting the members -------------------------------------------------- */

async function readMembers(record) {
  const members = (record.members || []).filter((m) => m.analysed !== false);
  /* Fetched one at a time rather than embedded in sweep.json: five full
     reports with every segment and every comment is several megabytes, and
     this page needs each one's conflict profile, frame and audience. */
  const loaded = await Promise.all(members.map(async (m) => {
    try {
      const report = await getSweepMember(record.sweep_id, m.video_id);
      const segments = (report.all_segments || []).filter(
        (s) => typeof s.start_s === "number" && typeof s.end_s === "number");
      return segments.length ? { m, videoId: m.video_id, report, segments } : null;
    } catch { return null; }
  }));
  return loaded.filter(Boolean);
}

function paintMembers(collected, man) {
  if (!collected.length) {
    for (const host of root.querySelectorAll("[data-trace]")) {
      host.innerHTML = `<p class="mem__loading">This video&rsquo;s run could not be read.</p>`;
    }
    return;
  }
  const longest = Math.max(...collected.map(({ segments }) =>
    Math.max(...segments.map((s) => s.end_s))));

  for (const { m, report, segments } of collected) {
    const host = root.querySelector(`[data-trace="${CSS.escape(m.video_id)}"]`);
    if (host) {
      const duration = Math.max(...segments.map((s) => s.end_s));
      host.innerHTML = `<div class="mem__scaled"
        style="width:${((duration / longest) * 100).toFixed(2)}%"></div>`;
      const clock = createClock(duration, segments);
      mountTransport(host.querySelector(".mem__scaled"), {
        report, segments, clock, compact: true, label: m.title || m.video_id,
      });
    }
    /* The most contested second, by the same reduction the library uses for a
       cover, so each video is pictured at the moment it disagreed with itself
       most. A frame that was never derived is left as the numbered plate. */
    const worst = segments.reduce((a, b) =>
      (b.conflict_score ?? -1) > (a.conflict_score ?? -1) ? b : a, segments[0]);
    const url = plateFor(man, videoIdOf(report), worst);
    const plate = root.querySelector(`[data-plate="${CSS.escape(m.video_id)}"]`);
    if (plate && url) {
      const img = new Image();
      img.alt = "";
      img.decoding = "async";
      img.onerror = () => img.remove();
      img.src = url;
      plate.prepend(img);
      plate.classList.add("has-img");
    }
  }
  for (const host of root.querySelectorAll("[data-trace]")) {
    if (host.querySelector(".mem__loading") && !collected.some((c) => c.m.video_id === host.dataset.trace)) {
      host.innerHTML = `<p class="mem__loading">This video&rsquo;s run could not be read.</p>`;
    }
  }
}

/* --- the combined written report's interactions ----------------------------- */

/* Days a window spans, as sweep.py WINDOWS defines them; used only to prefer
   a sibling period that shares no days with this one. */
const WINDOW_DAYS = { week: 7, month: 30, half: 182, year: 365 };

function spanOf(r) {
  const end = Number(r.offset_days || 0);
  return [end, end + (WINDOW_DAYS[r.window] || 0)];
}

/** Siblings with no days in common first: they are the honest comparison. */
function orderSiblings(record, siblings) {
  const [a0, a1] = spanOf(record);
  const apart = (s) => { const [b0, b1] = spanOf(s); return b0 >= a1 || a0 >= b1; };
  return [...siblings].sort((x, y) => Number(apart(y)) - Number(apart(x)));
}

/** Pointing at any mark of a video lights that video up across the spread. */
function wireHighlight(root) {
  const set = (el) => {
    const mark = el && el.closest && el.closest("[data-vid]");
    const spread = el && el.closest && el.closest("[data-cx-spread]");
    if (!spread) return;
    if (mark && spread.contains(mark)) spread.dataset.hl = mark.dataset.vid;
    else delete spread.dataset.hl;
  };
  const clear = () => {
    for (const s of root.querySelectorAll("[data-cx-spread][data-hl]")) delete s.dataset.hl;
  };
  root.addEventListener("pointerover", (e) => set(e.target));
  root.addEventListener("focusin", (e) => set(e.target));
  root.addEventListener("pointerleave", clear);
}

/** The comparison table sorts by any measured column, and says so. */
function wireSort(root) {
  const body = root.querySelector("[data-vt-body]");
  if (!body) return;
  const table = body.closest("table");
  for (const button of table.querySelectorAll("[data-sort]")) {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      const th = button.closest("th");
      const ascending = th.getAttribute("aria-sort") !== "ascending";
      for (const other of table.querySelectorAll("th[aria-sort]")) other.removeAttribute("aria-sort");
      th.setAttribute("aria-sort", ascending ? "ascending" : "descending");
      const rows = [...body.querySelectorAll("tr")];
      const value = (tr) => {
        const raw = tr.getAttribute(`data-sort-${key}`);
        return raw === null || raw === "" ? null : Number(raw);
      };
      const state = reduced() ? null : Flip.getState(rows);
      rows.sort((x, y) => {
        const a = value(x), b = value(y);
        if (a === null && b === null) return Number(x.dataset.sortN) - Number(y.dataset.sortN);
        if (a === null) return 1;
        if (b === null) return -1;
        return ascending ? a - b : b - a;
      });
      body.append(...rows);
      if (state) Flip.from(state, { duration: 0.45, ease: "power2.inOut" });
      announce(`Sorted by ${button.textContent.trim()}, ${ascending ? "lowest" : "highest"} first.`);
    });
  }
}

/** The matrix: one tab stop, arrow keys between cells, words for the cell in focus. */
function wireMatrix(root, ctx) {
  const grid = root.querySelector(".mx");
  const detail = root.querySelector("[data-mx-detail]");
  if (!grid || !detail) return;
  const cells = [...grid.querySelectorAll("[data-cell]")];
  const cols = grid.querySelectorAll("thead .mx__vid").length || 1;
  const show = (cell) => {
    const [theme, n] = cell.dataset.cell.split(":");
    detail.innerHTML = C.cellDetail(ctx, theme, Number(n));
  };
  for (const cell of cells) {
    cell.addEventListener("focus", () => show(cell));
    cell.addEventListener("pointerenter", () => show(cell));
    cell.addEventListener("click", () => show(cell));
  }
  grid.addEventListener("keydown", (e) => {
    const at = cells.indexOf(document.activeElement);
    if (at < 0) return;
    const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols, Home: -at, End: cells.length - 1 - at }[e.key];
    if (step === undefined) return;
    const next = cells[at + step];
    if (!next) return;
    e.preventDefault();
    cells[at].tabIndex = -1;
    next.tabIndex = 0;
    next.focus();
  });
}

/** The signs grid: what a present sign found, for the dot in focus. */
function wireSigns(root, ctx) {
  const line = root.querySelector("[data-sg-detail]");
  if (!line) return;
  const show = (dot) => { line.innerHTML = C.signEvidence(ctx, dot.dataset.sign, Number(dot.dataset.n)); };
  for (const dot of root.querySelectorAll(".sgx__dot")) {
    dot.addEventListener("focus", () => show(dot));
    dot.addEventListener("pointerenter", () => show(dot));
    dot.addEventListener("click", () => show(dot));
  }
}

/* --- boot ------------------------------------------------------------------ */

async function main() {
  mountAnnouncer();
  mountAll({ here: "/library" });

  const carried = takeVolume();

  const id = idFromPath();
  if (!id) {
    fail("No sweep named", "This address does not name a combined report.",
      "Combined reports are listed in the library.",
      '<a class="btn" href="/library">Open the library</a>');
    return;
  }

  let record = null;
  try {
    record = await getSweep(id);
  } catch (error) {
    if (error && error.status === 404) {
      fail("Not found", "There is no sweep saved under that id.",
        "It may have been removed from the outputs directory since the link was made.",
        '<a class="btn" href="/library">Open the library</a>');
    } else {
      fail("Unreachable", "The combined report could not be read.",
        `The backend answered: ${esc((error && error.message) || "no reason given")}.`,
        '<a class="btn" href="/library">Open the library</a>');
    }
    return;
  }

  /* The combined written report, or its facts computed live when the model
     has not written one yet. A failure here costs only the new pages: the
     book falls back to the chapters it had before. */
  const [all, analysis] = await Promise.all([
    listSweeps().catch(() => []),
    getSweepAnalysis(record.sweep_id || id).then((a) => (a && a.facts ? a : null)).catch(() => null),
  ]);
  let siblings = (all || []).filter((s) => s.sweep_id !== record.sweep_id
    && (s.subject || "").trim().toLowerCase() === (record.subject || "").trim().toLowerCase());
  siblings = orderSiblings(record, siblings);
  const ctx = analysis ? C.makeContext(record, analysis) : null;

  if (carried) root.dataset.opening = "yes";

  const refusedPage = () => `
    <p class="ref__range ref__range--cont" data-ref-range></p>
    <ul class="prov__list ref__list" data-cx-flow></ul>`;
  const memberPage = () => `<ul class="mem" data-cx-flow></ul>`;
  const channelsSection = () => `<section class="cv" aria-labelledby="cv2-h">
          <h2 id="cv2-h" class="cx-h">What each channel managed to read</h2>
          <p class="cx-lede">Counted across every segment of every video in this sweep
            that could be read. A channel that returned nothing for a segment is
            counted as a gap, never as a neutral reading.</p>
          <div data-channels><p class="mem__loading">Reading the videos&rsquo; runs</p></div>
        </section>`;
  const frameOf = (man) => (row) => {
    if (!row || !row.moment || !Number.isFinite(row.moment.start)) return null;
    return plateFor(man, row.video_id, { start_s: row.moment.start, end_s: row.moment.end ?? row.moment.start });
  };
  const groups = ctx && ctx.reading && ctx.reading.product_groups;
  const hasProducts = Boolean(ctx && record.subject_kind === "brand" && groups && groups.length);
  const man = ctx ? await manifest() : null;

  /* THE COMBINED WRITTEN REPORT'S BOOK (23 Sep 2026).

     In the order a reader asks: what does the set say (Overview), how do the
     videos compare (The videos), what do they agree and split on (Consensus),
     which products (for a brand), what do the audiences say (Audience), how
     does it compare with another period, and how far can it be trusted and
     could any of it be paid (Trust, where the caveats and the provenance now
     live). Without an analysis the book is the one it was before. */
  const chapters = ctx ? [
    { id: "overview", label: "Overview", spreads: [
      spread({ key: "overview", plain: ["verso", "recto"], verso: titlePage(record, ctx), recto: C.readingPage(ctx) }),
      /* The ranges page keeps the opening spread's plain head: it was fitted
         to a page without one, and its last line is the facial disclosure. */
      spread({ key: "overview-2", plain: ["recto"], verso: C.setTakeaways(ctx), recto: findingsPage(record, ctx) })] },
    { id: "videos", label: "The videos", spreads: [
      spread({ key: "videos-table", wide: true, verso: C.tablePage(ctx) }),
      spread({ key: "videos-vs", verso: C.quadrantPage(ctx), recto: C.oddPage(ctx, frameOf(man)) }),
      spread({ key: "videos-tone", wide: true, verso: C.tonesPage(ctx) }),
      spread({ key: "videos-moments", wide: true, verso: C.momentsPage(ctx, frameOf(man)) }),
      spread({ key: "videos", verso: membersShell(record), recto: memberPage() })] },
    { id: "consensus", label: "Consensus", spreads: [
      /* The matrix is a fold-out only when there are themes to fill it;
         until then the chapter is one ordinary spread that says what is
         missing and how to write it. */
      ...(ctx.themes.length ? [spread({ key: "consensus-matrix", wide: true,
        verso: C.matrixPage(ctx, hasProducts ? groups : null) })] : []),
      spread({ key: "consensus", verso: C.agreedPage(ctx), recto: C.splitPage(ctx) })] },
    ...(hasProducts ? [{ id: "products", label: "Products", spreads: [
      spread({ key: "products", verso: C.lineupPage(ctx), recto: C.productsWordsPage(ctx) })] }] : []),
    { id: "audience", label: "Audience", spreads: [
      spread({ key: "audience", verso: C.talkSetPage(ctx), recto: C.eachAudienceSet(ctx) }),
      spread({ key: "audience-2", verso: C.asksSetPage(ctx), recto: audiencePanel(record) })] },
    ...(siblings.length ? [{ id: "period", label: "Another period", spreads: [
      spread({ key: "period", verso: `${comparePanel(record, siblings, true)}<div data-checks-host></div>`,
        recto: `<div class="cp__host" data-compare-host>
          <p class="cx-note">Choose a period on the facing page to hold it against this one.</p></div>` }),
      spread({ key: "period-2", verso: `<div data-twice-host></div>`,
        recto: `<div data-themes-host></div>${C.earlierLinks(record, WINDOW_DAYS[record.window] || 0)}` })] }] : []),
    { id: "trust", label: "Trust", spreads: [
      spread({ key: "trust", verso: C.trustSetPage(ctx), recto: C.signsSetPage(ctx) }),
      /* One thing to a page: at 1512x830 the provenance page could not hold
         a failed video and the controller's pairs together (79px over). */
      spread({ key: "channels", verso: channelsSection(),
        recto: `<section class="prs" aria-labelledby="prs-h"><h2 id="prs-h" class="cx-h">Which channels disagreed</h2>
          <p class="cx-lede">Read off the controller's own record of which channels it saw in conflict, across every
            segment of every video.</p><div data-pairs></div></section>` }),
      spread({ key: "provenance", verso: caveats(record), recto: provenancePanel(record, false) }),
      spread({ key: "provenance-refused", verso: refusedHead(record), recto: refusedPage() })] },
  ].map((c) => ({ ...c, html: chapter(c) })) : [
    { id: "overview", label: "Overview", spreads: [spread({
        /* No running heads on the opening spread, as in report.js: the
           recto's line was what pushed the facial disclosure off the page. */
        key: "overview", plain: ["verso", "recto"],
        verso: titlePage(record), recto: findingsPage(record) })] },
    { id: "videos", label: "The videos", spreads: [spread({
        key: "videos", verso: membersShell(record), recto: memberPage() })] },
    { id: "channels", label: "Channels", spreads: [spread({
        key: "channels", verso: channelsSection(), recto: caveats(record) })] },
    { id: "audience", label: "Audience", spreads: [spread({
        key: "audience", verso: audiencePanel(record),
        recto: `<section class="ea" aria-labelledby="ea-h">
          <h2 id="ea-h" class="cx-h">Each audience on its own</h2>
          <p class="cx-lede">The pooled figure can hide a video whose audience said the
            opposite of the rest, so each is drawn separately on the same scale.</p>
          <div data-each><p class="mem__loading">Reading the videos&rsquo; runs</p></div>
        </section>` })] },
    ...(siblings.length ? [{ id: "period", label: "Another period", spreads: [spread({
        key: "period", verso: comparePanel(record, siblings),
        recto: `<div class="cp__host" data-compare-host>
          <p class="cx-note">Choose a period on the facing page to hold it against this one.</p>
        </div>` })] }] : []),
    { id: "provenance", label: "Provenance", spreads: [spread({
        key: "provenance", verso: provenancePanel(record), recto: refusedHead(record) })] },
  ].map((c) => ({ ...c, html: chapter(c) }));

  const title = record.subject || "Combined report";
  root.dataset.codex = "yes";
  root.innerHTML = codexShell({
    title: esc(title),
    chapters,
    backHref: "/library",
    backLabel: "Close the book",
  });

  const volumeId = `sweep:${record.sweep_id || id}`;
  wireClose(root, {
    link: root.querySelector("[data-cx-close]"),
    cover: carried && carried.cover,
    before: () => stashReturn(volumeId, "close"),
  });
  window.addEventListener("pagehide", () => stashReturn(volumeId, "leave"));

  const book = wireCodex(root, { title, onSpread: (s) => animateIn(s) });

  const memberItems = [...root.querySelectorAll("[data-members] > li")];
  const refusedItems = [...root.querySelectorAll(".ref__list > li")];
  if (book) {
    book.flow({
      chapter: "videos",
      items: memberItems,
      cont: (n) => spread({ key: `videos-${n}`, cont: true,
        verso: memberPage(), recto: memberPage() }),
    });
    if (refusedItems.length) {
      book.flow({
        chapter: ctx ? "trust" : "provenance",
        items: refusedItems,
        cont: (n) => spread({ key: `provenance-${n}`, cont: true,
          verso: refusedPage(), recto: refusedPage() }),
        after: (regions) => {
          for (const r of regions) {
            const range = r.parentElement.querySelector("[data-ref-range]");
            if (!range) continue;
            const before = refusedItems.indexOf(r.firstElementChild);
            range.textContent = r.childElementCount
              ? `${count(before + 1)} to ${count(before + r.childElementCount)} of ${count(refusedItems.length)}`
              : `End of the list, all ${count(refusedItems.length)} shown`;
          }
        },
      });
    }
  }

  document.title = `${title} — BrandPulse`;
  delete document.documentElement.dataset.carrying;
  clearTimeout(window.__bpFallback);
  requestAnimationFrame(() => openBook(root, carried));

  for (const link of root.querySelectorAll("[data-open-member]")) {
    link.addEventListener("click", () => {
      stashFlip(link.closest(".mem__one").querySelector(".tp"));
    });
  }

  if (ctx) {
    wireHighlight(root);
    wireSort(root);
    wireMatrix(root, ctx);
    wireSigns(root, ctx);
    if (book) {
      /* Evidence: a video number goes to its row, a theme to its row in the matrix. */
      root.addEventListener("click", (event) => {
        const v = event.target.closest("[data-evv]");
        const h = event.target.closest("[data-evh]");
        if (v) {
          const row = root.querySelector(`.vt__row[data-vid="${CSS.escape(v.dataset.evv)}"]`);
          if (!row) return;
          book.reveal(row);
          const spreadEl = row.closest("[data-cx-spread]");
          if (spreadEl) spreadEl.dataset.hl = v.dataset.evv;
        } else if (h) {
          const row = root.querySelector(`#theme-${CSS.escape(h.dataset.evh)}`);
          if (!row) return;
          book.reveal(row);
          const cell = row.querySelector("[data-cell]");
          if (cell) requestAnimationFrame(() => cell.focus({ preventScroll: true }));
        }
      });
      for (const link of root.querySelectorAll("[data-cx-goto-trust]")) {
        link.addEventListener("click", (event) => { event.preventDefault(); book.goChapter("trust"); });
      }
    }
  }

  /* The comparison. The chosen sibling is fetched whole, because the listing
     does not carry the per-video values the spread needs; with the written
     report, the period facts come from the server, which can read both sets
     of member reports. */
  const host = root.querySelector("[data-compare-host]");
  for (const button of root.querySelectorAll("[data-sib]")) {
    button.addEventListener("click", async () => {
      for (const other of root.querySelectorAll("[data-sib]")) {
        other.setAttribute("aria-pressed", String(other === button));
      }
      host.innerHTML = `<p class="cx-note">Reading that sweep</p>`;
      let other = null;
      let pf = null;
      try {
        [other, pf] = await Promise.all([
          getSweep(button.dataset.sib),
          ctx ? compareSweeps(record.sweep_id, button.dataset.sib).catch(() => null) : Promise.resolve(null),
        ]);
      } catch {
        host.innerHTML = `<p class="cx-note u-tear">That sweep could not be read.</p>`;
        return;
      }
      const refused = separable(record, other).length > 0;
      if (ctx && pf && pf.comparable && !refused) {
        const labels = [periodLabel(record), periodLabel(other)];
        root.querySelector("[data-checks-host]").innerHTML = C.periodChecks(pf, labels);
        host.innerHTML = C.periodSlopes(pf, labels);
        root.querySelector("[data-twice-host]").innerHTML = C.twicePage(pf, labels);
        root.querySelector("[data-themes-host]").innerHTML = C.themeChanges(pf, labels,
          [`python write_analysis.py --sweep ${record.sweep_id}`, `python write_analysis.py --sweep ${other.sweep_id}`]);
        for (const s of root.querySelectorAll('[data-cx-key^="period"]')) delete s.dataset.drawn;
        const shown = host.closest("[data-cx-spread]");
        if (shown && !shown.hidden) animateIn(shown);
        if (book) book.relayout();
      } else {
        host.innerHTML = comparisonBody(record, other);
        const checks = root.querySelector("[data-checks-host]");
        if (checks) checks.innerHTML = "";
        wireSplit();
      }
      if (button.dataset.quiet) { delete button.dataset.quiet; return; }
      announce(refused
        ? "Those two cannot honestly be compared. The reasons are on the facing page."
        : `Comparing ${periodLabel(record)} with ${periodLabel(other)}.`);
    });
  }

  /* The first other period is held against this one from the start, so the
     chapter opens on a comparison -- or on the reasons there cannot be one --
     rather than on two pages waiting for a click. It is a read of files on
     this machine, not a search. */
  const firstSib = root.querySelector("[data-sib]");
  if (firstSib) {
    firstSib.dataset.quiet = "yes";
    firstSib.click();
  }

  function wireSplit() {
    const cp = host.querySelector("[data-cp]");
    const slider = host.querySelector("[data-split]");
    if (!cp || !slider) return;
    const move = () => cp.style.setProperty("--split", `${slider.value}%`);
    slider.addEventListener("input", move);
    move();
  }

  /* Everything that needs the members' own reports arrives together, and the
     book is laid out again once, because traces and frames change how tall a
     video's entry is. */
  const [collected, manifestNow] = await Promise.all([readMembers(record), man ? Promise.resolve(man) : manifest()]);
  paintMembers(collected, manifestNow);
  root.querySelector("[data-channels]").innerHTML = channelsPanel(record, collected);
  const each = root.querySelector("[data-each]");
  if (each) each.innerHTML = eachAudience(record, collected);
  root.querySelector("[data-pairs]").innerHTML = pairsPanel(collected);
  if (book) book.relayout();
}

main();
