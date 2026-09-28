/* ===========================================================================
   predictivearc.js — vendored from ThreeUI, "Predictive Arc".

   PROVENANCE. Do not rewrite this file from what it looks like on screen.

     source   https://threeui.com/source-code/predictive-arc.json
     revision SHA-256 fa86582fc870
     fetched  22 Sep 2026, HTTP 200, 328,479 bytes
     bundle   SHA-256 138646da953c1bad8264d10cc7087f0108d189ebe819beb362117a16b07d1149

     src/shaders/predictive-arc/predictiveArcRenderer.ts
       SHA-256 fc08c66b13c4a8173c8a88845926b72266d1b1a4fc345c84f44ee61fbfaba92b
       4,088 bytes, 112 lines
     src/shaders/predictive-arc/PredictiveArcCanvas.tsx
       SHA-256 ebaa5a1b1f785c7772aaedc2b195318fd63bd9c3e5e5d8e175600968b245dae7
       4,365 bytes
     src/shaders/predictive-arc/PredictiveArcCollection.tsx
       SHA-256 b77a845ab2fa8e8ef8d9b6812d71efe6f320d865d97ec97b2e15253b5950fd63

   All 16 files in the bundle were hashed on fetch. Every one matched both the
   bundle's own .sha256 field and the integration brief, and the bundle hash
   above is byte-identical to the one datapixelarc.js recorded on 21 Sep, so
   the registered revision has not moved under us. The bundle carries no
   licence file and the registered files carry no copyright notice; that is
   recorded here rather than assumed either way.

   WHAT THE BRIEF DOES NOT SAY
   ---------------------------
   The brief lists the runtime as "Canvas 2D + Raw WebGL + Three.js r128".
   That is the COLLECTION's runtime, covering its four variants. This variant
   is Canvas 2D and nothing else: createPredictiveArcRenderer calls
   canvas.getContext("2d") and draws with fillRect. There is no shader, no
   WebGL context and no Three.js on this path, so like the data-pixel variant
   it costs no new dependency at all. Verified by reading the registered
   renderer, which is reproduced below.

   The brief's configured usage passes `hue` and `saturation`. Read the
   registered renderer and neither is used anywhere in its loop: they are
   declared in PredictiveArcOptions, defaulted in PREDICTIVE_ARC_DEFAULTS, and
   then never read. The component applies them one layer up, in
   PredictiveArcCanvas.tsx, as a CSS filter on the canvas element:

       style={{ filter: `hue-rotate(${hue}deg) saturate(${saturation})` }}

   That matters here, because hue is the lever this section needs (see below)
   and it is the component's own authored lever, not an edit to its colour
   maths. It is applied in the same place and by the same means.

   WHY THIS ONE, AND WHY ROTATED
   -----------------------------
   portalfield.js rejected this component for #proof on a measured hue
   collision. That finding stands, and it is the reason for the rotation
   rather than an argument against using it.

   Measured here rather than reasoned about: rendered at 1440x900 in the
   registered dark mode and sampled over every lit pixel, the unrotated ground
   has a MEDIAN HUE OF 262.2 degrees over n = 134,417 pixels. The four channel
   swatches and the alert colour, computed from tokens.css, are

       --ch-audience   35.9     --ch-facial    202.0
       --ch-transcript 170.2    --ch-vocal     252.2     --tear  334.2

   so unrotated it sits 10.0 degrees from the vocal swatch, and the registered
   dark path sets globalCompositeOperation = "lighter", so it stacks bright
   rather than settling. On a page where colour carries meaning -- four
   channels, four fixed swatches -- a ground that lands on a channel's own hue
   is not decoration, it is a false reading.

   The limits rail is the one section on this page that displays NO channel
   swatch: the only channel token in its stylesheet is a --ch-facial tint on
   its own ::before. The collision is therefore with the vocal swatch
   elsewhere on the page rather than with anything beside it, and the fix is
   to move the hue into a measured gap. Sweeping every whole-degree rotation
   and scoring each by its minimum separation from all five meaning-bearing
   hues, the maximum inside the violet family is

       +30 degrees -> 292.2, clearance 40.0 (nearest: vocal)

   with +25 at 35.0 and +35 at 37.0 either side of it, the ceiling being the
   half-width of the only wide gap this family has, 252.2 -> 334.2. Rotations
   that score higher exist (-159 reaches 67.0) but they are not this component
   any more; they are a green one, and there is already a green ground on this
   page.

   The host passes +20, not +30, and that is a trade rather than an
   oversight. +30 scores 40.0 and +20 scores 30.0, both far clear of the 10.0
   the component starts at; but rendered and looked at, +30 is far enough
   round to read as pink, and pink on this page is --tear, the alert colour,
   which appears on .f-measure strong and means a figure needs attention.
   Clearance from a swatch is measurable and was measured; whether a ground
   reads as an alert is not, and the 10 degrees was spent on it. Both numbers
   are recorded here so the choice can be re-argued rather than re-derived.

   DEVIATIONS FROM THE REGISTERED SOURCE, AND WHY
   ----------------------------------------------
   1. TypeScript annotations removed. This project is plain ESM; nothing else
      about the code changes.

   2. React removed. PredictiveArcRenderer's effect body becomes mountX(host)
      returning a teardown, which is the shape the three sibling ports already
      use. The ResizeObserver, the IntersectionObserver, the visibilitychange
      handler and the rAF bookkeeping are the registered ones.

   3. The opaque ground is not painted. The registered renderer takes its
      context with { alpha: false } and opens every frame by filling the whole
      canvas with #030303 (dark) or #eef1f6 (light). Both are wrong here: this
      is a BACKGROUND behind a themed section whose grounds are tokens
      (--screen #080A0B on BENCH, --body #DFE4E6 on FIELD), and the section
      behind the canvas must show through. The context is taken with
      { alpha: true } and that fill is replaced by clearRect over the same
      rectangle, which is the minimum substitution that still clears the
      frame. This is deviation 3 of datapixelarc.js, for the same reason.

   4. Reduced motion paints one frame and stops. The registered component has
      no reduced-motion path; this project checks for it three times and a
      permanently animating ground would defeat that.

   5. `opacity`, as in the three sibling ports. It is this project's, not the
      source's, and it is the only CSS value on the canvas that is not.

   THE PIXEL-RATIO CAP THIS FILE DELIBERATELY DOES NOT TAKE
   --------------------------------------------------------
   datapixelarc.js introduced a maxPixelRatio prop and capped its host to 1,
   on a measurement that the cap was nearly free. The same measurement was run
   for this component before copying that decision, and it does not hold here,
   so the cap is not taken and the registered literal 2 stands. At 1440x900 in
   headless Chrome on this machine, 40 frames after 5 warm-up frames:

                      dpr 1     dpr 2     cost of 2x
       predictive     8.94 ms   9.51 ms      0.57 ms
       data-pixel     4.98 ms   5.12 ms      0.14 ms

   The cap buys 0.57 ms, not a frame budget: the loop walks CSS pixels, so the
   fillRect COUNT is identical at either ratio and only the rasterised area
   differs, which for dots of at most 6 CSS px is little. And it is not free
   in the image. Rendering one frame at each ratio, box-downsampling the 2x
   backing store to 1x and differencing, the mean channel difference over the
   whole field is 18.58/255 for this component and 26.53/255 for data-pixel --
   these are hard-edged rects at fractional positions, so 2x genuinely
   antialiases edges that 1x cannot. Capping would be paying an image for
   half a millisecond.

   Recorded rather than acted on: that second column also does not reproduce
   the 1.8 ms / 15.8 ms in datapixelarc.js's own header. Different machine,
   different viewport and a different pixelSize, so it is not a contradiction
   that can be resolved from here, and that host's cap is left exactly as it
   was rather than changed on a measurement that was not aimed at it.
      =========================================================================== */

export const PREDICTIVE_ARC_DEFAULTS = {
  mode: "dark",
  speed: 1,
  spacing: 5,
  dotSize: 6,
  archHeight: 0.7,
  thickness: 1,
  brightness: 1,
  hue: 0,
  saturation: 1,
};

function resolveMode(mode) {
  if (mode === "light" || mode === 1 || mode === "1") return "light";
  return "dark";
}

/* ---------------------------------------------------------------------------
   The registered renderer. Deviations 1 and 3 only; see the header.
   --------------------------------------------------------------------------- */
export function createPredictiveArcRenderer(canvas, getOptions) {
  const context = canvas.getContext("2d", { alpha: true });
  if (!context) return null;
  let width = 1;
  let height = 1;
  let time = 0;

  const resize = (nextWidth, nextHeight) => {
    width = Math.max(1, nextWidth);
    height = Math.max(1, nextHeight);
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  };

  const render = () => {
    const options = getOptions();
    const mode = resolveMode(options.mode);
    const isLight = mode === "light";
    /* Deviation 3: the registered fillStyle/fillRect of #eef1f6 / #030303. */
    context.clearRect(0, 0, width, height);
    time += 0.015 * options.speed;

    const centerX = width / 2;
    const archPeakY = height * 0.35;
    const archWidth = width * 1.5;
    const archHeight = height * options.archHeight;
    context.globalCompositeOperation = isLight ? "source-over" : "lighter";

    for (let x = 0; x < width; x += options.spacing) {
      const normX = (x - centerX) / (archWidth / 2);
      const curveY = archPeakY + normX * normX * archHeight;
      for (let y = 0; y < height; y += options.spacing) {
        const distanceToCurve = Math.abs(y - curveY);
        const thickness = (140 + (1 - Math.abs(normX)) * 80) * options.thickness;
        if (distanceToCurve >= thickness) continue;
        let intensity = 1 - distanceToCurve / thickness;
        const waveX = Math.sin(x * 0.015 + time);
        const waveY = Math.cos(y * 0.02 + time);
        intensity = intensity * 0.7 + waveX * waveY * 0.3 * intensity;
        intensity *= Math.max(0, 1 - Math.pow(Math.abs(normX), 2.5));
        if (intensity <= 0.02) continue;

        let r;
        let g;
        let b;
        if (isLight) {
          // Cool violet ink on pale paper — readable without additive washout.
          r = Math.min(255, 48 * intensity + 70 * Math.pow(intensity, 3));
          g = Math.min(255, 28 * intensity + 45 * Math.pow(intensity, 4));
          b = Math.min(255, 120 * intensity + 110 * Math.pow(intensity, 2));
          if (intensity > 0.7) {
            const coreBoost = (intensity - 0.7) * 3.3;
            r = Math.min(255, r + 90 * coreBoost);
            g = Math.min(255, g + 70 * coreBoost);
            b = Math.min(255, b + 110 * coreBoost);
          }
        } else {
          r = Math.min(255, 60 * intensity + 100 * Math.pow(intensity, 3));
          g = Math.min(255, 20 * intensity + 60 * Math.pow(intensity, 4));
          b = Math.min(255, 120 * intensity + 135 * Math.pow(intensity, 2));
          if (intensity > 0.7) {
            const coreBoost = (intensity - 0.7) * 3.3;
            r = Math.min(255, r + 150 * coreBoost);
            g = Math.min(255, g + 150 * coreBoost);
            b = Math.min(255, b + 150 * coreBoost);
          }
        }
        context.fillStyle = `rgb(${Math.floor(r * options.brightness)}, ${Math.floor(g * options.brightness)}, ${Math.floor(b * options.brightness)})`;
        context.fillRect(x, y, options.dotSize * intensity, options.dotSize * intensity);
      }
    }
    context.globalCompositeOperation = "source-over";
  };

  return { resize, render };
}

/* ---------------------------------------------------------------------------
   The host. PredictiveArcRenderer's effect body, without React.
   --------------------------------------------------------------------------- */
export function mountPredictiveArc(host, props = {}) {
  if (!host) return null;

  const options = { ...PREDICTIVE_ARC_DEFAULTS, ...props };
  let still = Boolean(props.still);

  const canvas = document.createElement("canvas");
  host.appendChild(canvas);

  const renderer = createPredictiveArcRenderer(canvas, () => options);
  if (!renderer) { canvas.remove(); return null; }

  let frame = 0;
  let visible = true;

  const resize = () => {
    const bounds = host.getBoundingClientRect();
    renderer.resize(bounds.width, bounds.height);
    renderer.render();
  };
  const tick = () => {
    renderer.render();
    frame = visible && !document.hidden ? requestAnimationFrame(tick) : 0;
  };
  const start = () => {
    if (still || frame || !visible || document.hidden) return;
    frame = requestAnimationFrame(tick);
  };
  const stop = () => {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  };

  const observer = new ResizeObserver(resize);
  const intersection = new IntersectionObserver(([entry]) => {
    visible = entry?.isIntersecting ?? true;
    if (visible) start(); else stop();
  });
  const visibility = () => { if (document.hidden) stop(); else start(); };

  observer.observe(host);
  intersection.observe(host);
  document.addEventListener("visibilitychange", visibility);

  resize();
  if (!still) frame = requestAnimationFrame(tick);
  /* Follows the reader's motion setting live -- the OS preference or the
     in-page switch -- through the one event lib/motion.js sends, so a reader
     who turns motion off mid-page stops this loop too, and one who turns it
     back on gets it back (25 Sep 2026, INCLUSIVE_DESIGN.md I1). An event rather
     than an import keeps this vendored module free of the project's own. */
  const onMotion = (event) => {
    still = Boolean(event.detail && event.detail.reduced);
    if (still) { stop(); renderer.render(); } else start();
  };
  window.addEventListener("motionchange", onMotion);

  /* Same place and same means as PredictiveArcCanvas.tsx, which puts
     hue-rotate and saturate on the canvas element rather than in the loop.
     opacity is this project's, and is the one CSS value not from the source. */
  canvas.style.opacity = String(options.opacity ?? 1);
  canvas.style.filter =
    `hue-rotate(${options.hue}deg) saturate(${options.saturation})`;

  return () => {
    stop();
    window.removeEventListener("motionchange", onMotion);
    observer.disconnect();
    intersection.disconnect();
    document.removeEventListener("visibilitychange", visibility);
    canvas.remove();
  };
}
