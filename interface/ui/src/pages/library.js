/* ===========================================================================
   library.js — everything saved on this machine.

   A RACK, NOT A LIST OF ROWS.

   Every saved run already has a shape: its own conflict trace, its own flagged
   seconds, its own coverage. The build this replaces printed filenames and
   numbers, so two runs that look nothing like each other read identically. Here
   each run carries its own trace drawn from its own data at card size, so the
   rack is scannable by picture before it is read by name.

   Two runs can be selected and held against each other without leaving the
   page: the comparison strip at the foot draws both traces on ONE shared time
   scale, which is the only way two videos of different lengths can honestly be
   put side by side.

   Every figure on this page is read from the report it belongs to. Nothing is
   estimated and nothing is carried over from another run.
   ======================================================================== */

import "../styles/tokens.css";
import "../styles/chassis.css";
import "../styles/transport.css";
import "../styles/library.css";

import { mountAll } from "../lib/chrome.js";
import { mountAnnouncer, announce } from "../lib/announce.js";
import {
  listReports, getReport, getSweep, listSweeps, deleteReport, deleteSweep,
} from "../lib/api.js";
import { CHANNELS, CHANNEL_META, coverage, segmentValences } from "../lib/contract.js";
import { count, esc, mmss, pct, score, splitReportName, savedOn } from "../lib/format.js";
import { createClock, mountTransport } from "../lib/transport.js";
import { manifest, plateFor, videoIdOf } from "../lib/frames.js";
import { stashFlip, reduced, onReducedChange } from "../lib/motion.js";
import { onThemeChange } from "../lib/theme.js";
/* The volume's own handoff to the report page. See handOff() in wireShelf. */
import { stashVolume, takeReturn } from "../lib/leaf.js";
/* The bookcase's dimensions only -- about a kilobyte of arithmetic, and no
   three.js. The page needs the case's PROPORTION to size the stage before it
   knows whether it will draw one; the renderer stays behind a dynamic import. */
import { shelfBox } from "../lib/shelfgeom.js";
import "../styles/shelf.css";

const root = document.querySelector("[data-library]");

const ORDERS = [
  { key: "conflict", label: "Most disagreement", of: (r) => -(r.flaggedShare ?? -1) },
  { key: "auth", label: "Authenticity", of: (r) => -(r.authenticity ?? -1) },
  { key: "health", label: "Brand health", of: (r) => -(r.health ?? -1) },
  { key: "covered", label: "Least measured", of: (r) => (r.facialShare ?? 2) },
  { key: "size", label: "Longest run", of: (r) => -(r.segments ?? -1) },
];

const FILTERS = [
  { key: "all", label: "All", of: () => true },
  { key: "flagged", label: "Has flagged moments", of: (r) => (r.flagged || 0) > 0 },
  { key: "thin", label: "Thin facial coverage", of: (r) => (r.facialShare ?? 1) < 0.5 },
];

function state(tag, heading, body, extra = "") {
  root.innerHTML = `
    <section class="state${tag === "Unreachable" ? " state--error" : ""}">
      <p class="t-label state__tag">${esc(tag)}</p>
      <h1 class="t-l">${esc(heading)}</h1>
      <p class="t-body">${body}</p>${extra}
    </section>`;
  clearTimeout(window.__bpFallback);
}

/* --- reading one report down to what a card needs ----------------------- */

async function enrich(entry, man) {
  const { brand, product } = splitReportName(entry.filename);
  const base = {
    filename: entry.filename, brand, product, ok: false,
    savedOn: savedOn(entry.saved_at),
  };
  try {
    const report = await getReport(entry.filename);
    const segments = (report.all_segments || []).filter(
      (s) => typeof s.start_s === "number" && typeof s.end_s === "number");
    if (!segments.length) return { ...base, empty: true };

    const flagged = segments.filter((s) => s.flagged).length;
    const cov = coverage(segments, report.comment_sentiment);
    const duration = Math.max(...segments.map((s) => s.end_s));

    /* The most conflicted moment is the one worth showing a picture of. */
    const worst = segments.reduce((a, b) =>
      (b.conflict_score ?? -1) > (a.conflict_score ?? -1) ? b : a, segments[0]);

    return {
      ...base,
      ok: true,
      report,
      segments,
      duration,
      segmentCount: segments.length,
      flagged,
      flaggedShare: segments.length ? flagged / segments.length : 0,
      authenticity: report.authenticity_score,
      health: report.brand_health_score,
      comments: (report.all_comments || []).length,
      room: (report.comment_sentiment || {}).label || null,
      facialShare: cov.facial.share,
      thinChannels: CHANNELS.filter((c) => CHANNEL_META[c].perSegment && cov[c].thin),
      videoId: videoIdOf(report),
      plate: plateFor(man, videoIdOf(report), worst),
      worst,
      hasCaveat: Boolean(report.bias_caveat),
    };
  } catch (error) {
    return { ...base, error: (error && error.message) || "could not be read" };
  }
}

/* --- the volumes --------------------------------------------------------

   One volume per saved run, and one per sweep. Nothing printed on a board is
   invented: the brand and product are the report's own filename, the date is
   its mtime, the two figures are `authenticity_score` and `brand_health_score`
   read from the report, and the plate is the frame the pipeline extracted at
   that run's most-conflicted second.

   One video can be saved more than once (six of the eleven runs saved on 24
   Sep 2026 were the same one), so the picture cannot be what tells runs
   apart. The product, the date and the two scores are, and they are what the
   spine and the cover foot carry.
   ------------------------------------------------------------------------ */

const SHELF_MIN_WIDTH = 900;
/* A room needs height as well as width. The stage keeps a 640px floor on
   short windows (shelf.css), so at 1024x430 -- a phone held sideways, or a
   laptop at 200% zoom -- the shelf stood taller than the window with
   `touch-action: none` on it, and a finger on the canvas could not scroll the
   page. Below this the runs are a list. */
const SHELF_MIN_HEIGHT = 600;
const SHELF_FITS = `(min-width: ${SHELF_MIN_WIDTH}px) and (min-height: ${SHELF_MIN_HEIGHT}px)`;

/* The reader's own choice of view, kept per browser (a convenience, so it may
   be missing -- a private window, cleared storage -- and the page must not
   care). Only "list" is ever stored: the shelf is the default wherever it can
   be drawn, and asking for it back simply forgets the choice. */
const VIEW_KEY = "brandpulse-library-view";
function prefersList() {
  try { return localStorage.getItem(VIEW_KEY) === "list"; } catch { return false; }
}
function rememberList(yes) {
  try {
    if (yes) localStorage.setItem(VIEW_KEY, "list");
    else localStorage.removeItem(VIEW_KEY);
  } catch { /* storage refused: the choice lasts this page only */ }
}

/* three.js is 400KB of the library bundle and only the shelf uses it, so it is
   behind a dynamic import and is never fetched by a reader who will not get a
   shelf: a narrow viewport, no WebGL context, or reduced motion. The check
   itself has to be local for the same reason -- importing the module to ask it
   whether it is needed would defeat the split. */
/** Whether this window, this machine and this reader can have the shelf at all. */
function shelfPossible() {
  return shelfAvailable() && !reduced() && window.matchMedia(SHELF_FITS).matches;
}

/* Asked once. Each probe creates a WebGL context and a browser keeps only a
   handful alive, so a probe on every resize would starve the shelf's own. */
let glAnswer = null;
function shelfAvailable() {
  if (glAnswer !== null) return glAnswer;
  try {
    const c = document.createElement("canvas");
    glAnswer = Boolean(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { glAnswer = false; }
  return glAnswer;
}
function volumeOfRun(row) {
  const flagged = (row.flagged || 0) > 0;
  return {
    id: `run:${row.filename}`,
    kind: "run",
    href: `/library/${encodeURIComponent(row.filename)}`,
    title: row.brand || "Untitled",
    sub: row.product || "",
    kicker: "One video",
    authText: score(row.authenticity),
    healthText: score(row.health),
    foot: row.savedOn || "",
    filename: row.filename,
    spineTitle: row.product || row.brand || "Untitled",
    spineFoot: row.savedOn || "",
    flagged,
    seed: row.filename.length * 37 + 5,
    plateUrl: row.plate || null,
    ledger: [
      ["Authenticity", score(row.authenticity)],
      ["Brand health", score(row.health)],
      ["Segments", count(row.segmentCount)],
      ["Flagged", count(row.flagged)],
      ["Facial coverage", pct((row.facialShare || 0) * 100)],
    ],
    blurb: flagged
      ? `${count(row.flagged)} of ${count(row.segmentCount)} segments were flagged as disagreeing across the four channels.`
      : "No segment in this run crossed the conflict threshold.",
    listLine: `${row.brand}${row.product ? " " + row.product : ""} — ${score(row.authenticity)} authenticity`,
  };
}

function volumeOfSweep(sw) {
  const id = sw.sweep_id || sw.id || "";
  return {
    id: `sweep:${id}`,
    kind: sw.subject_kind || "unfiled",
    href: `/brand/${encodeURIComponent(id)}`,
    title: sw.subject || "Untitled sweep",
    sub: "",
    kicker: `${count(sw.video_count || 0)} videos combined`,
    authText: score(sw.authenticity),
    healthText: score(sw.brand_health),
    foot: savedOn(sw.finished_at) || "",
    filename: id,
    /* Named in the delete confirmation, so the warning can say what actually
       goes rather than "and its contents". */
    videoCount: sw.video_count || 0,
    spineTitle: sw.subject || "Sweep",
    spineFoot: sw.window ? `${sw.window}${Number(sw.offset_days || 0) ? `, ${count(Number(sw.offset_days))}d earlier` : ""}` : "",
    flagged: false,
    seed: id.length * 53 + 11,
    plateUrl: null,
    ledger: [
      ["Mean authenticity", score(sw.authenticity)],
      ["Mean brand health", score(sw.brand_health)],
      ["Videos", count(sw.video_count || 0)],
      ["Window", sw.window ? periodOf(sw) : "—"],
      ["Controller", sw.controller || "—"],
    ],
    blurb: "Five videos about one subject, combined. The spread is the finding, not the average.",
    listLine: `${sw.subject} — ${score(sw.authenticity)} mean authenticity`,
  };
}

/* Decode every plate before a board is painted. paintCover draws the image
   synchronously, so an undecoded one silently produces a cloth cover. */
async function withPlates(volumes) {
  await Promise.all(volumes.map((v) => new Promise((done) => {
    if (!v.plateUrl) return done();
    const im = new Image();
    im.onload = () => { v.plateImage = im; done(); };
    im.onerror = () => done();
    im.src = v.plateUrl;
  })));
  return volumes;
}

/* --- one card ------------------------------------------------------------ */

/* The id of a card's title. aria-labelledby takes a space-separated list of
   ids, so an id made from a raw filename ("Nike (Mind 001).json") names ids
   that do not exist and leaves the card's picture link with no accessible name. */
const titleId = (filename) => `t-${encodeURIComponent(filename)}`;

function card(row) {
  if (!row.ok) {
    return `
    <li class="rk__card is-broken">
      <div class="rk__body">
        <h3 class="t-panel">${esc(row.brand)}${row.product ? ` ${esc(row.product)}` : ""}</h3>
        <p class="t-small u-dim">${row.empty
          ? "This report has no segments. Transcription produced nothing to align the other three channels to, so there is nothing to draw and nothing to score."
          : `Could not be read. ${esc(row.error || "")}`}</p>
        <p class="t-micro u-faint"><code>${esc(row.filename)}</code></p>
      </div>
    </li>`;
  }

  return `
  <li class="rk__card" data-file="${esc(row.filename)}">
    <label class="rk__pick">
      <input type="checkbox" data-compare value="${esc(row.filename)}">
      <span class="sr-only">Hold ${esc(row.brand)} ${esc(row.product)} against another run</span>
    </label>

    <a class="rk__open" href="/library/${encodeURIComponent(row.filename)}"
       data-open aria-labelledby="${esc(titleId(row.filename))}">
      <span class="rk__frame" data-flip-id="library-frame">
        ${row.plate
          ? `<img src="${row.plate}" alt="" loading="lazy">`
          : `<span class="rk__noframe"></span>`}
      </span>
    </a>

    <div class="rk__body">
      <h3 class="t-panel" id="${esc(titleId(row.filename))}">
        <a href="/library/${encodeURIComponent(row.filename)}" data-open>
          ${esc(row.brand)}${row.product ? ` <span class="u-dim">${esc(row.product)}</span>` : ""}
        </a>
      </h3>

      <div class="rk__sig" data-sig="${esc(row.filename)}"></div>

      <dl class="rk__nums">
        <div><dt class="t-micro u-faint">Authenticity</dt>
          <dd class="t-read">${score(row.authenticity)}</dd></div>
        <div><dt class="t-micro u-faint">Brand health</dt>
          <dd class="t-read">${score(row.health)}</dd></div>
        <div><dt class="t-micro u-faint">Flagged</dt>
          <dd class="t-read${row.flagged ? " is-tear" : ""}">${count(row.flagged)}</dd></div>
        <div><dt class="t-micro u-faint">Segments</dt>
          <dd class="t-read">${count(row.segmentCount)}</dd></div>
      </dl>

      <p class="rk__meta t-micro u-faint">
        ${mmss(row.duration)} of video
        <span class="rk__sep" aria-hidden="true"></span>
        ${count(row.comments)} comments
        ${row.savedOn ? `<span class="rk__sep" aria-hidden="true"></span>${esc(row.savedOn)}` : ""}
      </p>

      ${row.thinChannels.length ? `
        <p class="rk__thin t-micro">
          Thin coverage: ${row.thinChannels.map((c) =>
            esc(CHANNEL_META[c].short.toLowerCase())).join(", ")}. Under half this
          run carries a reading on ${row.thinChannels.length === 1 ? "it" : "them"}.
        </p>` : ""}
      ${deleteControl({ kind: "report", target: row.filename,
                        name: `${row.brand}${row.product ? ` ${row.product}` : ""}` })}
    </div>
  </li>`;
}

/* --- the sweeps ---------------------------------------------------------- */

const SWEEP_PERIODS = {
  week: "the last week", month: "the last month",
  half: "the last six months", year: "the last year",
};

/* The period a sweep covers, with where it ends: "the last month" alone would
   shelve a month ending six months ago beside last month's, as if they were
   the same period. The same rule as the combined book's own label. */
function periodOf(s) {
  const base = SWEEP_PERIODS[s.window] || s.window || "";
  const off = Number(s.offset_days || 0);
  return off ? `${base}, ending ${count(off)} days ago` : base;
}

/* GET /sweeps is the shelf's listing: one flat row per set, with the count and
   the two means and no summary. The list's cards print the range and the
   spread sentence too, which live only in each set's sweep.json, so the list
   reads those (a few kilobytes each) when it is the view being built. Until
   24 Sep 2026 the cards read a `summary` the listing never carried and
   printed "0 videos" and dashes for every set. A set that cannot be read
   keeps its listing row. */
function withSummaries(sweeps) {
  return Promise.all(sweeps.map((s) => getSweep(s.sweep_id)
    .then((full) => ({ ...s, summary: (full && full.summary) || s.summary }))
    .catch(() => s)));
}

function sweepSection(sweeps) {
  if (!sweeps.length) return "";
  return `
  <section class="sw" aria-labelledby="sw-h">
    <h2 id="sw-h" class="t-m">Combined runs</h2>
    <p class="t-lede">
      Each of these analysed up to five videos about one subject and reported
      both the average and how far apart they ended up. A combined score is an
      average of facial-derived ones, so every caveat on a single report applies
      to it too.
    </p>
    <ul class="sw__list">
      ${sweeps.map((s) => {
        const summary = s.summary || {};
        const auth = summary.authenticity || {};
        /* The listing row carries the count and the mean flattened; the
           summary (withSummaries) carries the range and the sentence. Either
           is enough for the first two, so a summary that could not be read
           costs the range and nothing else. */
        const videos = summary.video_count ?? s.video_count ?? (s.members || []).length;
        return `
        <li class="sw__one">
          <a class="sw__link" href="/brand/${encodeURIComponent(s.sweep_id || s.id || "")}">
            <h3 class="t-panel">${esc(s.subject || "Untitled sweep")}</h3>
          </a>
          <p class="t-micro u-faint">
            ${count(videos)} videos
            ${s.window ? `over ${esc(periodOf(s))}` : ""}
          </p>
          <dl class="sw__nums">
            <div><dt class="t-micro u-faint">Mean authenticity</dt>
              <dd class="t-read">${score(auth.mean ?? s.authenticity)}</dd></div>
            <div><dt class="t-micro u-faint">Range</dt>
              <dd class="t-read">${score(auth.min)} to ${score(auth.max)}</dd></div>
          </dl>
          ${summary.spread_verdict
            ? `<p class="t-small u-dim">${esc(summary.spread_verdict)}</p>` : ""}
          ${deleteControl({ kind: "sweep", target: s.sweep_id || s.id || "",
                            name: s.subject || "this combined run", videos })}
        </li>`;
      }).join("")}
    </ul>
  </section>`;
}

/* --- deleting from the list ----------------------------------------------

   The list is what a phone, a reader who has asked for reduced motion, and a
   machine with no WebGL get, and until 25 Sep 2026 it had no way to delete
   anything: Delete lived only on the shelf's desk, which only a pointer could
   open (INCLUSIVE_DESIGN.md A2). Same two steps and the same words as the desk,
   because the rule is the same -- neither can be undone, and a set takes its
   videos with it. The destructive button never sits beside the one that
   cancels it: the question replaces the first button rather than joining it. */
function deleteControl({ kind, target, name, videos = 0 }) {
  const question = kind === "sweep"
    ? `Delete ${name} and the ${count(videos)} video report${videos === 1 ? "" : "s"} inside it? This cannot be undone.`
    : `Delete ${name}? This cannot be undone.`;
  return `
    <div class="rk__del" data-del data-kind="${kind}" data-target="${esc(target)}" data-name="${esc(name)}">
      <button class="btn rk__delbtn" data-variant="quiet" type="button" data-del-ask>Delete</button>
      <div class="rk__delq" data-del-confirm hidden>
        <p class="t-small" data-del-text>${esc(question)}</p>
        <div class="rk__delacts">
          <button class="btn" data-variant="danger" type="button" data-del-yes>Delete permanently</button>
          <button class="btn" data-variant="quiet" type="button" data-del-no>Keep it</button>
        </div>
      </div>
    </div>`;
}

function wireDeletes(scope) {
  if (!scope) return;
  scope.addEventListener("click", async (event) => {
    const box = event.target.closest("[data-del]");
    if (!box) return;
    const ask = box.querySelector("[data-del-ask]");
    const confirm = box.querySelector("[data-del-confirm]");
    const text = box.querySelector("[data-del-text]");
    const yes = box.querySelector("[data-del-yes]");
    const no = box.querySelector("[data-del-no]");
    if (event.target.closest("[data-del-ask]")) {
      ask.hidden = true;
      confirm.hidden = false;
      yes.focus();
      announce(text.textContent);
    } else if (event.target.closest("[data-del-no]")) {
      confirm.hidden = true;
      ask.hidden = false;
      ask.focus();
    } else if (event.target.closest("[data-del-yes]")) {
      const name = box.dataset.name;
      yes.disabled = true;
      no.disabled = true;
      text.textContent = `Deleting ${name}\u2026`;
      try {
        if (box.dataset.kind === "sweep") await deleteSweep(box.dataset.target);
        else await deleteReport(box.dataset.target);
        announce(`${name} deleted. Reopening the library.`);
        window.location.reload();
      } catch (error) {
        text.textContent = `${name} was not deleted. ${error.message}`;
        yes.disabled = false;
        no.disabled = false;
        announce(text.textContent);
      }
    }
  });
  /* Escape answers the question, as it does on the desk. */
  scope.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const box = event.target.closest("[data-del]");
    const confirm = box && box.querySelector("[data-del-confirm]");
    if (!confirm || confirm.hidden) return;
    confirm.hidden = true;
    const ask = box.querySelector("[data-del-ask]");
    ask.hidden = false;
    ask.focus();
  });
}

/* --- the comparison strip ------------------------------------------------ */

function compareStrip() {
  return `
  <aside class="cmp" data-cmp hidden aria-label="Two runs compared">
    <div class="cmp__inner">
      <p class="cmp__tag t-label" data-cmp-tag></p>
      <div class="cmp__pair" data-cmp-pair></div>
      <button class="btn" type="button" data-cmp-clear>Clear</button>
    </div>
  </aside>`;
}

/* Two runs of different lengths, held on ONE shared scale. The shorter trace
   stops where it actually stops rather than being stretched to fill the width,
   because stretching it would make two different videos look like the same
   length, which is a claim neither of them makes. */
function comparePair(rows) {
  const longest = Math.max(...rows.map((r) => r.duration));
  return rows.map((r) => `
    <div class="cmp__one">
      <p class="t-label">${esc(r.brand)} <span class="u-dim">${esc(r.product)}</span></p>
      <div class="cmp__scale">
        <div class="cmp__trace" style="width:${((r.duration / longest) * 100).toFixed(2)}%"
             data-cmp-sig="${esc(r.filename)}"></div>
      </div>
      <dl class="cmp__nums t-micro">
        <div><dt>Authenticity</dt><dd class="t-read">${score(r.authenticity)}</dd></div>
        <div><dt>Brand health</dt><dd class="t-read">${score(r.health)}</dd></div>
        <div><dt>Flagged</dt><dd class="t-read">${count(r.flagged)} of ${count(r.segmentCount)}</dd></div>
        <div><dt>Runs for</dt><dd class="t-read">${mmss(r.duration)}</dd></div>
      </dl>
    </div>`).join("")
    + `<p class="cmp__note t-micro u-faint">
         Both traces are drawn on one scale, so the shorter run stops where it
         actually stops. Neither score is comparable between videos: a score is a
         statement about one run of one video with one controller model installed.
       </p>`;
}

/* --- boot ---------------------------------------------------------------- */

let rows = [];
/* Held at module scope because the reduced-motion path rebuilds the list long
   after render() has returned, and the list prints the sweeps. */
let sweepsOnPage = [];
let order = ORDERS[0];
let filter = FILTERS[0];
const chosen = new Set();

/* The traces on the page, by where they are drawn. A repaint replaces their
   markup, and each trace watches its size, the theme and reduced motion, so
   one not destroyed first outlives its card: measured 26 Sep 2026, 7 live
   observers became 147 after 20 clicks on the order buttons, every one of them
   redrawing a detached canvas on each theme change. */
const traces = { rack: [], compare: [] };

function clearTraces(where) {
  for (const trace of traces[where]) trace.destroy();
  traces[where] = [];
}

function paintSignature(host, row, where) {
  if (!host || !row.ok) return;
  const clock = createClock(row.duration, row.segments);
  traces[where].push(mountTransport(host, {
    report: row.report, segments: row.segments, clock, compact: true,
    /* Named for its run, so a list of cards is not a list of identical
       "Playhead" sliders to a screen reader (A16). */
    label: `${row.brand}${row.product ? ` ${row.product}` : ""}`,
  }));
}

function paint() {
  /* No rack when only combined runs are saved (listMarkup). */
  if (!root.querySelector("[data-rack]")) return;
  const list = rows.filter((r) => !r.ok || filter.of(r));
  const sorted = [...list].sort((a, b) => {
    if (!a.ok) return 1;
    if (!b.ok) return -1;
    return order.of(a) - order.of(b);
  });

  const host = root.querySelector("[data-rack]");
  clearTraces("rack");
  host.innerHTML = sorted.map(card).join("");

  for (const r of sorted) {
    if (!r.ok) continue;
    paintSignature(host.querySelector(`[data-sig="${CSS.escape(r.filename)}"]`), r, "rack");
  }

  const empty = root.querySelector("[data-rack-empty]");
  empty.hidden = sorted.length > 0;
  if (!sorted.length) {
    empty.textContent = `No saved run matches "${filter.label}". `
      + "That is a fact about this machine's corpus rather than an empty page.";
  }
  wireCards();
}

function wireCards() {
  for (const box of root.querySelectorAll("[data-compare]")) {
    box.checked = chosen.has(box.value);
    box.addEventListener("change", () => {
      if (box.checked) {
        if (chosen.size >= 2) {
          box.checked = false;
          announce("Two runs at a time. Clear one first.", { urgent: false });
          return;
        }
        chosen.add(box.value);
      } else {
        chosen.delete(box.value);
      }
      paintCompare();
    });
  }

  /* Carry the frame across the navigation so opening a report reads as
     travelling into it rather than loading a different page. */
  for (const link of root.querySelectorAll("[data-open]")) {
    link.addEventListener("click", () => {
      const card = link.closest(".rk__card");
      stashFlip(card ? card.querySelector("[data-flip-id]") : null);
    });
  }
}

function paintCompare() {
  const strip = root.querySelector("[data-cmp]");
  const tag = root.querySelector("[data-cmp-tag]");
  const pair = root.querySelector("[data-cmp-pair]");
  const picked = rows.filter((r) => chosen.has(r.filename) && r.ok);
  clearTraces("compare");

  if (!picked.length) { strip.hidden = true; return; }
  strip.hidden = false;

  if (picked.length === 1) {
    tag.textContent = "Pick one more to hold them against each other";
    pair.innerHTML = "";
    return;
  }

  tag.textContent = "Two runs, one scale";
  pair.innerHTML = comparePair(picked);
  for (const r of picked) {
    paintSignature(pair.querySelector(`[data-cmp-sig="${CSS.escape(r.filename)}"]`), r, "compare");
  }
  announce(`Comparing ${picked[0].brand} ${picked[0].product} and `
    + `${picked[1].brand} ${picked[1].product}.`);
}

async function main() {
  mountAnnouncer();
  mountAll({ here: "/library" });

  /* EVERYTHING THAT DOES NOT DEPEND ON THE LISTING STARTS NOW.

     This used to be four awaits in a row -- listing, then sweeps, then the
     frame manifest, then every report -- and each one waited for the last
     although only the reports actually need anything the others return.
     Measured on this machine, the manifest alone is a 315ms server call that
     was sitting between the listing and the first report read.

     The renderer goes with them. It is 523kB of WebGL that depends on no data
     at all, and it was being imported at the END of the wait, after every
     report had been read and every plate decoded. Whether a shelf is wanted is
     answerable immediately -- it asks the window and the reader's motion
     preference, nothing else -- so the download overlaps the reads instead of
     following them.

     Rejections are handled where they are created, not where they are awaited:
     a failed listing returns early, and a promise still in flight at that
     point must not become an unhandled rejection. */
  const wantShelf = shelfPossible() && !prefersList();
  const sweepsSoon = listSweeps().catch(() => []);
  const manifestSoon = manifest();               // catches internally
  const rendererSoon = wantShelf ? import("../lib/shelf.js") : null;
  /* Marks it handled so a failure during an early return is not an unhandled
     rejection. The real handling stays at the await below, unchanged: this
     attaches a second reaction, it does not replace the first. */
  if (rendererSoon) rendererSoon.catch(() => {});

  let entries = [];
  let sweeps = [];
  try {
    entries = await listReports();
  } catch (error) {
    /* A server that is not running and a server that cannot read its own
       outputs directory are different problems with different fixes, and
       telling a reader to start a server that is already running is worse than
       saying nothing. */
    if (error && error.status >= 500) {
      /* Every other state on this interface offers a way onward. This one
         used to be the exception, which left a reader who hit it with nothing
         to press. */
      state("Unreadable", "The reports directory could not be read.",
        `The server answered: ${esc(error.message)}. The reports are plain JSON in `
        + "<code>brandpulse_ai/outputs/</code>; a permissions problem there is the "
        + "usual cause.",
        '<a class="btn" href="/run">Analyse a video</a>');
    } else {
      state("Unreachable", "Nothing answered on this machine.",
        "The interface is served by the same Flask process that reads the reports, "
        + "so if this page loaded and the listing did not, the server is part-way up. "
        + "Start it with <code>python -m flask --app app run --port 5001</code> from "
        + "<code>brandpulse_ai/</code>.");
    }
    return;
  }

  sweeps = await sweepsSoon;
  sweepsOnPage = sweeps;

  /* The list offers the shelf only while the shelf could actually be drawn. */
  const offerShelf = () => {
    const offer = root.querySelector("[data-view-shelf]");
    if (offer) offer.hidden = !shelfPossible();
  };
  window.matchMedia(SHELF_FITS).addEventListener("change", offerShelf);
  onReducedChange(offerShelf);

  /* Empty means all three cases are empty. Until 24 Sep 2026 this read the
     single runs alone, so deleting the last one hid every brand and product
     set still on disk behind "nothing has been analysed". A case with no
     volumes in it is still a case (shelfgeom.js keeps all three the same
     height for exactly that reason). */
  if (!entries.length && !sweeps.length) {
    state("Empty", "Nothing has been analysed on this machine yet.",
      "Reports are written to <code>outputs/</code> when a run finishes. The first "
      + "one takes four to nine minutes.",
      '<a class="btn" data-variant="solid" href="/run">Analyse a video</a>');
    return;
  }

  const man = await manifestSoon;
  rows = await Promise.all(entries.map((entry) => enrich(entry, man)));
  const readable = rows.filter((r) => r.ok);

  /* The three ways a run can be started, in the order run.js offers them, so
     the library is the same shape as the thing that filled it. A sweep with
     no framing recorded is shelved as unfiled rather than guessed at. */
  const BAYS = [
    { key: "video", label: "A video", items: readable.map(volumeOfRun) },
    { key: "brand", label: "A brand",
      items: sweeps.filter((w) => w.subject_kind === "brand").map(volumeOfSweep) },
    { key: "product", label: "A product",
      items: sweeps.filter((w) => w.subject_kind === "product").map(volumeOfSweep) },
  ];
  const unfiled = sweeps.filter((w) => w.subject_kind !== "brand" && w.subject_kind !== "product");
  if (unfiled.length) BAYS[0].items.push(...unfiled.map(volumeOfSweep));

  /* ONE LIBRARY, NOT TWO.

     The shelf and the rack hold the same runs, so showing both put the whole
     library on the page twice and made the second one look like a different
     collection. The rack is now the OTHER view of this page rather than a
     companion to the shelf: it is what a narrow viewport, a reader who has
     asked for reduced motion, a reader who chose the list, or a machine with
     no WebGL context gets, and it is what appears if reduced motion is switched
     on mid-session. It is not built at all while the shelf is up -- a card per
     run, each painting a canvas trace, is real work to do for something nobody
     can see.

     Reaching every run by keyboard and by screen reader is NOT left to it. The
     shelf carries `.bk__index`, a list of the same runs as real links, held
     off-screen and revealed on focus in the way a skip link is. The canvas
     cannot be tabbed into or read aloud; that list can. */

  const box = shelfBox(BAYS.map((b) => b.items.length));

  if (wantShelf) {
    /* THE RENDERER AND EVERY PLATE ARRIVE BEFORE THE MARKUP DOES.

       These two awaits used to live inside wireShelf, which meant the boot
       panel was torn down first and the room was then assembled in front of
       the reader: measured on a return to this page, the frame appeared at
       164ms and the canvas not until 2297ms, with the case labels sitting
       327px out of place for the two seconds in between. Two seconds of a
       half-built bookcase is worse than two seconds of a page that says it is
       reading, which is what the boot panel is for.

       Hoisted here, the wait happens under the boot panel and the shelf lands
       whole. Both jobs are independent, so they run together rather than in
       sequence. */
    const [{ mountShelf }] = await Promise.all([
      rendererSoon,
      withPlates(BAYS.flatMap((b) => b.items)),
    ]);

    /* THE LOADING STATE STAYS UNTIL THE ROOM IS ON THE CANVAS.

       Building the context, compiling the passes and uploading every cover
       texture is over a second of blocking work on a machine without a GPU,
       and for all of it the canvas is there at full size with nothing drawn
       on it. Measured on a return to this page: the frame appeared at 734ms
       and the first painted pixel not until 2195ms.

       So the shelf is appended rather than swapped in, held out of flow and
       unpainted while it settles, and the boot panel above it is removed only
       when the renderer says it has drawn. One change, not three. */
    const boot = root.querySelector("[data-boot]");
    root.insertAdjacentHTML("beforeend", shelfMarkup(BAYS, box, readable, sweeps));

    const bk = root.querySelector(".bk");
    bk.dataset.settling = "yes";
    root.querySelector("[data-stage]").style.setProperty("--bk-ratio", box.ratio.toFixed(4));

    wireShelf(BAYS, box, mountShelf, () => handOver(bk, boot));
  } else {
    sweepsOnPage = await withSummaries(sweeps);
    root.innerHTML = listMarkup(readable, sweepsOnPage);
    wireList();
  }
  clearTimeout(window.__bpFallback);
}

/* Hands the page from the loading panel to the room without a cut.

   The room is revealed whole -- it has painted a real frame by the time this
   runs, which is what onReady means -- and the panel dissolves off the top of
   it. Both attributes are set in the same turn and nothing waits on a frame
   callback: the renderer is mid-intro at this moment and its own loop owns the
   frame queue. An earlier version faded the room UP over two nested
   requestAnimationFrames and measured 1.7s before the second one ran, with the
   panel already gone and the room still invisible.

   The removal is a timer rather than a transitionend: a backgrounded tab can
   mean that event never fires, and a panel outliving its own fade sits
   invisibly over the room swallowing clicks. */

function handOver(bk, boot) {
  delete bk.dataset.settling;
  if (!boot) return;
  if (reduced()) { boot.remove(); return; }
  boot.dataset.leaving = "yes";
  setTimeout(() => boot.remove(), 420);   /* outlasts the 260ms it fades over */
}

/* --- the caveats ---------------------------------------------------------

   Every score on this page -- the covers, the desk, the cards, the sets -- is
   partly facial-derived, so the bias-caveat rule (README, "Engineering rules") applies here exactly as it does on
   a report: BIAS_CAVEAT is shown, in full, never behind a disclosure.

   The words are NOT restated in this file. Flask substitutes BIAS_CAVEAT and
   VOCAL_CAVEAT from pipeline/scorer.py into this document's no-script core
   (app._caveat_block), so the page lifts those blocks into view rather than
   carrying a second copy that would one day disagree with the first.

   Measured 25 Sep 2026 (ui_evidence/verify_ui.py, check 24): with scripting on,
   the library carried no caveat at all. The 12 Sep band had gone with the
   rack's redesign, and the no-script copy is hidden once the page renders. */
function caveatNote() {
  const blocks = [...document.querySelectorAll("[data-fallback] .fallback__caveat")];
  if (!blocks.length) return "";
  return `
    <aside class="lcav" id="caveats" data-caveat aria-label="Caveats that apply to every score on this page">
      ${blocks.map((block) => {
        const head = block.querySelector("h2");
        const body = block.querySelector("p");
        return `<p class="lcav__item"><b class="lcav__k">${esc(head ? head.textContent : "")}</b>
          ${esc(body ? body.textContent : "")}</p>`;
      }).join("")}
    </aside>`;
}

/* --- the shelf's page ---------------------------------------------------

   A masthead, the room, and a footing line. The three case labels are set in
   the masthead rather than over the canvas so that they are type on a page
   instead of type on a picture, and each one is positioned from the custom
   property the component publishes for its own case -- `--bk-bay-N`, the
   projected centre of that case in pixels from the middle of the stage. Thirds
   of the frame would have been about seven pixels out at this width, which is
   the whole difference between aligned and nearly aligned.                    */

function shelfMarkup(bays, box, readable, sweeps) {
  const total = readable.length + sweeps.length;
  const full = bays.reduce((n, b) => n + b.items.length, 0);
  return `
    <section class="bk" data-bk>
      <!-- The page's only heading is here, and it is not drawn. Nothing is
           meant to be read above the shelf -- the room, the volumes and the
           three case labels are the whole interface. An <h1> still has to
           exist for the document to have an outline a screen reader and the
           browser's own heading navigation can use, so it is carried
           off-screen rather than deleted. -->
      <h1 class="sr-only">${count(total)} ${total === 1 ? "analysis" : "analyses"} saved on this machine</h1>

      <div class="bk__frame">
        <div class="bk__cases" data-cases aria-hidden="true">
          ${bays.map((b, i) => `<span class="bk__case" style="--i:${i}">
            <b>${esc(b.label)}</b>
            <span>${count(b.items.length)} volume${b.items.length === 1 ? "" : "s"}</span>
          </span>`).join("")}
        </div>

        <div class="bk__stage" data-stage>
          <div class="bk__desk" data-desk>
            <p class="bk__kicker" data-desk-kicker></p>
            <h2 class="bk__title" data-desk-title></h2>
            <p class="bk__blurb" data-desk-blurb></p>
            <dl class="bk__ledger" data-desk-ledger></dl>
            <div class="bk__acts">
              <a class="bk__act bk__act--solid" data-desk-open href="#">Open the report
                <svg viewBox="0 0 16 11" width="15" height="11" aria-hidden="true" fill="none"
                     stroke="currentColor" stroke-width="1.2"><path d="M0 5.5H14.6M10.3 1.2 14.9 5.5 10.3 9.8"/></svg></a>
              <button class="bk__act" type="button" data-desk-flip>Turn it over</button>
              <button class="bk__act bk__act--quiet" type="button" data-desk-close>Put it back</button>
              <button class="bk__act bk__act--danger" type="button" data-desk-delete>Delete</button>
            </div>

            <!-- The second step. It replaces the row above rather than sitting
                 beside it, so the destructive button is never next to the one
                 that cancels it, and so the question is the only thing being
                 answered at that moment. -->
            <div class="bk__confirm" data-desk-confirm hidden>
              <p class="bk__confirmq" data-desk-confirm-text></p>
              <div class="bk__confirmacts">
                <button class="bk__act bk__act--danger" type="button" data-desk-confirm-yes>
                  Delete permanently</button>
                <button class="bk__act bk__act--quiet" type="button" data-desk-confirm-no>
                  Keep it</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- The shared page ending (chassis.css .end): what this room is on the
           left, how to use it on the right, on the page grid. -->
      <p class="bk__rail end">
        <span class="end__sig">${count(total)} ${total === 1 ? "analysis" : "analyses"} on this machine, read by a local model</span>
        <span class="bk__hint">Click a volume to take it down, drag to turn it, press Esc to put it back</span>
        <button class="bk__aslist" type="button" data-as-list>Show as a list</button>
      </p>

      ${caveatNote()}

      <!-- The keyboard's way onto the shelf. Each entry takes that volume down
           exactly as a click on it does -- the same shelf.focus() -- so the desk,
           its report link, Turn it over, Put it back and Delete are all one Tab
           away. Until 25 Sep 2026 these were links straight to the report, which
           left a keyboard reader no way to reach the desk at all, and so no way
           to delete anything (INCLUSIVE_DESIGN.md A2). -->
      <nav class="bk__index" aria-label="Every run on the shelf">
        <p>The shelf above is a canvas and cannot be read aloud or tabbed into.
          These are the same ${count(full)} volumes; each one takes its volume down.</p>
        <ul>
          ${bays.flatMap((b) => b.items.map((v) => `<li><button type="button" data-take="${esc(v.id)}">
            Take down ${esc(b.label)}: ${esc(v.title)}${v.sub ? ` ${esc(v.sub)}` : ""} —
            authenticity ${esc(v.authText)}, brand health ${esc(v.healthText)}</button></li>`)).join("")}
        </ul>
      </nav>
    </section>`;
}



/* --- the list's page ----------------------------------------------------

   The same library, read as text. This is what a narrow viewport, a reader who
   has asked for reduced motion, and a machine with no WebGL context get, and
   it is not a lesser view: it is the only one that can be filtered, ordered,
   and compared two runs at a time, and the only one a screen reader can work
   through card by card. Nothing here changed when the shelf arrived except
   that it is no longer drawn underneath it.                                   */

/* The way back to the room, offered only where the room can be drawn. Hidden
   rather than omitted, so a window that grows past the shelf's size can show
   it without rebuilding the page (main() listens). */
function shelfToggle() {
  return `<p class="lb__view" data-view-shelf${shelfPossible() ? "" : " hidden"}>
    <button class="btn" data-variant="quiet" type="button" data-as-shelf>Show as a shelf</button></p>`;
}

function listMarkup(readable, sweeps) {
  /* Only combined runs on this machine. The filters, the orders and the rack
     all work on single runs, so with none saved they would be a toolbar of
     zeros over an apology; the page leads with the sets instead. */
  if (!rows.length) {
    return `
    <div class="lb">
      <header class="lb__head">
        <h1 class="t-l">${count(sweeps.length)} combined run${sweeps.length === 1 ? "" : "s"}
          saved on this machine.</h1>
        <p class="t-lede">
          Every one of them was analysed here and is stored here. No single
          video is saved at the moment; each run below opens as a report of its
          own, with its videos inside it.
        </p>
        ${shelfToggle()}
      </header>

      ${caveatNote()}

      ${sweepSection(sweeps)}
    </div>
    ${compareStrip()}`;
  }

  return `
    <div class="lb">
      <header class="lb__head">
        <h1 class="t-l">${count(rows.length)} run${rows.length === 1 ? "" : "s"}
          saved on this machine.</h1>
        <p class="t-lede">
          Every one of them was analysed here and is stored here. Each card
          carries that run&rsquo;s own trace, drawn from its own data, so the
          rack can be read by picture before it is read by name.
        </p>
        ${shelfToggle()}
      </header>

      ${caveatNote()}

      <div class="lb__controls">
        <div class="lb__group" role="group" aria-label="Filter the runs">
          ${FILTERS.map((f, i) => `
            <button class="chip" type="button" data-filter="${f.key}"
                    aria-pressed="${i === 0}">${esc(f.label)}
              <span class="chip__n t-read">${count(readable.filter(f.of).length)}</span>
            </button>`).join("")}
        </div>
        <div class="lb__group" role="group" aria-label="Order the runs">
          ${ORDERS.map((o, i) => `
            <button class="chip" type="button" data-order="${o.key}"
                    aria-pressed="${i === 0}">${esc(o.label)}</button>`).join("")}
        </div>
      </div>

      <p class="lb__empty t-small u-dim" data-rack-empty hidden></p>
      <ul class="rk" data-rack></ul>

      ${sweepSection(sweeps)}
    </div>
    ${compareStrip()}`;
}

function wireList() {
  wireDeletes(root.querySelector(".lb"));
  const asShelf = root.querySelector("[data-as-shelf]");
  if (asShelf) {
    asShelf.addEventListener("click", () => {
      rememberList(false);
      /* The shelf is built by main() from a renderer, the plates and the bay
         lists; asking for it is asking for that page, so it is loaded. */
      window.location.reload();
    });
  }
  for (const button of root.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => {
      filter = FILTERS.find((f) => f.key === button.dataset.filter) || FILTERS[0];
      for (const other of root.querySelectorAll("[data-filter]")) {
        other.setAttribute("aria-pressed", String(other === button));
      }
      paint();
      announce(`${filter.label}.`);
    });
  }
  for (const button of root.querySelectorAll("[data-order]")) {
    button.addEventListener("click", () => {
      order = ORDERS.find((o) => o.key === button.dataset.order) || ORDERS[0];
      for (const other of root.querySelectorAll("[data-order]")) {
        other.setAttribute("aria-pressed", String(other === button));
      }
      paint();
      announce(`Ordered by ${order.label.toLowerCase()}.`);
    });
  }
  root.querySelector("[data-cmp-clear]").addEventListener("click", () => {
    chosen.clear();
    paint();
    paintCompare();
  });
  paint();
}


/* ---------------------------------------------------------------- the shelf

   The component owns the room and the volumes; this owns the desk beside it.
   Everything the desk prints comes off the volume, which came off the report,
   so there is no second source of truth to drift.

   The shelf is mounted and torn down on a theme change rather than tinted,
   because the room is baked -- the wall light, the oak and the boards are all
   painted once into textures from SHELF_PALETTE -- and a baked room cannot be
   re-lit by a filter without lying about where its light comes from.          */

/* `mountShelf` is handed in rather than imported here. Every plate is decoded
   before a single board is painted -- paintCover draws the image
   synchronously, so a volume whose frame had not finished decoding would be
   printed on cloth and stay that way, which is exactly what the first build of
   this page did. Both that decode and the renderer's own 523KB now finish
   under the boot panel, before this function is reached; see main(). */
function wireShelf(bays, box, mountShelf, onReady) {
  const stage = root.querySelector("[data-stage]");
  const desk = root.querySelector("[data-desk]");
  const cases = root.querySelector("[data-cases]");
  const frame = root.querySelector(".bk__frame");
  if (!stage || !desk) return;

  const kicker = desk.querySelector("[data-desk-kicker]");
  const title = desk.querySelector("[data-desk-title]");
  const blurb = desk.querySelector("[data-desk-blurb]");
  const ledger = desk.querySelector("[data-desk-ledger]");
  const openLink = desk.querySelector("[data-desk-open]");
  const flipBtn = desk.querySelector("[data-desk-flip]");
  const closeBtn = desk.querySelector("[data-desk-close]");
  const acts = desk.querySelector(".bk__acts");
  const deleteBtn = desk.querySelector("[data-desk-delete]");
  const confirmBox = desk.querySelector("[data-desk-confirm]");
  const confirmText = desk.querySelector("[data-desk-confirm-text]");
  const confirmYes = desk.querySelector("[data-desk-confirm-yes]");
  const confirmNo = desk.querySelector("[data-desk-confirm-no]");

  let shelf = null;
  let current = null;
  /* The index entry that last took a volume down, and whether it did so
     just now -- the desk follows keyboard focus only when keyboard focus
     asked for it; a click on the canvas leaves the pointer where it is. */
  let taker = null;
  let byKeys = false;

  /* THE VOLUME YOU WERE READING IS STILL THE ONE IN YOUR HAND.

     Closing a report records which volume it was; the shelf takes that one
     down again rather than presenting a rack with nothing selected. Claimed
     once, here — a shelf should do this because you have just put a book down,
     not because you did earlier in the session.

     Acted on from onReady rather than from a timer. onReady fires on a real
     painted frame, and before it the renderer has a book list but no room:
     focusing then puts a volume on a desk the reader cannot see yet, and the
     intro that is still running would take it straight back. */
  const returning = takeReturn();

  const show = (v) => {
    current = v;
    /* Any change of volume answers the question by abandoning it. A
       confirmation left standing from the last book would otherwise be aimed
       at this one. */
    endConfirm();
    if (!v) {
      /* Put back. A keyboard reader who was inside the desk is returned to the
         entry that took the volume down, rather than to the top of the page. */
      const wasInDesk = desk.contains(document.activeElement);
      desk.classList.remove("is-open");
      if (wasInDesk && taker && taker.isConnected) taker.focus({ preventScroll: true });
      return;
    }
    /* The date came off the cover, where it was three pixels tall. It belongs
       here, where the volume is being read, and on the spine. */
    /* Two facts, parted by a hairline rather than by a dot pressed into
       service as a separator (the design line; tests/test_ui_contracts.py). */
    const kick = document.createElement("span");
    kick.textContent = v.kicker;
    const parts = [kick];
    if (v.foot) {
      const foot = document.createElement("span");
      foot.className = "bk__kfoot";
      foot.textContent = v.foot;
      parts.push(foot);
    }
    kicker.replaceChildren(...parts);
    title.innerHTML = `${esc(v.title)}${v.sub ? ` <em>${esc(v.sub)}</em>` : ""}`;
    blurb.textContent = v.blurb;
    ledger.innerHTML = v.ledger.map(([k, val]) => `<div>
      <dt>${esc(k)}</dt>
      <dd${k === "Flagged" && val !== "0" ? ' class="is-tear"' : ""}>${esc(val)}</dd></div>`).join("");
    openLink.setAttribute("href", v.href);
    desk.classList.add("is-open");
    /* Taken down from the keyboard: the reader goes with the volume. */
    if (byKeys) { byKeys = false; openLink.focus({ preventScroll: true }); }
    announce(`${v.title}${v.sub ? " " + v.sub : ""} taken down. `
      + `Authenticity ${v.authText}, brand health ${v.healthText}.`);
  };

  const mount = () => {
    if (shelf) { shelf.destroy(); shelf = null; }
    desk.classList.remove("is-open");
    shelf = mountShelf(stage, {
      bays,
      theme: document.documentElement.dataset.theme === "field" ? "field" : "bench",
      /* The labels are type on the page and the cases are pixels in a
         perspective projection, so the component is the only thing that can
         say where a case actually landed. It writes --bk-bay-0..2 straight
         onto the label row, on mount and on every resize. */
      anchor: cases,
      /* `frame` is the shared ancestor of the masthead, the case labels and
         the stage -- mountShelf publishes --bk-top on it, the measured pixel
         row where the top shelf's books actually begin, so both the heading
         and the label row can be positioned from a real number instead of a
         guessed percentage of the stage. See publishBays() in shelf.js. */
      frame,
      /* No composition options. They existed only to push the room down the
         frame so a masthead could sit above it; with the masthead gone the
         camera is the registered one -- see applyCamera/frameCamera in
         shelf.js, and the constants in shelfgeom.js. */
      onFocus: show,
      onOpen: (v) => { handOff(); window.location.href = v.href; },
      /* Fired from inside the render loop after a real frame, not when
         mountShelf returns. See the note at the call site in main(). */
      onReady: () => {
        onReady();
        if (!returning) return;
        /* ASKED UNTIL IT TAKES, NOT ONCE AFTER A GUESSED DELAY.

           The renderer refuses setActive while its intro is running, and the
           intro's length is a function of how many volumes are on the shelf.
           A single call 320ms after the first painted frame was measured
           landing inside that window and being dropped silently: the reader
           closed a book and the shelf opened with nothing in hand.

           So it asks, checks whether the volume is actually out, and asks
           again — stopping the moment it takes, and giving up after two and a
           half seconds rather than polling something that is never going to
           answer. */
        const deadline = performance.now() + 2500;
        const ask = () => {
          if (!shelf) return;
          if (shelf.activeId() === returning) {
            announce("Back on the shelf, with the volume you were reading still out.");
            return;
          }
          if (performance.now() > deadline) return;
          shelf.focus(returning);
          setTimeout(ask, 120);
        };
        setTimeout(ask, 120);
      },
    });
  };

  /* THE VOLUME GOES WITH YOU.

     The report is not a different place, it is this volume opened, so what
     crosses the navigation is the volume itself: the cover plate the shelf
     painted for this run, and the rectangle it is standing in at the moment
     of the click. report.js flies it to the desk and turns the cover back.

     stashFlip(null) stays. It is the report's own no-transition path for the
     carried frame photograph, which the shelf has no card to supply; the two
     stashes are independent, one carrying a frame and this one a book. If the
     shelf cannot hand its volume over -- nothing out, reduced motion, or a
     canvas the browser will not read back -- nothing is stashed and the
     report renders plainly, which is the normal path and not a degraded one. */
  /* DELETING A VOLUME.

     One rule, whatever is being held: the book goes, and what is inside the
     book goes with it. A video volume is one report file. A brand or product
     volume is a sweep, which is a directory with its member reports inside it,
     so deleting it deletes those videos too — that is not a side effect, it is
     what deleting that book means.

     Two steps, because neither can be undone. There is no trash on disk and no
     undo here; the file is gone when the server says it is.

     The page reloads afterwards rather than splicing the volume out of the
     room. The shelf is a WebGL scene built once from the bay lists, and its
     carcass proportions, its case labels' counts and the list view's own rows
     are all derived from those lists at mount. Rebuilding one of them by hand
     and leaving the rest is how a shelf ends up disagreeing with itself about
     what is on it. */

  const endConfirm = () => {
    confirmBox.hidden = true;
    acts.hidden = false;
    confirmYes.disabled = false;
    confirmNo.disabled = false;
    delete desk.dataset.confirming;
  };

  const beginConfirm = () => {
    if (!current) return;
    const isSweep = current.id.startsWith("sweep:");
    const name = `${current.title}${current.sub ? ` ${current.sub}` : ""}`;
    confirmText.textContent = isSweep
      ? `Delete ${name} and the ${count(current.videoCount)} `
        + `video report${current.videoCount === 1 ? "" : "s"} inside it? `
        + "This cannot be undone."
      : `Delete ${name}? This cannot be undone.`;
    acts.hidden = true;
    confirmBox.hidden = false;
    desk.dataset.confirming = "yes";
    confirmYes.focus();
    announce(confirmText.textContent);
  };

  const doDelete = async () => {
    if (!current) return;
    const isSweep = current.id.startsWith("sweep:");
    const name = `${current.title}${current.sub ? ` ${current.sub}` : ""}`;
    confirmYes.disabled = true;
    confirmNo.disabled = true;
    confirmText.textContent = `Deleting ${name}\u2026`;
    try {
      if (isSweep) await deleteSweep(current.filename);
      else await deleteReport(current.filename);
      announce(`${name} deleted. Reopening the shelf.`);
      window.location.reload();
    } catch (error) {
      /* The server's own words. A sweep still running is refused by name, and
         that is worth reading rather than replacing with "could not delete". */
      confirmText.textContent = `${name} was not deleted. ${error.message}`;
      confirmYes.disabled = false;
      confirmNo.disabled = false;
      announce(confirmText.textContent);
    }
  };

  const handOff = () => {
    stashFlip(null);
    if (!shelf) return;
    const v = shelf.activeVolume();
    if (v) stashVolume(v);
  };

  for (const button of root.querySelectorAll("[data-take]")) {
    button.addEventListener("click", () => {
      if (!shelf) return;
      taker = button;
      byKeys = true;
      shelf.focus(button.dataset.take);
    });
  }
  openLink.addEventListener("click", handOff);
  flipBtn.addEventListener("click", () => shelf && shelf.flip());
  closeBtn.addEventListener("click", () => shelf && shelf.clear());
  deleteBtn.addEventListener("click", beginConfirm);
  confirmNo.addEventListener("click", endConfirm);
  confirmYes.addEventListener("click", doDelete);

  /* Escape answers the question before it reaches the room. The shelf puts the
     volume back on Escape, and a volume returning to the shelf under a live
     confirmation would leave the question pointing at nothing. Capture phase,
     so this runs before the component's own handler. */
  const onEscape = (event) => {
    if (event.key !== "Escape" || !desk.dataset.confirming) return;
    event.stopPropagation();
    endConfirm();
    deleteBtn.focus();
  };
  window.addEventListener("keydown", onEscape, true);

  mount();

  /* THE LIGHTS CHANGE, THE ROOM STAYS.

     A theme switch used to tear the whole room down and build it again --
     a new WebGL context, every cover re-uploaded, the intro replayed, and the
     volume in the reader's hand put back on the shelf. (It also never ran:
     the event it listened for was never sent. lib/theme.js sends it now.)
     The shelf re-lights itself in place instead, so the volume that is out
     stays out and nothing moves. */
  const stopTheme = onThemeChange((theme) => { if (shelf) shelf.setTheme(theme); });



  /* THE ROOM GIVES WAY TO THE LIST, FOR ANY OF THREE REASONS.

     Reduced motion asked for mid-session; the reader asking for the list; or
     the window becoming too small for a room -- narrowed, split, rotated, or
     zoomed past 160% on a laptop. The room stops entirely rather than freezing,
     and the list is built now and put in its place: the same markup and wiring
     the narrow path uses. The sets' summaries are read before the room comes
     down, so the page is never left with neither.

     The third reason is new on 25 Sep 2026. The choice between room and list
     used to be made once, at load, while shelf.css hid the room below 900px --
     so narrowing a loaded shelf, or rotating a tablet to portrait, left a blank
     page with the index hidden too (INCLUSIVE_DESIGN.md R1). */
  let leaving = false;
  const toList = async (message) => {
    if (!shelf || leaving) return;
    leaving = true;
    const sets = await withSummaries(sweepsOnPage);
    if (!shelf) return;
    sweepsOnPage = sets;
    shelf.destroy(); shelf = null;
    stopTheme();
    fits.removeEventListener("change", onFit);
    window.removeEventListener("keydown", onEscape, true);
    const hadFocus = root.contains(document.activeElement);
    root.innerHTML = listMarkup(rows.filter((r) => r.ok), sweepsOnPage);
    wireList();
    /* Focus inside what was just replaced (Show as a list, or an entry of the
       shelf's index) would fall to the page body: it goes to the list's
       heading instead. Focus that was elsewhere is left where it is. */
    const heading = hadFocus && root.querySelector("h1");
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }
    announce(message);
  };

  onReducedChange((less) => {
    if (less) toList("Reduced motion. The shelf has been replaced by the list of runs.");
  });

  const fits = window.matchMedia(SHELF_FITS);
  const onFit = () => {
    if (!fits.matches) toList("The window is too small for the shelf, so the runs are shown as a list.");
  };
  fits.addEventListener("change", onFit);

  const asList = root.querySelector("[data-as-list]");
  if (asList) {
    asList.addEventListener("click", () => {
      rememberList(true);
      toList("The runs are shown as a list. Show as a shelf brings the room back.");
    });
  }
}

main();
