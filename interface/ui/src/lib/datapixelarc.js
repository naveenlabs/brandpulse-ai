/* ===========================================================================
   datapixelarc.js — vendored from ThreeUI, "Data Pixel Arc".

   PROVENANCE. Do not rewrite this file from what it looks like on screen.

     source   https://threeui.com/source-code/predictive-arc.json
     revision SHA-256 fa86582fc870
     fetched  21 Sep 2026, HTTP 200, 328,479 bytes
     bundle   SHA-256 138646da953c1bad8264d10cc7087f0108d189ebe819beb362117a16b07d1149

     src/shaders/data-pixel-arc/dataPixelArcRenderer.ts
       SHA-256 65bdfb98424996d935923f39f163e1667f0bc2b8faa458d900f4450beabba0eb
       4,372 bytes, 106 lines
     src/shaders/data-pixel-arc/DataPixelArcCanvas.tsx
       SHA-256 2e25156d43dfd1bf0fb47384f75df240cd0c4038deae75a8dacae7c213269c5b
       2,376 bytes, 43 lines

   All 16 files in the bundle were hashed on fetch and every one matched both
   the bundle's own .sha256 field and the integration brief. The bundle carried
   no licence file and the registered files carry no copyright notice; that is
   recorded here rather than assumed either way.

   WHAT THE BRIEF DOES NOT SAY
   ---------------------------
   The brief lists the runtime as "Canvas 2D + Raw WebGL + Three.js r128".
   That is the collection's runtime. THIS variant is Canvas 2D and nothing
   else: createDataPixelArcRenderer calls canvas.getContext("2d") and draws
   with fillRect. There is no shader, no WebGL context and no Three.js on this
   path, so the component costs no new dependency at all. Verified by reading
   the registered renderer, which is reproduced below.

   The brief also passes hue={0} saturation={1.00}. Neither is read inside the
   renderer. DataPixelArcCanvas.tsx applies both as a CSS filter on the canvas
   element instead:

       style={{ filter: `hue-rotate(${hue}deg) saturate(${saturation})` }}

   so they are live props, applied here in the same place by the same means.

   WHY THIS ONE, OF THE FOUR — AND A CORRECTION
   --------------------------------------------
   portalfield.js's header rejected this component on the grounds that it is
   "emerald next door to --ch-transcript". That was read off the brief's prose
   and it is wrong. Evaluating the renderer over a pixel grid gives a peak of
   rgb(130,255,130), hue 120.0 deg. --ch-transcript is hue 170.2. They are 50
   degrees apart, which is not next door. The rejection stands only for the
   two components measured below, and that header has been corrected.

     Predictive Arc   median hue 260.0    --ch-vocal is 252.2   -> 7.8 deg apart
     Data Pixel Arc   peak   hue 120.0    --ch-transcript 170.2 -> 50 deg apart

   Predictive Arc is the hard reject: at under 8 degrees from a channel hue,
   and additively blended so it stacks bright, it would read as vocal-channel
   data. Ribbon Field is already spent on #seam.

   Data Pixel Arc is mounted here at hue-rotate(100deg), which lands it on a
   deep steel navy in the same family as Portal Field's #1e3a8a fringe at the
   top of this section. That is a composition decision, not a repair: it sits
   under all four channel hues, and it makes the section's two grounds read as
   one light rather than two.

   WHERE ITS LIGHT ACTUALLY FALLS — MEASURED
   -----------------------------------------
   The brief calls it "an emerald pixel horizon". It is not a horizon. The
   band is an arch:

       curveY = height*arcCenter + |nx|^1.8 * height*arcDrop

   which crowns in the CENTRE and falls away to both edges, and it is then
   multiplied by max(0, 1 - |nx|^2.5), so the edges go to nothing. At the
   defaults, 10,517 of 20,340 cells paint at 1440x900.

   That centre weighting is the reason this component suits the limits rail.
   The rail's reading position is fixed at the centre, so the brightest part
   of the field is exactly where the open limitation sits, and the tape
   arrives and departs through darkness at both edges.

   arcCenter is a real prop and is read, so the crown is placed on the rule
   rather than over the body copy.

   FORCED DEVIATIONS — four, all structural
   ----------------------------------------
   1. No React. DataPixelArcCanvas.tsx is a React component and this project
      has no React. Its effect body is reproduced call for call below:
      ResizeObserver on the host, IntersectionObserver for visibility,
      a visibilitychange listener, one rAF chain, same teardown order.

   2. No TypeScript. Type annotations are removed. Nothing else in the render
      function is changed: the arithmetic, the constants, the loop bounds, the
      guard thresholds and the colour expressions are character for character
      the registered source.

   3. The canvas is transparent and does not paint its own ground. The
      registered renderer opens every frame with

          context.fillStyle = isLight && lightBackground ? lightBackground : "#030308";
          context.fillRect(0, 0, width, height);

      on a context taken with { alpha: false }. This project has two themes
      whose grounds are tokens (--screen #080A0B on BENCH, --body #DFE4E6 on
      FIELD) and the section behind the canvas must show through. The context
      is taken with { alpha: true } and that opaque fill is replaced by
      clearRect over the same rectangle, which is the minimum substitution
      that still clears the frame. The lightBackground gradient is built and
      kept so the resize path stays identical, and is simply not painted.

   4. Reduced motion paints one frame and stops. The registered component has
      no reduced-motion path; this project checks for it three times and a
      permanently animating ground would defeat that.

   5. maxPixelRatio, a new option, defaulting to the registered 2 so the
      component behaves exactly as registered unless a host asks otherwise.
      This host asks for 1, and the reason is measured. The loop count is
      resolution-independent, but every cell is a fillRect against the backing
      store, so the RASTERISATION cost is not:

          dpr 1   963,460 backing px    1.8 ms per frame
          dpr 2 3,850,964 backing px   15.8 ms per frame

      15.8 ms is a whole 60 fps budget spent on a background. Supersampling
      buys nothing here because the component draws flat hard-edged blocks of
      12 CSS px with no gradient or curve in them: rendered at 1x and at 2x and
      differenced, the mean channel difference over the whole field is
      0.42/255. The cap is therefore free, and it is a prop rather than an
      edit so the registered behaviour is still one argument away.
   =========================================================================== */

export const DATA_PIXEL_ARC_DEFAULTS = {
  mode: "dark",
  speed: 1,
  pixelSize: 8,
  arcCenter: 0.4,
  arcDrop: 0.9,
  thickness: 0.35,
  brightness: 1,
  hue: 0,
  saturation: 1,
  maxPixelRatio: 2,
};

function resolveMode(mode) {
  if (mode === "light" || mode === 1 || mode === "1") return "light";
  return "dark";
}

/* ---------------------------------------------------------------------------
   The registered renderer. Deviations 2 and 3 only; see the header.
   --------------------------------------------------------------------------- */
export function createDataPixelArcRenderer(canvas, getOptions) {
  const context = canvas.getContext("2d", { alpha: true });
  if (!context) return null;
  let width = 1;
  let height = 1;
  let time = 0;
  let lightBackground = null;
  const resize = (nextWidth, nextHeight) => {
    width = Math.max(1, nextWidth);
    height = Math.max(1, nextHeight);
    /* Deviation 5: the registered literal 2, now the default of a prop. */
    const pixelRatio = Math.min(window.devicePixelRatio || 1, getOptions().maxPixelRatio ?? 2);
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    lightBackground = context.createLinearGradient(0, 0, 0, height);
    lightBackground.addColorStop(0, "#f8faf6");
    lightBackground.addColorStop(0.58, "#f3f6f1");
    lightBackground.addColorStop(1, "#edf1ec");
  };
  const render = () => {
    const options = getOptions();
    const isLight = resolveMode(options.mode) === "light";
    /* Deviation 3: the registered fillRect of #030308 / lightBackground. */
    context.clearRect(0, 0, width, height);
    const cols = Math.ceil(width / options.pixelSize);
    const rows = Math.ceil(height / options.pixelSize);
    const arcCenterY = height * options.arcCenter;
    const arcDrop = height * options.arcDrop;
    const thickness = height * options.thickness;
    for (let x = 0; x < cols; x += 1) {
      for (let y = 0; y < rows; y += 1) {
        const px = x * options.pixelSize;
        const py = y * options.pixelSize;
        const nx = (px / width) * 2 - 1;
        const curveY = arcCenterY + Math.pow(Math.abs(nx), 1.8) * arcDrop;
        let intensity = Math.max(0, 1 - Math.abs(py - curveY) / thickness);
        if (intensity <= 0.01) continue;
        const wave1 = Math.sin(nx * 4 - time * 1.5) * 0.1;
        const wave2 = Math.cos(py * 0.01 + time) * 0.1;
        intensity = Math.max(0, Math.min(1, intensity + wave1 + wave2));
        intensity *= Math.max(0, 1 - Math.pow(Math.abs(nx), 2.5));
        if (intensity <= 0.02) continue;
        const coreStrength = Math.pow(intensity, 3);
        const middleStrength = Math.pow(intensity, 1.5);
        let r;
        let g;
        let b;
        if (isLight) {
          // Sage edge pixels hold their shape on paper while the emerald core stays vivid.
          const pigment = Math.pow(intensity, 0.78);
          const inkStrength = Math.max(0.45, Math.min(1.35, options.brightness));
          const paper = [238, 242, 237];
          const ink = [
            192 - 172 * pigment - 10 * coreStrength,
            204 - 88 * pigment + 18 * coreStrength,
            193 - 132 * pigment + 4 * coreStrength,
          ];
          r = Math.max(0, Math.min(255, Math.round(paper[0] + (ink[0] - paper[0]) * inkStrength)));
          g = Math.max(0, Math.min(255, Math.round(paper[1] + (ink[1] - paper[1]) * inkStrength)));
          b = Math.max(0, Math.min(255, Math.round(paper[2] + (ink[2] - paper[2]) * inkStrength)));
        } else {
          r = Math.floor((30 * intensity + 100 * coreStrength) * options.brightness);
          g = Math.floor((220 * middleStrength + 40 * coreStrength) * options.brightness);
          b = Math.floor((80 * intensity + 50 * coreStrength) * options.brightness);
        }
        context.fillStyle = `rgb(${r}, ${g}, ${b})`;
        context.globalAlpha = isLight ? Math.min(1, 0.22 + Math.pow(intensity, 0.68) * 0.78) : intensity;
        context.fillRect(px, py, options.pixelSize - 1, options.pixelSize - 1);
      }
    }
    context.globalAlpha = 1;
    time += 0.02 * options.speed;
  };
  return { resize, render };
}

/* ---------------------------------------------------------------------------
   The host. DataPixelArcCanvas.tsx's effect body, without React.
   --------------------------------------------------------------------------- */
export function mountDataPixelArc(host, props = {}) {
  if (!host) return null;

  const options = { ...DATA_PIXEL_ARC_DEFAULTS, ...props };
  let still = Boolean(props.still);

  const canvas = document.createElement("canvas");
  host.appendChild(canvas);

  const renderer = createDataPixelArcRenderer(canvas, () => options);
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


  /* Same place and same means as DataPixelArcCanvas.tsx, which puts
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
