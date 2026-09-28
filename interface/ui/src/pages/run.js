/* ===========================================================================
   run.js — starting an analysis, and watching it.

   THE WAIT IS THE POINT OF THIS PAGE.

   A run takes four to nine minutes and somebody sits and watches it. The build
   this replaces gave them a progress bar with four labels next to it. Here the
   instrument assembles itself: four empty lanes at the start, each one armed,
   scanned and then marked recorded as its stage completes, with a real clock
   and the real stage names.

   WHAT IT DOES NOT DO IS DRAW DATA IT DOES NOT HAVE.

   There is no trace on this screen, because nothing has been measured yet.
   Inventing a plausible-looking one to fill the lanes would be fabricating a
   measurement, which is the one thing this project never does. The lanes are
   drawn EMPTY and say so. The instrument is what gets built here; the readings
   arrive on the report.

   The one live reading on this screen is honest and is the product's own
   central claim made watchable: THE APERTURE. Three of the five stages reach a
   network (the comment fetch, the video download, and the written report's one
   lookup of the video's paid-promotion label) and two do not. While a network
   stage is running the aperture is open and says so; the rest of the time the
   chassis is sealed. The long stages are local, so over nine minutes you can
   watch the thing be sealed for most of them.
   ======================================================================== */

import "../styles/tokens.css";
import "../styles/chassis.css";
import "../styles/transport.css";
import "../styles/run.css";
import "../styles/run-scene.css";

import { mountAll } from "../lib/chrome.js";
import { mountAnnouncer, announce } from "../lib/announce.js";
import {
  activeJob, jobStatus, startJob, cancelJob,
  sweepSearch, sweepStart, sweepStatus, cancelSweep,
} from "../lib/api.js";
import { CHANNELS, CHANNEL_META } from "../lib/contract.js";
import { count, esc, mmss, pct, score } from "../lib/format.js";
import { reduced } from "../lib/motion.js";

const root = document.querySelector("[data-run]");

const POLL_MS = 1500;
const SWEEP_SIZE = 5;
const BASE_TITLE = "Analyse — BrandPulse";

/* ------------------------------------------------------------------- modes
   Three things this page can be asked to do. One video is the original; the
   other two analyse five videos about a subject and combine them, because this
   is sold as brand sentiment analysis and one video is not a brand.

   They are one mechanism with two framings. A brand query returns whatever
   that maker has shipped recently; a product query returns one thing reviewed
   by several people. The machinery underneath does not know the difference,
   but the reader does, and the wording follows the reader. */

const MODES = Object.freeze({
  video: {
    key: "video",
    tab: "One video",
    title: "Look closer.",
    lede: "The words. The expression. The voice. The audience. "
        + "Read one video from four perspectives—and find where they disagree.",
  },
  brand: {
    key: "brand",
    tab: "A brand",
    title: "Beyond the brand.",
    lede: "It finds five recent reviews of whatever that maker has shipped, runs "
        + "all five through the same four channels, and reports both the average "
        + "and how far apart the five ended up.",
    label: "Brand",
    placeholder: "Samsung",
    hint: "A maker. Five of their recent reviews will be found.",
  },
  product: {
    key: "product",
    tab: "A product",
    title: "Every perspective.",
    lede: "It finds five recent reviews of the same thing, runs all five through "
        + "the same four channels, and reports both the average and how far apart "
        + "the five reviewers ended up.",
    label: "Product",
    placeholder: "iPhone 18 Pro Max",
    hint: "One product. Five reviews of it will be found.",
  },
});

/* The four windows the backend offers, in the order it offers them, with the
   length sweep.py's WINDOWS gives each (a contract test keeps the two equal).
   The length is here only to say how far back each one may end. */
const WINDOWS = [
  ["week", "Last week", 7],
  ["month", "Last month", 30],
  ["half", "Last 6 months", 182],
  ["year", "Last year", 365],
];

/* Where that window ends, in days back from today (sweep.py
   offset_window_bounds). A window that ends earlier shares no days with a
   recent one of the same length, which is what makes a before-and-after
   honest: two windows that both end today are nested, not two periods. It
   may end at most one window back (sweep.py offset_problem): "last week,
   ending a year ago" is not last week. */
const ENDINGS = [
  ["0", "Today"],
  ["7", "A week ago"],
  ["30", "A month ago"],
  ["91", "Three months ago"],
  ["182", "Six months ago"],
  ["365", "A year ago"],
];

/* The five stages, tied to app.py `_STAGES` by index. `reaches` is the honest
   part: which stages touch a network. A contract test asserts the labels here
   still match the ones the backend reports. The fifth, added 23 Sep 2026, is
   the written report: the same local model reads the finished run and writes
   it up, after one YouTube lookup for the creator's own paid-promotion label. */
const STAGES = [
  {
    records: ["audience"],
    label: "Fetching and classifying audience comments",
    spoken: "fetching and classifying audience comments",
    what: "The Data API returns the video's comments, relevance-ranked, and each "
        + "one is classified on its own. Author identifiers are never stored.",
    reaches: "The YouTube Data API, for the comments.",
  },
  {
    /* One stage genuinely records three channels: Whisper sets the segment
       boundaries and the face and the voice are then read against them. */
    records: ["transcript", "facial", "vocal"],
    label: "Downloading, transcribing, reading the face and the voice",
    spoken: "downloading the video, transcribing it, and reading the face and the "
          + "voice. This is the long stage",
    what: "yt-dlp fetches the video and Whisper transcribes it, which is what sets "
        + "the segment boundaries every other channel aligns to. The face and the "
        + "voice are then read against those boundaries. This is the long one.",
    reaches: "YouTube, for the video itself.",
  },
  {
    /* Records nothing. By this point all four channels are on disk and the
       controller is reading them, which is what the fifth row shows. */
    records: [],
    label: "Scoring cross-modal conflicts",
    spoken: "scoring cross-modal conflicts, one local model call per segment",
    what: "Every segment goes to the local controller as four separate readings "
        + "and it answers where they stop agreeing. One call per segment, on this "
        + "machine.",
    reaches: null,
  },
  {
    records: [],
    label: "Computing the final scores",
    spoken: "computing the final scores",
    what: "Flagged segments count twice toward Authenticity; Brand Health is 60% "
        + "of the audience reading and 40% of that.",
    reaches: null,
  },
  {
    /* Records nothing new. The controller reads the finished run a second
       time and writes the report; every figure in it is computed by code and
       every sentence is checked against the run before it is kept. */
    records: [],
    label: "Writing the report",
    spoken: "writing the report with the local model",
    what: "The local model reads the finished run and writes what the reviewer "
        + "liked and disliked, what the audience talks about and whether the two "
        + "agree. Every figure comes from the run, and every sentence is checked "
        + "against it before it is kept.",
    reaches: "The YouTube Data API, once, for the video's own paid-promotion "
           + "label and its description. The report is written on this machine.",
  },
];

function setTitle(prefix) {
  document.title = prefix ? `${prefix} — ${BASE_TITLE}` : BASE_TITLE;
}

function opticalScene() {
  const instruments = {
    transcript: `<div class="optic optic--transcript">
      <div class="optic__grooves"></div><div class="optic__words">Words / phrases / sentiment / context</div>
      <div class="optic__hub"><i></i><b></b></div></div>`,
    facial: `<div class="optic optic--facial"><div class="optic__aperture">
      ${Array.from({ length: 8 }, (_, n) => `<i style="--n:${n}"></i>`).join("")}
      <div class="optic__focus"><span></span><b></b></div></div></div>`,
    vocal: `<div class="optic optic--vocal"><div class="optic__diaphragm">
      ${Array.from({ length: 5 }, (_, n) => `<i style="--n:${n}"></i>`).join("")}
      <span class="optic__needle"></span></div></div>`,
    audience: `<div class="optic optic--audience"><div class="optic__crowd">
      ${Array.from({ length: 28 }, (_, n) => `<i style="--n:${n}"></i>`).join("")}
      <div class="optic__core">Audience</div></div></div>`,
  };
  return `<div class="optics" aria-hidden="true">
    <div class="optics__halo"></div>
    <div class="optics__coordinates"><span>BP / Optical array</span><span>04 channels<span class="sep" aria-hidden="true"></span>read locally</span></div>
    <div class="optics__assembly">
      ${CHANNELS.map((channel, i) => `<div class="optics__plate" data-optic="${channel}" style="--i:${i};--optic:var(--ch-${channel})">
        <span class="optics__serial">0${i + 1} / ${esc(CHANNEL_META[channel].short)}</span>
        ${instruments[channel]}
        <span class="optics__etch">Independent signal / ${String(i + 1).padStart(2, "0")}</span>
      </div>`).join("")}
      <div class="optics__beam"></div>
    </div>
    <div class="optics__caption"><span class="optics__cross">+</span><p>Every review.<br><em>Four ways of seeing.</em></p><span>The signal chamber</span></div>
  </div>`;
}

function shell(inner) {
  /* The page ends on the shared ending (chassis.css .end), the same line the
     library, the book and the opening page end on. */
  return `<div class="rn"><div class="rn__edition"><span>BrandPulse / Analysis studio</span><span><i></i> Local intelligence</span></div>${opticalScene()}${inner}<div class="rn__colophon end"><span class="end__sig">Independent readings. A clearer perspective.</span><span>Words / face / voice / audience</span></div></div>`;
}

/* --- the form, as one instrument rather than a stack of inputs ---------- */

function modeSwitch(current) {
  return `
  <div class="rn__modes" role="group" aria-label="What to analyse">
    ${Object.values(MODES).map((mode) => `
      <button class="mode" type="button" data-mode="${mode.key}"
              aria-pressed="${mode.key === current}">${esc(mode.tab)}</button>`).join("")}
  </div>`;
}

function field(id, label, hint, input, problem) {
  /* A field with a problem says so to assistive technology as well as in
     colour and words: aria-invalid is what a screen reader announces as
     "invalid entry" on arrival (INCLUSIVE_DESIGN.md A15). */
  const marked = problem ? input.replace("<input ", '<input aria-invalid="true" ') : input;
  return `
  <div class="fld${problem ? " is-wrong" : ""}">
    <label class="t-label" for="${id}">${esc(label)}</label>
    ${marked}
    <p class="fld__hint t-micro" id="${id}-hint">${problem ? esc(problem) : esc(hint)}</p>
  </div>`;
}

function videoForm(prefill, problems) {
  return `
    ${field("url", "YouTube address",
      "One video. The address has to contain an eleven-character video id.",
      `<input id="url" name="video_url" type="url" inputmode="url" required
              autocomplete="off" spellcheck="false"
              aria-describedby="url-hint"
              placeholder="https://www.youtube.com/watch?v="
              value="${esc(prefill.video_url || "")}">`, problems.video_url)}
    <div class="fld__pair">
      ${field("brand", "Brand", "Names the saved report.",
        `<input id="brand" name="brand_name" required autocomplete="off" autocapitalize="words"
                aria-describedby="brand-hint" placeholder="Samsung"
                value="${esc(prefill.brand_name || "")}">`, problems.brand_name)}
      ${field("product", "Product", "Must not match a report already saved here.",
        `<input id="product" name="product_name" required autocomplete="off" autocapitalize="words"
                aria-describedby="product-hint" placeholder="Ultra 25"
                value="${esc(prefill.product_name || "")}">`, problems.product_name)}
    </div>`;
}

/* The standard endings, plus the one a link asked for when it is not one of
   them. It is held to the same rule as the rest. */
function endingsFor(offset) {
  const want = String(offset || "0");
  return ENDINGS.some(([d]) => d === want) ? ENDINGS
    : [...ENDINGS, [want, `${want} days ago`]].sort(([a], [b]) => Number(a) - Number(b));
}

/* A window may end at most its own length back (sweep.py offset_problem,
   which refuses the rest, so a hand-made request gets no further). */
function endingFits(windowKey, days) {
  const w = WINDOWS.find(([k]) => k === windowKey);
  return Boolean(w) && Number(days) >= 0 && Number(days) <= w[2];
}

/* The endings too far back for the chosen window are greyed out, and saying
   so is part of greying them out. A chosen ending that stops fitting when a
   shorter window is picked goes back to today, out loud. */
function fitEndings(form, { speak = false } = {}) {
  const chosen = form.querySelector('input[name="window"]:checked');
  const offsets = [...form.querySelectorAll('input[name="offset"]')];
  if (!chosen || !offsets.length) return;
  const [, label, days] = WINDOWS.find(([k]) => k === chosen.value) || WINDOWS[1];
  /* Every window's own length is one of the standard endings, so the limit
     always has a name a reader already sees on the row. */
  const limit = (ENDINGS.find(([d]) => Number(d) === days) || ["", `${days} days ago`])[1].toLowerCase();
  const rule = `${label} can end at most ${limit}`;
  for (const input of offsets) {
    input.disabled = !endingFits(chosen.value, input.value);
    input.closest(".win__one").title = input.disabled ? `Too far back: ${rule.toLowerCase()}` : "";
  }
  const picked = offsets.find((i) => i.checked);
  if (picked && picked.disabled) {
    picked.checked = false;
    offsets.find((i) => i.value === "0").checked = true;
    if (speak) announce(`Ending moved to today: ${rule.toLowerCase()}.`);
  }
  const note = form.querySelector("[data-ending-note]");
  if (note) {
    note.textContent = `${rule}, one window back. Ending there searches the period just before, with no `
      + "days in common, for a clean before-and-after in the combined book.";
  }
}

function subjectForm(mode, prefill, problems) {
  return `
    ${field("subject", mode.label, mode.hint,
      `<input id="subject" name="subject" required autocomplete="off" autocapitalize="words"
              aria-describedby="subject-hint"
              placeholder="${esc(mode.placeholder)}"
              value="${esc(prefill.subject || "")}">`, problems.subject)}
    <fieldset class="win">
      <legend class="t-label">Look back over</legend>
      <div class="win__row">
        ${WINDOWS.map(([key, label], i) => `
          <label class="win__one">
            <input type="radio" name="window" value="${key}"
                   ${(prefill.window || "month") === key ? "checked" : ""}>
            <span>${esc(label)}</span>
          </label>`).join("")}
      </div>
    </fieldset>
    <fieldset class="win">
      <legend class="t-label">Ending</legend>
      <div class="win__row">
        ${endingsFor(prefill.offset).map(([days, label]) => `
          <label class="win__one">
            <input type="radio" name="offset" value="${days}"
                   ${String(prefill.offset || "0") === days ? "checked" : ""}>
            <span>${esc(label)}</span>
          </label>`).join("")}
      </div>
      <p class="t-micro u-faint" data-ending-note>Ending earlier searches a window of the same length that shares
        no days with a recent one, for a clean before-and-after in the combined book.</p>
    </fieldset>`;
}

function formView(modeKey = "video", prefill = {}, problems = {}, notice = "") {
  const mode = MODES[modeKey] || MODES.video;
  const isSweep = mode.key !== "video";

  return shell(`
    <section class="rn__form" aria-labelledby="fm-h">
      <div class="rn__brief">
        <p class="rn__eyebrow">The analysis studio</p>
        <h1 id="fm-h" class="t-l">${esc(mode.title)}</h1>
        <p class="t-lede">${esc(mode.lede)}</p>
        ${notice ? `<p class="notice t-small">${notice}</p>` : ""}
      </div>

      ${modeSwitch(mode.key)}

      <form class="rn__panel" data-form novalidate>
        <input type="hidden" name="mode" value="${mode.key}">
        ${isSweep ? subjectForm(mode, prefill, problems) : videoForm(prefill, problems)}
        <div class="rn__go">
          <button class="btn" data-variant="solid" type="submit">
            ${isSweep ? `Discover ${SWEEP_SIZE} videos` : "Begin analysis"}
          </button>
          <p class="t-micro u-faint">${isSweep
            ? "Searching costs one API call and starts nothing. You confirm the "
              + "five before any of the machine's time is spent."
            : "Four to nine minutes. Needs Ollama running on this machine."}</p>
        </div>
      </form>

      <aside class="rn__what">
        <h2 class="t-label">Four independent lenses <span>Held-out accuracy</span></h2>
        <ul class="rn__chans">
          ${CHANNELS.map((channel) => {
            const meta = CHANNEL_META[channel];
            return `
            <li data-channel="${channel}" style="--ch:var(--ch-${channel})">
              <i class="tp__mark" data-mark="${channel}" aria-hidden="true"></i>
              <span class="rn__cn t-label">${esc(meta.label)}</span>
              <span class="t-read">${pct(meta.accuracy)}</span>
              <span class="t-micro u-faint">${esc(meta.sample)}</span>
            </li>`;
          }).join("")}
        </ul>
        <p class="t-micro u-faint">
          Each percentage is what that channel scored on this project's own
          hand-labelled data, on speakers or videos it had never seen. Two of the
          four are at or near guessing, which is why a run reports where they
          disagree rather than averaging them into one number.
        </p>
      </aside>
    </section>`);
}

/* --- the casting table -------------------------------------------------- */

function candidateCard(entry, chosen) {
  const ok = entry.verdict === "ok";
  const mins = Math.floor((entry.duration_s || 0) / 60);
  const secs = String((entry.duration_s || 0) % 60).padStart(2, "0");
  return `
  <li class="cand${ok ? "" : " is-refused"}"><div class="cand__visual" aria-hidden="true"><img class="cand__thumb" src="/thumbnails/${esc(entry.video_id)}.jpg" alt="" loading="lazy" decoding="async"><span>Play / review</span><svg viewBox="0 0 80 80"><circle cx="40" cy="40" r="30"/><path d="M34 27L53 40L34 53Z"/></svg><span>${mins}:${secs}</span></div>
    <label class="cand__pick">
      <input type="checkbox" name="pick" value="${esc(entry.video_id)}"
             ${chosen ? "checked" : ""}>
      <span class="sr-only">Include ${esc(entry.title)}</span>
    </label>
    <div class="cand__body">
      <h3 class="cand__title t-panel">${esc(entry.title)}</h3>
      <p class="cand__meta t-micro u-faint">
        ${esc(entry.channel)}
        <span class="cand__sep" aria-hidden="true"></span>
        ${mins}m ${secs}s
        <span class="cand__sep" aria-hidden="true"></span>
        ${count(entry.view_count)} views
        <span class="cand__sep" aria-hidden="true"></span>
        ${count(entry.comment_count)} comments
      </p>
    </div>
    <p class="cand__verdict t-label">${ok
      ? "Eligible"
      : esc(entry.verdict)}</p>
  </li>`;
}

/* Which refusals a person may legitimately overrule.

   `sweep.verdict_for` returns the reason rather than applying it, precisely
   because some of them are judgements and some are close to mechanical. A video
   whose title does not name the subject may still be about it; a video with
   comments switched off has nothing for the audience channel to read. Only the
   first kind is arguable, and the page counts them rather than asserting a
   number. */
const ARGUABLE = /subject not named/i;

/** An RFC-3339 instant as "12 Sept 2026", or the raw text when unparseable. */
function dayOf(value) {
  const d = new Date(value || "");
  return Number.isNaN(d.getTime()) ? String(value || "") : d.toLocaleDateString("en-GB",
    { day: "numeric", month: "short", year: "numeric" });
}

function selectionView(modeKey, result) {
  const candidates = result.candidates || [];
  const suggested = new Set(result.suggested || []);
  const eligible = candidates.filter((c) => c.verdict === "ok");
  const refused = candidates.filter((c) => c.verdict !== "ok");
  const arguable = refused.filter((c) => ARGUABLE.test(c.verdict || ""));

  if (!candidates.length) {
    return shell(`
      <section class="state">
        <p class="t-label state__tag">Nothing found</p>
        <h2 class="t-l">The search came back empty.</h2>
        <p class="t-body">No videos matched
          &ldquo;${esc(result.subject || "")}&rdquo; in that period. A longer
          window usually fixes it.</p>
        <button class="btn" type="button" data-back>Change the search</button>
      </section>`);
  }

  return shell(`
    <section class="cast" aria-labelledby="ca-h">
      <div class="cast__head">
        <p class="rn__eyebrow">Curate your perspective</p><h1 id="ca-h" class="t-l">Choose your five.</h1>
        <p class="t-lede">
          ${count(candidates.length)} videos came back for
          &ldquo;${esc(result.subject || "")}&rdquo;, ${count(eligible.length)} of
          them eligible.${arguable.length ? `
          ${count(arguable.length)} of the ${count(refused.length)} refusals
          ${arguable.length === 1 ? "is a judgement" : "are judgements"} you can
          overrule: a video whose title does not name the subject may still be
          about it.` : ""} Every refusal is shown with the rule that produced it
          rather than hidden, and all of them stay selectable.
        </p>
        ${eligible.length < SWEEP_SIZE ? `
          <p class="cast__short t-small">
            Only ${count(eligible.length)} passed every rule, so reaching
            ${SWEEP_SIZE} means taking ${count(SWEEP_SIZE - eligible.length)}
            from the refused list below. Each one carries its reason, and a run
            built on them is worth exactly what those reasons are worth.
          </p>` : ""}
        <p class="t-micro u-faint">Searched as
          <code>${esc(result.query_used || "")}</code>, published ${esc(dayOf(result.published_after))}
          to ${result.published_before ? esc(dayOf(result.published_before)) : "today"}</p>
      </div>

      <form data-pick>
        <div class="cast__bar">
          <p class="t-label" data-tally></p>
          <div class="cast__acts">
            <button class="btn" type="button" data-back>Change the search</button>
            <button class="btn" data-variant="solid" type="submit" data-start-sweep>
              Analyse the ${SWEEP_SIZE} chosen
            </button>
          </div>
        </div>

        <ul class="cast__list">
          ${eligible.map((c) => candidateCard(c, suggested.has(c.video_id))).join("")}
        </ul>

        ${refused.length ? `
          <div class="cast__refused">
            <h2 class="t-label">Refused, with the reason</h2>
            <p class="t-micro u-faint">
              These are still selectable. Nothing here is hidden from you, and
              the rule that refused each one is printed beside it.
            </p>
            <ul class="cast__list">
              ${refused.map((c) => candidateCard(c, false)).join("")}
            </ul>
          </div>` : ""}
      </form>
    </section>`);
}

/* --- the wait ------------------------------------------------------------ */

/* A channel's lane state is derived from which stage actually records it,
   rather than from a one-to-one mapping that does not exist. */
function laneState(channel, stageIndex) {
  if (stageIndex < 0) return "waiting";
  for (let i = 0; i < STAGES.length; i += 1) {
    if (!STAGES[i].records.includes(channel)) continue;
    if (i < stageIndex) return "recorded";
    if (i === stageIndex) return "recording";
    return "waiting";
  }
  return "waiting";
}

/* The controller row. It appears only once all four channels are on disk,
   because that is when it has something to read. */
function controllerState(stageIndex) {
  if (stageIndex < 2) return "waiting";
  /* It reads all four at stage three and writes the report at stage five. */
  if (stageIndex === 2 || stageIndex === 4) return "recording";
  return "recorded";
}

function runningView(kind, data) {
  const stageIndex = typeof data.stage_index === "number" ? data.stage_index : -1;
  const stage = STAGES[stageIndex] || null;
  const isSweep = kind === "sweep";

  return shell(`
    <section class="wait" aria-labelledby="wa-h" data-wait>
      <div class="wait__top">
        <div><p class="rn__eyebrow">Analysis in motion</p><h1 id="wa-h" class="t-l">${isSweep ? "Five perspectives." : "Reading between<br>the signals."}</h1></div>
        <div class="wait__time"><span class="rn__eyebrow">Elapsed</span><p class="wait__clock t-readout" data-elapsed>0:00</p></div>
      </div>

      ${isSweep ? `
        <div class="wait__which">
          <p class="t-label" data-video-line>${data.video_index ? `Video ${data.video_index} of ${data.video_total || SWEEP_SIZE}` : "Preparing your five videos"}</p>
          <p class="t-small u-dim" data-video-title>${esc(data.video_title || "")}</p>
          <ol class="wait__dots" data-dots aria-hidden="true"></ol>
        </div>` : ""}

      <div class="wait__stage">
        <p class="t-label u-faint" data-stage-no>${stage ? `Stage ${stageIndex + 1} of ${STAGES.length}` : "Queued"}</p>
        <h2 class="t-panel" data-stage-name>${stage ? esc(stage.label) : "Preparing the instrument"}</h2>
        <p class="t-small u-dim" data-stage-what>${stage ? esc(stage.what) : "Waiting for the worker. Your session will appear here as soon as processing starts."}</p>
      </div>

      <!-- The instrument assembling itself. The lanes are EMPTY on purpose:
           nothing has been measured yet, and drawing a plausible trace to fill
           them would be inventing a measurement. -->
      <div class="rec" data-rec role="progressbar"
           aria-label="How far this run has got"
           aria-valuemin="0" aria-valuemax="${STAGES.length}">
        ${CHANNELS.map((channel) => `
          <div class="rec__lane" data-channel="${channel}"
               data-state="${laneState(channel, stageIndex)}"
               style="--ch:var(--ch-${channel})">
            <span class="rec__id t-label">
              <i class="tp__mark" data-mark="${channel}" aria-hidden="true"></i>
              ${esc(CHANNEL_META[channel].short)}
            </span>
            <span class="rec__track"><i class="rec__scan"></i></span>
            <span class="rec__state t-micro"></span>
          </div>`).join("")}
        <div class="rec__lane rec__lane--ctrl" data-controller
             data-state="${controllerState(stageIndex)}">
          <span class="rec__id t-label">
            <i class="rec__ctrlmark" aria-hidden="true"></i>
            Controller
          </span>
          <span class="rec__track"><i class="rec__scan"></i></span>
          <span class="rec__state t-micro"></span>
        </div>
        <p class="rec__note t-micro u-faint">
          Live processing status. Measured readings appear in the finished report.
        </p>
      </div>

      <!-- The product's central claim, as a live reading. -->
      <div class="port" data-port>
        <span class="port__lamp" aria-hidden="true"></span>
        <div>
          <p class="t-label" data-port-state></p>
          <p class="t-micro u-faint" data-port-why></p>
        </div>
      </div>

      <div class="wait__acts">
        <button class="btn" type="button" data-cancel>Stop this run</button>
        <p class="t-micro u-faint">
          ${isSweep
            ? "Stopping is checked between stages, so it is not instant. Every report "
              + "already finished is kept, and running the same sweep again resumes from there."
            : "Stopping ends the run at once. Nothing is written to the outputs "
              + "directory unless the run finishes."}
        </p>
      </div>
    </section>`);
}

/* --- the five endings ----------------------------------------------------
   Finished, partly finished, cancelled, failed, and a job the server has
   forgotten. Each is a designed screen with its own words, because the ones
   people remember are not the success. Every one of them is also SPOKEN: a run
   lasts four to nine minutes and a reader using a screen reader was never told
   it had ended. */

const OUTCOMES = {
  done: {
    tag: "Finished",
    urgent: false,
    say: ({ result, kind }) => {
      if (kind === "sweep") {
        const summary = (result && result.summary) || {};
        const auth = summary.authenticity || {};
        return `The sweep finished. ${summary.video_count || 0} videos. `
             + `Mean authenticity ${score(auth.mean)} out of 100, ranging from `
             + `${score(auth.min)} to ${score(auth.max)}. `
             + `${summary.spread_verdict || ""}. A link to the combined report follows.`;
      }
      const flagged = ((result && result.flagged_segments) || []).length;
      return `The analysis finished. Authenticity ${score(result.authenticity_score)} `
           + `out of 100. Brand health ${score(result.brand_health_score)} out of 100. `
           + `${result.segment_count ?? "An unknown number of"} segments, ${flagged} `
           + `flagged as cross-channel conflicts. The bias caveat is on the report. `
           + `A link to open it follows.`;
    },
  },
  partial: {
    tag: "Partly finished",
    urgent: false,
    /* Not a success and not a failure, so it is neither. A sweep that analysed
       three of five produced a real result and a real reason the other two are
       missing, and reporting it as either of the other outcomes would be a lie
       in one direction or the other. */
    say: ({ result }) => {
      const summary = (result && result.summary) || {};
      const failed = ((result && result.failed) || []).length;
      return `The sweep finished partly. ${summary.video_count || 0} of `
           + `${(summary.video_count || 0) + failed} videos were analysed; ${failed} `
           + `could not be. Each failure is listed with its reason. The combined `
           + `report covers the videos that did finish.`;
    },
  },
  cancelled: {
    tag: "Stopped",
    urgent: false,
    say: ({ kind }) => kind === "sweep"
      ? "The sweep was stopped. Every report it had already finished is kept, and "
      + "running the same sweep again resumes from there rather than starting over."
      : "The run was stopped. Nothing was written to the outputs directory. Links "
      + "to start again and to open the library follow.",
  },
  error: {
    tag: "Failed",
    urgent: true,
    /* Concatenated rather than interpolated: the backend's message is untrusted
       text and must not pass through a template literal on its way to a live
       region. */
    say: ({ data }) => "The run did not finish. The backend reported: "
      + ((data && data.error) || "no reason given")
      + ". The usual causes are a private, region-locked or removed video, "
      + "comments disabled on it, an exhausted YouTube quota, or Ollama not running.",
  },
  lost: {
    tag: "No longer known",
    urgent: true,
    say: () => "That run is no longer known to the server. Jobs are held in memory, "
      + "so restarting Flask forgets them. If the run had already finished, its "
      + "report is in the library.",
  },
};

/**
 * Where the report this run just wrote can be read: the file name the server
 * chose when the run started (app.py `_report_filename`, returned by
 * /analyse/status as `report_file`). Not rebuilt here from the brand and
 * product: the report does not carry the product, a page reloaded mid-run never
 * saw the form, and the server strips characters a file name cannot hold.
 */
function reportLink(data) {
  return data && data.report_file
    ? `/library/${encodeURIComponent(data.report_file)}` : null;
}

function outcomeView(kind, data) {
  const spec = OUTCOMES[kind] || OUTCOMES.error;
  const result = data.result || data.report || {};
  const isSweep = data.kind === "sweep";

  let detail = "";
  if (kind === "done" && !isSweep) {
    const link = reportLink(data);
    const flagged = (result.flagged_segments || []).length;
    detail = `
      <dl class="fin__scores">
        <div><dt class="t-label u-faint">Authenticity</dt>
          <dd class="t-readout">${score(result.authenticity_score)}</dd></div>
        <div><dt class="t-label u-faint">Brand health</dt>
          <dd class="t-readout">${score(result.brand_health_score)}</dd></div>
        <div><dt class="t-label u-faint">Flagged</dt>
          <dd class="t-readout${flagged ? " is-tear" : ""}">${count(flagged)}</dd></div>
      </dl>
      <p class="t-small u-dim">
        ${count(result.segment_count)} segments. Both scores measure how far four
        independent readings of the same moment disagreed. Neither is a finding
        about whether anyone was telling the truth.
      </p>
      <div class="fin__acts">
        ${link ? `<a class="btn" data-variant="solid" href="${link}">Open the report</a>` : ""}
        <a class="btn" href="/library">Open the library</a>
      </div>`;
  } else if ((kind === "done" || kind === "partial") && isSweep) {
    const summary = result.summary || {};
    const auth = summary.authenticity || {};
    const failed = result.failed || [];
    detail = `
      <dl class="fin__scores">
        <div><dt class="t-label u-faint">Mean authenticity</dt>
          <dd class="t-readout">${score(auth.mean)}</dd></div>
        <div><dt class="t-label u-faint">Lowest</dt>
          <dd class="t-readout">${score(auth.min)}</dd></div>
        <div><dt class="t-label u-faint">Highest</dt>
          <dd class="t-readout">${score(auth.max)}</dd></div>
      </dl>
      ${summary.spread_verdict
        ? `<p class="t-small u-dim">${esc(summary.spread_verdict)}</p>` : ""}
      ${failed.length ? `
        <div class="fin__failed">
          <h2 class="t-label">Could not be analysed</h2>
          <ul class="t-small">
            ${failed.map((f) => `<li><b>${esc(f.title || f.video_id || "A video")}</b>
              <span class="u-dim">${esc(f.reason || f.error || "no reason recorded")}</span></li>`).join("")}
          </ul>
        </div>` : ""}
      <div class="fin__acts">
        ${data.sweep_id
          ? `<a class="btn" data-variant="solid" href="/brand/${encodeURIComponent(data.sweep_id)}">Open the combined report</a>`
          : ""}
        <a class="btn" href="/library">Open the library</a>
      </div>`;
  } else {
    detail = `
      <div class="fin__acts">
        <button class="btn" data-variant="solid" type="button" data-again>Start another run</button>
        <a class="btn" href="/library">Open the library</a>
      </div>`;
  }

  return shell(`
    <section class="fin" data-outcome="${kind}" aria-labelledby="fi-h">
      <p class="t-label fin__tag${spec.urgent ? " is-tear" : ""}">${esc(spec.tag)}</p>
      <h1 id="fi-h" class="t-l">${esc(
        kind === "done" ? (isSweep ? "Five videos, combined." : "The run finished.")
        : kind === "partial" ? "Some of it finished."
        : kind === "cancelled" ? "Stopped."
        : kind === "lost" ? "That run is no longer known."
        : "The run did not finish.")}</h1>
      ${kind === "error"
        ? `<p class="fin__why t-body">${esc((data && data.error) || "No reason was given.")}</p>
           <p class="t-small u-dim">
             The usual causes are a private, region-locked or removed video, comments
             disabled on it, an exhausted YouTube quota, or Ollama not running on
             <code>localhost:11434</code>.
           </p>`
        : kind === "lost"
          ? `<p class="t-body">Jobs are held in memory, so restarting the server forgets
               them. If this run had already finished, its report is in the library.</p>`
          : kind === "cancelled"
            ? `<p class="t-body">${isSweep
                 ? "Every report it had already finished is kept. Running the same sweep again resumes from there rather than starting over."
                 : "Nothing was written to the outputs directory."}</p>`
            : ""}
      ${detail}
    </section>`);
}

/* --- driving it ---------------------------------------------------------- */

let poller = null;
let elapsedTimer = null;
let currentJob = null;
let lastStage = -2;

function stopTimers() {
  if (poller) { clearTimeout(poller); poller = null; }
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
}

function paintRunning(kind, data, startedAt) {
  for (const plate of root.querySelectorAll("[data-optic]")) {
    plate.dataset.state = laneState(plate.dataset.optic, data.stage_index ?? -1);
  }
  const scene = root.querySelector(".optics");
  if (scene) scene.dataset.stage = String(data.stage_index ?? -1);
  const stageIndex = typeof data.stage_index === "number" ? data.stage_index : -1;
  const stage = STAGES[stageIndex] || null;
  const total = data.total_stages || STAGES.length;

  const noEl = root.querySelector("[data-stage-no]");
  const nameEl = root.querySelector("[data-stage-name]");
  const whatEl = root.querySelector("[data-stage-what]");
  if (!noEl) return;

  noEl.textContent = stageIndex < 0
    ? "Queued" : `Stage ${stageIndex + 1} of ${total}`;
  nameEl.textContent = stage ? stage.label : "Waiting for the worker";
  whatEl.textContent = stage ? stage.what : "";

  /* The lanes are this page's progress indicator, so they report as one. */
  const rec = root.querySelector("[data-rec]");
  if (rec) {
    if (stageIndex < 0) {
      rec.removeAttribute("aria-valuenow");
      rec.setAttribute("aria-valuetext", "Queued. No stage has started yet.");
    } else {
      rec.setAttribute("aria-valuenow", String(stageIndex));
      rec.setAttribute("aria-valuetext",
        `Stage ${stageIndex + 1} of ${total}, ${stage ? stage.spoken : "working"}. `
        + `${stageIndex} of ${total} stages complete.`);
    }
  }

  const word = { recorded: "recorded", recording: "recording", waiting: "not yet" };
  for (const lane of root.querySelectorAll("[data-channel].rec__lane")) {
    const state = laneState(lane.dataset.channel, stageIndex);
    lane.dataset.state = state;
    lane.querySelector(".rec__state").textContent = word[state];
  }
  const ctrl = root.querySelector("[data-controller]");
  if (ctrl) {
    const state = controllerState(stageIndex);
    ctrl.dataset.state = state;
    ctrl.querySelector(".rec__state").textContent =
      state === "recorded" ? "done"
        : state === "recording" ? (stageIndex === 4 ? "writing the report" : "reading all four")
        : "waiting for four";
  }

  /* The aperture. Three of the five stages reach a network and two do not;
     the long ones are local, so over a run this reads sealed for most of it. */
  const port = root.querySelector("[data-port]");
  const reaches = stage ? stage.reaches : null;
  if (port) {
    port.dataset.open = String(Boolean(reaches));
    root.querySelector("[data-port-state]").textContent =
      reaches ? "The aperture is open" : "Sealed";
    root.querySelector("[data-port-why]").textContent = reaches
      ? reaches
      : "Nothing is leaving this machine. The controller is a local model on "
        + "localhost:11434.";
  }

  if (kind === "sweep") {
    const line = root.querySelector("[data-video-line]");
    const title = root.querySelector("[data-video-title]");
    const dots = root.querySelector("[data-dots]");
    if (line) {
      const at = data.video_index || 0;
      const of = data.video_total || SWEEP_SIZE;
      line.textContent = data.phase === "combined"
        ? `All ${of} videos read. Writing the combined report`
        : at ? `Video ${at} of ${of}` : "Starting";
      title.textContent = data.video_title || "";
      dots.innerHTML = Array.from({ length: of }, (_, i) =>
        `<li data-state="${i < at - 1 ? "done" : i === at - 1 ? "now" : "next"}"></li>`).join("");
    }
  }

  if (stageIndex !== lastStage) {
    lastStage = stageIndex;
    const spoken = stage ? stage.spoken : "waiting for the worker";
    announce(`Stage ${Math.max(1, stageIndex + 1)} of ${total}: ${spoken}.`);
    setTitle(stageIndex < 0 ? "Queued" : `Stage ${stageIndex + 1} of ${total}`);
  }

  const clock = root.querySelector("[data-elapsed]");
  if (clock && !elapsedTimer) {
    const tick = () => {
      const from = startedAt || Date.now() / 1000;
      clock.textContent = mmss(Math.max(0, Date.now() / 1000 - from));
    };
    tick();
    elapsedTimer = setInterval(tick, 1000);
  }
}

/* A NEW STEP OPENS AT ITS OWN TITLE.

   The form, the casting table, the wait and the ending replace one another in
   place, and the page used to keep whatever scroll the last step had: pressing
   "Discover" from below the fold landed the reader in the middle of the cards,
   under a heading they never saw. Each step now starts at its top, and focus
   moves to its title so a keyboard or screen-reader user arrives in the same
   place a sighted one does. Instant, not smooth: this is a change of view,
   not a movement through one. */
function arrive() {
  if (window.scrollY > 0) window.scrollTo({ top: 0, behavior: "instant" });
  const title = root.querySelector("h1");
  if (title) {
    title.setAttribute("tabindex", "-1");
    title.focus({ preventScroll: true });
  }
}

function finish(kind, data) {
  stopTimers();
  currentJob = null;
  const spec = OUTCOMES[kind] || OUTCOMES.error;
  root.innerHTML = outcomeView(kind, data);
  arrive();
  setTitle(spec.tag);
  announce(spec.say({ result: data.result || data.report || {}, data,
                      kind: data.kind || "analysis" }), { urgent: spec.urgent });
  wireOutcome();
}

function wireOutcome() {
  const again = root.querySelector("[data-again]");
  if (again) again.addEventListener("click", () => { setTitle(""); showForm(); });
}

async function watch(jobId, kind, startedAt) {
  currentJob = { jobId, kind };
  root.innerHTML = runningView(kind, { stage_index: -1 });
  arrive();
  wireRunning(jobId, kind);

  const ask = kind === "sweep" ? sweepStatus : jobStatus;

  async function tick() {
    if (!currentJob || currentJob.jobId !== jobId) return;
    let data;
    try {
      data = await ask(jobId);
    } catch (error) {
      if (error && error.status === 404) { finish("lost", {}); return; }
      poller = setTimeout(tick, POLL_MS * 2);
      return;
    }
    const status = data.status;
    if (status === "running") {
      paintRunning(kind, data, startedAt || data.started_at);
      poller = setTimeout(tick, POLL_MS);
      return;
    }
    if (status === "done") finish("done", data);
    else if (status === "partial") finish("partial", data);
    else if (status === "cancelled") finish("cancelled", data);
    else finish("error", data);
  }

  tick();
}

function wireRunning(jobId, kind) {
  const cancel = root.querySelector("[data-cancel]");
  if (!cancel) return;
  cancel.addEventListener("click", async () => {
    cancel.disabled = true;
    cancel.textContent = "Stopping";
    /* A single analysis runs in its own process and is killed at once
       (app.py, _stop_child); a five-video run stops at its next checkpoint. */
    announce(kind === "sweep"
      ? "Stopping the run. This is checked between stages, so it is not instant."
      : "Stopping the run.");
    try {
      await (kind === "sweep" ? cancelSweep(jobId) : cancelJob(jobId));
    } catch {
      cancel.disabled = false;
      cancel.textContent = "Stop this run";
      announce("The stop request did not reach the server. The run is still going.",
        { urgent: true });
    }
  });
}

/* --- the form ------------------------------------------------------------ */

const VIDEO_ID = /(?:v=|youtu\.be\/|\/shorts\/|\/embed\/)([A-Za-z0-9_-]{11})/;

function readForm(form) {
  const data = new FormData(form);
  const out = {};
  for (const [key, value] of data.entries()) out[key] = String(value).trim();
  return out;
}

function showForm(modeKey = "video", prefill = {}, problems = {}, notice = "") {
  stopTimers();
  currentJob = null;
  lastStage = -2;
  root.innerHTML = formView(modeKey, prefill, problems, notice);
  wireForm();
}

function wireForm() {
  for (const button of root.querySelectorAll("[data-mode]")) {
    button.addEventListener("click", () => {
      const form = root.querySelector("[data-form]");
      showForm(button.dataset.mode, form ? readForm(form) : {});
      /* The form is redrawn, button included, which would leave focus on the
         page body: back to the mode just chosen, now pressed. */
      const chosen = root.querySelector(`[data-mode="${button.dataset.mode}"]`);
      if (chosen) chosen.focus();
    });
  }

  const form = root.querySelector("[data-form]");
  if (!form) return;

  fitEndings(form);
  for (const input of form.querySelectorAll('input[name="window"]')) {
    input.addEventListener("change", () => fitEndings(form, { speak: true }));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = readForm(form);
    const modeKey = values.mode || "video";
    const button = form.querySelector('button[type="submit"]');
    const problems = {};

    if (modeKey === "video") {
      if (!values.video_url) problems.video_url = "Paste the address of a YouTube video.";
      else if (!VIDEO_ID.test(values.video_url)) {
        problems.video_url = "That address has no eleven-character video id in it.";
      }
      if (!values.brand_name) problems.brand_name = "Needed: it names the saved report.";
      if (!values.product_name) problems.product_name = "Needed: it names the saved report.";
    } else if (!values.subject) {
      problems.subject = `Name the ${modeKey} to look for.`;
    }

    if (Object.keys(problems).length) {
      showForm(modeKey, values, problems);
      const first = root.querySelector(".is-wrong input");
      if (first) first.focus();
      announce(Object.values(problems).join(" "), { urgent: true });
      return;
    }

    button.disabled = true;
    button.textContent = modeKey === "video" ? "Preparing analysis…" : "Discovering videos…";
    form.setAttribute("aria-busy", "true");
    root.querySelector(".rn").classList.add("is-discovering");

    try {
      if (modeKey === "video") {
        const started = await startJob({
          video_url: values.video_url,
          brand_name: values.brand_name,
          product_name: values.product_name,
        });
        announce("The analysis has started. It takes four to nine minutes.");
        watch(started.job_id, "analysis", Date.now() / 1000);
      } else {
        const result = await sweepSearch({
          subject: values.subject,
          window: values.window || "month",
          offset_days: Number(values.offset || 0),
        });
        root.innerHTML = selectionView(modeKey, result);
        arrive();
        wireSelection(modeKey, values, result);
        announce(`${(result.candidates || []).length} videos found, `
          + `${result.eligible || 0} of them eligible. Choose ${SWEEP_SIZE}.`);
      }
    } catch (error) {
      const message = (error && error.message) || "the request failed";
      showForm(modeKey, values, {}, esc(message));
      announce(message, { urgent: true });
    }
  });
}

function wireSelection(modeKey, values, result) {
  const form = root.querySelector("[data-pick]");
  const tally = root.querySelector("[data-tally]");
  const start = root.querySelector("[data-start-sweep]");
  const back = root.querySelectorAll("[data-back]");

  for (const button of back) {
    button.addEventListener("click", () => showForm(modeKey, values));
  }
  if (!form) return;

  function retally() {
    const picked = form.querySelectorAll('input[name="pick"]:checked').length;
    tally.textContent = `${picked} chosen of ${SWEEP_SIZE}`;
    tally.classList.toggle("is-tear", picked !== SWEEP_SIZE);
    start.disabled = picked !== SWEEP_SIZE;
  }

  form.addEventListener("change", retally);
  retally();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const picked = [...form.querySelectorAll('input[name="pick"]:checked')]
      .map((i) => i.value);
    start.disabled = true;
    start.textContent = "Starting";
    try {
      const started = await sweepStart({
        subject: values.subject,
        /* Which framing this was started from. The two are one mechanism, but
           the library shelves them apart, and this is the only moment the
           distinction is known -- it is not recoverable from the subject
           string afterwards. */
        subject_kind: modeKey,
        window: values.window || "month",
        offset_days: Number(values.offset || 0),
        video_ids: picked,
        /* The search result goes back with the choice: it is the only place
           the titles, channels and dates are known, and the server files what
           it is sent in sweep.json, with the query and the dates searched.
           Left out, every page of the book named its videos by id. */
        candidates: result.candidates || [],
        query_used: result.query_used || "",
        published_after: result.published_after || "",
        published_before: result.published_before || null,
      });
      /* The same five, already analysed: the server hands back the finished
         sweep instead of a job, so open its book rather than wait on nothing. */
      if (started.already_finished) {
        window.location.href = `/brand/${encodeURIComponent(started.sweep_id)}`;
        return;
      }
      announce(`The sweep has started on ${picked.length} videos. `
        + "This takes considerably longer than a single run.");
      watch(started.job_id, "sweep", Date.now() / 1000);
    } catch (error) {
      const message = (error && error.message) || "the sweep could not be started";
      showForm(modeKey, values, {}, esc(message));
      announce(message, { urgent: true });
    }
  });
}

/* --- boot ---------------------------------------------------------------- */

async function main() {
  mountAnnouncer();
  mountAll({ here: "/run" });
  const footer = document.querySelector("[data-footer]");
  if (footer) footer.remove();

  /* If this machine is already running something, join it rather than offering
     a form that will be refused with a 409. */
  try {
    const active = await activeJob();
    if (active && active.active) {
      const kind = active.kind === "sweep" ? "sweep" : "analysis";
      watch(active.job_id, kind, active.started_at);
      announce("This machine is already running an analysis. Showing its progress.");
      clearTimeout(window.__bpFallback);
      return;
    }
  } catch {
    /* The backend is unreachable. Say so rather than offering a form whose
       submit will fail with no explanation. */
    root.innerHTML = shell(`
      <section class="state state--error">
        <p class="t-label state__tag">Backend unreachable</p>
        <h1 class="t-l">Nothing answered on this machine.</h1>
        <p class="t-body">
          The interface is served by the same Flask process that runs the
          pipeline, so if this page loaded and the API did not, the server is
          part-way up or has stopped. Start it with
          <code>python -m flask --app app run --port 5001</code> from
          <code>brandpulse_ai/</code>.
        </p>
        <a class="btn" href="/library">Try the library</a>
      </section>`);
    clearTimeout(window.__bpFallback);
    return;
  }

  /* A combined book's "search an earlier period" arrives pre-filled: the same
     subject, kind and window, ending earlier. Nothing is searched until the
     form is sent. */
  const q = new URLSearchParams(window.location.search);
  if (q.get("subject")) {
    const kind = q.get("kind") === "brand" ? "brand" : "product";
    const win = WINDOWS.some(([k]) => k === q.get("window")) ? q.get("window") : "month";
    const raw = q.get("offset") || "0";
    const asked = /^\d{1,4}$/.test(raw) ? String(Number(raw)) : "0";
    /* A link can ask for anything; the form starts only where the rule allows,
       and says so rather than quietly changing what the link asked for. */
    const offset = endingFits(win, asked) ? asked : "0";
    showForm(kind, { subject: q.get("subject"), window: win, offset }, {},
      offset === asked ? "" : "That link asked for an ending further back than this window allows, so it "
        + "starts at today. A window can end at most one window back.");
  } else {
    showForm();
  }
  clearTimeout(window.__bpFallback);
}

main();
