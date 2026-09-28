/* A scroll-driven optical bench. Geometry is illustrative; all readings are
   from the selected report. The audience reading remains video-level. */
import { gsap, ScrollTrigger, reduced, onReducedChange, motionMedia } from './motion.js';
import { CHANNELS, CHANNEL_META, rawReading, FACIAL_REFERENCES } from './contract.js';
import { esc, mmss, confidence, pct, sentence, arrow } from './format.js';
import { mountDataPixelArc } from './datapixelarc.js';
import '../styles/film.css';

export function filmMarkup(pick) {
  const segment = pick.flagged || pick.segment;
  const midpoint = (segment.start_s + segment.end_s) / 2;
  const second = pick.strip.seconds.reduce((a, b) => Math.abs(b - midpoint) < Math.abs(a - midpoint) ? b : a);
  const frame = `/static/frames/${pick.videoId}/p/${second}.jpg`;
  return `<section id="film" class="film film--chamber" aria-labelledby="film-heading">
    <div class="f-chamber">
      <div class="f-field" data-film-field aria-hidden="true"></div>
      <div class="f-atmosphere" aria-hidden="true"></div>
      <div class="f-topline"><span><i></i> BrandPulse / The signal chamber</span><span>One real analysis<span class="sep" aria-hidden="true"></span>${esc(pick.report.brand_name || 'Local video')}</span></div>
      <div class="f-space" aria-hidden="true">
        <canvas class="f-orbits"></canvas>
        <div class="f-optics"><div class="f-object">
          ${CHANNELS.map((c, i) => `<div class="f-plate" style="--channel:var(--ch-${c});--i:${i}">
            <div class="f-plate__image"><img src="${esc(frame)}" alt=""><span class="f-plate__scan"></span></div>
            <div class="f-plate__label"><span>0${i + 1} / ${esc(CHANNEL_META[c].short)}</span><span>${esc(sentence(rawReading(segment, c, pick.report.comment_sentiment)) || 'Not measured')}</span></div>
            <span class="f-plate__corner"></span>
          </div>`).join('')}
        </div></div>
        <span class="f-coordinate f-coordinate--a">Signal / ${esc(mmss(segment.start_s))}</span>
        <span class="f-coordinate f-coordinate--b">Four independent readings</span>
      </div>
      <div class="f-story">
        <article class="f-beat is-current" data-beat="0">
          <p class="f-eyebrow">01 / Look beneath the surface</p>
          <h2 id="film-heading">A second.<br><em>Four sides.</em></h2>
          <p class="f-body">A video gives you one impression.<br>Turn it over. There’s more underneath.</p>
          <p class="f-invitation">${arrow("down")} Scroll to pull the moment apart</p>
        </article>
        <article class="f-beat" data-beat="1">
          <p class="f-eyebrow">02 / Separate the signals</p>
          <h2>The words.<br>The <em>undertow.</em></h2>
          <p class="f-body">What was said. The face. The voice.<br>Three readings of the same moment.<br>And one account from the audience.</p>
          <p class="f-aside">The audience is read across the whole video.<br>Comments cannot be pinned to a second.</p>
        </article>
        <article class="f-beat" data-beat="2">
          <p class="f-eyebrow">03 / ${pick.flagged ? 'The point of disagreement' : 'Inside the measurement'}</p>
          <h2>${pick.flagged ? 'The signal<br><em>splits here.</em>' : 'Every signal.<br><em>Accounted for.</em>'}</h2>
          <div class="f-measure"><span>${esc(mmss(segment.start_s))}</span><div>Conflict score<strong>${esc(confidence(segment.conflict_score))}</strong></div></div>
          <p class="f-body">${pick.flagged ? 'This moment was flagged by the local model. Different channels told different stories.' : 'The local model compares the channels. This report has no flagged moments.'}</p>
        </article>
        <article class="f-beat" data-beat="3">
          <p class="f-eyebrow">04 / Evidence, with its edges intact</p>
          <h2>Nothing hidden.<br><em>Nothing sent.</em></h2>
          <p class="f-body">Every reading stays on this machine.<br>Every weakness stays in the report.</p>
          <p class="f-aside">Facial accuracy: ${esc(pct(CHANNEL_META.facial.accuracy))} on held-out speakers.<br>Always-neutral baseline: ${esc(pct(FACIAL_REFERENCES.constant.value))}. We publish both.</p>
          <a class="f-link" href="${esc(pick.href)}">Open this analysis ${arrow("next")}</a>
        </article>
      </div>
      <div class="f-evidence" role="group" aria-label="Readings for the selected moment">
        ${CHANNELS.map((c, i) => `<div style="--channel:var(--ch-${c})"><span class="f-evidence__name"><i></i>${esc(CHANNEL_META[c].short)}<small>${c === 'audience' ? 'Video-level' : mmss(segment.start_s)}</small></span><strong>${esc(sentence(rawReading(segment, c, pick.report.comment_sentiment)) || 'Not measured')}</strong></div>`).join('')}
      </div>
      <div class="f-bottom"><span class="f-step">01 / 04</span><div class="f-track"><i></i></div><span>Scroll to explore ${arrow("down")}</span><a href="#proof">Skip sequence ${arrow("down")}</a></div>
    </div>
  </section>`;
}

/* Takes no argument: everything measured is already printed into the markup by
   filmMarkup(), and the wiring only has to move what is there. */
export function wireFilm() {
  const section = document.getElementById('film');
  if (!section) return;
  const canvas = section.querySelector('.f-orbits');
  const ctx = canvas.getContext('2d');
  const plates = [...section.querySelectorAll('.f-plate')];
  const beats = [...section.querySelectorAll('.f-beat')];
  const object = section.querySelector('.f-object');
  const space = section.querySelector('.f-space');
  const evidence = section.querySelector('.f-evidence');
  const progress = section.querySelector('.f-track i');
  const step = section.querySelector('.f-step');
  const state = { p: 0 };
  let width = 1, height = 1, colors = [], ink = '', lastBeat = -1;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const smooth = (a, b, p) => { const t = clamp((p - a) / (b - a)); return t * t * (3 - 2 * t); };
  // How far apart the four channel plates are drawn, 0 closed to 1 open.
  //
  // Under reduced motion this is FROZEN OPEN rather than driven by scroll.
  // `soft` already held the lens still, but separation was still scrubbing, so
  // the plates slid apart, the rings breathed and the readings faded in and out
  // under a setting whose whole point is that they should not. Frozen at 1 the
  // instrument is a still diagram with all four channels visible at once, which
  // is the complete content -- not a reduced version of it.
  const separation = (p, soft) =>
    soft ? 1 : smooth(.16, .43, p) * (1 - smooth(.77, .96, p));
  // Perspective projection of a shared three-dimensional scene. The orbit
  // and lens move with scroll; there is no autonomous animation loop.
  function draw(p, soft) {
    if (!ctx) return;
    ctx.clearRect(0, 0, width, height);
    const split = separation(p, soft);
    const turn = soft ? -.28 : -.28 + p * 2.5;
    const tilt = soft ? .65 : .65 + Math.sin(p * Math.PI) * .38;
    const radius = Math.min(width * .39, height * .40);
    const project = (x, y, z) => {
      const xx = x * Math.cos(turn) + z * Math.sin(turn);
      const zz = -x * Math.sin(turn) + z * Math.cos(turn);
      const yy = y * Math.cos(tilt) - zz * Math.sin(tilt);
      const depth = y * Math.sin(tilt) + zz * Math.cos(tilt);
      const scale = 1000 / (1000 + depth);
      return [width * .5 + xx * scale, height * .5 + yy * scale, depth, scale];
    };
    // Four fine, densely ruled annuli form the body of the instrument.
    for (let band = 0; band < 4; band++) {
      const r = radius * (.72 + band * .105);
      const offset = (band - 1.5) * (14 + split * 52);
      for (let rail = 0; rail < 6; rail++) {
        ctx.beginPath();
        for (let j = 0; j <= 180; j++) {
          const a = j / 180 * Math.PI * 2;
          const rr = r + rail * 1.8;
          const v = project(Math.cos(a) * rr, offset + Math.sin(a * 3 + band) * split * 13, Math.sin(a) * rr);
          if (!j) ctx.moveTo(v[0], v[1]); else ctx.lineTo(v[0], v[1]);
        }
        ctx.strokeStyle = colors[band];
        ctx.globalAlpha = rail === 0 ? .7 : .12;
        ctx.lineWidth = rail === 0 ? 1 : .65;
        ctx.stroke();
      }
      for (let j = 0; j < 140; j++) {
        const a = j / 140 * Math.PI * 2;
        const length = j % 5 === 0 ? 18 : 6;
        const v = project(Math.cos(a) * (r + 12), offset, Math.sin(a) * (r + 12));
        const u = project(Math.cos(a) * (r + 12 + length), offset, Math.sin(a) * (r + 12 + length));
        ctx.beginPath(); ctx.moveTo(...v.slice(0, 2)); ctx.lineTo(...u.slice(0, 2));
        ctx.strokeStyle = colors[band]; ctx.globalAlpha = .22 + (v[2] < 0 ? .32 : 0); ctx.stroke();
        if (j % 35 === 0) {
          ctx.fillStyle = colors[band]; ctx.globalAlpha = .9;
          ctx.beginPath(); ctx.arc(v[0], v[1], 2.3 * v[3], 0, Math.PI * 2); ctx.fill();
        }
      }
    }
    // A sparse spherical calibration field gives parallax beyond the rings.
    for (let i = 0; i < 240; i++) {
      const y = 1 - i / 239 * 2;
      const r = Math.sqrt(1 - y * y);
      const a = i * 2.399963;
      const v = project(Math.cos(a) * r * radius * 1.3, y * radius * 1.3, Math.sin(a) * r * radius * 1.3);
      ctx.globalAlpha = v[2] < 0 ? .35 : .12; ctx.fillStyle = ink;
      ctx.fillRect(v[0], v[1], 1.2 * v[3], 1.2 * v[3]);
    }
    ctx.globalAlpha = 1;
  }
  let soft = false;
  // The beats' words did not fit the chamber (see watchWords below).
  let wordsOverflow = false;
  // Stacked: the window is too short to hold the chamber, so it is not pinned
  // and every beat is laid out in order (film.css .film--stacked).
  let stacked = false;
  // Scroll position at which each beat is the current one, for focusin below.
  const BEAT_AT = [.1, .36, .63, .88];
  let trigger = null;
  function render() {
    const p = state.p;
    const split = separation(p, soft);
    const close = soft ? 0 : smooth(.78, 1, p);
    const narrow = section.clientWidth < 760;
    const active = stacked ? -1 : p < .23 ? 0 : p < .49 ? 1 : p < .77 ? 2 : 3;
    if (active !== lastBeat) {
      /* Every beat stays in the accessibility tree. Until 25 Sep 2026 the
         three that were not on screen carried aria-hidden and inert, so a
         screen reader reading in order met the first beat only -- and the
         fourth holds the facial-accuracy disclosure and the one link out of
         the section (INCLUSIVE_DESIGN.md A5). They are now faded rather than
         removed, and a keyboard that lands in one scrolls the film to it. */
      beats.forEach((beat, i) => beat.classList.toggle('is-current', stacked || i === active));
      step.textContent = stacked ? '04 / 04' : `0${active + 1} / 04`;
      lastBeat = active;
    }
    progress.style.transform = `scaleX(${stacked ? 1 : p})`;
    // The readings are the section's evidence. Under reduced motion, and when
    // stacked, they are simply present rather than scrubbed in and out of view.
    // Faded by opacity only, never hidden, so they are always readable aloud.
    evidence.style.opacity = soft || stacked ? '1'
      : String(smooth(.27, .40, p) * (1 - smooth(.76, .85, p)));
    space.style.setProperty('--separation', split);
    space.style.transform = soft ? 'none' : `scale(${1 + smooth(.45, .72, p) * .12 - close * .12})`;
    object.style.transform = soft ? 'none' : `rotateX(${-8 + split * 9}deg) rotateY(${-22 + p * 75}deg) rotateZ(${-8 + split * 12 - close * 4}deg)`;
    plates.forEach((plate, i) => {
      const depth = (i - 1.5) * (soft ? 0 : (3 + split * 105));
      const x = (i - 1.5) * split * (narrow ? 23 : 42);
      const y = (i - 1.5) * split * (narrow ? 18 : 32);
      plate.style.transform = `translate3d(${x}px,${y}px,${depth}px)`;
      plate.style.opacity = '1';
    });
    draw(p, soft);
  }
  function resize() {
    const box = canvas.getBoundingClientRect();
    width = box.width; height = box.height;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const css = getComputedStyle(section);
    colors = CHANNELS.map(c => css.getPropertyValue(`--ch-${c}`).trim());
    ink = css.getPropertyValue('--ink').trim();
    render();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(space);
  const themeObserver = new MutationObserver(resize);
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  /* A keyboard that lands inside a beat that is not on screen -- the fourth
     beat's link, reached by Tab -- takes the film to that beat, so the focused
     thing is always the visible thing. */
  section.addEventListener('focusin', (event) => {
    const beat = event.target.closest && event.target.closest('.f-beat');
    if (!beat || stacked || !trigger) return;
    const i = beats.indexOf(beat);
    if (i < 0 || i === lastBeat) return;
    const top = trigger.start + BEAT_AT[i] * (trigger.end - trigger.start);
    window.scrollTo({ top, behavior: 'instant' });
    state.p = BEAT_AT[i];
    render();
  });
  /* PINNED ONLY WHERE THE CHAMBER FITS.

     The chamber is a 640px box (720px below 760 wide), pinned for 4.8 screen
     heights of scroll. On a window shorter than the box -- a phone held
     sideways, a laptop at 200% zoom, Safari's small viewport on an iPhone SE --
     the readings, the progress and "Skip sequence" sat below the fold for the
     whole pin, and at 320x568 two of the four readings were never reachable
     (measured 22 Sep; INCLUSIVE_DESIGN.md R2). There the film is laid out
     as a still: the instrument frozen open, then the four beats and the four
     readings in reading order. proof.js and seam.js already gate their pins
     the same way. */
  const mm = motionMedia({
    motion: '(prefers-reduced-motion: no-preference)',
    reduce: '(prefers-reduced-motion: reduce)',
    fits: '(min-width: 760px) and (min-height: 640px), (max-width: 759.98px) and (min-height: 720px)',
  }, context => {
    stacked = !context.conditions.fits || wordsOverflow;
    soft = !!context.conditions.reduce || stacked;
    section.classList.toggle('film--stacked', stacked);
    lastBeat = -2;
    if (stacked) {
      trigger = null;
      state.p = 1;
      resize();
      return () => { section.classList.remove('film--stacked'); };
    }
    const tween = gsap.fromTo(state, { p: 0 }, { p: 1, ease: 'none', onUpdate: render,
      scrollTrigger: { trigger: section, start: 'top top', end: () => `+=${window.innerHeight * (soft ? 3 : 4.8)}`, pin: true, scrub: soft ? true : .65, anticipatePin: 1, invalidateOnRefresh: true },
    });
    trigger = tween.scrollTrigger;
    resize();
    return () => { trigger = null; tween.scrollTrigger?.kill(); tween.kill(); };
  });
  /* STACKED, TOO, WHEN THE WORDS DO NOT FIT.

     The chamber's size is set by the window, and its four beats share one box
     inside it. A reader who sets their own text spacing (WCAG 1.4.12), or a
     larger text size, can make a beat taller than the chamber, and the chamber
     clips: measured 25 Sep 2026 under the 1.4.12 override, three beats ran 30 to
     140 px past it at 1280x800 and 1440x900 (verify_ui.py check 14). Whatever the
     cause, words that do not fit are the one thing this section cannot trade for
     its staging, so once they stop fitting the film is laid out as the stacked
     still, where nothing is clipped, for the rest of the visit. */
  const chamber = section.querySelector('.f-chamber');
  const overflowing = () => {
    const floor = chamber.getBoundingClientRect().bottom;
    return beats.some((beat) => [...beat.querySelectorAll('*')]
      .some((el) => el.getBoundingClientRect().bottom > floor + 1));
  };
  let pending = 0;
  const watchWords = new ResizeObserver(() => {
    if (stacked || wordsOverflow || pending) return;
    pending = requestAnimationFrame(() => {
      pending = 0;
      if (!stacked && !wordsOverflow && overflowing()) { wordsOverflow = true; mm.rebuild(); }
    });
  });
  for (const beat of beats) for (const el of beat.children) watchWords.observe(el);
  wireFilmField(section);
  window.addEventListener('pagehide', () => { mm.revert(); observer.disconnect(); themeObserver.disconnect(); watchWords.disconnect(); }, { once: true });
}

/* ---------------------------------------------------------------------------
   THE GROUND.

   The chamber had no background of its own: .f-atmosphere is two token tints
   and a grain plate, and below them was flat --screen. This puts the Data
   Pixel Arc behind it -- vendored in datapixelarc.js, which holds the
   provenance and the deviations, and until now mounted nowhere.

   WHY THIS COMPONENT HERE. The chamber's whole subject is a video frame
   quantised into bands: .f-plate__scan already rules the plates with
   repeating 3px/4px scanlines, and the object is a raster taken apart. The
   Data Pixel Arc is the only one of the four that draws in hard-edged blocks
   rather than a continuous field, so it is the only one whose MATERIAL is the
   same as the section's. The other three would have been a gradient behind a
   raster.

   WHY IT IS SAFE HERE, MEASURED. #film is the one section that shows all four
   channel swatches at once -- .f-topline i, the four .f-plate__label rules,
   the four .f-evidence markers -- so its ground has to be the one least able
   to be mistaken for a channel. Sampled over every lit pixel at 1440x900 in
   dark mode, this component's median hue is 140.7 (n = 425,411), and its
   nearest meaning-bearing hue is --ch-transcript at 170.2, a separation of
   29.5 degrees. That is the tightest pairing of the two grounds added today
   and it is stated rather than hidden; it is also 3.8x the 7.8 degrees that
   portalfield.js rejected, and unlike the violet variant this one composites
   source-over rather than "lighter", so it settles instead of stacking.

   THE THREE PROPS THAT ARE NOT REGISTERED DEFAULTS, and why each moved:

   arcCenter 0.4 -> 0.82   The registered arc crowns at 40% of the height,
                           which here is exactly where .f-beat h2 sits. Pushed
                           down it becomes a horizon under the composition
                           rather than a wash behind the headline. Its legs
                           then fall off the bottom of the frame, which is the
                           intended reading: a curve too big to fit.
   pixelSize 8 -> 10       Matched to the section's own raster rather than
                           chosen: .f-plate__scan rules every 3px + 1px, and
                           at 10 the ground's blocks read as the same family
                           of quantisation two steps coarser.
   speed 1 -> 0.55         A ground that moves at the speed of a foreground is
                           a foreground.

   brightness and opacity are not taste either; see ui_evidence for the
   contrast measurement that set them.
   --------------------------------------------------------------------------- */
/* Set by measurement, not by eye.

   BENCH: ui_evidence/measure_grounds.py, which reads the ground at the pixels
   the glyphs actually cover and reports the worst contrast on each. At these
   two values the chamber's six text targets move by at most 0.01 against the
   same page with the ground hidden.

   FIELD: a different constraint decides these, and it is arithmetic rather
   than a screenshot. The light path's alpha floor is 0.22 and its colour at
   the renderer's own 0.02 cutoff is already 46 units off its paper, so the
   field begins with a STEP rather than a fade -- invisible on the opaque
   paper the component paints for itself, a hard parabolic wedge over
   --screen once datapixelarc.js's deviation 3 clears instead of filling.
   Solving that step, composited through the multiply in film.css:

       brightness   opacity   step at cutoff   delta at core
          0.85        0.40        6.73 units      82.0 units
          0.45        0.30        3.31             34.9
          0.45        0.22        2.43             25.6
          0.45        0.18        1.99             20.9
          0.45        0.15        1.66             17.4

   0.45 is the light path's own clamp floor -- Math.max(0.45, ...) -- so it is
   as close to paper as the component will go, and 0.18 is the first opacity
   that puts the step under two units while the core is still 20.9, which is
   a fifth of the range and reads plainly. */
const FIELD_BRIGHTNESS = { dark: 0.50, light: 0.45 };
const FIELD_OPACITY = { dark: 0.55, light: 0.18 };

function wireFilmField(section) {
  const host = section.querySelector('[data-film-field]');
  if (!host) return;

  let teardown = null;
  const mount = () => {
    if (teardown) { teardown(); teardown = null; }
    const mode = document.documentElement.dataset.theme === 'field' ? 'light' : 'dark';
    teardown = mountDataPixelArc(host, {
      mode,
      still: reduced(),
      arcCenter: 0.82,
      arcDrop: 0.9,
      thickness: 0.4,
      pixelSize: 10,
      speed: 0.55,
      brightness: FIELD_BRIGHTNESS[mode],
      opacity: FIELD_OPACITY[mode],
      hue: 0,
      /* Its own grade is a saturated green (median hue 140.7, measured in the
         note above). Most of the way to neutral it is the same raster, lit by
         the building's silver key instead of a wash of its own; the four
         channel colours on the plates stay the only strong hues here. */
      saturation: 0.3,
    });
  };

  mount();
  window.addEventListener('themechange', mount);
  onReducedChange(mount);
}
