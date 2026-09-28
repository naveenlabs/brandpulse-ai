/* ===========================================================================
   motion.js — one switch for motion, not a library of effects.

   Motion here is either driven by the reader or plays once:

     1. `t`, the position in the video (see transport.js), which the reader
        moves by dragging, by pressing an arrow key, or by clicking a row;
     2. the opening page's sections, scrubbed by the reader's own scroll
        (hero.js, seam.js, film.js, proof.js) rather than played at them;
     3. a draw-on or count-up that plays once when a figure is first shown;
     4. the ambient grounds, the water gate and the boot screen, the only
        things that move on their own, all of which stop under reduced motion.

   Every one of them asks `reduced()` below. There is no scroll-triggered
   fade-and-slide-up on any section anywhere in this build. That treatment is the most common tell of a generated page, and
   more importantly it would be decoration: nothing about a section arriving
   from below tells a reader anything about four channels disagreeing.

   Durations are READ FROM CSS rather than restated here, so the two cannot
   drift. tests/test_ui_contracts.py asserts this file contains no hard-coded
   millisecond literal for the shared tokens.
   ======================================================================== */

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Flip } from "gsap/Flip";
import { applyTheme } from "./theme.js";

gsap.registerPlugin(ScrollTrigger, Flip);

export { gsap, ScrollTrigger, Flip };

/* --- reduced motion -----------------------------------------------------
   Live, not sampled once at boot: a reader can turn this on mid-session and
   the interface has to stop moving, not wait for a reload.

   TWO WAYS TO ASK, ONE ANSWER (25 Sep 2026). The operating system's setting,
   and the Motion switch in the masthead (chrome.js). Three of the five people
   in the final evaluation asked for a way to turn motion off (D5), and most
   readers who need less movement -- a migraine, a vestibular condition, a
   slow machine, a projector in a meeting -- have never found the OS setting.
   So `reduced()` is true when EITHER says so, every module keeps asking this
   one function, and nothing else in the interface had to learn a second
   question. CSS follows the same attribute: vite.config.js re-emits every
   prefers-reduced-motion block under :root[data-motion="off"]. The attribute
   is set before first paint by the inline script in each document's head. */

const QUERY = window.matchMedia("(prefers-reduced-motion: reduce)");
export const MOTION_KEY = "brandpulse-motion";
export const MOTION_EVENT = "motionchange";

const chosenOff = () => document.documentElement.dataset.motion === "off";
let reducedNow = QUERY.matches || chosenOff();
const listeners = new Set();

function settle() {
  const next = QUERY.matches || chosenOff();
  if (next === reducedNow) return;
  reducedNow = next;
  for (const fn of listeners) fn(reducedNow);
  /* For the vendored renderers, which take no imports from this project. */
  window.dispatchEvent(new CustomEvent(MOTION_EVENT, { detail: { reduced: reducedNow } }));
}

QUERY.addEventListener("change", settle);

/** Whether this reader has asked for less movement, by either route. */
export const reduced = () => reducedNow;

/** Whether the OS asks for less movement (the switch cannot overrule it). */
export const reducedBySystem = () => QUERY.matches;

/** Whether the in-page switch has turned motion off. */
export const motionSwitchedOff = () => chosenOff();

/**
 * Turn motion off or back on from the page. Remembered per browser; storage
 * that refuses (a private window) costs only the remembering.
 */
export function setMotionOff(off) {
  const root = document.documentElement;
  if (off) root.dataset.motion = "off";
  else delete root.dataset.motion;
  try {
    if (off) localStorage.setItem(MOTION_KEY, "off");
    else localStorage.removeItem(MOTION_KEY);
  } catch { /* not remembered, still applied */ }
  settle();
}

/** Be told when that changes. Returns an unsubscribe. */
export function onReducedChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/* gsap.matchMedia answers media queries, and the switch is not one. This is
   gsap.matchMedia with every prefers-reduced-motion condition answered by
   reduced() instead: a condition asking for no-preference becomes a query
   that never matches while motion is off, one asking for reduce becomes one
   that always does, and the context is rebuilt whenever the answer changes.
   The other conditions -- widths, heights -- are left to the browser. */
const NEVER = "(min-width: 100000px)";
const ALWAYS = "(min-width: 0px)";
function answered(query) {
  if (!chosenOff()) return query;
  return query
    .replace(/\(\s*prefers-reduced-motion\s*:\s*no-preference\s*\)/g, NEVER)
    .replace(/\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)/g, ALWAYS);
}

export function motionMedia(conditions, fn) {
  let mm = null;
  const build = (again) => {
    if (mm) mm.revert();
    mm = gsap.matchMedia();
    const asked = typeof conditions === "string" ? answered(conditions)
      : Object.fromEntries(Object.entries(conditions).map(([k, q]) => [k, answered(q)]));
    mm.add(asked, fn);
    /* A rebuilt pin changes the page's height; the first build is measured by
       the page's own refresh once everything is wired. */
    if (again) ScrollTrigger.refresh();
  };
  build(false);
  const off = onReducedChange(() => build(true));
  return {
    revert() { off(); if (mm) mm.revert(); mm = null; },
    /* Ask again, for a caller whose own condition changed (film.js: its
       words stopped fitting the chamber). */
    rebuild() { build(true); },
  };
}

/* --- durations ----------------------------------------------------------
   One source of truth, in tokens.css. Read once per call rather than cached,
   because the value is cheap to read and a cached one would survive a theme
   or stylesheet change that moved it. */

function cssMs(name, fallback) {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(name).trim();
  if (raw.endsWith("ms")) return parseFloat(raw);
  if (raw.endsWith("s")) return parseFloat(raw) * 1000;
  return fallback;
}

export const MS = {
  get fast() { return cssMs("--t-fast", 130); },
  get med() { return cssMs("--t-med", 280); },
  get slow() { return cssMs("--t-slow", 900); },
};

/* --- the one orchestrated entrance --------------------------------------
   The four tracks write themselves once, left to right, staggered by channel.
   Under reduced motion they are simply there, complete, on the first frame:
   the still version is the finished drawing, never a broken one. */

export function drawOn(targets, { stagger = 0.07, onUpdate } = {}) {
  if (reduced()) {
    for (const target of targets) target.value = 1;
    if (onUpdate) onUpdate();
    return null;
  }
  for (const target of targets) target.value = 0;
  return gsap.to(targets, {
    value: 1,
    duration: MS.slow / 1000,
    ease: "power2.out",
    stagger,
    onUpdate,
  });
}

/* --- carrying an element across a navigation ----------------------------
   Library to report, report to a sweep member, and back. The frame under the
   playhead is the carried element: it is the same photograph of the same
   second either side of the navigation, so animating it from where it was to
   where it now is tells the truth about what happened.

   Implemented with GSAP Flip on a shared `data-flip-id`. Both documents are
   separate HTML pages, so the state is stashed in sessionStorage on the way
   out and consumed on the way in. If anything is missing — no stash, no
   matching element, reduced motion — the page simply renders, which is the
   normal behaviour and not a degraded one. */

const FLIP_KEY = "brandpulse-flip";

/** Record where the carried element is, immediately before navigating away. */
export function stashFlip(element) {
  if (!element || reduced()) return;
  const box = element.getBoundingClientRect();
  try {
    sessionStorage.setItem(FLIP_KEY, JSON.stringify({
      id: element.dataset.flipId || "",
      x: box.left, y: box.top, w: box.width, h: box.height,
      at: Date.now(),
    }));
  } catch { /* storage unavailable; the navigation is still fine */ }
}

/**
 * Play the arriving half, if there is one to play.
 *
 * The stash is dropped after one use and ignored if it is older than a few
 * seconds, so a back-button return or a stale tab never animates a frame in
 * from a position it was never at.
 */
export function playFlip(element) {
  if (!element || reduced()) return;
  let stash = null;
  try {
    const raw = sessionStorage.getItem(FLIP_KEY);
    sessionStorage.removeItem(FLIP_KEY);
    stash = raw ? JSON.parse(raw) : null;
  } catch { return; }

  if (!stash || Date.now() - stash.at > 4000) return;
  if (stash.id && element.dataset.flipId && stash.id !== element.dataset.flipId) return;

  const box = element.getBoundingClientRect();
  if (!box.width || !box.height) return;

  gsap.fromTo(element,
    {
      x: stash.x - box.left,
      y: stash.y - box.top,
      scaleX: stash.w / box.width,
      scaleY: stash.h / box.height,
      transformOrigin: "top left",
    },
    {
      x: 0, y: 0, scaleX: 1, scaleY: 1,
      duration: 0.62,
      ease: "expo.inOut",
      clearProps: "transform",
    });
}

/* --- the theme change, as an event rather than a repaint ----------------
   A band of illumination crosses the chassis and the screens re-light behind
   it. The attribute is swapped at the moment the band covers the viewport, so
   nobody sees the two themes at once.

   Under reduced motion the attribute swaps immediately and no band is drawn:
   a full-width bright sweep is exactly the kind of thing that setting exists
   to prevent. */

export function sweepTheme(next) {
  /* The swap itself is theme.js's: it sets the attribute, remembers it,
     suspends transitions for the frame, and tells every renderer. This only
     decides whether a band of light crosses the page while it happens. */
  const apply = () => { applyTheme(next); };

  if (reduced()) { apply(); return; }

  const band = document.createElement("div");
  band.className = "sweep";
  band.setAttribute("aria-hidden", "true");
  document.body.appendChild(band);

  gsap.timeline({ onComplete: () => band.remove() })
    .fromTo(band, { xPercent: -104 }, {
      xPercent: 0, duration: 0.26, ease: "power3.in",
    })
    .add(apply)
    .to(band, { xPercent: 104, duration: 0.3, ease: "power3.out" });
}
