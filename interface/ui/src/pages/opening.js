/* Opening-page composition. The isolated signal chamber lives in lib/film.js. */

import "../styles/tokens.css";
import "../styles/chassis.css";
import "../styles/opening.css";
import "../styles/hero.css";
import "../styles/seam.css";
import "../styles/close.css";
import "../styles/proof.css";

import { mountAll } from "../lib/chrome.js";
import {
  getFigures, getReport, getSweep, getSweepMember, listReports, listSweeps,
} from "../lib/api.js";
import { mountAnnouncer } from "../lib/announce.js";
import { segmentValences } from "../lib/contract.js";
import { esc } from "../lib/format.js";
import { ScrollTrigger } from "../lib/motion.js";
import { manifest, stripInfo, videoIdOf } from "../lib/frames.js";
import { filmMarkup, wireFilm } from "../lib/film.js";
import { mountGate } from "../lib/gate.js";
import { mountBoot } from "../lib/boot.js";
import { heroMarkup, wireHero, playHero } from "../lib/hero.js";
import { seamMarkup, wireSeam } from "../lib/seam.js";
import { closeMarkup, wireClose } from "../lib/close.js";
import { proofMarkup, wireProof } from "../lib/proof.js";

const root = document.querySelector("[data-opening]");

/* The film is shot on one report. It is chosen, not random: it has to hold
   enough agreement that the photograph resolves and enough conflict that it
   visibly comes apart, and it must have a sprite sheet derived. The list is a
   preference order; any report with a sheet will do if none of these is here,
   and then the newest is used -- which in a fresh clone, where every file has
   the same date, is no choice at all. Until 26 Sep 2026 none of the names below
   matched a shipped report (two had been deleted, one renamed), so the film
   fell back to that; the one survivor, under its current name, was set by the
   author. */
const PREFERRED = [
  "Apple (iPhone 18 Pro Max).json",
];

/* -------------------------------------------------------------- the picking */

/* Every report the film could be shot on, in the order they are tried, each
   with the address its own page lives at.

   Saved single runs come first, the preference list ahead of the rest, which
   is the order this page has always used. After them come the videos inside
   combined runs, newest set first: each member is an ordinary report with its
   own frames, opened at /brand/<set>/<video> rather than /library/<file>.
   Until 24 Sep 2026 only single runs were tried, so a machine holding combined
   runs and no single one opened on an error page instead of this one.

   A generator, so a set is only read when every candidate before it has been
   refused -- on a machine with single runs, no set is read at all. A video in
   two sets is tried once. A member's video id is known before its report is,
   so one without a sprite sheet is passed over without being fetched: on
   24 Sep 2026 two of the 20 videos in the frame manifest had a sheet, and
   finding that out report by report read 17 member reports (1,213 KB)
   before the film could start; skipped by id, it reads one (136 KB). */
async function* filmCandidates(man) {
  let names = [];
  try {
    const listed = await listReports();
    const rows = listed.reports || listed || [];
    names = rows.map((r) => (typeof r === "string" ? r : r.filename)).filter(Boolean);
  } catch { names = []; }

  const order = [...PREFERRED.filter((n) => names.includes(n)),
    ...names.filter((n) => !PREFERRED.includes(n))];
  for (const filename of order) {
    yield { href: `/library/${encodeURIComponent(filename)}`, load: () => getReport(filename) };
  }

  let sets = [];
  try { sets = await listSweeps(); } catch { sets = []; }
  const tried = new Set();
  for (const set of Array.isArray(sets) ? sets : []) {
    let detail;
    try { detail = await getSweep(set.sweep_id); } catch { continue; }
    for (const member of detail.members || []) {
      const videoId = member.video_id;
      if (!videoId || member.analysed === false || tried.has(videoId)) continue;
      tried.add(videoId);
      if (!hasSheet(stripInfo(man, videoId))) continue;
      yield {
        href: `/brand/${encodeURIComponent(set.sweep_id)}/${encodeURIComponent(videoId)}`,
        load: () => getSweepMember(set.sweep_id, videoId),
      };
    }
  }
}

/** A sprite sheet with enough seconds on it for the film to move through. */
const hasSheet = (strip) => !!(strip && strip.seconds && strip.seconds.length >= 8);

/** The report the film is shot on, and the seconds it parks on. */
async function pickFilmSubject(man) {
  for await (const candidate of filmCandidates(man)) {
    let report;
    try { report = await candidate.load(); } catch { continue; }
    const videoId = videoIdOf(report);
    const strip = videoId ? stripInfo(man, videoId) : null;
    if (!hasSheet(strip)) continue;

    const segments = (report.all_segments || []).slice()
      .sort((a, b) => a.start_s - b.start_s);
    if (!segments.length) continue;
    for (const segment of segments) {
      segment.__v = segmentValences(segment, report.comment_sentiment);
    }

    const flaggedList = segments.filter((s) => s.flagged);
    const flagged = flaggedList.length
      ? flaggedList.reduce((a, b) => (b.conflict_score > a.conflict_score ? b : a))
      : null;

    /* The first frame of the film is the most important image on the site, so
       it is chosen rather than taken. The opening second is the earliest one
       the sheet holds that falls inside a segment where a face was actually
       detected — otherwise the page can open on b-roll, which is honest but is
       also luck. Falls back to the first second held when no segment in the
       whole report carries a facial reading, which is a real case: a quarter
       of segments in this corpus have no face in them at all. */
    const faced = segments.filter((seg) => (seg.__v || {}).facial);
    const openAt = (() => {
      for (const seg of faced) {
        const hit = strip.seconds.find((s) => s >= seg.start_s && s < seg.end_s);
        if (hit !== undefined) return hit;
      }
      return strip.seconds[0];
    })();

    /* This used to eagerly fetch and decode the 2560px hero tier of `openAt`,
       to have it ready before the shader that sampled it compiled. That shader
       is no longer what the film is built on: it draws its own still from the
       1440px plate tier, and the hero bitmap was being decoded and then closed
       unused on every load. The fetch is gone with it. `openAt` stays -- it is
       still the chosen opening second, and it is still chosen rather than
       taken. `h/` is now fetched by nothing on this page. */

    return {
      href: candidate.href, report, videoId, strip, segments, flagged, openAt,
      segment: segments[Math.floor(segments.length / 3)],
      duration: segments[segments.length - 1].end_s || 1,
    };
  }
  return null;
}

/* -------------------------------------------------------------------- boot */

function fail(message) {
  root.innerHTML = `
    <section class="state state--error">
      <p class="state__tag">Unavailable</p>
      <h1 class="t-l">${esc(message)}</h1>
      <p>
        The interface could not read this machine's own analyses. The API is
        still reachable at <code>/reports</code>, and
        <a href="/library">the library</a> lists what is on disk.
      </p>
    </section>`;
}

/* The gate goes up before anything is fetched, so the water covers the build
   rather than following it. It is raised here and not in the document head
   because a gate that outlives a broken bundle would be a locked door: if this
   module never runs, no gate is ever drawn and the page is simply the page.

   Null means the effect could not run on this machine. There is then no gate
   and no delay, which is the correct behaviour and not a degraded one. */
const gate = mountGate({
  /* The water opens onto the boot screen, not onto the page. Chained here
     rather than inside the gate so each screen stays ignorant of the other:
     the gate's only job is to end, and this decides what ends after it.

     `onDone` is the hero's cue. It fires from inside the boot screen's own
     teardown, after its fade and after its element has been removed, so the
     composition starts arriving against nothing but its own film -- and it
     fires on the boot screen's failure path too, where there was never a
     screen to remove. */
  onEnter: () => mountBoot({ autoStart: false, onDone: playHero }),
});

/* No gate means no boot screen either, and so no cue from below. Nothing is
   covering the page on this machine, so the entrance belongs to the load. */
if (!gate) playHero();

/* Hand over only once the document behind is actually on screen. Everything
   below calls this, including both failure paths, because a reader stuck
   looking at water while an error sits underneath it is the worst outcome
   available. */
function opened() {
  if (gate) gate.ready();
}

async function main() {
  if (!root) return;

  mountAll({ here: "opening" });
  mountAnnouncer();

  let figures = {};
  try { figures = await getFigures(); } catch { figures = {}; }

  const man = await manifest();
  const pick = await pickFilmSubject(man);

  if (!pick) {
    fail("There is no analysed video on this machine to open with.");
    clearTimeout(window.__bpFallback);
    opened();
    return;
  }

  /* The closing section is emitted here rather than from inside proofMarkup,
     which is where it used to live. A section that renders a sibling section
     hides the page's own running order from the one place that states it. */
  root.innerHTML = heroMarkup() + seamMarkup(figures)
    + filmMarkup(pick) + proofMarkup(figures)
    + closeMarkup(figures.corpus || {}, pick);
  clearTimeout(window.__bpFallback);

  /* One frame, so the pin measures a laid-out document rather than one caught
     mid-paint. ScrollTrigger reads heights here, and a wrong one pins wrong. */
  requestAnimationFrame(() => {
    wireHero();
    wireSeam();
    wireFilm();
    wireProof(figures);
    wireClose();
    ScrollTrigger.refresh();
    opened();
  });
}

main().catch((error) => {
  fail("This page could not be drawn.");
  clearTimeout(window.__bpFallback);
  opened();
  if (import.meta.env && import.meta.env.DEV) console.error(error);
});
