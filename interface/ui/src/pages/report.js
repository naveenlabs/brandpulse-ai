/* ===========================================================================
   report.js — one analysed video, as the volume it is on the shelf.

   THE BOOK IS COMPOSED, NOT A DASHBOARD PUT INSIDE COVERS.

   The build this replaces moved every panel of the old report onto a spread
   unchanged: the same tables, the same warning boxes, the same long columns,
   inside a book-shaped frame. The overview's left page held a title and three
   numbers; its right page held two pink warning boxes and a calibration
   table, so the first thing a reader met was a wall of disclosure with the
   finding stranded opposite it.

   Here each spread is composed for what it has to say. These are the chapters
   before the written report exists; the book with it is laid out in main()
   (THE WRITTEN REPORT'S BOOK), and keeps every page below.

     1  Overview       a title page carrying the same frame and the same
                       tracked serif as the cover, facing the two scores with
                       what each is made of, the counts that matter, a summary
                       written from the run's own figures, what the scores are
                       not, and the facial disclosure as a footnote to the
                       numbers it qualifies
     2  Key moments    the frame large on one page with the timeline under it;
                       what was said, what each channel read and why it scored
                       that on the other
     3  Four channels  how each channel was read and how reliable it is, facing
                       what limits it; then what was measured and not scored,
                       facing how a disagreement becomes a score
     4  Audience       the split of the room, then the comments themselves,
                       carried over as many spreads as they need
     5  Evidence       every segment, folded out across the whole block

   Nothing is invented to fill a page. Every sentence that states a finding is
   assembled from this report's own fields, and every number printed was read
   from them.

   The transport is no longer pinned to the window over every chapter. It is
   printed under the frame on the moments spread, where it is the instrument
   the reader is using, and it is gone from the chapters that have no time.
   ======================================================================== */

import "../styles/tokens.css";
import "../styles/chassis.css";
import "../styles/transport.css";
import "../styles/leaf.css";
import "../styles/codex.css";
import "../styles/report.css";
import "../styles/analysis.css";

import { mountAll } from "../lib/chrome.js";
import { getReport } from "../lib/api.js";
import { mountAnnouncer, announce } from "../lib/announce.js";
import {
  CHANNELS, CHANNEL_META, FACIAL_REFERENCES, CONFLICT_FLAG_THRESHOLD,
  segmentValences, rawReading, readingConfidence, facialFrameCount, toValence,
  coverage, aggregateIsNearTie, damping, vocalDimensions, conflictChannels,
} from "../lib/contract.js";
import { count, esc, mmss, pct, score, confidence, splitReportName } from "../lib/format.js";
import { createClock, mountTransport } from "../lib/transport.js";
import { playFlip } from "../lib/motion.js";
import { ARROW, chapter, codexShell, openBook, spread, titleLength, wireClose, wireCodex } from "../lib/codex.js";
import { animateIn } from "../lib/charts.js";
import {
  verdictBlock, levelPill, inShort, inShortBlock, takeawaysPage, agreementPage, tonePage, timePage, topicsPage,
  claimItems, talkPage, askPage, oddMomentsPage, trustPage, signsPage, notYet,
} from "../lib/written.js";
import { takeVolume, stashReturn } from "../lib/leaf.js";
import { manifest, plateFor, videoIdOf, hasImagery, midpointOf } from "../lib/frames.js";

const root = document.querySelector("[data-report]");

/* Which file to open.

   A saved report lives at /library/<filename>. One video of a sweep lives at
   /brand/<sweep_id>/<video_id> and is served the same document, because it IS
   the same report with a bar across the top saying which of five it is. Both
   addresses are read back off the path here; neither reaches the filesystem,
   and the ids are validated on the API side where they are actually used. */
function sourceFromPath() {
  const path = decodeURIComponent(window.location.pathname);
  const member = path.match(/^\/brand\/([^/]+)\/([^/]+)\/?$/);
  if (member) return { kind: "member", sweepId: member[1], videoId: member[2] };
  const one = path.match(/^\/library\/(.+?)\/?$/);
  if (one) return { kind: "report", filename: one[1] };
  return { kind: "none" };
}

function fail(tag, heading, body, extra = "") {
  root.innerHTML = `
    <section class="state${tag === "Unreachable" ? " state--error" : ""}">
      <p class="t-label state__tag">${esc(tag)}</p>
      <h1 class="t-l">${esc(heading)}</h1>
      <p class="t-body">${body}</p>${extra}
    </section>`;
  /* Whatever went wrong, no volume is going to open now. Clearing the flag
     here as well as on the success path keeps the two exits symmetrical --
     every route out of this module leaves the document without it. */
  delete document.documentElement.dataset.carrying;
  clearTimeout(window.__bpFallback);
}

/* The segment with the highest conflict score: the same reduction the library
   uses to choose the frame it paints on the cover, so the plate inside the
   book is the plate outside it. Ties keep the earliest. */
const mostContested = (segments) => segments.reduce((a, b) =>
  (b.conflict_score ?? -1) > (a.conflict_score ?? -1) ? b : a, segments[0]);

/* --- 1. the title page ---------------------------------------------------- */

/* The chapters, and the element on each chapter's first page that its page
   number is read from once the book is laid out. */
const CONTENTS = [
  ["Overview", "ti-h"], ["Key moments", "mo-h"], ["Four channels", "rl-h"],
  ["Audience", "au-h"], ["Evidence", "le-h"],
];

function titlePage(t) {
  const facts = [
    ["Length", mmss(t.duration)],
    ["Segments", count(t.segments)],
    ["Comments read", count(t.comments)],
  ];
  const mid = t.worst ? midpointOf(t.worst) : null;
  const contested = t.worst && typeof t.worst.conflict_score === "number"
    && t.worst.conflict_score > 0;

  let caption;
  if (!t.plate) {
    caption = "No frame was derived for this video, so this page carries no plate.";
  } else if (contested) {
    caption = `The plate is ${mmss(mid)}, the midpoint of the run&rsquo;s most contested
      segment (${mmss(t.worst.start_s)} to ${mmss(t.worst.end_s)}, conflict
      ${confidence(t.worst.conflict_score)}).${t.onShelf
        ? " The same frame is printed on this volume&rsquo;s cover." : ""}`;
  } else {
    caption = `The plate is ${mmss(mid)}. No segment in this run scored any conflict,
      so it is the first segment&rsquo;s midpoint.`;
  }

  /* With a plate, the frame is printed to the edge and the title set under
     it. Without one, the page is the cover itself: the title in foil on the
     board's own cloth, which is exactly what the shelf painted when it had no
     frame to show. */
  const heading = t.plate ? `
      <p class="cx-kicker">${t.kicker}</p>
      <h1 id="ti-h" class="ti__title cx-display" data-len="${titleLength(t.brand)}">${esc(t.brand)}</h1>
      ${t.product ? `<p class="ti__sub">${esc(t.product)}</p>` : ""}
      <span class="ti__rule cx-rule" aria-hidden="true"></span>` : "";
  return `
  <section class="ti${t.plate ? "" : " ti--plain"}" aria-labelledby="ti-h">
    ${t.plate ? `
      <figure class="ti__plate cx-bleed">
        <img src="${t.plate}" alt="A frame from this video at ${mmss(mid)}." decoding="async">
      </figure>` : `
      <div class="ti__board cx-bleed">
        <p class="ti__bk">${t.kicker}</p>
        <h1 id="ti-h" class="ti__title cx-display" data-len="${titleLength(t.brand)}">${esc(t.brand)}</h1>
        <span class="ti__brule" aria-hidden="true"></span>
        ${t.product ? `<p class="ti__bsub">${esc(t.product)}</p>` : ""}
      </div>`}
    <div class="ti__block">${heading}
      <dl class="ti__facts">
        ${facts.map(([k, v]) => `<div><dt>${k}</dt><dd class="t-read">${v}</dd></div>`).join("")}
      </dl>
      ${inShortBlock(t.short)}
      ${t.plate ? "" : `
      <nav class="toc toc--chapters" aria-label="Contents">
        <p class="cx-h3">Contents</p>
        <ol class="toc__list">
          ${CONTENTS.map(([label, target], i) => `
            <li><span class="toc__n t-read">${i + 1}</span>
              <button class="toc__t" type="button" data-cx-xref="${target}">${label}</button>
              <span class="toc__pg t-read" data-cx-xref="${target}"><span data-cx-xref-page></span></span></li>`).join("")}
        </ol>
      </nav>`}
      ${t.plate ? `<p class="ti__stand cx-note">If you are the person in this frame,
        <button class="cx-xref" type="button" data-cx-xref="standing">page
        <span data-cx-xref-page></span></button> is written to you.</p>` : ""}
      <p class="ti__cap cx-note">${caption}${t.videoId ? ` Source:
        <a href="${esc(t.videoUrl)}" rel="noopener noreferrer" target="_blank">${t.videoTitle
          ? `“${esc(t.videoTitle)}”, on YouTube` : "the video, on YouTube"}<span class="sr-only"> (opens in a new tab)</span></a>.` : ""}</p>
    </div>
  </section>`;
}

/* --- 1. the findings ------------------------------------------------------ */

/* The run's findings in sentences, assembled from its own fields. No model
   writes this and nothing in it is a judgement: every clause is a count, a
   time or a label the report already carries. Worded for a reader who has
   not met the pipeline (24 Sep 2026): three of five people in the final user
   evaluation stopped at "conflict threshold", "controller" and a bare 0.600,
   so the threshold says what it is on and the controller is the local model. */
function summaryOf(report, segments, flagged, cov, worst) {
  const n = segments.length;
  const dur = mmss(Math.max(...segments.map((s) => s.end_s)));
  const out = [];
  out.push(flagged
    ? `${count(n)} segments across ${dur}. In ${count(flagged)} of them
       (${pct((flagged / n) * 100, 0)}) the readings disagreed enough to be flagged
       (${confidence(CONFLICT_FLAG_THRESHOLD)} or more on a 0 to 1 scale); those count twice.`
    : `${count(n)} segments across ${dur}; none disagreed enough to be flagged
       (${confidence(CONFLICT_FLAG_THRESHOLD)} on a 0 to 1 scale).`);
  if (worst && typeof worst.conflict_score === "number" && worst.conflict_score > 0) {
    out.push(`The biggest disagreement is at ${mmss(worst.start_s)}, scored
      ${confidence(worst.conflict_score)} by the local model.`);
  }
  const f = cov.facial;
  out.push(`A face was read in ${count(f.read)} of ${count(f.total)}
    segments${f.thin ? ", under half the video" : ""}.`);
  const cs = report.comment_sentiment || {};
  const dist = cs.distribution || {};
  const tie = aggregateIsNearTie(dist);
  if (cs.label && tie) {
    out.push(tie.nearTie
      ? `The audience, read once for the whole video, is close to a tie:
         ${count(tie.top[1])} ${esc(tie.top[0].toLowerCase())} against
         ${count(tie.second[1])} ${esc(tie.second[0].toLowerCase())}.`
      : `The audience, read once for the whole video, reads
         ${esc(cs.label.toLowerCase())}: ${count(dist.POSITIVE || 0)} positive,
         ${count(dist.NEUTRAL || 0)} neutral and ${count(dist.NEGATIVE || 0)} negative comments.`);
  } else {
    out.push("No audience reading was recorded for this video.");
  }
  return out.join(" ");
}

function findingsPage(report, segments, flagged, cov, worst, analysis = null, lookup = null) {
  const n = segments.length;
  const place = (v) => (typeof v === "number" && Number.isFinite(v)
    ? Math.min(100, Math.max(0, v)).toFixed(2) : null);

  const scoreBlock = (label, value, def) => {
    const at = place(value);
    return `
    <div class="fi__score">
      <p class="fi__k">${label}<span class="fi__dag" aria-hidden="true">&dagger;</span></p>
      <p class="fi__v"><span class="t-read">${score(value)}</span><span class="fi__of">of 100</span></p>
      <span class="fi__scale" aria-hidden="true">${at != null ? `<i style="--at:${at}%"></i>` : ""}</span>
      <p class="fi__def">${def}</p>
    </div>`;
  };

  const facial = cov.facial;
  const comments = (report.all_comments || []).length;
  const caveat = report.bias_caveat
    ? `<p class="fi__note cal__caveat"><span class="fi__dag" aria-hidden="true">&dagger;</span>
         ${esc(report.bias_caveat)}${report.vocal_caveat ? ` The vocal channel carries a
         caveat of its own, printed with the channels on
         <button class="cx-xref" type="button" data-cx-xref="vocal-caveat">page
         <span data-cx-xref-page></span></button>.` : ""}</p>`
    : `<p class="fi__note cal__caveat">This report carries no caveat text of its own.
         That is unusual and is stated rather than passed over: every report
         written by the current pipeline carries at least the facial bias
         disclosure.</p>`;
  const not = `<p class="fi__not cx-note">
      Both scores measure how far four independent readings of the same
      moment disagreed with each other.
      Neither is a finding about whether anyone was telling the truth,
      and neither is comparable between videos.
    </p>`;

  /* THE READING. With the written report present, the recto opens on what
     the video says, in words, and the scores follow it with what they are
     and are not. The counts moved to the facing title page and the Trust
     chapter; the summary written from the figures is the verdict's fallback. */
  if (analysis) {
    return `
  <section class="fi rd" aria-label="The reading">
    <div class="rd__head"><p class="cx-kicker">The reading</p>
      ${levelPill(analysis.facts.confidence.level, "#channels")}</div>
    ${verdictBlock(analysis, lookup, summaryOf(report, segments, flagged, cov, worst))}
    <div class="fi__scores">
      ${scoreBlock("Authenticity", report.authenticity_score,
        "How far the four readings of each moment agreed; flagged moments count twice.")}
      ${scoreBlock("Brand health", report.brand_health_score,
        "60% audience comment sentiment and 40% Authenticity.")}
    </div>
    ${not}
    ${caveat}
  </section>`;
  }

  return `
  <section class="fi" aria-label="What the run found">
    <div class="fi__scores">
      ${scoreBlock("Authenticity", report.authenticity_score,
        "100 minus the weighted mean conflict between channels; flagged segments count twice.")}
      ${scoreBlock("Brand health", report.brand_health_score,
        "60% audience comment sentiment and 40% Authenticity.")}
    </div>

    <dl class="fi__counts">
      <div><dt>Segments</dt><dd class="t-read">${count(n)}</dd>
        <dd class="fi__sub">across ${mmss(Math.max(...segments.map((sg) => sg.end_s)))}</dd></div>
      <div><dt>Flagged</dt><dd class="t-read${flagged ? " is-tear" : ""}">${count(flagged)}</dd>
        <dd class="fi__sub">${pct(n ? (flagged / n) * 100 : 0, 0)} of the run</dd></div>
      <div><dt>Faces read</dt><dd class="t-read">${count(facial.read)}</dd>
        <dd class="fi__sub">of ${count(facial.total)} segments</dd></div>
      <div><dt>Comments</dt><dd class="t-read">${count(comments)}</dd>
        <dd class="fi__sub">whole video</dd></div>
    </dl>

    <p class="fi__summary cx-text">${summaryOf(report, segments, flagged, cov, worst)}</p>

    ${not}

    ${caveat}
  </section>`;
}

/* --- 2. the moment ---------------------------------------------------------

   THE CENTREPIECE SPREAD. The frame is the largest thing in the book, printed
   to the edge of its page, with the timeline directly under it: the picture
   and the strip it was taken from. The facing page is what was said, what
   each channel read, and why the segment scored what it did.

   Every data hook keeps the name it had, and all of the wiring is scoped to
   `root`, so moving the markup across the gutter changes nothing about how
   the moment is bound to the clock. */

function momentPlate() {
  return `
  <section class="mo" data-act="moment" aria-labelledby="mo-h">
    <h2 id="mo-h" class="sr-only">The moment under the playhead</h2>
    <figure class="mo__plate cx-bleed">
      <div class="mo__frame" data-flip-id="report-frame">
        <img alt="" data-frame hidden>
        <div class="mo__none" data-noframe hidden><p>No frame was derived for this second.</p></div>
      </div>
    </figure>
    <p class="mo__cap"><span class="mo__when t-time" data-at></span>
      <span class="mo__capt" data-cap></span></p>
    <div class="mo__strip" data-transport></div>
    <nav class="mo__nav" aria-label="Moments">
      <div class="mo__step">
        <button class="cx-btn cx-btn--icon" type="button" data-mo-step="-1"
                aria-label="Previous moment">${ARROW("prev")}</button>
        <span class="mo__navl">Moment</span>
        <button class="cx-btn cx-btn--icon" type="button" data-mo-step="1"
                aria-label="Next moment">${ARROW("next")}</button>
      </div>
      <div class="mo__step" data-mo-flags>
        <button class="cx-btn cx-btn--icon" type="button" data-mo-flag="-1"
                aria-label="Previous flagged moment">${ARROW("prev")}</button>
        <span class="mo__navl" data-mo-flagpos></span>
        <button class="cx-btn cx-btn--icon" type="button" data-mo-flag="1"
                aria-label="Next flagged moment">${ARROW("next")}</button>
      </div>
      <a class="mo__all" href="#evidence" data-mo-all>Every moment</a>
    </nav>
  </section>`;
}

function momentRead() {
  return `
  <section class="mr" data-act="moment-read" aria-label="What was said, and what each channel read">
    <header class="mr__head">
      <p class="mr__pos" data-pos></p>
      <p class="mr__flag" data-flagged hidden>Flagged</p>
    </header>
    <blockquote class="mr__said" data-said></blockquote>
    <button class="cx-btn mr__more" type="button" data-said-more hidden></button>
    <table class="rd">
      <caption class="sr-only">Each channel's reading of this segment</caption>
      <colgroup><col class="rd__c1"><col><col class="rd__c3"><col class="rd__c4"></colgroup>
      <thead>
        <tr>
          <th scope="col">Channel</th>
          <th scope="col">Read</th>
          <th scope="col"><span class="rd__axis" aria-hidden="true"><i>&minus;</i><i>0</i><i>+</i></span>
            <span class="sr-only">Valence, negative to positive</span></th>
          <th scope="col">Score</th>
        </tr>
      </thead>
      <tbody data-rows></tbody>
    </table>
    <p class="rd__verdict" data-verdict></p>
    <div class="why" data-why></div>
  </section>`;
}

/* One channel's reading of one segment. The dot sits in the column of the
   valence the pipeline mapped the reading to; four dots in one column is four
   channels agreeing, and a scatter is the disagreement this system exists to
   find. A reading with no valence gets no dot, and says why. */
function readRow(segment, channel, commentSentiment) {
  const meta = CHANNEL_META[channel];
  const raw = rawReading(segment, channel, commentSentiment);
  const conf = readingConfidence(segment, channel, commentSentiment);
  const frames = channel === "facial" ? facialFrameCount(segment) : null;
  const valence = toValence(raw);

  let note = "";
  if (channel === "audience") note = "one reading, whole video";
  else if (channel === "facial") {
    note = frames != null
      ? `pooled from ${count(frames)} frame${frames === 1 ? "" : "s"}`
      : "no face found";
  } else if (channel === "vocal") {
    const dims = vocalDimensions((segment.model_outputs || {}).vocal_emotion);
    note = dims && dims.arousal != null ? "read on arousal" : "";
  }
  if (raw && !valence) note = `${raw.toLowerCase()} has no valence, so it is not compared`;

  const confText = conf != null ? confidence(conf) : null;
  const what = channel === "vocal" ? "arousal"
    : channel === "audience" ? "mean confidence" : "confidence";

  return `
  <tr data-channel="${channel}" style="--ch:var(--ch-${channel})"${raw ? "" : " data-absent"}>
    <th scope="row">
      <span class="rd__ch"><i class="mo__mark" data-mark="${channel}" aria-hidden="true"></i>${esc(meta.short)}</span>
      ${note ? `<span class="rd__note">${esc(note)}</span>` : ""}
    </th>
    <td class="rd__read">${raw ? esc(raw.toLowerCase()) : "<span class='is-absent'>no reading</span>"}</td>
    <td class="rd__scale">
      <span class="rd__dots" data-v="${valence || "none"}" aria-hidden="true"><i></i><i></i><i></i></span>
      <span class="sr-only">${valence ? `valence ${valence.toLowerCase()}` : "no valence"}</span>
    </td>
    <td class="rd__score">${confText != null ? `<span class="t-read">${confText}</span>
      <span class="rd__what">${what}</span>` : "<span class='is-absent'>none</span>"}</td>
  </tr>`;
}

/* --- why it scored that, bound to the clock ------------------------------- */

function whyPanel(segment) {
  const cs = segment.conflict_score;
  const damped = damping(segment);
  const reasons = (segment.conflict_reasons || []).filter((r) => typeof r === "string");
  const attributed = reasons
    .filter((r) => r.startsWith("channels_in_conflict: "))
    .map((r) => r.slice("channels_in_conflict: ".length));
  const at = typeof cs === "number" && Number.isFinite(cs)
    ? (Math.min(1, Math.max(0, cs)) * 100).toFixed(2) : null;

  return `
    <div class="why__row">
      <p class="why__k">Conflict</p>
      <p class="why__n t-read${segment.flagged ? " is-tear" : ""}">${confidence(cs)}</p>
      <span class="why__scale" aria-hidden="true" style="--thr:${(CONFLICT_FLAG_THRESHOLD * 100).toFixed(1)}%">
        <b class="why__thr"></b>${at != null ? `<i class="${segment.flagged ? "is-tear" : ""}" style="--at:${at}%"></i>` : ""}
        <span class="why__lo">0</span><span class="why__hi">1</span>
      </span>
    </div>
    <p class="why__says cx-note">${segment.flagged
      ? `At or above the ${confidence(CONFLICT_FLAG_THRESHOLD)} threshold, so this segment is
         flagged and counted twice toward Authenticity.`
      : `Below the ${confidence(CONFLICT_FLAG_THRESHOLD)} threshold, so it is counted once.`}
      ${attributed.length
        ? `The controller named ${attributed.map((a) => `<code>${esc(a)}</code>`).join(", ")} as in conflict.`
        : "The controller named no channels."}</p>
    ${damped ? `
      <p class="why__damp cx-note">
        The controller scored this ${confidence(damped.before)}. It was reduced to
        <b>${confidence(damped.after)}</b> because the conflict rested on the
        <b>${esc(damped.channel || "weak")}</b> channel alone, which is down-weighted by its
        own measured accuracy (&times;${damped.weight.toFixed(3)}). The value before the
        reduction is read from the orchestrator&rsquo;s audit trail, not worked back out.
      </p>` : ""}`;
}

/* --- 3. how each channel was read ------------------------------------------ */

function reliabilityPage(report, segments) {
  const cov = coverage(segments, report.comment_sentiment);
  const f = FACIAL_REFERENCES;
  const thin = CHANNELS.filter((c) => CHANNEL_META[c].perSegment && cov[c].thin);

  return `
  <section class="rl" data-act="coverage" aria-labelledby="rl-h">
    <h2 id="rl-h" class="cx-h">How the evidence was read</h2>
    <p class="cx-lede">
      How much of this video each channel could read, and how accurate each was
      when tested on this project&rsquo;s own hand-labelled data. A segment a
      channel could not read is a gap, never a neutral reading.
    </p>
    <table class="rl__t">
      <caption class="sr-only">Coverage in this video and measured accuracy, per channel</caption>
      <thead>
        <tr><th scope="col">Channel</th><th scope="col">Read in this video</th>
            <th scope="col">Accuracy when tested</th></tr>
      </thead>
      <tbody>
      ${CHANNELS.map((channel) => {
        const c = cov[channel];
        const meta = CHANNEL_META[channel];
        const facial = channel === "facial";
        return `
        <tr data-channel="${channel}" style="--ch:var(--ch-${channel})"${c.thin && meta.perSegment ? " data-thin" : ""}>
          <th scope="row">
            <span class="rl__name"><i class="mo__mark" data-mark="${channel}" aria-hidden="true"></i>${esc(meta.label)}</span>
            <span class="rl__reads">${esc(meta.reads)}</span>
          </th>
          <td>
            ${meta.perSegment ? `
              <span class="rl__bar" aria-hidden="true"><i style="--to:${(c.share * 100).toFixed(2)}%"></i></span>
              <span class="rl__v"><span class="t-read">${count(c.read)}</span> of ${count(c.total)} segments</span>`
            : `<span class="rl__v">${c.read ? "One reading for the whole video" : "<span class='is-absent'>no reading</span>"}</span>`}
          </td>
          <td>
            <span class="rl__acc${facial ? " rl__acc--ref" : ""}" aria-hidden="true">
              <i style="--at:${meta.accuracy}%"></i>
              ${facial ? `<b data-kind="constant" style="--at:${f.constant.value}%"></b>
                          <b data-kind="ceiling" style="--at:${f.ceiling.value}%"></b>` : ""}
            </span>
            <span class="rl__v"><span class="t-read">${pct(meta.accuracy)}</span>
              <span class="rl__sample">${esc(meta.sample)}</span></span>
          </td>
        </tr>`;
      }).join("")}
      </tbody>
    </table>
    <p class="rl__legend cx-note">On the facial row,
      <i class="rl__tick" aria-hidden="true"></i> is a constant that always answers neutral
      (${pct(f.constant.value)}), <i class="rl__tick rl__tick--ceil" aria-hidden="true"></i>
      the human ceiling (${pct(f.ceiling.value)}).${thin.length ? `
      ${thin.map((c) => esc(CHANNEL_META[c].label)).join(" and ")} read under half of this video.` : ""}</p>
  </section>`;
}

/* --- 3. what limits the reading ------------------------------------------

   BIAS_CAVEAT is required wherever a facial-derived score is surfaced.
   It is printed in full as the footnote to the scores on the overview, and
   again here beside the channel it is about, together with the vocal caveat.
   It is never collapsed, never behind a disclosure, and set at a reading
   size -- a disclosure in a pink box at the top of a report is shouted and
   then skipped; a note beside the thing it qualifies is read. */

function limitsPage(report) {
  const caveats = [report.bias_caveat, report.vocal_caveat].filter(Boolean);
  return `
  <section class="lm" data-act="weak" aria-labelledby="lm-h">
    <h2 id="lm-h" class="cx-h">What limits the reading</h2>
    ${caveats.length ? `
      <ol class="lm__notes">
        ${caveats.map((text, i) => {
          const facial = text === report.bias_caveat;
          return `
          <li class="lm__note" id="${facial ? "bias-caveat" : "vocal-caveat"}">
            <p class="lm__k"><span class="lm__n">${i + 1}</span>${facial ? "Facial emotion" : "Vocal prosody"}</p>
            <p class="cal__caveat">${esc(text)}</p>
            ${facial ? `<p class="lm__plus cx-note">Measured here: ${pct(CHANNEL_META.facial.accuracy)}
              on held-out speakers, below a constant that always answers neutral
              (${pct(FACIAL_REFERENCES.constant.value)}). None of nine models benched beat it, so the
              channel stays in, down-weighted to 0.342 when it is the only one dissenting.</p>` : ""}
          </li>`;
        }).join("")}
      </ol>`
      : `<p class="cal__caveat">This report carries no caveat text of its own. That is
           unusual and is stated rather than passed over: every report written by the
           current pipeline carries at least the facial bias disclosure.</p>`}
  </section>`;
}

/* --- 3. what the numbers are not, and who they are about ------------------

   Two pages restored on 25 Sep 2026 (INCLUSIVE_DESIGN.md A7). Both were built
   on 12 Sep and were lost when the report became a
   book; the written report (section 3.8) still says they are here.

   The first says what a reader must not conclude. The second is addressed to
   the one person the report is about and was never asked: the face on the
   title page. It is a statement written by the developer, not consultation,
   and says so; the honest version of "a route to contest" in a build with no
   server and no account is to say there is none and name what a deployed one
   would owe. The facial figures come from CHANNEL_META and FACIAL_REFERENCES,
   so the channel is never quoted without what it is worse than. */

function cannotTellPage() {
  const items = [
    ["Whether anyone was honest.",
      "Authenticity measures how far four automatic readings of the same seconds disagreed. It is not a judgement of sincerity, and a low score is not evidence of a lie."],
    ["Whether the product is any good.",
      "Brand health mixes the audience's tone with that disagreement. It says nothing about the product's quality."],
    ["How this video compares with another.",
      "Both scores depend on the video's length, its speaker, and which local model is installed on this machine, so they are read within one video, not ranked across several."],
    ["Anything outside English.",
      "The transcript, the comments and every sentence written about them are read as English."],
  ];
  return `
  <section class="lm" data-cannot-tell aria-labelledby="ct-h">
    <h2 id="ct-h" class="cx-h">What these numbers cannot tell you</h2>
    <ol class="lm__notes">
      ${items.map(([head, body], i) => `
        <li class="lm__note">
          <p class="lm__k"><span class="lm__n">${i + 1}</span>${esc(head)}</p>
          <p class="cal__caveat">${esc(body)}</p>
        </li>`).join("")}
    </ol>
  </section>`;
}

function standingPage() {
  return `
  <section class="lm" id="standing" data-standing tabindex="-1" aria-labelledby="st-h">
    <h2 id="st-h" class="cx-h">If you are the person in this video</h2>
    <ol class="lm__notes">
      <li class="lm__note">
        <p class="lm__k"><span class="lm__n">1</span>None of these numbers is a finding about you.</p>
        <p class="cal__caveat">They measure how far four automated readings of the same
          seconds drifted apart. A low Authenticity score is a disagreement between
          machines, not evidence that anyone was insincere, and it should not be
          repeated as though it were.</p>
      </li>
      <li class="lm__note">
        <p class="lm__k"><span class="lm__n">2</span>The reading taken from your face is the weakest here.</p>
        <p class="cal__caveat">It scored ${pct(CHANNEL_META.facial.accuracy)} on speakers it had
          never seen, below a constant that always answers neutral
          (${pct(FACIAL_REFERENCES.constant.value)}). Its usual mistake is to read a neutral
          face as a negative one.</p>
      </li>
      <li class="lm__note">
        <p class="lm__k"><span class="lm__n">3</span>There is no way to contest a reading in this build.</p>
        <p class="cal__caveat">It runs on one machine, with no server and no account.
          Everything behind the numbers stays on this machine and can be inspected: the
          frames that were sampled, what each channel returned, and the conflict score that
          followed. A deployed version would owe you three things this one does not have:
          a named person to contact, the right to see the frames a reading was drawn from,
          and a way to have a reading struck from a report.</p>
      </li>
    </ol>
  </section>`;
}

/* --- 3. measured, not used ------------------------------------------------ */

const MEASURES = [
  ["pitch", "Pitch", "Hz", "vocal", "mean fundamental frequency per segment, by autocorrelation"],
  ["energy", "Energy", "", "vocal", "mean short-term energy, unitless"],
  ["arousal", "Arousal", "", "vocal", "the one dimension the orchestrator reads, before thresholding"],
  ["valence", "Valence", "", "vocal", "recorded, never read"],
  ["dominance", "Dominance", "", "vocal", "recorded, never read"],
];

function measurePoints(segments, key) {
  const out = [];
  for (const segment of segments) {
    const mo = segment.model_outputs || {};
    let value = null;
    if (key === "pitch") value = mo.pitch_mean_hz;
    else if (key === "energy") value = mo.energy_mean;
    else {
      const dims = vocalDimensions(mo.vocal_emotion);
      value = dims ? dims[key] : null;
    }
    out.push(typeof value === "number" && Number.isFinite(value) ? value : null);
  }
  return out;
}

function measuresPanel(segments) {
  const rows = MEASURES.map(([key, label, unit, channel, note]) => {
    const points = measurePoints(segments, key);
    const real = points.filter((v) => v != null);
    return { key, label, unit, channel, note, points, real };
  }).filter((r) => r.real.length);

  return `
  <section class="me" data-act="measures" aria-labelledby="me-h">
    <h2 id="me-h" class="cx-h">Measured, and deliberately not scored</h2>
    <p class="cx-lede">
      The pipeline extracts these for every segment and the scorer reads none of
      them. They are printed because a number that was computed and discarded is
      part of what the run did, and hiding it would make the system look tidier
      than it is. Each line runs the length of the video.
    </p>
    ${rows.length ? `
    <ul class="me__list">
      ${rows.map((r) => {
        const lo = Math.min(...r.real);
        const hi = Math.max(...r.real);
        const mean = r.real.reduce((a, b) => a + b, 0) / r.real.length;
        return `
        <li class="me__row">
          <p class="me__id"><b>${esc(r.label)}</b><span>${esc(r.note)}</span></p>
          <span class="me__spark" data-spark="${r.key}" aria-hidden="true"></span>
          <dl class="me__stats">
            <div><dt>low</dt><dd class="t-read">${lo.toFixed(2)}${esc(r.unit)}</dd></div>
            <div><dt>mean</dt><dd class="t-read">${mean.toFixed(2)}${esc(r.unit)}</dd></div>
            <div><dt>high</dt><dd class="t-read">${hi.toFixed(2)}${esc(r.unit)}</dd></div>
            <div><dt>read on</dt><dd class="t-read">${count(r.real.length)} of ${count(r.points.length)}</dd></div>
          </dl>
        </li>`;
      }).join("")}
    </ul>` : `<p class="cx-note">This run recorded none of these measures.</p>`}
  </section>`;
}

/* --- 3. how a disagreement becomes a score --------------------------------- */

function methodPage(report, segments) {
  const n = segments.length;
  const flagged = segments.filter((s) => s.flagged).length;
  const zero = segments.filter((s) => s.conflict_score === 0).length;
  const damped = segments.map(damping).filter(Boolean);
  const byChannel = (ch) => damped.filter((d) => d.channel === ch);
  const weights = (list) => [...new Set(list.map((d) => d.weight.toFixed(3)))];
  const named = segments.filter((s) => conflictChannels(s).channels.size > 0).length;

  const reduced = ["facial", "vocal"].map((ch) => {
    const list = byChannel(ch);
    return list.length
      ? `${CHANNEL_META[ch].short.toLowerCase()} &times;${weights(list).join(", &times;")} on
         ${count(list.length)} segment${list.length === 1 ? "" : "s"}`
      : null;
  }).filter(Boolean);

  return `
  <section class="mt" aria-labelledby="mt-h">
    <h2 id="mt-h" class="cx-h">How a disagreement becomes a score</h2>
    <p class="cx-text">
      For every segment, the four readings are sent together to a language model
      running on this machine, the controller, which answers with a conflict score
      between 0 and 1. The two scores on the overview are built from those
      answers and nothing else.
    </p>
    <dl class="mt__figs">
      <div><dt>At or above the ${confidence(CONFLICT_FLAG_THRESHOLD)} threshold, so flagged and counted twice</dt>
        <dd><span class="t-read">${count(flagged)}</span> of ${count(n)}</dd></div>
      <div><dt>Scored exactly zero</dt>
        <dd><span class="t-read">${count(zero)}</span> of ${count(n)}</dd></div>
      <div><dt>Reduced because one weak channel was the only dissent</dt>
        <dd><span class="t-read">${count(damped.length)}</span> of ${count(n)}</dd></div>
      <div><dt>The controller named which channels were in conflict</dt>
        <dd><span class="t-read">${count(named)}</span> of ${count(n)}</dd></div>
    </dl>
    <p class="cx-note">
      When the only dissent comes from the facial or the vocal channel, the
      controller&rsquo;s score is multiplied by that channel&rsquo;s measured accuracy,
      so a channel that is usually wrong cannot flag a segment on its own.
      ${reduced.length ? `In this video: ${reduced.join("; ")}.`
        : "No segment in this video was reduced that way."}
    </p>
    <p class="cx-note">
      The controller can also name the channels it thought were in conflict.
      ${named === 0 ? "In this video it named none."
        : `In this video it did so on ${count(named)} of ${count(n)} segments.`}
      The reduction above does not depend on it: it also has a deterministic
      trigger that reads the pipeline&rsquo;s own channel labels and needs no
      model compliance.
    </p>
  </section>`;
}

/* --- 4. the audience ------------------------------------------------------ */

const SENTIMENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"];

function audiencePage(report) {
  const cs = report.comment_sentiment || {};
  const dist = cs.distribution || {};
  const tie = aggregateIsNearTie(dist);
  const comments = (report.all_comments || []).filter((c) => c && c.text);
  const total = Object.values(dist).reduce((a, b) => a + b, 0);
  const share = (k) => (total ? ((dist[k] || 0) / total) * 100 : 0);

  return `
  <section class="au" data-act="audience" aria-labelledby="au-h">
    <h2 id="au-h" class="cx-h">What the audience said</h2>
    <p class="cx-lede">
      One reading for the whole video. Comments are posted hours or days after
      it and cannot know which second they are about, so this channel has no
      time resolution and is drawn flat across the timeline.
    </p>
    ${total ? `
    <figure class="au__fig">
      <div class="au__band" role="img" aria-label="${SENTIMENTS.map((k) =>
        `${count(dist[k] || 0)} ${k.toLowerCase()}`).join(", ")}, of ${count(total)} comments">
        ${SENTIMENTS.map((k) => `<i data-k="${k}" style="--n:${dist[k] || 0}"></i>`).join("")}
      </div>
      <dl class="au__nums">
        ${SENTIMENTS.map((k) => `
          <div data-k="${k}"><dt><i class="cm__glyph" aria-hidden="true"></i>${k.toLowerCase()}</dt>
            <dd class="t-read">${count(dist[k] || 0)}</dd>
            <dd class="au__pct">${pct(share(k), 1)}</dd></div>`).join("")}
      </dl>
    </figure>` : `<p class="cx-note">No distribution of comment classes was recorded for this video.</p>`}
    <p class="au__verdict cx-text">${cs.label
      ? `Classified <b>${esc(cs.label.toLowerCase())}</b> overall${cs.confidence != null
        ? `, with a mean confidence of ${confidence(cs.confidence)}` : ""}, across
        ${count(cs.comment_count || comments.length)} comments.`
      : "No aggregate audience reading was recorded."}</p>
    ${tie && tie.nearTie ? `
      <p class="au__tie cx-note">
        This is close. ${esc(tie.top[0].toLowerCase())} leads
        ${esc(tie.second[0].toLowerCase())} by ${pct(tie.margin * 100, 1)} of the
        comments, so reporting the leading label as a verdict would overstate it.
        Both counts are above.
      </p>` : ""}
    <p class="cx-note">A sample of ${count(comments.length)} comments, each classified on
      its own. No author is stored, logged or shown anywhere in this system.</p>
  </section>`;
}

function audienceQuotesHead() {
  return `
  <div class="cm__head" data-act="audience-quotes">
    <h3 class="cx-h3">The comments, as classified</h3>
    <p class="cm__range" data-cm-range></p>
  </div>
  <ul class="cm__list" data-cx-flow data-comments></ul>
  <button class="cx-btn cm__showmore" type="button" data-more hidden>Show more comments</button>`;
}

const LONG_COMMENT = 420;
const CUT_COMMENT = 340;

/* A word boundary at or before `at`, so a long passage is never cut through a
   word. The cut is a disclosure the reader controls, never a clip: the whole
   text is one press away and the button says how long it is. */
function cutAt(text, at) {
  const slice = text.slice(0, at);
  const space = slice.lastIndexOf(" ");
  return (space > at * 0.6 ? slice.slice(0, space) : slice).replace(/[\s,.;:]+$/, "");
}

/* The comments are built once, as elements, and handed to the book to lay
   across as many spreads as they need. The classification is the one the
   pipeline wrote, under `label`; an older shape wrote `sentiment`, and a
   comment with neither is printed as unclassified rather than given one. */
function buildComments(report) {
  /* `src` is the comment's place in all_comments, which is how the written
     report cites it ("comment 12"); `i` is its place among those with text. */
  const comments = (report.all_comments || []).map((c, src) => ({ c, src }))
    .filter(({ c }) => c && c.text);
  const full = [];
  const items = comments.map(({ c, src }, i) => {
    const raw = typeof c.label === "string" ? c.label
      : typeof c.sentiment === "string" ? c.sentiment : "";
    const k = toValence(raw) || "";
    const text = String(c.text);
    const long = text.length > LONG_COMMENT;
    full.push(text);
    const li = document.createElement("li");
    li.className = "cm";
    li.dataset.i = String(i);
    li.dataset.src = String(src);
    if (k) li.dataset.k = k;
    li.innerHTML = `
      <blockquote class="cm__q" data-cm-text>${long ? `${esc(cutAt(text, CUT_COMMENT))}&hellip;` : esc(c.text)}</blockquote>
      <p class="cm__k">${k ? `<i class="cm__glyph" aria-hidden="true"></i>` : ""}
        <span>${raw ? esc(raw.toLowerCase()) : "unclassified"}</span>${
        typeof c.confidence === "number" ? `<span class="t-read">${confidence(c.confidence)}</span>` : ""}${
        long ? `<button class="cm__more" type="button" data-cm-more aria-expanded="false">Read all
          ${count(text.length)} characters</button>` : ""}</p>`;
    return li;
  });
  return { items, full };
}

/* --- 5. the ledger, folded out -------------------------------------------- */

const LEDGER_VIEWS = [
  { key: "all", label: "All", of: () => true },
  { key: "flagged", label: "Flagged", of: (s) => Boolean(s.flagged) },
  /* "Channels disagree" was true of 93 of 94 segments on one report and 132 of
     136 on another, which is a filter that narrows nothing. This one is the
     facial channel's documented failure mode instead: it calls 33.8% of
     verified-neutral held-out frames NEGATIVE, so segments where it reads
     negative over positive words are exactly where that error would show. */
  { key: "facevwords", label: "Face against words",
    of: (_s, v) => v.facial === "NEGATIVE" && v.transcript === "POSITIVE" },
  { key: "noface", label: "No face read", of: (_s, v) => !v.facial },
];

const LEDGER_SORTS = [
  { key: "time", label: "In time order", of: (a, b) => a.start_s - b.start_s },
  { key: "conflict", label: "Most conflict first",
    of: (a, b) => (b.conflict_score ?? -1) - (a.conflict_score ?? -1) },
];

function ledgerPanel(report, segments) {
  const cs = report.comment_sentiment;
  const counts = Object.fromEntries(LEDGER_VIEWS.map((v) => [
    v.key, segments.filter((s) => v.of(s, segmentValences(s, cs))).length,
  ]));

  return `
  <section class="le" data-act="ledger" aria-labelledby="le-h">
    <div class="le__top">
      <div class="le__intro">
        <h2 id="le-h" class="cx-h">Every segment</h2>
        <p class="cx-lede">
          The whole record, folded out. Filter it, reorder it, and pick any row to
          make it the current moment. Arrow keys move between rows.
        </p>
      </div>
      <div class="le__acts">
        <button class="cx-btn" type="button" data-cx-tomoment>Open the selected moment</button>
        <button class="cx-btn" type="button" data-cx-foldback>${ARROW("prev")} Fold back into the book</button>
      </div>
    </div>

    <div class="le__controls">
      <div class="le__group" role="group" aria-label="Filter the segments">
        ${LEDGER_VIEWS.map((v, i) => `
          <button class="chip" type="button" data-view="${v.key}"
                  aria-pressed="${i === 0}">${esc(v.label)}
            <span class="chip__n t-read">${count(counts[v.key])}</span></button>`).join("")}
      </div>
      <div class="le__group" role="group" aria-label="Order the segments">
        ${LEDGER_SORTS.map((s, i) => `
          <button class="chip" type="button" data-sort="${s.key}"
                  aria-pressed="${i === 0}">${esc(s.label)}</button>`).join("")}
      </div>
    </div>

    <p class="le__empty cx-note" data-empty hidden></p>

    <table class="le__table">
      <caption class="sr-only">Every segment, with each channel's reading and its
        conflict score</caption>
      <thead>
        <tr>
          <th scope="col">At</th>
          <th scope="col">Readings</th>
          <th scope="col">What was said</th>
          <th scope="col">Conflict</th>
        </tr>
      </thead>
      <tbody data-ledger></tbody>
    </table>

    <p class="le__end">
      <button class="cx-btn" type="button" data-cx-foldback>${ARROW("prev")} Fold back into the book</button>
    </p>
  </section>`;
}

function ledgerRow(report, segment) {
  const v = segmentValences(segment, report.comment_sentiment);
  const cs = segment.conflict_score ?? 0;
  return `
  <tr data-seg="${segment.segment_id}"${segment.flagged ? " data-flag" : ""} tabindex="-1">
    <th scope="row" class="t-time">${mmss(segment.start_s)}</th>
    <td>
      <span class="le__glyphs" aria-hidden="true">
        ${CHANNELS.map((c) => `<i data-channel="${c}" data-v="${v[c] || "none"}"
             style="--ch:var(--ch-${c})"></i>`).join("")}
      </span>
      <span class="sr-only">${CHANNELS
        .map((c) => `${CHANNEL_META[c].short} ${v[c] ? v[c].toLowerCase() : "not measured"}`)
        .join(", ")}.</span>
    </td>
    <td class="le__txt">${esc(segment.text || "")}</td>
    <td class="le__cs">
      <span class="le__bar" style="--to:${(cs * 100).toFixed(1)}%"></span>
      <span class="t-read">${confidence(segment.conflict_score)}</span>
      ${segment.flagged ? '<span class="sr-only">Flagged.</span>' : ""}
    </td>
  </tr>`;
}

/* --- wiring --------------------------------------------------------------- */

const LONG_QUOTE = 460;
const CUT_QUOTE = 380;

function wireMoment(report, segments, videoId, man) {
  const cs = report.comment_sentiment;
  const img = root.querySelector("[data-frame]");
  const none = root.querySelector("[data-noframe]");
  const cap = root.querySelector("[data-cap]");
  const at = root.querySelector("[data-at]");
  const pos = root.querySelector("[data-pos]");
  const flag = root.querySelector("[data-flagged]");
  const said = root.querySelector("[data-said]");
  const more = root.querySelector("[data-said-more]");
  const rows = root.querySelector("[data-rows]");
  const verdict = root.querySelector("[data-verdict]");
  const why = root.querySelector("[data-why]");
  const flagPos = root.querySelector("[data-mo-flagpos]");
  const flagged = segments.filter((s) => s.flagged);

  let text = "";
  let open = false;
  const paintSaid = () => {
    const long = text.length > LONG_QUOTE;
    said.textContent = text
      ? `“${long && !open ? `${cutAt(text, CUT_QUOTE)}…` : text}”` : "";
    said.hidden = !text;
    /* The size follows the length, so a two-line quote has the presence of a
       pull quote and a paragraph-long one is still comfortable to read. */
    said.dataset.size = text.length > 300 ? "s" : text.length > 140 ? "m" : "l";
    more.hidden = !long;
    more.textContent = open ? "Show less of this segment"
      : `Show all ${count(text.length)} characters of this segment`;
    more.setAttribute("aria-expanded", String(open));
  };
  more.addEventListener("click", () => { open = !open; paintSaid(); });

  return function show(segment) {
    if (!segment) return;
    /* The position in the run, not the stored id: segment_id is zero-based on
       disk, so "segment 0 of 94" reads as an off-by-one bug. The stored id
       still drives the ledger and the transport. */
    const position = segments.indexOf(segment) + 1;
    at.textContent = `${mmss(segment.start_s)} to ${mmss(segment.end_s)}`;
    pos.textContent = `Segment ${count(position)} of ${count(segments.length)}, ${mmss(segment.start_s)} to ${mmss(segment.end_s)}`;
    flag.hidden = !segment.flagged;

    text = segment.text || "";
    open = false;
    paintSaid();

    rows.innerHTML = CHANNELS.map((c) => readRow(segment, c, cs)).join("");

    const valences = segmentValences(segment, cs);
    const present = Object.values(valences);
    const distinct = new Set(present).size;
    verdict.textContent = present.length < 2
      ? "Fewer than two channels read this segment, so there is nothing to compare."
      : distinct === 1
        ? `All ${present.length} channels that read this segment agree.`
        : `${distinct} different readings of the same segment.`;
    verdict.classList.toggle("is-tear", Boolean(segment.flagged));

    why.innerHTML = whyPanel(segment);

    const url = plateFor(man, videoId, segment);
    if (url) {
      img.src = url;
      img.alt = `A frame this run analysed at ${mmss((segment.start_s + segment.end_s) / 2)}.`;
      img.hidden = false;
      none.hidden = true;
    } else {
      img.hidden = true;
      none.hidden = false;
    }
    const frames = facialFrameCount(segment);
    cap.textContent = hasImagery(man, videoId)
      ? `The segment midpoint${frames != null
          ? `, one of ${count(frames)} frame${frames === 1 ? "" : "s"} the facial channel pooled` : ""}.`
      : "No imagery was derived for this video.";

    if (flagged.length) {
      const i = flagged.indexOf(segment);
      flagPos.textContent = i >= 0
        ? `Flagged ${count(i + 1)} of ${count(flagged.length)}`
        : `${count(flagged.length)} flagged`;
    }
  };
}

function wireMomentNav(segments, clock) {
  const flagged = segments.filter((s) => s.flagged);
  for (const b of root.querySelectorAll("[data-mo-step]")) {
    b.addEventListener("click", () => clock.step(Number(b.dataset.moStep)));
  }
  const flagsBox = root.querySelector("[data-mo-flags]");
  if (!flagged.length) {
    flagsBox.innerHTML = `<span class="mo__navl">No segment in this run was flagged</span>`;
    return;
  }
  for (const b of root.querySelectorAll("[data-mo-flag]")) {
    b.addEventListener("click", () => {
      const dir = Number(b.dataset.moFlag);
      const now = clock.t;
      const next = dir > 0
        ? flagged.find((s) => s.start_s > now + 0.02) || flagged[0]
        : [...flagged].reverse().find((s) => s.start_s < now - 0.02) || flagged[flagged.length - 1];
      clock.set(next.start_s + 0.01, { reason: "jump" });
    });
  }
}

function wireLedger(report, segments, clock) {
  const body = root.querySelector("[data-ledger]");
  const empty = root.querySelector("[data-empty]");
  if (!body) return () => {};

  let view = LEDGER_VIEWS[0];
  let sort = LEDGER_SORTS[0];
  let shown = [];

  function paint() {
    const cs = report.comment_sentiment;
    shown = segments
      .filter((s) => view.of(s, segmentValences(s, cs)))
      .sort(sort.of);
    body.innerHTML = shown.map((s) => ledgerRow(report, s)).join("");
    const none = shown.length === 0;
    empty.hidden = !none;
    if (none) {
      empty.textContent = view.key === "facevwords"
        ? "No segment in this run has the face reading negative while the words read positive. "
          + "That is a finding about this video, not an empty table."
        : "No segment in this run matches that filter.";
    }
    mark(clock.segment);
  }

  /* One Tab stop into the ledger -- the current row, or the first -- and the
     arrow keys between rows (the handler below). Every row used to be
     tabindex="-1" with nothing ever set to 0, so the arrow keys worked only for
     a reader who had clicked a row first (INCLUSIVE_DESIGN.md A13). */
  function mark(segment) {
    const rows = body.querySelectorAll("tr[data-seg]");
    for (const tr of rows) { tr.removeAttribute("aria-current"); tr.tabIndex = -1; }
    const row = segment ? body.querySelector(`tr[data-seg="${segment.segment_id}"]`) : null;
    if (row) row.setAttribute("aria-current", "true");
    const stop = row || rows[0];
    if (stop) stop.tabIndex = 0;
  }

  for (const button of root.querySelectorAll("[data-view]")) {
    button.addEventListener("click", () => {
      view = LEDGER_VIEWS.find((v) => v.key === button.dataset.view) || LEDGER_VIEWS[0];
      for (const other of root.querySelectorAll("[data-view]")) {
        other.setAttribute("aria-pressed", String(other === button));
      }
      paint();
      announce(`${view.label}. ${shown.length} segment${shown.length === 1 ? "" : "s"}.`);
    });
  }

  for (const button of root.querySelectorAll("[data-sort]")) {
    button.addEventListener("click", () => {
      sort = LEDGER_SORTS.find((s) => s.key === button.dataset.sort) || LEDGER_SORTS[0];
      for (const other of root.querySelectorAll("[data-sort]")) {
        other.setAttribute("aria-pressed", String(other === button));
      }
      paint();
      announce(sort.label);
    });
  }

  /* A row drives the clock. The ledger and the moment are the same document
     seen two ways, so pressing a row makes it the current moment rather than
     opening anything; "Open the selected moment" then turns to it. */
  body.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-seg]");
    if (!row) return;
    const segment = segments.find((s) => String(s.segment_id) === row.dataset.seg);
    if (segment) clock.set(segment.start_s + 0.01, { reason: "jump" });
  });

  body.addEventListener("keydown", (event) => {
    const row = event.target.closest("tr[data-seg]");
    if (!row) return;
    const keys = { ArrowDown: 1, ArrowUp: -1 };
    if (event.key in keys) {
      const all = [...body.querySelectorAll("tr[data-seg]")];
      const next = all[all.indexOf(row) + keys[event.key]];
      if (next) { row.tabIndex = -1; next.tabIndex = 0; next.focus(); next.click(); }
      event.preventDefault();
    }
    if (event.key === "Enter" || event.key === " ") { row.click(); event.preventDefault(); }
  });

  paint();
  return mark;
}

function wireSparks(segments) {
  for (const host of root.querySelectorAll("[data-spark]")) {
    const points = measurePoints(segments, host.dataset.spark);
    const real = points.filter((v) => v != null);
    if (!real.length) continue;
    const lo = Math.min(...real);
    const hi = Math.max(...real);
    const span = hi - lo || 1;
    /* A gap stays a gap: a segment with no reading breaks the line rather than
       being drawn at the midpoint. */
    const d = points.map((v, i) => {
      if (v == null) return null;
      const x = (i / Math.max(1, points.length - 1)) * 100;
      const y = 100 - ((v - lo) / span) * 100;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });
    let path = "";
    let open = false;
    for (const point of d) {
      if (point == null) { open = false; continue; }
      path += `${open ? "L" : "M"}${point} `;
      open = true;
    }
    host.innerHTML = `<svg viewBox="0 0 100 100" preserveAspectRatio="none"
      aria-hidden="true"><path d="${path.trim()}" fill="none"
      stroke="var(--ch-vocal)" stroke-width="1.4" vector-effect="non-scaling-stroke"/></svg>`;
  }
}

/* --- the sweep-member bar ------------------------------------------------ */

function memberBar(context) {
  if (!context) return "";
  return `
  <nav class="member" aria-label="This video inside a combined report">
    <a class="member__back" href="/brand/${encodeURIComponent(context.sweepId)}">
      Back to the combined report</a>
    <p class="member__which">Video ${context.index} of ${context.total}${
      context.subject ? ` on ${esc(context.subject)}` : ""}</p>
    <div class="member__kin">
      ${context.prev ? `<a href="${context.prev}">Previous video</a>` : ""}
      ${context.next ? `<a href="${context.next}">Next video</a>` : ""}
    </div>
  </nav>`;
}

/* --- boot ----------------------------------------------------------------- */

async function main() {
  mountAnnouncer();
  mountAll({ here: "/library" });

  /* Claimed before anything is fetched, so the page knows whether it is being
     opened out of a volume or arrived at directly. The stash is single-use, so
     a reload or a back-button return gets the plain page -- which is right:
     the second time you look at a report you did not just take it down. */
  const carried = takeVolume();

  const source = sourceFromPath();
  if (source.kind === "none") {
    fail("No report named", "This address does not name a report.",
      "A report is opened from the library, which lists everything saved on this machine.",
      '<a class="btn" href="/library">Open the library</a>');
    return;
  }

  let report = null;
  let context = null;
  try {
    if (source.kind === "member") {
      const { getSweep, getSweepMember } = await import("../lib/api.js");
      report = await getSweepMember(source.sweepId, source.videoId);
      try {
        const sweep = await getSweep(source.sweepId);
        const members = sweep.members || [];
        const i = members.findIndex((m) => m.video_id === source.videoId);
        if (i >= 0) {
          const link = (m) => m
            ? `/brand/${encodeURIComponent(source.sweepId)}/${encodeURIComponent(m.video_id)}`
            : null;
          context = {
            sweepId: source.sweepId, index: i + 1, total: members.length,
            subject: sweep.subject || sweep.query || "",
            title: members[i].title || "", channel: members[i].channel || "",
            prev: link(members[i - 1]), next: link(members[i + 1]),
          };
        }
      } catch { /* the member still reads on its own */ }
      report.__filename = report.brand_name
        ? `${report.brand_name} (${report.product_name || ""}).json` : "";
    } else {
      report = await getReport(source.filename);
      report.__filename = source.filename;
    }
  } catch (error) {
    if (error && error.status === 404) {
      fail("Not found", "There is no report saved under that name.",
        "It may have been renamed or removed from the outputs directory since the "
        + "link was made.",
        '<a class="btn" href="/library">Open the library</a>');
    } else {
      fail("Unreachable", "The report could not be read.",
        `The backend answered: ${esc((error && error.message) || "no reason given")}. `
        + "Reports are plain JSON in this machine's own <code>outputs/</code> directory, "
        + "so this is a local read rather than a network problem.",
        '<a class="btn" href="/library">Open the library</a>');
    }
    return;
  }

  const segments = (report.all_segments || []).filter(
    (s) => typeof s.start_s === "number" && typeof s.end_s === "number");

  if (!segments.length) {
    fail("Empty run", "This report has no segments.",
      "It was written without any, which means transcription produced nothing to "
      + "align the other three channels to. There is nothing to draw and nothing to score.",
      '<a class="btn" href="/library">Open the library</a>');
    return;
  }

  /* The written report, or its facts computed live when the model has not
     written one yet. A failure here costs only the new pages: the book falls
     back to the chapters it had before. */
  let analysis = null;
  try {
    const { getReportAnalysis, getMemberAnalysis } = await import("../lib/api.js");
    analysis = source.kind === "member"
      ? await getMemberAnalysis(source.sweepId, source.videoId)
      : await getReportAnalysis(source.filename);
    if (!analysis || !analysis.facts) analysis = null;
  } catch { analysis = null; }
  const command = source.kind === "member"
    ? `python write_analysis.py --sweep ${source.sweepId} --member ${source.videoId}`
    : `python write_analysis.py --report "${source.filename}"`;

  const flaggedCount = (report.flagged_segments || []).length
    || segments.filter((s) => s.flagged).length;
  const man = await manifest();
  const videoId = videoIdOf(report);
  const cov = coverage(segments, report.comment_sentiment);
  const worst = mostContested(segments);
  const duration = Math.max(...segments.map((s) => s.end_s));

  /* Set before the document is written, not after, so the book is never
     painted at full strength and then hidden a frame later. */
  if (carried) root.dataset.opening = "yes";

  const { brand, product } = splitReportName(report.__filename || "");
  const title = {
    brand: context && context.title ? context.title : (brand || report.brand_name || "Untitled"),
    product: context && context.title ? (context.channel || "") : product,
    kicker: context
      ? `Video ${context.index} of ${context.total}${context.subject ? ` in ${esc(context.subject)}` : ""}`
      : "One video, read four ways",
    plate: plateFor(man, videoId, worst),
    worst,
    duration,
    segments: segments.length,
    comments: (report.all_comments || []).length,
    videoId,
    /* Built from the id rather than taken from report.video_url: the link says
       "on YouTube", and a report file copied in from elsewhere could otherwise
       carry any address, a javascript: one included. */
    videoUrl: videoId ? `https://www.youtube.com/watch?v=${videoId}` : "",
    /* The video's own name for the source line, never its id: the sweep's
       record first, then what YouTube told the written report. */
    videoTitle: String((context && context.title)
      || (analysis && analysis.video_meta && analysis.video_meta.fetched && analysis.video_meta.title)
      || report.video_title || "").trim(),
    onShelf: !context,
    short: analysis ? inShort(analysis) : "",
  };
  const runningTitle = [title.brand, context ? "" : title.product].filter(Boolean).join(", ");

  /* The comments continue over as many spreads as they need. The first two
     pages of every continuation are laid out the same way, so the chapter
     reads as one run of comments rather than a new section per spread. */
  const commentPage = () => `
    <p class="cm__range cm__range--cont" data-cm-range></p>
    <ul class="cm__list" data-cx-flow></ul>`;

  const segById = new Map(segments.map((s) => [s.segment_id, s]));
  const topicById = new Map(((analysis && analysis.reading && analysis.reading.topics) || [])
    .map((t) => [t.id, t]));
  const lookup = {
    segment: (n) => segById.get(n) || null,
    comment: (n) => (report.all_comments || [])[n] || null,
    topic: (id) => topicById.get(id) || null,
  };
  const frameFor = (m) => {
    const seg = segById.get(m.seg);
    return seg ? plateFor(man, videoId, seg) : null;
  };
  const claimsPage = () => `<ul class="cl__list" data-cx-flow></ul>`;
  const hasClaims = Boolean(analysis && analysis.reading && analysis.reading.claims.length);

  /* THE WRITTEN REPORT'S BOOK (23 Sep 2026).

     Six chapters, in the order a reader asks the questions: what does it say
     (Overview), what did the reviewer say about what (What they said), what
     does the audience say (Audience), where do the readings stop agreeing
     (Key moments), how far can I trust it and could it be paid (Trust), and
     the whole record (Evidence). The caveats, the reliability of each channel
     and how a disagreement becomes a score are all still here, once, in
     Trust, rather than on every page. Without an analysis the book is the one
     it was before. */
  const chapters = analysis ? [
    { id: "overview", label: "Overview", spreads: [
      spread({ key: "overview", plain: ["verso", "recto"], verso: titlePage(title),
        recto: findingsPage(report, segments, flaggedCount, cov, worst, analysis, lookup) }),
      spread({ key: "overview-2", verso: takeawaysPage(analysis, lookup, command),
        recto: agreementPage(analysis, lookup) })] },
    { id: "said", label: "What they said", spreads: [
      spread({ key: "said-tone", wide: true, verso: tonePage(analysis, report, lookup) }),
      spread({ key: "said", verso: timePage(analysis, command), recto: topicsPage(analysis, command) }),
      ...(hasClaims ? [spread({ key: "said-claims", verso: claimsPage(), recto: claimsPage() })] : [])] },
    { id: "audience", label: "Audience", spreads: [
      spread({ key: "audience-talk", verso: talkPage(analysis, lookup, command),
        recto: askPage(analysis, lookup, command) }),
      spread({ key: "audience", verso: audiencePage(report), recto: audienceQuotesHead() })] },
    { id: "moments", label: "Key moments", spreads: [
      spread({ key: "moments-odd", wide: true,
        verso: oddMomentsPage(analysis, report, lookup, frameFor, command) }),
      spread({ key: "moments", plain: ["verso"], verso: momentPlate(), recto: momentRead() })] },
    { id: "channels", label: "Trust", spreads: [
      spread({ key: "trust", verso: trustPage(analysis), recto: signsPage(analysis, lookup) }),
      spread({ key: "channels",
        verso: reliabilityPage(report, segments), recto: limitsPage(report) }),
      spread({ key: "channels-2",
        verso: measuresPanel(segments), recto: methodPage(report, segments) }),
      spread({ key: "standing", verso: cannotTellPage(), recto: standingPage() })] },
    { id: "evidence", label: "Evidence", spreads: [spread({
        key: "evidence", wide: true, verso: ledgerPanel(report, segments) })] },
  ].map((c) => ({ ...c, html: chapter(c) })) : [
    { id: "overview", label: "Overview", spreads: [spread({
        /* A chapter's opening spread carries no running heads, as in print.
           On this one the recto's cost a line the facial disclosure needed:
           at 1512x860 it was the part of the page that scrolled out of view. */
        key: "overview", plain: ["verso", "recto"],
        verso: titlePage(title),
        recto: findingsPage(report, segments, flaggedCount, cov, worst) })] },
    { id: "moments", label: "Key moments", spreads: [spread({
        key: "moments", plain: ["verso"],
        verso: momentPlate(), recto: momentRead() })] },
    { id: "channels", label: "Four channels", spreads: [
        spread({ key: "channels",
          verso: reliabilityPage(report, segments), recto: limitsPage(report) }),
        spread({ key: "channels-2",
          verso: measuresPanel(segments), recto: methodPage(report, segments) }),
        spread({ key: "standing", verso: cannotTellPage(), recto: standingPage() })] },
    { id: "audience", label: "Audience", spreads: [spread({
        key: "audience", verso: audiencePage(report), recto: audienceQuotesHead() })] },
    { id: "evidence", label: "Evidence", spreads: [spread({
        key: "evidence", wide: true, verso: ledgerPanel(report, segments) })] },
  ].map((c) => ({ ...c, html: chapter(c) }));

  root.dataset.codex = "yes";
  root.innerHTML = `
    ${memberBar(context)}
    ${codexShell({
      title: esc(runningTitle || "this report"),
      chapters,
      backHref: context ? `/brand/${encodeURIComponent(context.sweepId)}` : "/library",
      backLabel: context ? "Back to the combined report" : "Close the book",
    })}`;

  const clock = createClock(duration, segments);
  const showMoment = wireMoment(report, segments, videoId, man);
  const markRow = wireLedger(report, segments, clock);

  mountTransport(root.querySelector("[data-transport]"), {
    report, segments, clock,
    onSegment: (segment) => { showMoment(segment); markRow(segment); },
  });

  clock.set(segments[0].start_s + 0.01, { reason: "boot" });
  showMoment(segments[0]);
  wireMomentNav(segments, clock);
  wireSparks(segments);

  /* THE BOOK IS BOUND LAST.

     Everything above queried a document in which every chapter is present, so
     all of it is wired against real elements whichever spread is on the desk.
     Only now is the book laid out and all but one spread put away. */
  let lastSpread = "overview";
  const book = wireCodex(root, {
    title: runningTitle,
    onSpread: (s) => {
      if (!s.hasAttribute("data-wide")) lastSpread = s.dataset.cxKey;
      animateIn(s);
    },
  });

  /* The reviewer's claims continue over as many spreads as they need, the
     same way the comments do. */
  if (book && hasClaims) {
    book.flow({
      chapter: "said",
      items: claimItems(analysis, lookup),
      cont: (n) => spread({ key: `said-claims-${n}`, cont: true,
        verso: claimsPage(), recto: claimsPage() }),
    });
  }

  const { items, full } = buildComments(report);
  const showMore = root.querySelector("[data-more]");
  let limit = 12;
  const narrowLimit = () => {
    items.forEach((it, i) => { it.hidden = i >= limit; });
    showMore.hidden = limit >= items.length;
  };
  if (book) {
    book.flow({
      chapter: "audience",
      items,
      cont: (n) => spread({ key: `audience-${n}`, cont: true,
        verso: commentPage(), recto: commentPage() }),
      /* Every comment is measured visible. On a single page, where there are
         no spreads to carry them onto, they arrive twelve at a time instead of
         as one very long page, and the button says how many more there are. */
      prepare: () => { for (const it of items) it.hidden = false; showMore.hidden = true; },
      after: (regions) => {
        if (!book.isWide()) {
          narrowLimit();
          const range = root.querySelector("[data-cm-range]");
          if (range) range.textContent = `${count(items.length)} comments`;
          return;
        }
        for (const r of regions) {
          const list = r.querySelectorAll("li[data-i]");
          const range = r.parentElement.querySelector("[data-cm-range]");
          if (!range) continue;
          /* The chapter can end on a verso. Its facing page says so rather
             than standing blank, the way a book marks the end of a section. */
          if (!list.length) { range.textContent = `End of the comments, all ${count(items.length)} shown`; continue; }
          const a = Number(list[0].dataset.i) + 1;
          const b = Number(list[list.length - 1].dataset.i) + 1;
          range.textContent = `Comments ${count(a)} to ${count(b)} of ${count(items.length)}`;
        }
      },
    });
  }
  showMore.addEventListener("click", () => {
    limit += 24;
    narrowLimit();
    announce(`Showing ${Math.min(limit, items.length)} of ${items.length} comments.`);
  });
  root.addEventListener("click", (event) => {
    const b = event.target.closest("[data-cm-more]");
    if (!b) return;
    const li = b.closest("li[data-i]");
    const q = li.querySelector("[data-cm-text]");
    const text = full[Number(li.dataset.i)];
    const opening = b.getAttribute("aria-expanded") !== "true";
    q.textContent = opening ? text : `${cutAt(text, CUT_COMMENT)}…`;
    b.setAttribute("aria-expanded", String(opening));
    b.textContent = opening ? "Show less" : `Read all ${count(text.length)} characters`;
  });

  /* CLOSING PUTS THIS VOLUME BACK IN YOUR HAND.

     The id is the shelf's own id for this volume, so the shelf can take the
     same book down again rather than opening on nothing. Recorded on the close
     control, and again on `pagehide` so the browser's Back button lands the
     same way — takeReturn() is what decides whether an unload was really a
     way back, and it only honours one on a back/forward navigation. */
  const volumeId = context
    ? `sweep:${context.sweepId}`
    : `run:${report.__filename || source.filename || ""}`;
  wireClose(root, {
    link: root.querySelector("[data-cx-close]"),
    cover: carried && carried.cover,
    before: () => stashReturn(volumeId, "close"),
  });
  window.addEventListener("pagehide", () => stashReturn(volumeId, "leave"));

  /* A moment picked anywhere in the book is answered on the moments spread. */
  if (book) {
    /* The moment spread is the chapter's second since the written report
       put the three moments that do not add up in front of it. */
    const toMoment = () => {
      const m = root.querySelector('[data-cx-key="moments"]');
      if (m) book.reveal(m); else book.goChapter("moments");
    };
    for (const b of root.querySelectorAll("[data-cx-tomoment]")) {
      b.addEventListener("click", toMoment);
    }

    /* Evidence. A time goes to that moment, a comment number to that comment,
       a topic to the topics spread. */
    const openEvidence = (id) => {
      const kind = id[0];
      const n = Number(id.slice(1));
      if (kind === "S") {
        const seg = segById.get(n);
        if (!seg) return;
        clock.set(seg.start_s + 0.01, { reason: "evidence" });
        toMoment();
      } else if (kind === "C") {
        const li = root.querySelector(`.cm[data-src="${n}"]`);
        if (!li) return;
        li.hidden = false;
        book.reveal(li);
        li.setAttribute("tabindex", "-1");
        requestAnimationFrame(() => li.focus({ preventScroll: true }));
      } else if (kind === "T") {
        const t = root.querySelector('[data-cx-key="said"]');
        if (t) book.reveal(t);
      }
    };
    root.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-ev]");
      if (chip) openEvidence(chip.dataset.ev);
    });

    /* The combined book's evidence arrives as an address: ?at=<segment> opens
       that moment, ?c=<comment> that comment. Anything else is ignored. */
    const query = new URLSearchParams(window.location.search);
    const at = query.get("at"), c = query.get("c");
    const deep = /^\d{1,5}$/.test(at || "") ? `S${Number(at)}` : /^\d{1,5}$/.test(c || "") ? `C${Number(c)}` : null;
    if (deep) requestAnimationFrame(() => openEvidence(deep));
    for (const link of root.querySelectorAll("[data-cx-goto-trust]")) {
      link.addEventListener("click", (event) => { event.preventDefault(); book.goChapter("channels"); });
    }
    for (const b of root.querySelectorAll("[data-cx-foldback]")) {
      b.addEventListener("click", () => {
        const back = root.querySelector(`[data-cx-key="${CSS.escape(lastSpread)}"]`);
        if (back) book.reveal(back); else book.goChapter("moments");
      });
    }
    const all = root.querySelector("[data-mo-all]");
    all.addEventListener("click", (event) => { event.preventDefault(); book.goChapter("evidence"); });
  }

  /* The frame carried in from the opening page or a combined report lands here. */
  playFlip(root.querySelector('[data-flip-id="report-frame"]'));

  /* The boot panel has been replaced, so the flag that suppressed it has done
     its job and should not be left on the document. */
  delete document.documentElement.dataset.carrying;

  /* One frame, so the opening measures a laid-out book. */
  requestAnimationFrame(() => openBook(root, carried));

  document.title = `${runningTitle || "Report"} — BrandPulse`;
  clearTimeout(window.__bpFallback);
}

main();
