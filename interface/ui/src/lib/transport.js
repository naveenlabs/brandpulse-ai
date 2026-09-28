/* ===========================================================================
   transport.js — four tracks, one clock.

   This is the instrument the whole interface is built around, and it is the
   one component that appears on every surface that has a video behind it.

   WHY A TRANSPORT AND NOT A CHART
   -------------------------------
   The product reads one video four ways and reports where the four accounts
   diverge. A line chart would draw that; a transport lets a reader DRIVE it.
   The difference matters here more than it usually does, because the single
   hardest fact about this system to explain in a sentence is that one of the
   four channels has no time resolution at all: comment sentiment is one
   video-level reading, posted hours or days afterwards, and it cannot be
   aligned to a second.

   On this transport you learn that by trying to scrub it. Three tracks move
   under the playhead and the fourth does not. Nobody is told; they cause it.

   FOUR MATERIALS, NOT FOUR COLOURS
   --------------------------------
   Each channel is drawn in its own MATERIAL as well as its own tint, so no
   reading on this interface is carried by hue alone and the trace survives
   greyscale, print and colour-vision deficiency:

     transcript  bar     a solid block. The words are the most substantial
                         reading the system has, and the only one it measures
                         at 67.8% on unseen speakers.
     facial      frame   a HOLLOW rectangle, like a film frame. Drawn hollow
                         because it is the least substantial reading in the
                         system: 34.2% on held-out speakers, below an
                         always-NEUTRAL constant's 67.5%.
     vocal       wave    an oscillating stroke.
     audience    field   a stipple, spanning the entire width at one level,
                         because it is ONE reading stretched across the whole
                         video rather than a reading per second.

   ABSENCE IS DRAWN AS ABSENCE
   ---------------------------
   A channel that returned no usable reading for a segment gets NO MARK. Not a
   mark at the middle level, not a zero, not a dash. The pen lifts off the
   paper and the gap is the finding: on one report in this corpus 71% of
   segments carry no facial reading at all, and that has to be visible.

   VERTICAL POSITION IS THE READING
   --------------------------------
   Within its own lane each mark sits at one of three levels: positive at the
   top, neutral in the middle, negative at the bottom. When the four channels
   agree, their four marks line up into a column. When they disagree, the
   column breaks into a scatter. That is the product's whole thesis, drawn at
   1:1 scale with no interpretation layer in between.
   ======================================================================== */

import { CHANNELS, CHANNEL_META, segmentValences } from "./contract.js";
import { drawOn, reduced, onReducedChange } from "./motion.js";
import { esc, mmss } from "./format.js";
import { announce } from "./announce.js";

const LEVEL = { POSITIVE: 0, NEUTRAL: 1, NEGATIVE: 2 };

/** Lane geometry, in CSS pixels.

   LANE_H is the default; the report's fixed transport overrides `--lane-h` in
   CSS because it is pinned to the window for a whole document and has to cost
   as little height as it can. The canvas reads the value back off the element
   rather than assuming it, or the marks would be drawn for one height and
   displayed at another. */
const LANE_H = 38;
const PAD_Y_RATIO = 9 / 38;   /* from lane top to the POSITIVE level */

/* --- the clock ----------------------------------------------------------
   One scalar, `t`, in seconds. Scroll, drag, arrow keys, the ledger and the
   moment panel all write to it; every visual reads from it. That is what
   makes the motion on this interface one authored mechanism rather than a
   collection of separate effects. */

export function createClock(duration, segments = []) {
  let value = 0;
  const subscribers = new Set();
  const bounds = segments
    .map((s) => s.start_s)
    .filter((n) => typeof n === "number" && Number.isFinite(n))
    .sort((a, b) => a - b);

  const clamp = (n) => Math.min(duration, Math.max(0, n));

  const clock = {
    duration,
    get t() { return value; },
    get fraction() { return duration > 0 ? value / duration : 0; },

    set(next, meta = {}) {
      const to = clamp(next);
      if (to === value) return;
      value = to;
      for (const fn of subscribers) fn(value, meta);
    },

    setFraction(f, meta) { clock.set(f * duration, meta); },

    /** The index of the segment the playhead is inside, or -1. */
    get index() {
      for (let i = segments.length - 1; i >= 0; i -= 1) {
        if (value >= segments[i].start_s) return i;
      }
      return segments.length ? 0 : -1;
    },

    get segment() {
      const i = clock.index;
      return i >= 0 ? segments[i] : null;
    },

    /** Move by whole segments. Used by the arrow keys and the transport keys. */
    step(delta) {
      const i = clock.index;
      const next = Math.min(segments.length - 1, Math.max(0, i + delta));
      if (segments[next]) clock.set(segments[next].start_s, { reason: "step" });
    },

    /** The nearest segment boundary to a given time. */
    nearestBound(at) {
      if (!bounds.length) return at;
      let best = bounds[0];
      for (const b of bounds) {
        if (Math.abs(b - at) < Math.abs(best - at)) best = b;
      }
      return best;
    },

    subscribe(fn) { subscribers.add(fn); return () => subscribers.delete(fn); },
  };

  return clock;
}

/* --- drawing ------------------------------------------------------------ */

function themeColours() {
  const css = getComputedStyle(document.documentElement);
  const read = (name) => css.getPropertyValue(name).trim();
  return {
    transcript: read("--ch-transcript"),
    facial: read("--ch-facial"),
    vocal: read("--ch-vocal"),
    audience: read("--ch-audience"),
    tear: read("--tear"),
    edge: read("--edge"),
    ink3: read("--ink-3"),
  };
}

/**
 * Draw one lane.
 *
 * `progress` is 0..1 and is how far left-to-right the one orchestrated
 * draw-on has got. At 1 the lane is complete; under reduced motion it starts
 * at 1 and is never animated.
 */
function paintLane(ctx, opts) {
  const { channel, segments, valences, duration, width, height, colours, progress } = opts;
  const colour = colours[channel];
  const pad = height * PAD_Y_RATIO;
  const x = (s) => (duration > 0 ? (s / duration) * width : 0);
  const y = (level) => pad + level * ((height - pad * 2) / 2);
  const cut = width * progress;

  ctx.clearRect(0, 0, width, height);

  /* The neutral reference line. An instrument draws its zero. */
  ctx.globalAlpha = 0.5;
  ctx.fillStyle = colours.edge;
  ctx.fillRect(0, y(1), cut, 1);
  ctx.globalAlpha = 1;

  ctx.strokeStyle = colour;
  ctx.fillStyle = colour;

  if (channel === "audience") {
    /* ONE reading, stretched. Drawn as a stipple across the whole width at a
       single level, at reduced weight, because it is not 94 measurements: it
       is one measurement that cannot know which second it is about. */
    const level = valences.audience;
    if (level == null) return;
    const yy = y(LEVEL[level]);
    ctx.globalAlpha = 0.8;
    for (let px = 0; px < cut; px += 4) ctx.fillRect(px, yy, 2, 2);
    ctx.globalAlpha = 1;
    return;
  }

  for (let i = 0; i < segments.length; i += 1) {
    const segment = segments[i];
    const level = valences.per[i][channel];
    if (!level) continue;                       // absence: the pen lifts off
    const x0 = x(segment.start_s);
    if (x0 > cut) break;
    const x1 = Math.min(x(segment.end_s), cut);
    const w = Math.max(2, x1 - x0 - 0.5);
    const yy = y(LEVEL[level]);

    if (channel === "transcript") {
      ctx.fillRect(x0, yy - 1.5, w, 3);
    } else if (channel === "facial") {
      /* Hollow, because the reading is. */
      ctx.lineWidth = 1;
      ctx.strokeRect(x0 + 0.5, yy - 2, Math.max(2, w - 1), 4);
    } else if (channel === "vocal") {
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      const steps = Math.max(2, Math.round(w / 3));
      for (let s = 0; s <= steps; s += 1) {
        const px = x0 + (w * s) / steps;
        const py = yy + Math.sin((s / steps) * Math.PI * 2) * 1.7;
        if (s === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
  }
}

/* --- the component ------------------------------------------------------ */

/**
 * Mount the transport into `host`.
 *
 * @returns {{destroy: function, redraw: function, clock: object}}
 */
let transportCount = 0;

export function mountTransport(host, options) {
  const { report, segments, clock, onSegment, compact = false, label = "" } = options;
  const duration = clock.duration;
  /* Several transports can share one document (the library rack draws one per
     card), so the description each one points at needs its own id. */
  const uid = (transportCount += 1);
  /* A NAME, not a paragraph: the keys live in the description. Named for its
     run where a page carries several (the library's cards, a sweep's videos),
     so a screen reader does not meet a list of identical "Playhead" sliders
     (INCLUSIVE_DESIGN.md A16). */
  const sliderName = label ? `Playhead, ${label}` : "Playhead";

  const commentSentiment = report ? report.comment_sentiment : null;
  const per = segments.map((s) => segmentValences(s, commentSentiment));
  const audience = per.length ? per[0].audience || null : null;
  const valences = { per, audience };
  const flagged = segments.filter((s) => s.flagged);

  host.innerHTML = `
    <div class="tp${compact ? " tp--compact" : ""}">
      <div class="tp__head">
        <span class="tp__now t-time" data-now>0:00</span>
        <span class="tp__seg t-label u-faint" data-seg></span>
        <span class="tp__dur t-time u-faint">${mmss(duration)}</span>
      </div>
      <div class="tp__field" data-field tabindex="0" role="slider"
           aria-label="${esc(sliderName)}"
           aria-describedby="tp-how-${uid}"
           aria-valuemin="0" aria-valuemax="${Math.round(duration)}"
           aria-valuenow="0" aria-valuetext="0 minutes 0 seconds">
        <div class="tp__lanes" data-lanes>
          ${CHANNELS.map((channel) => {
            const meta = CHANNEL_META[channel];
            return `
            <div class="tp__lane" data-channel="${channel}">
              <span class="tp__id t-label">
                <i class="tp__mark" data-mark="${channel}" aria-hidden="true"></i>
                ${meta.short}
              </span>
              <canvas data-lane="${channel}" aria-hidden="true"></canvas>
            </div>`;
          }).join("")}
        </div>
        <div class="tp__flags" aria-hidden="true">
          ${flagged.map((span) => {
            const left = (span.start_s / duration) * 100;
            const wide = Math.max(0.28, ((span.end_s - span.start_s) / duration) * 100);
            return `<i style="left:${left.toFixed(4)}%;width:${wide.toFixed(4)}%"></i>`;
          }).join("")}
        </div>
        <div class="tp__playhead" data-playhead aria-hidden="true"></div>
      </div>
      <!-- The instruction is a DESCRIPTION, not the control's name. A screen
           reader reads a name every time focus lands, and a paragraph of
           keyboard help read on every arrow press is noise; it also leaves a
           speech-input user with nothing sayable (WCAG 2.5.3). -->
      <p class="sr-only" id="tp-how-${uid}">
        Drag to scrub. Left and right arrows step one segment, Home and End jump
        to the ends, Page Up and Page Down move ten segments.
      </p>
    </div>`;

  const field = host.querySelector("[data-field]");
  const lanes = host.querySelector("[data-lanes]");
  const playhead = host.querySelector("[data-playhead]");
  const nowEl = host.querySelector("[data-now]");
  const segEl = host.querySelector("[data-seg]");
  const canvases = CHANNELS.map((c) => host.querySelector(`[data-lane="${c}"]`));

  let width = 0;
  const laneProgress = CHANNELS.map(() => ({ value: reduced() ? 1 : 0 }));

  function laneArea() {
    /* The canvas starts after the fixed-width identity column, so the
       playhead and the marks have to agree about where zero is. */
    const first = lanes.querySelector("canvas");
    return first ? first.getBoundingClientRect() : field.getBoundingClientRect();
  }

  function redraw() {
    const dpr = Math.min(3, window.devicePixelRatio || 1);
    canvases.forEach((cv, i) => {
      const w = Math.max(1, Math.round(cv.clientWidth));
      const laneH = Math.max(8, Math.round(cv.clientHeight)) || LANE_H;
      if (cv.width !== w * dpr || cv.height !== laneH * dpr) {
        cv.width = w * dpr;
        cv.height = laneH * dpr;
      }
      const ctx = cv.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      width = w;
      paintLane(ctx, {
        channel: CHANNELS[i], segments, valences, duration, width,
        height: laneH, colours: themeColours(), progress: laneProgress[i].value,
      });
    });
  }

  /* --- the readout ------------------------------------------------------ */

  let lastIndex = -1;

  function render(meta = {}) {
    playhead.style.setProperty("--at", `${(clock.fraction * 100).toFixed(4)}%`);

    nowEl.textContent = mmss(clock.t);
    field.setAttribute("aria-valuenow", String(Math.round(clock.t)));
    field.setAttribute("aria-valuetext",
      `${Math.floor(clock.t / 60)} minutes ${Math.round(clock.t % 60)} seconds`);

    const index = clock.index;
    if (index !== lastIndex) {
      lastIndex = index;
      const segment = segments[index];
      if (segment) {
        segEl.textContent = `Segment ${index + 1} of ${segments.length}${
          segment.flagged ? ", flagged" : ""}`;
        segEl.classList.toggle("is-flagged", Boolean(segment.flagged));
        if (onSegment) onSegment(segment, index);
        /* Only speak when a person moved deliberately. Coasting through
           ninety segments would otherwise produce ninety announcements. */
        if (meta.reason === "step" || meta.reason === "jump") {
          announce(`${mmss(segment.start_s)}. Segment ${index + 1} of ${segments.length}.`
            + (segment.flagged ? " Flagged." : "")
            + ` ${CHANNELS.map((c) => {
                const v = per[index][c];
                return `${CHANNEL_META[c].short} ${v ? v.toLowerCase() : "not measured"}`;
              }).join(", ")}.`);
        }
      }
    }
  }

  /* --- driving it -------------------------------------------------------
     One control, not two. The track surface IS the shuttle: you drag where
     your eye already is, and on release the movement carries with the
     velocity you let go at, decaying under friction, until it is slow enough
     to settle onto the nearest segment boundary.

     A separate jog wheel would be a second control with the same intent. */

  let dragging = false;
  let velocity = 0;          /* seconds of video per frame */
  let lastX = 0;
  let lastAt = 0;
  let coasting = 0;

  const FRICTION = 0.94;
  const SETTLE = 0.012;      /* below this, snap and stop */
  const MAX_RATE = duration * 0.015;   /* a real shuttle has a top speed */

  function timeFromPointer(clientX) {
    const box = laneArea();
    return ((clientX - box.left) / box.width) * duration;
  }

  function stopCoast() {
    if (coasting) cancelAnimationFrame(coasting);
    coasting = 0;
  }

  function coast() {
    coasting = requestAnimationFrame(function frame() {
      velocity *= FRICTION;
      if (Math.abs(velocity) < SETTLE) {
        velocity = 0;
        coasting = 0;
        if (!reduced()) clock.set(clock.nearestBound(clock.t), { reason: "settle" });
        return;
      }
      clock.set(clock.t + velocity, { reason: "coast" });
      if (clock.t <= 0 || clock.t >= duration) { velocity = 0; coasting = 0; return; }
      coasting = requestAnimationFrame(frame);
    });
  }

  function onDown(event) {
    if (event.button != null && event.button !== 0) return;
    stopCoast();
    dragging = true;
    velocity = 0;
    lastX = event.clientX;
    lastAt = event.timeStamp;
    field.setPointerCapture(event.pointerId);
    field.classList.add("is-dragging");
    clock.set(timeFromPointer(event.clientX), { reason: "jump" });
    event.preventDefault();
  }

  function onMove(event) {
    if (!dragging) return;
    const dt = Math.max(1, event.timeStamp - lastAt);
    const box = laneArea();
    const moved = ((event.clientX - lastX) / box.width) * duration;
    /* Smooth the velocity estimate: a single frame's delta is noisy enough
       that a slow drag can end in a fast flick that never happened. */
    const sampled = (moved / dt) * 16;
    velocity = Math.max(-MAX_RATE, Math.min(MAX_RATE, velocity * 0.6 + sampled * 0.4));
    lastX = event.clientX;
    lastAt = event.timeStamp;
    clock.set(timeFromPointer(event.clientX), { reason: "drag" });
  }

  function onUp(event) {
    if (!dragging) return;
    dragging = false;
    field.classList.remove("is-dragging");
    try { field.releasePointerCapture(event.pointerId); } catch { /* already gone */ }
    if (reduced()) { clock.set(clock.nearestBound(clock.t), { reason: "settle" }); return; }
    if (Math.abs(velocity) > SETTLE) coast();
    else clock.set(clock.nearestBound(clock.t), { reason: "settle" });
  }

  function onKey(event) {
    const keys = {
      ArrowLeft: () => clock.step(-1),
      ArrowRight: () => clock.step(1),
      ArrowDown: () => clock.step(-1),
      ArrowUp: () => clock.step(1),
      PageDown: () => clock.step(-10),
      PageUp: () => clock.step(10),
      Home: () => clock.set(0, { reason: "step" }),
      End: () => clock.set(duration, { reason: "step" }),
    };
    const fn = keys[event.key];
    if (!fn) return;
    stopCoast();
    velocity = 0;
    fn();
    event.preventDefault();
  }

  field.addEventListener("pointerdown", onDown);
  field.addEventListener("pointermove", onMove);
  field.addEventListener("pointerup", onUp);
  field.addEventListener("pointercancel", onUp);
  field.addEventListener("keydown", onKey);

  /* --- lifecycle -------------------------------------------------------- */

  const unsubscribe = clock.subscribe((_, meta) => render(meta));

  const resize = new ResizeObserver(() => { redraw(); render(); });
  resize.observe(field);

  const themeWatch = new MutationObserver(() => { redraw(); });
  themeWatch.observe(document.documentElement, {
    attributes: true, attributeFilter: ["data-theme"],
  });

  const stopReducedWatch = onReducedChange(() => { redraw(); });

  redraw();
  render();

  /* The one orchestrated entrance in the whole build: the four tracks write
     themselves, left to right, staggered by channel. It happens once. */
  const entrance = drawOn(laneProgress, { stagger: 0.07, onUpdate: redraw });

  return {
    clock,
    redraw,
    destroy() {
      unsubscribe();
      resize.disconnect();
      themeWatch.disconnect();
      stopReducedWatch();
      stopCoast();
      if (entrance) entrance.kill();
      field.removeEventListener("pointerdown", onDown);
      field.removeEventListener("pointermove", onMove);
      field.removeEventListener("pointerup", onUp);
      field.removeEventListener("pointercancel", onUp);
      field.removeEventListener("keydown", onKey);
    },
  };
}
