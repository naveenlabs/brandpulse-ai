/* ===========================================================================
   proof.js — "Everything the film just claimed, with its working."

   The film asserts. This section is where every assertion is made checkable,
   so it is the one section on the page that may not put looking good ahead of
   being readable. Three movements:

     1. THE LEDGER   what the corpus actually is, as four counts
     2. THE BENCH    three tabbed views of one horizontal bar chart
     3. THE LIMITS   five panels, scrubbed sideways under a pin

   WHY TABS, WHEN THE TABLE SHOWED EVERYTHING AT ONCE
   --------------------------------------------------
   The previous build put all four channels in one table. That was denser than
   it needed to be, and it was also quietly dishonest: a shared table invites a
   reader to compare 34.2% against 78.7% as though they were the same
   measurement, when each was taken on a different task against a different
   baseline. Tabs separate the comparisons that are real from the ones that are
   not, and the axis label on each panel says which quantity is on screen.

   The one place a shared axis IS honest is the controller tab, and it says so:
   those four bars were measured on byte-identical payloads under one prompt.

   COUNT-UP, AND THE GUARD ON IT
   -----------------------------
   motion.js records that count-up was built here once and removed, on the
   grounds that a number tweening through 21.5% en route to 34.2% paints a
   reading no bench produced. That decision has been revisited and reversed at
   the project owner's explicit direction, twice stated. It is implemented with
   the objection engineered out rather than ignored:

     - the easing is power2.out, which is monotonic, so no digit above the
       measured one is ever painted on the way;
     - onComplete writes the final string from the source value, not from the
       tweened float, so the resting figure is exact and carries no dust;
     - the running digits are aria-hidden and the real figure sits beside them
       in an .sr-only span, so assistive technology is never handed a number in
       motion;
     - print, reduced motion, and any tab the reader has not visited all render
       the final value with no tween at all.

   The largest figures on the page are the ledger's four, and those are whole
   counts, so the boldest instance of the effect is also the safest one.

   ON THE ROW ENTRANCE
   -------------------
   The integration brief this chart's layout comes from specifies a
   translateY(18px) + opacity entrance on each row. That is the one motion this
   build does not use on scroll, for the reason motion.js gives. It is kept
   where it belongs instead: rows animate that way when the READER SWITCHES
   TAB, because that is motion answering an action and showing what changed.
   Arriving by scroll, the rows are already in place and it is the bars that
   move.
   ======================================================================== */

import { CHANNEL_META, FACIAL_REFERENCES } from "./contract.js";
import { count, esc, pct } from "./format.js";
import { gsap, ScrollTrigger, reduced, onReducedChange, motionMedia } from "./motion.js";
import { mountPortalField } from "./portalfield.js";
import { mountPredictiveArc } from "./predictivearc.js";
import { limitsMarkup, wireLimits } from "./limits.js";

/* --------------------------------------------------------------- the data */

/* A share in words, for a title that has to stay true of whatever corpus is on
   disk: the largest plain fraction no more than two points above the share,
   with "Over" when the share is more than two points past it. 25.8% reads
   "A quarter of", 43.1% "Over two in five". Below 8% it says "Some". */
const FRACTIONS = [[0.5, "Half of"], [0.4, "Two in five"], [1 / 3, "A third of"],
  [0.25, "A quarter of"], [0.2, "A fifth of"], [0.1, "A tenth of"]];
function shareInWords(percent) {
  const p = (Number(percent) || 0) / 100;
  const hit = FRACTIONS.find(([f]) => p >= f - 0.02);
  if (!hit) return "Some";
  const [f, words] = hit;
  return p - f > 0.02 ? `Over ${words.charAt(0).toLowerCase()}${words.slice(1)}` : words;
}

/* Which part of the system each limitation lives in. Not a sequence, so not
   numbered -- 01/02/03 would promise an order that does not exist. The tag is
   real structure instead, and it says something true on its own: two of the
   five are the controller. */
const LIMITS = [
  {
    where: "channels",
    title: "Two of the four are near guessing",
    claim: () => `Facial ${pct(CHANNEL_META.facial.accuracy)} and vocal `
      + `${pct(CHANNEL_META.vocal.accuracy)} on held-out speakers.`,
    body: () => `The facial channel scores ${pct(CHANNEL_META.facial.accuracy)} on
      held-out speakers, ${CHANNEL_META.facial.worseThanConstant}. The vocal
      channel reaches ${pct(CHANNEL_META.vocal.accuracy)}. Both are
      down-weighted in the controller by those measured accuracies rather than
      removed, and both are labelled wherever they are shown.`,
  },
  {
    where: "controller",
    title: "The flag threshold may be unreachable",
    claim: () => "A perfect implementation of the scoring rule flags 0 of 62 "
      + "polar probes.",
    body: (f) => `A deterministic implementation of the controller's own
      specification flags none of the constructed polar disagreements. The
      threshold sits at ${f.pipeline.conflict_flag_threshold ?? 0.75} and is
      documented as possibly unattainable at four channels. It has not been
      changed, because moving it would move every score this system has ever
      reported.`,
  },
  {
    where: "corpus",
    title: (f) => `${shareInWords(f.corpus.no_face_share_pct)} segments have no face at all`,
    claim: (f) => `${pct(f.corpus.no_face_share_pct ?? 0)} of segments carry no `
      + "facial reading.",
    body: (f) => `${pct(f.corpus.no_face_share_pct ?? 0)} of segments in the
      corpus carry no facial reading &mdash; b-roll, cutaways, hands on a
      product. Those are drawn as absences on every report rather than
      defaulted to neutral.`,
  },
  {
    where: "controller",
    title: "A score is partly a claim about which model is installed",
    claim: () => "Swapping only the controller moved mean Authenticity by "
      + "49.08 points.",
    body: () => `Swapping only the controller, on byte-identical channel
      inputs, moved the mean Authenticity across this corpus by 49.08 points.
      Scores are not comparable between videos, and only comparable between
      runs of the same video when the same controller wrote them. A combined
      report records which one did; a single report does not yet.`,
  },
  {
    where: "scope",
    title: "It only reads English",
    claim: () => 'Transcription is fixed to <code>language="en"</code>.',
    body: () => `Transcription runs with <code>language="en"</code> fixed, and
      transcript and comment sentiment were both benchmarked on English. A
      video in any other language will still produce numbers, and those numbers
      are not evidence of anything.`,
  },
];

/**
 * A bar.
 *
 * `ratio` drives the geometry and `to`/`kind` drive the count-up. They are
 * separate on purpose: a bar whose scale is a share of every segment still prints a
 * whole count, and a bar drawn from a fraction never prints a percentage the
 * source write-up does not itself state.
 */
function bar({ id, label, note, channel = null, tone = null, ratio, to, kind,
  final, band = null, absent = false }) {
  return { id, label, note, channel, tone, ratio, to, kind, final, band, absent };
}

/* TAB 1. Coverage is the only quantity honestly comparable across all four
   channels, because it asks one question of each: did you report anything.
   It also makes a point the page makes nowhere else -- the facial channel is
   not merely the least accurate, it is the most often absent. */
function coverageBars(figures) {
  const corpus = figures.corpus || {};
  const readings = corpus.channel_readings || {};
  const total = corpus.segments_total || 0;
  const out = [];

  for (const channel of ["transcript", "vocal", "facial"]) {
    const seen = readings[channel];
    if (typeof seen !== "number" || !total) continue;
    out.push(bar({
      id: channel,
      label: CHANNEL_META[channel].short,
      note: `${count(seen)} of ${count(total)} segments`,
      channel,
      ratio: seen / total,
      to: seen,
      kind: "int",
      final: count(seen),
    }));
  }

  /* The audience channel is video-level by design, not by failure. A bar
     scaled against every segment in the corpus would be a category error, so it is drawn
     as an absence of that scale rather than as a low value on it. */
  out.push(bar({
    id: "audience",
    label: CHANNEL_META.audience.short,
    note: "one reading for the whole video, by design",
    channel: "audience",
    ratio: 1,
    to: 0,
    kind: "int",
    final: "—",
    absent: true,
  }));

  return out;
}

/* TAB 2. Four accuracies that share an axis but NOT a task. The axis label and
   each row's own note carry the sample, because the number is meaningless
   without it. Only the facial row carries a band, because only the facial
   question was benched against a constant and a human ceiling. */
function accuracyBars() {
  const rows = [
    ["audience", CHANNEL_META.audience],
    ["transcript", CHANNEL_META.transcript],
    ["vocal", CHANNEL_META.vocal],
    ["facial", CHANNEL_META.facial],
  ];

  return rows.map(([channel, meta]) => bar({
    id: channel,
    label: meta.short,
    note: meta.sample,
    channel,
    ratio: meta.accuracy / 100,
    to: meta.accuracy,
    kind: "pct",
    final: pct(meta.accuracy),
    band: channel === "facial"
      ? {
        from: FACIAL_REFERENCES.constant.value / 100,
        to: FACIAL_REFERENCES.ceiling.value / 100,
        label: `${pct(FACIAL_REFERENCES.constant.value)} always-NEUTRAL constant `
          + `to ${pct(FACIAL_REFERENCES.ceiling.value)} human ceiling`,
      }
      : null,
  }));
}

/* TAB 3. The one shared axis on this page that is fully earned: byte-identical
   payloads, one prompt, one grid. Drawn from fractions and printed as
   fractions, so nothing rounds into a claim the write-up does not make. */
function controllerBars(figures) {
  const refs = figures.controller_references || [];
  return refs.map((ref, index) => bar({
    id: `ctl-${index}`,
    label: `${ref.model} — ${ref.role.split(" ")[0]}`,
    note: ref.probe,
    /* Deliberately NOT a channel hue. A reader has just been taught that teal
       means the transcript channel; reusing it here to mean "the adopted
       model" would make the colour lie. These two are a state, so they get
       the ink scale: the deployed one bright, the replaced one dim. */
    tone: ref.role.startsWith("adopted") ? "adopted" : "replaced",
    ratio: ref.total ? ref.detected / ref.total : 0,
    to: ref.detected,
    kind: "int",
    final: `${count(ref.detected)} of ${count(ref.total)}`,
  }));
}

const TABS = [
  {
    id: "coverage",
    tab: "How often it spoke",
    title: "Segments carrying a reading",
    axis: "share of every segment in the corpus",
    comparable: "One question asked of all four, so these four are comparable.",
    bars: coverageBars,
  },
  {
    id: "accuracy",
    tab: "How often it was right",
    title: "Accuracy on held-out data",
    axis: "percent correct — each on its own task",
    comparable: "Four different tasks against four different baselines. "
      + "The axis is shared; the measurement is not.",
    bars: accuracyBars,
  },
  {
    id: "controller",
    tab: "What the controller changed",
    title: "Polar disagreements detected",
    axis: "share of polar probes detected",
    comparable: "Byte-identical payloads under one prompt — the one "
      + "comparison here that a shared axis fully earns.",
    bars: controllerBars,
  },
];

/* --------------------------------------------------------------- the markup */

function ledgerMarkup(figures) {
  const c = figures.corpus || {};
  const cells = [
    { to: c.report_count, label: "reports on disk", note: `across ${count(c.distinct_videos)} videos` },
    { to: c.segments_total, label: "segments", note: "the spine every channel attaches to" },
    { to: c.comments_total, label: "comments", note: "classified one at a time" },
    { to: c.controller_calls_total, label: "controller calls", note: "one local LLM call per segment" },
  ].filter((cell) => typeof cell.to === "number");

  return `
    <ol class="ledger">
      ${cells.map((cell) => `
        <li class="ledger__cell">
          <span class="ledger__n" data-count="${cell.to}" data-kind="int">
            <span class="ledger__run" aria-hidden="true">0</span>
            <span class="sr-only">${esc(count(cell.to))}</span>
          </span>
          <span class="ledger__label">${esc(cell.label)}</span>
          <span class="ledger__note">${esc(cell.note)}</span>
        </li>`).join("")}
    </ol>`;
}

function barMarkup(row, index) {
  /* The band is the whole point of the facial row, so it is labelled on screen
     and not only in the accessible name. A hatched rectangle nobody can read
     is decoration; a hatched rectangle with its two ends named is the finding. */
  const band = row.band
    ? `<span class="bar__band" style="--from:${row.band.from};--to:${row.band.to}"
         aria-hidden="true"></span>`
    : "";

  const bandNote = row.band
    ? `<p class="bar__gap">
         <span class="bar__gap-k">did not reach</span>
         ${esc(row.band.label)}
       </p>`
    : "";

  const fill = row.absent
    ? '<span class="bar__fill bar__fill--absent"></span>'
    : '<span class="bar__fill"></span>';

  /* The value rides the end of its own bar rather than sitting at a fixed
     right edge. A fixed edge puts it on the fill for a long bar and on the
     empty track for a short one, so no single colour can be made to hold
     against both. Past 0.8 there is no room outside, so it moves inside and
     takes the reversed colour with it. */
  const inside = row.absent || row.ratio > 0.8;

  return `
    <li class="bar" style="--i:${index};--ratio:${row.absent ? 1 : row.ratio}"${
      row.channel ? ` data-channel="${esc(row.channel)}"` : ""}${
      row.tone ? ` data-tone="${esc(row.tone)}"` : ""}>
      <div class="bar__id">
        <span class="bar__mark" data-channel="${esc(row.channel || "")}"${
          row.tone ? ` data-tone="${esc(row.tone)}"` : ""} aria-hidden="true"></span>
        <span class="bar__name">${esc(row.label)}</span>
        <span class="bar__note">${esc(row.note)}</span>
      </div>
      <div class="bar__track">
        ${band}
        ${fill}
        <span class="bar__value" data-inside="${inside}"${
          row.absent ? "" : ` data-count="${row.to}" data-kind="${row.kind}"`
        } data-final="${esc(row.final)}">
          <span class="bar__run" aria-hidden="true">${row.absent ? esc(row.final) : ""}</span>
          <span class="sr-only">${esc(row.final)}</span>
        </span>
      </div>
      ${bandNote}
    </li>`;
}

function chartMarkup(tab, figures) {
  const rows = tab.bars(figures);
  const ticks = [0, 20, 40, 60, 80, 100];

  return `
    <div class="chart__head">
      <h4 class="chart__title">${esc(tab.title)}</h4>
      <p class="chart__axis">${esc(tab.axis)}</p>
    </div>
    <ol class="chart__bars">${rows.map(barMarkup).join("")}</ol>
    <div class="chart__foot">
      <div class="chart__scale" aria-hidden="true">
        ${ticks.map((t) => `<span>${t}</span>`).join("")}
      </div>
      <p class="chart__note">${esc(tab.comparable)}</p>
    </div>`;
}

export function proofMarkup(figures) {
  const f = {
    corpus: (figures && figures.corpus) || {},
    pipeline: (figures && figures.pipeline) || {},
    controller_references: (figures && figures.controller_references) || [],
  };

  const tabs = TABS.map((tab, i) => `
    <button class="bench__tab${i === 0 ? " is-active" : ""}" type="button"
            role="tab" id="bench-tab-${tab.id}" data-tab="${tab.id}"
            aria-selected="${i === 0}" aria-controls="bench-panel"
            tabindex="${i === 0 ? 0 : -1}">${esc(tab.tab)}</button>`).join("");

  /* THE WELL is new, and it is the whole structural change.

     The ledger and the bench used to be two siblings in one column, so the
     section was as tall as both of them plus the heading -- 1227px against a
     900px screen, measured. They are now two states of ONE box. Stacked, the
     well is an ordinary two-row grid and nothing has moved. Locked, both
     children take the same grid cell and the well is as tall as the taller of
     them, which is what lets the heading, the counts and the chart share a
     single screen instead of queueing down a page.

     The stage exists so the two full-screen layers -- the reading column and
     the limits rail -- have one positioned parent to be absolute against, and
     so the pin has something to hold that is not the section's own border. */
  return `
    <section class="proof" id="proof" data-proof aria-labelledby="proof-h">
      <div class="proof__field" data-proof-field aria-hidden="true"></div>

      <div class="proof__stage" data-proof-stage>
        <div class="proof__inner" data-proof-reading>
          <header class="proof__head">
            <h2 class="proof__h" id="proof-h">Everything the film just claimed, with its working.</h2>
            <p class="proof__lede">
              Every figure below was measured on this project's own data, and is
              re-derived from its source by <code>ui_evidence/extract_figures.py</code>.
              Nothing here is quoted from a paper.
            </p>
          </header>

          <div class="proof__well" data-well>
            ${ledgerMarkup(f)}

            <div class="bench" data-bench>
              <div class="bench__tabs" role="tablist" aria-label="What was measured">${tabs}</div>
              <div class="bench__chart" id="bench-panel" role="tabpanel"
                   aria-labelledby="bench-tab-${TABS[0].id}"
                   data-chart>${chartMarkup(TABS[0], f)}</div>
            </div>
          </div>
        </div>

        ${limitsMarkup(LIMITS, f)}
      </div>
    </section>`;
}

/* --------------------------------------------------------------- the wiring */

const CHART_TICK = 1.05;

/**
 * Tween an integer or a one-decimal percentage up from zero.
 *
 * power2.out is monotonic, so nothing above `to` is ever painted. onComplete
 * writes `final` rather than the tweened float, so the resting string is exact.
 */
function countUp(host, { delay = 0 } = {}) {
  const run = host.querySelector("[aria-hidden]");
  const to = Number(host.dataset.count);
  const kind = host.dataset.kind;
  const final = host.dataset.final ?? (kind === "pct" ? pct(to) : count(to));
  if (!run || !Number.isFinite(to)) return null;

  const show = (v) => (kind === "pct" ? pct(v) : count(Math.round(v)));

  if (reduced()) { run.textContent = final; return null; }

  const state = { v: 0 };
  run.textContent = show(0);
  return gsap.to(state, {
    v: to,
    duration: CHART_TICK,
    delay,
    ease: "power2.out",
    onUpdate: () => { run.textContent = show(state.v); },
    onComplete: () => { run.textContent = final; },
  });
}

/** Everything a chart panel does when it becomes visible, or is switched to. */
function playChart(chart, { entrance = false } = {}) {
  const bars = [...chart.querySelectorAll(".bar")];
  const fills = [...chart.querySelectorAll(".bar__fill:not(.bar__fill--absent)")];
  const absent = [...chart.querySelectorAll(".bar__fill--absent")];
  const bands = [...chart.querySelectorAll(".bar__band")];
  const values = [...chart.querySelectorAll(".bar__value[data-count]")];

  gsap.killTweensOf([...bars, ...fills, ...absent, ...bands]);

  /* NOT EVERY VIEW HAS EVERY PART. Only the accuracy view carries a band --
     the facial row's -- and only the coverage view carries an absence. Handed
     an empty array, gsap logs "target not found" and does nothing, which is
     harmless but not free: once the scrub began turning all three views by
     itself, the page printed eight of those warnings on every load. Nothing was
     wrong; there was simply nothing to tween. A console that cries wolf is one
     nobody reads, so the empty cases are asked for explicitly. */
  const on = (list, run) => { if (list.length) run(list); };

  if (reduced()) {
    on(bars, (t) => gsap.set(t, { opacity: 1, y: 0 }));
    on(fills, (t) => gsap.set(t, { scaleX: 1 }));
    on(absent, (t) => gsap.set(t, { scaleX: 1, opacity: 1 }));
    on(bands, (t) => gsap.set(t, { opacity: 1, scaleX: 1 }));
    values.forEach((v) => countUp(v));
    return;
  }

  /* The row entrance belongs to the tab switch, not to the scroll. See header. */
  on(bars, (t) => (entrance
    ? gsap.fromTo(t,
      { opacity: 0, y: 18 },
      { opacity: 1, y: 0, duration: 0.52, ease: "power3.out", stagger: 0.09 })
    : gsap.set(t, { opacity: 1, y: 0 })));

  /* Each fill's true length is in its markup (--ratio, turned into a width by
     proof.css); the tween only scales it from zero. A fill whose tween never
     runs therefore shows its true value, never an empty track. */
  on(fills, (t) => gsap.set(t, { scaleX: 0, transformOrigin: "left center" }));
  on(absent, (t) => gsap.set(t, { scaleX: 0, opacity: 0, transformOrigin: "left center" }));
  on(bands, (t) => gsap.set(t, { opacity: 0, scaleX: 0.6, transformOrigin: "left center" }));

  on(bands, (t) => gsap.to(t, {
    opacity: 1, scaleX: 1, duration: 0.62, ease: "power3.out",
    stagger: 0.09, delay: 0.06,
  }));
  on(fills, (t) => gsap.to(t, {
    scaleX: 1, duration: 0.9, ease: "power3.out", stagger: 0.09, delay: 0.11,
  }));
  on(absent, (t) => gsap.to(t, {
    scaleX: 1, opacity: 1, duration: 0.9, ease: "power3.out", stagger: 0.09, delay: 0.11,
  }));
  values.forEach((v, i) => countUp(v, { delay: 0.11 + i * 0.09 }));
}

/* The stage a tab talks to when there is no pin -- below the locked
   breakpoint, and under reduced motion. It declines every seek, so the tabs
   fall back to plain immediate selection with no branch anywhere else. */
const UNPINNED = { seekTab: () => false, locked: () => false };

/* THE TABS, UNDER A PIN.

   These are real buttons and they stay real buttons. But once the section is
   one pinned screen, the scroll position IS the tab index for the length of
   the bench movement, so a click that merely set the panel would be overridden
   by the reader's next wheel notch and would read as the control being broken.

   The rail already answered this question. Its five nav buttons never set a
   panel; they seek their timeline and let the scrub arrive at the panel by
   itself (limits.js, the `onJump` note). The tabs now do the same thing, and
   `stage` is how: locked, a click or an arrow key scrolls to that tab's slice
   of the pin and the timeline selects it on the way past. Stacked, the stage
   declines the seek and selection stays immediate, which is exactly the
   control this was before.

   One source of truth either way: nothing calls `select` except this file, and
   under the pin only the timeline calls it. */
function wireTabs(proof, figures, state, stage = UNPINNED) {
  const bench = proof.querySelector("[data-bench]");
  const chart = proof.querySelector("[data-chart]");
  if (!bench || !chart) return null;

  const tabs = [...bench.querySelectorAll("[data-tab]")];

  const select = (id, { focus = false } = {}) => {
    const tab = TABS.find((t) => t.id === id);
    if (!tab || state.current === id) return;
    state.current = id;

    tabs.forEach((button) => {
      const on = button.dataset.tab === id;
      button.classList.toggle("is-active", on);
      button.setAttribute("aria-selected", String(on));
      button.tabIndex = on ? 0 : -1;
      if (on && focus) button.focus();
    });
    chart.setAttribute("aria-labelledby", `bench-tab-${id}`);

    /* The brief's own sequence: clear, swap after a beat, replay. The delay is
       what makes the swap read as a change rather than a jump cut. */
    const swap = () => {
      chart.innerHTML = chartMarkup(tab, figures);
      requestAnimationFrame(() => playChart(chart, { entrance: true }));
      /* Locked, the chart is absolutely placed and its height cannot move the
         document, so there is nothing to refresh -- and refreshing mid-scrub
         re-measures a pin the reader is standing inside, which jumps the
         scroll under them. Stacked, the swap really does change the page
         height and the refresh is still correct. */
      if (!stage.locked()) ScrollTrigger.refresh();
    };

    if (reduced()) { swap(); return; }
    gsap.to(chart, {
      opacity: 0, duration: 0.14, ease: "power1.in",
      onComplete: () => {
        swap();
        gsap.to(chart, { opacity: 1, duration: 0.2, ease: "power1.out" });
      },
    });
  };

  const go = (id, opts) => {
    const index = TABS.findIndex((t) => t.id === id);
    if (index < 0) return;
    /* Locked, the seek reports that it took the request and the timeline will
       do the selecting on the way past. Stacked, it declines and the panel
       changes here and now, which is the behaviour this control has always
       had. */
    if (stage.seekTab(index)) return;
    select(id, opts);
  };

  bench.addEventListener("click", (event) => {
    const button = event.target.closest("[data-tab]");
    if (button) go(button.dataset.tab);
  });

  bench.addEventListener("keydown", (event) => {
    const index = tabs.indexOf(document.activeElement);
    if (index < 0) return;
    let next = -1;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    event.preventDefault();
    /* Focus moves with the arrow key even when the panel is being reached by a
       seek, so the keyboard reader is never left focused on the tab they came
       from while a different one becomes current. */
    tabs[next].focus();
    go(tabs[next].dataset.tab, { focus: true });
  });

  return { select, tabs };
}

function wireField(proof) {
  const host = proof.querySelector("[data-proof-field]");
  if (!host) return;

  let teardown = null;
  const mount = () => {
    if (teardown) { teardown(); teardown = null; }
    const mode = document.documentElement.dataset.theme === "field" ? "light" : "dark";
    teardown = mountPortalField(host, {
      mode,
      still: reduced(),
      /* The registered component applies these four as CSS on its own element.
         brightness is the lever that keeps the arc's 0.517 peak off the type;
         the rest are the registered defaults. */
      /* Measured, not chosen by eye: at brightness 0.62 the lit ground pushed
         --ink-3 small text down to 3.84:1 against a 4.5 floor. These two are
         the levers the registered component exposes for exactly this. */
      opacity: mode === "light" ? 0.42 : 0.62,
      brightness: 0.46,
      /* 24 Sep 2026: its navy is pulled most of the way to neutral, so the
         proof is lit by the same silver key as the film above it and the
         shelf it leads to, rather than by a blue of its own. Saturation only;
         the brightness and opacity that the contrast floors were measured
         against are unchanged. */
      saturation: 0.3,
      hue: 0,
      speed: 1,
    });
  };

  mount();
  window.addEventListener("themechange", mount);
  onReducedChange(mount);
}

/* ---------------------------------------------------------------------------
   THE LIMITS RAIL'S GROUND.

   The rail had no background of its own: a --ch-facial tint on its ::before,
   a grain plate on its ::after, and flat --screen under both. This puts the
   Predictive Arc behind them -- vendored in predictivearc.js, which holds the
   provenance, the deviations and the hue measurement.

   WHY THIS COMPONENT HERE. The rail's subject is the boundary of the
   instrument, and the registered arc is literally a boundary figure: a dome
   that rises, crowns, and is extinguished at both edges by its own
   1 - |normX|^2.5 falloff. It ends rather than continues, which is the one
   thing every other ground on this page does not do. It also sits behind a
   lit 3D helicoid the rail already draws, and an additive dome is the only
   one of the four that backlights rather than competes with it.

   WHY THE HOST IS BUILT HERE RATHER THAN IN limits.js. The field is #proof's
   concern -- wireField above mounts the other one -- and limits.js stays about
   the rail's own content and behaviour, which is the separation it already had.

   The host is prepended rather than appended so it is the first child in
   paint order. Nothing in limits.css or limits.js selects by position; that
   was checked before doing it.
   --------------------------------------------------------------------------- */
function wireLimitsField(proof) {
  const rail = proof.querySelector("[data-limits]");
  if (!rail) return;

  let host = rail.querySelector("[data-limits-field]");
  if (!host) {
    host = document.createElement("div");
    host.className = "la-field";
    host.setAttribute("data-limits-field", "");
    host.setAttribute("aria-hidden", "true");
    rail.prepend(host);
  }

  let teardown = null;
  const mount = () => {
    if (teardown) { teardown(); teardown = null; }
    const mode = document.documentElement.dataset.theme === "field" ? "light" : "dark";
    teardown = mountPredictiveArc(host, {
      mode,
      still: reduced(),
      /* Unrotated this ground sits 10.0 degrees from --ch-vocal. +30 is the
         measured peak of the only wide gap its hue family has (clearance
         40.0) and +20 is the value here (clearance 30.0), traded down because
         +30 reads pink and pink means --tear on this page. The sweep and the
         trade are both written out in predictivearc.js. */
      hue: 20,
      /* The dome's violet is the last coloured wash on the page. Pulled to a
         silver dome it still backlights the helicoid, and violet stays what
         it means everywhere else: the vocal channel. */
      saturation: 0.25,
      /* spacing 5 -> 7 is a cost decision, measured: see the note in
         LIMITS_FIELD below. dotSize stays at the registered 6, so at 7 the
         dots stop overlapping and the dome resolves as a matrix rather than a
         wash -- which is the reading this rail wants anyway. */
      spacing: 7,
      dotSize: 6,
      speed: 0.6,
      brightness: LIMITS_FIELD.brightness[mode],
      opacity: LIMITS_FIELD.opacity[mode],
    });
  };

  mount();
  window.addEventListener("themechange", mount);
  onReducedChange(mount);
}

/* Set by measurement, not by eye; ui_evidence/measure_grounds.py is the run
   that produced them and the contrast floors they were tuned against. */
const LIMITS_FIELD = {
  brightness: { dark: 0.58, light: 0.9 },
  opacity: { dark: 0.72, light: 0.38 },
};

/* ---------------------------------------------------------------------------
   THE STORYBOARD.

   Measured on the build this replaces, at 1440x900: the reading column stood
   1227px tall against a 900px screen, of which only 931px was content -- the
   heading and lede 286, the four counts 145, the bench 500. The remaining
   297px was padding and two gaps. So the section could not be made to fit by
   trimming space: even stripped of every pixel of it the content was 31px over
   at 900 and 187px over at 1280x720. A section that will not fit a screen as a
   column can still fit one as a sequence, which is what the film and the seam
   above it already are, and what this now is.

   THREE MOVEMENTS, ONE SCREEN

     1. THE LEDGER   the heading, and four counts that tick up beside it
     2. THE BENCH    the counts leave, the chart takes the same box, and the
                     three views turn under the scrub
     3. THE RAIL     the reading column crosses out and the five limits take
                     the whole screen, exactly as they did before

   The heading does not move between 1 and 2. It is the section's one claim and
   the evidence under it is what changes, so holding it still and swapping the
   surface underneath says that, where fading it out and bringing it back would
   say these were two unrelated screens.

   WHAT IT COSTS THE READER: ABOUT TWO SCREENS MORE

   Measured at 1440x900, the old section occupied 5908px of document -- 1227px
   of ordinary column and 4680px of the rail's own pin spacer. This one
   occupies 7605px: the screen itself plus SPAN screens of scroll. So it is
   1697px longer, a little under two screens, and that is the real price of
   holding the ledger and the bench instead of letting the reader scroll past
   them.

   It buys the rhythm the rest of the page keeps -- hero, seam, film, each one
   screen -- which used to break here and resume at the bottom of the section.

   THE DWELL IS NOT NEGOTIABLE, AND THAT WAS LEARNED THE HARD WAY

   The first version of this budget spent 6.5 screens rather than 7.45, by
   taking the difference out of the rail. Measured against the build it
   replaced, on the same machine, the five panels went from 756px of scroll
   each to 512 -- a third less -- and the author reported the rail as jumping
   straight to the next section. It was not: panel 05 was still reached and
   still held. It was simply moving half again as fast as it used to, in a page
   whose whole argument is that each screen is held.

   So the rail is back to 720px a panel, near the 756 it always had, and the
   bench's three views give up the difference at 450px each -- a bar chart is
   read faster than five lines of prose about a limitation, so that is where
   the saving belongs. A quarter screen of stillness is left at the end, after
   the fifth panel finishes and before the pin lets go, because a scrubbed
   timeline lags the scroll and without it the last panel is still settling as
   the section starts to leave.

   WHY ONE PIN AND NOT TWO

   The rail used to pin itself. Nesting that inside a section pin makes the two
   triggers measure against each other's spacers and disagree on every refresh.
   The rail therefore gave up its ScrollTrigger and kept everything else; see
   the note at the top of wireLimits in limits.js.
   --------------------------------------------------------------------------- */

/* The scroll budget and every beat inside it, in viewport heights. SPAN runs
   past the last beat on purpose: 7.20 to 7.45 is the hold described above. */
const SPAN = 7.45;

const BEAT = {
  ledgerOut:  0.85,   // the counts leave the well
  benchIn:    0.95,   // the chart arrives in it
  tabsFrom:   1.20,   // the three views begin their turn, 0.50 each -- 450px
  tabsTo:     2.70,
  crossFrom:  2.75,   // the reading column goes, the rail comes
  crossTo:    3.20,
  limitsFrom: 3.20,   // and the rail starts its own five, 0.80 each -- 720px
  limitsTo:   7.20,
};

/* THE CROSS IS NOT A DISSOLVE.

   Half a screen of two entirely different compositions at half opacity each
   reads as mud, not as a transition: at the midpoint the reader is looking at
   a bar chart and a lit helicoid through one another. These two numbers make
   the column finish leaving before the rail is much more than started, so
   there is a moment of nothing but the ground between them -- a cut with a
   breath in it rather than a fade. 0.10 of the cross is spent with both on
   screen, against 1.00 for a straight crossfade. */
const OUT_BY = 0.55;   // the reading column is gone by here
const IN_FROM = 0.45;  // the rail starts here

/* Where in the scroll a given view or limit is the one being shown. Both land
   a little past the start of their own slice rather than on the boundary, so a
   seek arrives inside a panel and never on the seam between two. */
const tabAt = (i) =>
  BEAT.tabsFrom + ((BEAT.tabsTo - BEAT.tabsFrom) * (i + 0.4)) / TABS.length;
const limitAt = (i) =>
  BEAT.limitsFrom + ((BEAT.limitsTo - BEAT.limitsFrom) * (i + 0.4)) / 5;

export function wireProof(figures) {
  const proof = document.querySelector("[data-proof]");
  if (!proof) return;

  const f = {
    corpus: (figures && figures.corpus) || {},
    pipeline: (figures && figures.pipeline) || {},
    controller_references: (figures && figures.controller_references) || [],
  };
  const state = { current: TABS[0].id };

  const parts = {
    reading: proof.querySelector("[data-proof-reading]"),
    ledger: proof.querySelector(".ledger"),
    bench: proof.querySelector("[data-bench]"),
    atlas: proof.querySelector("[data-limits]"),
    portal: proof.querySelector("[data-proof-field]"),
    chart: proof.querySelector("[data-chart]"),
  };
  const counts = [...proof.querySelectorAll(".ledger__n")];

  /* The one trigger, held here because both navigations seek it: the bench's
     three tabs and the rail's five. Null whenever the section is not locked,
     which is the only test either of them needs. */
  let master = null;
  const locked = () => !!master;

  const seekTo = (seconds) => {
    if (!master) return false;
    const { start, end } = master;
    window.scrollTo({
      top: start + (end - start) * (seconds / SPAN),
      behavior: reduced() ? "auto" : "smooth",
    });
    return true;
  };

  wireField(proof);
  wireLimitsField(proof);
  const rail = wireLimits(proof, { onJump: (i) => seekTo(limitAt(i)) });
  const tabs = wireTabs(proof, f, state, {
    locked,
    seekTab: (i) => seekTo(tabAt(i)),
  });

  /* THE WELL MUST NOT CHANGE HEIGHT WHEN THE VIEW DOES.

     The three views are not the same height -- measured at 1440x900 they came
     out 523, 596 and 576px, because only the accuracy view carries the facial
     row's band caption and the notes wrap differently under each. Centred in a
     box that resizes under them, the bars stepped up to 73px vertically at the
     moment of a swap, which is the one motion on this screen the reader did not
     ask for.

     So the well is floored at the tallest of the four states it can hold -- the
     ledger and the three views -- measured from the real DOM at the real width
     rather than guessed at as a magic number, and re-measured whenever the pin
     re-measures. The chart's markup is swapped in to be measured and put back
     exactly as it was found, inline styles and all, so a floor taken after the
     bars have played does not reset them. */
  const floorWell = () => {
    const well = proof.querySelector("[data-well]");
    if (!well || !parts.chart || !parts.bench) return;
    const keep = parts.chart.innerHTML;
    well.style.removeProperty("min-block-size");
    /* The ledger is deliberately NOT in this maximum. It is swapped for the
       chart under a slide and a fade, and a box that resizes behind a moving
       object is invisible; it is the tab swap, where nothing else moves, that
       the eye catches. Flooring to the ledger as well would only add empty
       space under the counts for no reading anyone gets. */
    let tallest = 0;
    for (const tab of TABS) {
      parts.chart.innerHTML = chartMarkup(tab, f);
      tallest = Math.max(tallest, parts.bench.offsetHeight);
    }
    parts.chart.innerHTML = keep;
    well.style.setProperty("min-block-size", `${Math.ceil(tallest)}px`);
  };
  const unfloorWell = () => {
    proof.querySelector("[data-well]")?.style.removeProperty("min-block-size");
  };

  /* Both count-ups are one-shot. Under the pin the timeline fires them, and a
     scrubbed timeline runs a callback every time the playhead crosses it in
     either direction -- so the guard lives here rather than in either caller,
     and the same two functions serve the pinned and the stacked path. */
  const fired = new Set();
  const once = (key, run) => {
    if (fired.has(key)) return;
    fired.add(key);
    run();
  };
  const runLedger = () => once("ledger", () => {
    counts.forEach((cell, i) => countUp(cell, { delay: i * 0.08 }));
  });
  const runChart = () => once("chart", () => playChart(parts.chart));

  /* Stacked, each block is still triggered where IT enters, not where the
     section does -- firing everything from the section's top edge finished the
     whole animation a screen and a half before the reader reached the chart. */
  const onEnter = (trigger, run) => {
    if (!trigger) return;
    if (reduced()) { run(); return; }
    ScrollTrigger.create({ trigger, start: "top bottom-=18%", once: true, onEnter: run });
  };

  /* The rail's own condition, kept exactly as it was. It is the binding one:
     .la-playing asks for 680px of height and lays five panels out against a
     screen, so a viewport that cannot hold the rail cannot hold the locked
     section either. Reusing it means there is no second breakpoint to keep in
     step with the first. */
  let media = null;
  const buildStage = () => {
    media = motionMedia({
      lock: "(min-width: 860px) and (min-height: 740px) and (prefers-reduced-motion: no-preference)",
      stack: "(max-width: 859px), (max-height: 739px), (prefers-reduced-motion: reduce)",
    }, (context) => {
      if (!context.conditions.lock) {
        /* Stacked: the section is the document it has always been. Every block
           is present, nothing is driven, and the reader scrolls past all three
           movements in order. This is also the reduced-motion path. */
        delete proof.dataset.locked;
        delete proof.dataset.stage;
        delete proof.dataset.grounds;
        rail?.setPlaying(false);
        gsap.set([parts.reading, parts.ledger, parts.bench, parts.atlas, parts.portal],
          { clearProps: "opacity,visibility,transform" });
        unfloorWell();
        onEnter(parts.ledger, runLedger);
        onEnter(parts.chart, runChart);
        return;
      }

      proof.dataset.locked = "";
      proof.dataset.stage = "reading";
      proof.dataset.grounds = "reading";
      rail?.setPlaying(true);

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: proof,
          start: "top top",
          end: () => `+=${window.innerHeight * SPAN}`,
          scrub: 0.55,
          pin: true,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          /* The last pinned section on the page, so it refreshes last and its
             start is measured against spacers the seam and the film have
             already inserted above it. */
          refreshPriority: -1,
          /* The floor is a pixel height taken at the current width, so it is
             wrong the moment the window is resized -- and a refresh is exactly
             when ScrollTrigger has decided everything else is wrong too. */
          onRefresh: floorWell,
        },
      });
      master = tl.scrollTrigger;
      floorWell();

      /* The storyboard is written in viewport heights, so the timeline has to
         actually be SPAN long or every beat drifts forward by the shortfall.
         Same reason the seam does it. */
      tl.set({}, {}, SPAN);

      /* The rail is the last layer and must not be sitting over the first two
         before its turn. Set at 0 rather than left to CSS so that reverting the
         media query has an inline property to clear. */
      tl.set(parts.atlas, { opacity: 0 }, 0);

      /* 1. THE LEDGER. */
      tl.call(runLedger, null, 0.05);

      /* 2. THE BENCH takes the well. The counts leave upward and the chart rises
            into the same box, so the heading never moves: one surface changing
            rather than two screens passing. */
      tl.to(parts.ledger,
        { autoAlpha: 0, y: -28, duration: 0.32, ease: "power2.in" }, BEAT.ledgerOut);
      tl.fromTo(parts.bench,
        { autoAlpha: 0, y: 30 },
        { autoAlpha: 1, y: 0, duration: 0.38, ease: "power2.out" }, BEAT.benchIn);
      tl.call(runChart, null, BEAT.benchIn + 0.22);

      /* 3. THE THREE VIEWS turn under the scrub. `select` returns immediately
            when the id has not changed, so this is three swaps across the slice
            and not one a frame. */
      const cursor = { i: 0 };
      tl.to(cursor, {
        i: TABS.length,
        duration: BEAT.tabsTo - BEAT.tabsFrom,
        ease: "none",
        onUpdate: () => {
          const index = Math.min(TABS.length - 1, Math.max(0, Math.floor(cursor.i)));
          tabs?.select(TABS[index].id);
        },
      }, BEAT.tabsFrom);

      /* 4. THE CROSS. One scalar carries the reading column out and the rail in,
            so the two can never be half-lit by tweens that disagree, and the
            attribute deciding which layer takes the mouse is written from the
            same number that decides what can be seen. The portal field goes with
            the column it belongs to: the rail brings its own ground, and lighting
            the screen twice was measured as the thing that made this section read
            as a lit box rather than a lit page. */
      const cross = { t: 0 };
      tl.to(cross, {
        t: 1,
        duration: BEAT.crossTo - BEAT.crossFrom,
        ease: "power2.inOut",
        onUpdate: () => {
          const out = 1 - Math.min(1, cross.t / OUT_BY);
          const into = Math.max(0, (cross.t - IN_FROM) / (1 - IN_FROM));
          gsap.set(parts.reading, { opacity: out });
          gsap.set(parts.portal, { opacity: out });
          gsap.set(parts.atlas, { opacity: into });
          proof.dataset.stage = into >= out ? "limits" : "reading";
          /* And which GROUNDS may run. Not the same question as which layer
             takes the mouse, and not switchable at the same moment: the mouse
             can change hands at the midpoint, but a ground left unmounted until
             the midpoint would pop in behind a rail that is already half lit.
             So this opens at the first pixel of either layer and closes at the
             last, and both are mounted through the crossfade only. The reason
             it matters is measured in proof.css, under THE COST OF A GROUND
             THAT NEVER LEAVES. */
          proof.dataset.grounds = into > 0 ? (out > 0 ? "both" : "limits") : "reading";
        },
      }, BEAT.crossFrom);

      /* 5. THE FIVE, driven exactly as the rail used to drive itself -- the same
            scalar, the same easing, the same render. */
      if (rail) {
        tl.fromTo(rail.state, { p: 0 }, {
          p: 1,
          ease: "none",
          duration: BEAT.limitsTo - BEAT.limitsFrom,
          onUpdate: rail.render,
        }, BEAT.limitsFrom);
      }

      return () => {
        master = null;
        unfloorWell();
        delete proof.dataset.locked;
        delete proof.dataset.stage;
        delete proof.dataset.grounds;
      };
    });
  };

  buildStage();

  /* Printing must never capture a number mid-tween, and a printed page has no
     scroll to have triggered anything in the first place. */
  const settle = () => {
    gsap.globalTimeline.progress(1);
    counts.forEach((cell) => {
      const run = cell.querySelector("[aria-hidden]");
      const sr = cell.querySelector(".sr-only");
      if (run && sr) run.textContent = sr.textContent;
    });
    proof.querySelectorAll(".bar__value[data-final]").forEach((v) => {
      const run = v.querySelector(".bar__run");
      if (run) run.textContent = v.dataset.final;
    });
    proof.querySelectorAll(".bar").forEach((b) => gsap.set(b, { opacity: 1, y: 0 }));
    proof.querySelectorAll(".bar__fill, .bar__band").forEach((b) => gsap.set(b, { scaleX: 1, opacity: 1 }));
    /* Every movement prints, whichever one the scrub happened to stop on. The
       CSS puts them back into flow; this clears the inline opacities the
       timeline left on them. */
    gsap.set([parts.reading, parts.ledger, parts.bench, parts.atlas, parts.portal],
      { clearProps: "opacity,visibility,transform" });
  };
  /* A PINNED SECTION CANNOT BE PRINTED BY A STYLESHEET ALONE.

     ScrollTrigger pins by writing `position: fixed` inline on the element and
     reserving its height in a spacer around it. An inline declaration outranks
     any rule in a print block that is not `!important`, and nothing in CSS can
     collapse the spacer -- so `@media print` alone printed this section as one
     frozen frame inside 6750px of reserved blank, which is what the first run
     of the check found.

     Dropping the pin first is not a workaround for the print stylesheet. It IS
     the print layout: reverting the media query puts the section back into the
     stacked path this file already has, spacer and all inline styles removed
     with it, and that path is an ordinary document in reading order. The print
     rules in proof.css stay as a net for any pipeline that renders to paper
     without firing these events. */
  window.addEventListener("beforeprint", () => {
    if (media) { media.revert(); media = null; }
    rail?.setPlaying(false);
    settle();
  });
  window.addEventListener("afterprint", () => { if (!media) buildStage(); });

  onReducedChange((now) => { if (now) settle(); });
}
