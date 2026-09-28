/* ===========================================================================
   seam.js — the mark comes apart, and one piece does not come back.

   This sits between the hero and the film, and it exists because of a gap in
   what the page says rather than because a logo animation would look good.

   The hero says the system reads four channels. The film says watch the four
   disagree. Neither says WHY four readings of one second are never collapsed
   into a single number, which is the oldest and most consequential design
   decision in this project (the "no fused multimodal model" rule, README,
   "Engineering rules"). This section is that
   sentence, drawn.

   WHAT IS TRUE AND WHAT IS ASSIGNED
   ---------------------------------
   True: the wordmark is drawn as four separate subpaths. Measured by the
   shoelace formula on its own path data, they are two large slabs of 41.08
   square units and two small wedges of 12.44, a ratio of 3.30 to 1.

   Assigned: WHICH channel rides which piece. That mapping is a decision made
   here, not a property of the drawing, and it was made by the one thing that
   should decide it -- measured accuracy. The two slabs carry the two channels
   that work (audience 78.7%, transcript 67.8%); the two wedges carry the two
   that do not (vocal 48.9%, facial 34.2%). Nothing on screen claims the mark
   was designed this way, because it was not, and saying so would be a
   fabricated origin story.

   The piece that fails to close is the facial channel, and that is not a
   flourish either. It is the one channel this project benched twice and
   adopted nothing for, because on held-out speakers all nine candidate models
   scored below an always-NEUTRAL constant. The pipeline already treats it as
   the piece that does not fit: FACIAL_ONLY_CONFLICT_WEIGHT cuts its vote to
   0.342 of itself wherever it is the only channel dissenting. The gap on
   screen is that constant, drawn.

   EVERY FIGURE IS READ, NEVER TYPED
   ---------------------------------
   The accuracies come from CHANNEL_META, the constant from FACIAL_REFERENCES,
   and the down-weight from figures.json at run time. A test already asserts
   CHANNEL_META agrees with ui_evidence/figures.json, so a number cannot move
   here without its evidence moving first.

   contract.js states a hard rule about one of them: this interface may not
   quote the facial 34.2% without also quoting what it is worse than. The
   facial row therefore carries the constant on its own line, in both the
   still layout and the moving one, and so does the closing paragraph.

   WHAT THIS SECTION DELIBERATELY DOES NOT SAY
   -------------------------------------------
   Two drafts of it were cut for repeating the page.

   It does not gloss the four channels. The hero's own feature list already
   reads "What was said / The face on camera / How it was said / What the room
   wrote", and the film's third shot names them a third time. The rows carry a
   name, a measured number and its sample, and nothing else.

   It does not argue that the facial channel is weak. The film's fifth shot is
   that argument, at length, with the constant and the human ceiling drawn as
   bars. Here the facial number is evidence for a different claim -- that four
   readings are never averaged into one -- which is the project's oldest design
   decision and was, until this section, the one thing the page never said.

   TWO LAYOUTS, BOTH FINISHED
   --------------------------
   The still layout is the default and is written in ordinary flow: a heading,
   the four pieces already apart and labelled, then the closing paragraph. It
   is a complete article that happens to be illustrated, and it is what a
   reader gets under prefers-reduced-motion, on a short viewport, or if this
   module's wiring never runs.

   `.is-play` is added only when there is room and permission to move. It
   converts the same DOM into one pinned viewport and hands the choreography
   to a scrubbed timeline. The pin is deliberately SHORT -- 260% of viewport
   height against the film's 760% -- because the film is pinned too and it
   starts the moment this one lets go.
   ======================================================================== */

import { CHANNEL_META, FACIAL_REFERENCES } from "./contract.js";
import { esc, pct } from "./format.js";
import { gsap, ScrollTrigger, reduced, motionMedia } from "./motion.js";
import { mountRibbonField } from "./ribbonfield.js";

/* The wordmark's own four subpaths, in the order they are drawn, with the
   centroid of each computed off this same geometry. `cy` is what decides
   where a piece comes to rest, so it is the true area centroid and not the
   mean of the vertices -- the two middle pieces are trapezoids, where those
   two numbers differ.

   The channel on each piece is the assigned half of the mapping; see above. */
const PIECES = [
  { channel: "vocal", cy: 5.66667, d: "M4.46 3L10.68 7L4.46 7Z" },
  { channel: "transcript", cy: 9.80188, d: "M4.46 7.6L11.62 7.6L17.84 11.6L4.46 11.6Z" },
  { channel: "audience", cy: 14.19812, d: "M6.16 12.4L19.54 12.4L13.32 16.4L6.16 16.4Z" },
  { channel: "facial", cy: 18.33333, d: "M4.46 17L10.68 17L4.46 21Z" },
];

/* The ink's own bounding box rather than the icon's 24x24 frame. The frame
   would pad the mark with 29% empty width, which matters when the glyph is a
   column of a two-column composition. */
const VIEW = "4.46 3 15.08 18";

/** The piece that is measured worst, and so the one that never closes. */
const BROKEN = "facial";

/* The extrusion, as offsets in the mark's own units. Eight steps down and to
   the right, because the chrome ramp puts its light at the upper left. */
const DEPTH = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1];

/**
 * Where a piece rests when the mark is apart, as a CSS expression.
 *
 * The pieces are four identically-framed SVGs stacked on top of each other, so
 * stacked at rest they are indistinguishable from the whole mark. Apart, each
 * one slides to the centre line of its own row.
 *
 *   dy = (12 - cy)/18 * markHeight  +  (index - 1.5) * rowPitch
 *        \_______________________/     \____________________/
 *        back to the glyph's centre     out to this row's centre
 *
 * It is emitted as `calc()` against the two layout variables rather than as a
 * pixel number, so the still layout stays correct at every width with no
 * JavaScript involved at all.
 */
function restAt(piece, index) {
  const k = (12 - piece.cy) / 18;
  const m = index - 1.5;
  const lift = `${Math.abs(k).toFixed(5)} * var(--mh)`;
  const out = `${Math.abs(m).toFixed(1)} * var(--row)`;
  return `calc(${k < 0 ? "0px - " : ""}${lift} ${m < 0 ? "-" : "+"} ${out})`;
}

/* ---------------------------------------------------------------- markup */

export function seamMarkup(figures = {}) {
  const pipeline = (figures && figures.pipeline) || {};
  const damp = pipeline.facial_only_conflict_weight;
  const constant = FACIAL_REFERENCES.constant;

  /* Each piece is drawn three times in one frame: an extruded body stepped
     down and to the right, the milled face carrying the chrome ramp, and a
     tint that colours the metal without flattening its highlight. The step is
     0.1 user units, which is about 1.2px at the resting mark size -- enough
     for an edge, small enough that the face's centroid still lands on its
     row. */
  const body = (d) => DEPTH.map((step, i) =>
    `<path d="${d}" transform="translate(${step.toFixed(2)} ${(step * 1.35).toFixed(2)})"
           opacity="${(0.96 - i * 0.085).toFixed(3)}"/>`).join("");

  const glyph = `
      <svg class="seam__ghost" viewBox="${VIEW}" aria-hidden="true" focusable="false">
        <path d="${PIECES.map((p) => p.d).join(" ")}"/>
      </svg>
      ${PIECES.map((p, i) => `
      <svg class="seam__piece" data-piece="${p.channel}" viewBox="${VIEW}"
           style="--dy: ${restAt(p, i)}" aria-hidden="true" focusable="false">
        <g class="seam__extrude">${body(p.d)}</g>
        <g class="seam__top">
          <path class="seam__face" d="${p.d}" fill="url(#seam-chrome)"/>
          <path class="seam__tint" d="${p.d}"/>
        </g>
      </svg>`).join("")}`;

  /* The light, as one ramp shared by all four pieces.

     userSpaceOnUse rather than objectBoundingBox on purpose: the four pieces
     are different widths, and a per-shape gradient would put a different
     highlight on each one, which reads as four objects rather than four parts
     of the same milled thing. In the mark's own coordinates they share one
     light. wireSeam slides it with the scroll, so the reader turns the object
     under the lamp rather than watching it shine at them. */
  const defs = `
    <svg class="seam__defs" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="seam-chrome" gradientUnits="userSpaceOnUse"
                        x1="2.2" y1="1.4" x2="21.8" y2="22.6"
                        data-chrome>
          <stop offset="0"    stop-color="#20262f"/>
          <stop offset="0.11" stop-color="#75808f"/>
          <stop offset="0.21" stop-color="#e6eefa"/>
          <stop offset="0.30" stop-color="#9dabbc"/>
          <stop offset="0.44" stop-color="#ffffff"/>
          <stop offset="0.55" stop-color="#93a1b3"/>
          <stop offset="0.68" stop-color="#3e4653"/>
          <stop offset="0.82" stop-color="#c8d4e4"/>
          <stop offset="1"    stop-color="#2a313b"/>
        </linearGradient>
      </defs>
    </svg>`;

  const row = (p) => {
    const meta = CHANNEL_META[p.channel];
    const note = p.channel === BROKEN
      ? `${meta.sample} — ${meta.worseThanConstant}`
      : meta.sample;
    return `
      <li class="seam__row" data-channel="${p.channel}">
        <span class="seam__rule" aria-hidden="true"></span>
        <p class="seam__name">${esc(meta.label)}</p>
        <b class="seam__num">${esc(pct(meta.accuracy))}</b>
        <p class="seam__note">${esc(note)}</p>
      </li>`;
  };

  /* The closing paragraph states the misalignment in words. On the still
     layout that sentence is the only place it exists, and on the moving one
     it is what the picture has just said. */
  const shut = `
        Averaging the four would hide the one thing worth seeing. The face reads
        ${esc(pct(CHANNEL_META.facial.accuracy))} here, below an always-NEUTRAL
        constant at ${esc(pct(constant.value))}; the words read
        ${esc(pct(CHANNEL_META.transcript.accuracy))}. Blend them and the face&rsquo;s
        error is carried into the answer while the disagreement that produced it
        disappears. So they are never fused. They are kept apart, compared, and
        the seconds where they contradict each other are what gets scored.`;

  return `
  <section class="seam" id="seam" aria-labelledby="seam-h" data-seam>
    <div class="seam__field" data-field aria-hidden="true"></div>
    <div class="seam__air" aria-hidden="true"></div>
    ${defs}

    <div class="seam__open" data-beat="open">
      <h2 class="seam__h" id="seam-h">The mark is four pieces.</h2>
      <p class="seam__sub">
        So is every second this system scores: four readings, taken
        separately, never merged into one. Keep going and it comes apart.
      </p>
    </div>

    <div class="seam__stage">
      <div class="seam__glyph" data-glyph>${glyph}</div>
      <ol class="seam__rows" data-rows>${PIECES.map(row).join("")}</ol>
    </div>

    <div class="seam__shut" data-beat="shut">
      <h3 class="seam__h2">One piece never closes.</h3>
      <p class="seam__body">${shut}</p>
    </div>
  </section>`;
}

/* --------------------------------------------------------------- the move */

/* Storyboard positions in 0..1 across the pinned scroll, kept together so the
   sequence can be re-timed without touching a tween. */
const BEAT = {
  openOut: 0.06,
  apart: 0.12,
  rowsIn: 0.24,
  rowsOut: 0.62,
  home: 0.68,
  shutIn: 0.84,
};

/* How far the mark is turned while it is still one solid object. It resolves
   to flat exactly as the pieces separate, because every rest position in this
   section is measured in the plane and a tilt left in would project them off
   their rows. */
const TILT = { y: -21, x: 8 };

const SPAN = 260;                      // percent of viewport height scrolled
const at = (x) => x * (SPAN / 100);
const dur = (x) => x * (SPAN / 100);

export function wireSeam() {
  const seam = document.querySelector("[data-seam]");
  if (!seam) return;

  const glyph = seam.querySelector("[data-glyph]");
  const pieces = [...seam.querySelectorAll(".seam__piece")];
  const tints = pieces.map((el) => el.querySelector(".seam__tint"));
  const ghost = seam.querySelector(".seam__ghost");
  const rows = [...seam.querySelectorAll(".seam__row")];
  const open = seam.querySelector('[data-beat="open"]');
  const shut = seam.querySelector('[data-beat="shut"]');
  const chrome = seam.querySelector("[data-chrome]");
  if (!glyph || pieces.length !== PIECES.length) return;

  /* The field behind everything. It is mounted whatever the motion setting --
     a still frame of it is a finished picture -- and it takes itself off the
     animation loop whenever the section is out of view or the tab is hidden. */
  mountRibbonField(seam.querySelector("[data-field]"), { still: reduced() });

  /* How far each piece travels, measured rather than recomputed.

     The CSS has already laid the pieces out apart, so their real positions are
     on screen to be read. Clearing the transform puts each one back where it
     belongs in the assembled mark, and the difference between the two
     measurements is the journey. Nothing is derived from the constants twice,
     and a change to --mh or --row at any breakpoint is picked up for free. */
  const cssNum = (name, fallback) => {
    const raw = parseFloat(getComputedStyle(seam).getPropertyValue(name));
    return Number.isFinite(raw) ? raw : fallback;
  };

  const travel = pieces.map(() => 0);
  function measure() {
    /* Both readings are taken with the glyph at its resting scale, because a
       rect inside a scaled parent comes back in scaled pixels and GSAP's `y`
       is set in the parent's own. The swell is applied afterwards. */
    gsap.set(glyph, { scale: 1, rotationX: 0, rotationY: 0 });
    gsap.set(pieces, { clearProps: "transform" });
    const apart = pieces.map((el) => el.getBoundingClientRect().top);
    gsap.set(pieces, { y: 0 });
    const home = pieces.map((el) => el.getBoundingClientRect().top);
    for (let i = 0; i < pieces.length; i += 1) travel[i] = apart[i] - home[i];
    gsap.set(glyph, {
      scale: cssNum("--pop", 1.45),
      rotationY: TILT.y,
      rotationX: TILT.x,
      transformPerspective: 1100,
      transformOrigin: "50% 50%",
    });
  }

  /* The gap the broken piece is left holding, in the same proportion at every
     size: a fourteenth of the mark's height, which is about a fifth of that
     piece's own height. Large enough to read as wrong, small enough to read as
     a measurement rather than a collapse. */
  const gapOf = () => cssNum("--mh", 190) / 14;

  const hue = (channel) =>
    getComputedStyle(seam).getPropertyValue(`--s-${channel}`).trim() || "#ffffff";

  /* The light a piece throws once it is lit, written straight onto the
     element. One drop-shadow rather than a stack of them: this sits over a
     live WebGL field and every extra blur pass is paid for on every frame. */
  const glowOf = (piece, channel) => {
    const colour = channel ? hue(channel) : "";
    return function paint() {
      const t = channel ? this.progress() : 1 - this.progress();
      piece.style.filter = t < 0.02
        ? "none"
        : `drop-shadow(0 0 ${(t * 15).toFixed(1)}px ${colour || hue(piece.dataset.piece)})`;
    };
  };

  const mm = motionMedia({
    play: "(prefers-reduced-motion: no-preference) and (min-height: 640px)",
    still: "(prefers-reduced-motion: reduce), (max-height: 639px)",
  }, (context) => {
    /* The still branch is the absence of work, not a lesser version of it: the
       CSS has already drawn the finished article and the class that would turn
       it into a stage is never added. */
    if (context.conditions.still) return;

    seam.classList.add("is-play");
    measure();

    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: seam,
        start: "top top",
        end: `+=${SPAN}%`,
        scrub: 0.5,
        pin: true,
        anticipatePin: 1,
        invalidateOnRefresh: true,
        /* This section is pinned and sits directly above another pinned one.
           Refreshing top-down keeps the film's start from being measured
           against a pin spacer this one has not inserted yet. */
        refreshPriority: 1,
        onRefreshInit: measure,
      },
    });

    /* The storyboard is written in fractions of the scroll, so the timeline has
       to actually be that long. Without this the last beat ends early and its
       positions all drift forward by the shortfall. */
    tl.set({}, {}, at(1));

    /* 1. The mark is whole and oversized, and the opening line is the only
          text on screen. */
    tl.to(open, { autoAlpha: 0, y: -18, duration: dur(0.08), ease: "power2.in" },
      at(BEAT.openOut));

    /* 2. It comes apart, shedding the swell as it goes, and each piece takes
          its channel's hue on the way out. */
    tl.to(glyph, {
      scale: 1, rotationY: 0, rotationX: 0,
      duration: dur(0.22), ease: "power3.inOut",
    }, at(BEAT.apart));

    /* The light moves across the mark for the whole length of the scroll, so
       the metal is being turned rather than blinking at the reader. One
       attribute write a frame, and only while the scrub is actually moving. */
    if (chrome) {
      const lamp = { s: -1 };
      tl.to(lamp, {
        s: 1,
        duration: dur(1),
        ease: "none",
        onUpdate: () => {
          chrome.setAttribute("gradientTransform",
            `translate(${(lamp.s * 7).toFixed(3)} ${(lamp.s * 7.6).toFixed(3)})`);
        },
      }, 0);
    }

    pieces.forEach((piece, i) => {
      tl.to(piece, {
        y: () => travel[i],
        duration: dur(0.2),
        ease: "power3.inOut",
      }, at(BEAT.apart) + dur(0.035 * i));
      tl.to(tints[i], {
        opacity: 0.88,
        duration: dur(0.16),
        ease: "none",
      }, at(BEAT.apart) + dur(0.035 * i));

      /* A piece tips as it leaves and is flat again by the time it arrives. */
      tl.fromTo(piece, { rotationX: 0 }, {
        rotationX: -16,
        duration: dur(0.1),
        ease: "power2.out",
        transformPerspective: 900,
      }, at(BEAT.apart) + dur(0.035 * i));
      tl.to(piece, {
        rotationX: 0,
        duration: dur(0.1),
        ease: "power2.inOut",
      }, at(BEAT.apart) + dur(0.035 * i) + dur(0.1));

      tl.to(piece, {
        duration: dur(0.16),
        ease: "none",
        onUpdate: glowOf(piece, PIECES[i].channel),
      }, at(BEAT.apart) + dur(0.035 * i));
    });

    /* 3. Each row writes itself in beside its piece, rule first. */
    rows.forEach((el, i) => {
      const rule = el.querySelector(".seam__rule");
      tl.fromTo(rule, { scaleX: 0 }, {
        scaleX: 1, duration: dur(0.1), ease: "power2.out",
      }, at(BEAT.rowsIn) + dur(0.045 * i));
      tl.fromTo(el.querySelectorAll(".seam__name, .seam__num, .seam__note"),
        { autoAlpha: 0, y: 10 },
        { autoAlpha: 1, y: 0, duration: dur(0.09), ease: "power2.out", stagger: dur(0.012) },
        at(BEAT.rowsIn) + dur(0.045 * i) + dur(0.02));
    });

    /* 4. The rows clear, the outline of where the mark belongs is drawn, and
          the pieces go home -- three of them exactly. */
    tl.to(ghost, { opacity: 0.34, duration: dur(0.08), ease: "none" }, at(BEAT.rowsOut));

    tl.to(rows, {
      autoAlpha: 0, y: -12, duration: dur(0.08), ease: "power2.in", stagger: dur(0.015),
    }, at(BEAT.rowsOut));

    pieces.forEach((piece, i) => {
      const broken = PIECES[i].channel === BROKEN;
      tl.to(piece, {
        y: () => (broken ? gapOf() : 0),
        duration: dur(broken ? 0.16 : 0.14),
        ease: broken ? "power4.out" : "power3.inOut",
      }, at(BEAT.home) + dur(0.02 * i));
      tl.to(tints[i], {
        opacity: 0, duration: dur(0.12), ease: "none",
      }, at(BEAT.home) + dur(0.02 * i));
      tl.to(piece, {
        duration: dur(0.12), ease: "none", onUpdate: glowOf(piece, null),
      }, at(BEAT.home) + dur(0.02 * i));
    });

    /* 5. The sentence the gap has just made. */
    tl.fromTo(shut, { autoAlpha: 0, y: 18 },
      { autoAlpha: 1, y: 0, duration: dur(0.1), ease: "power2.out" }, at(BEAT.shutIn));

    return () => {
      seam.classList.remove("is-play");
      gsap.set([glyph, ...pieces, ...tints, ghost, ...rows, open, shut],
        { clearProps: "all" });
      pieces.forEach((piece) => { piece.style.filter = ""; });
      if (chrome) chrome.removeAttribute("gradientTransform");
    };
  });

  /* The pin changes the document's height, and the film below is pinned to a
     position inside it. */
  ScrollTrigger.refresh();
}
