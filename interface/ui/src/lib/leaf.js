/* ===========================================================================
   leaf.js — a cover that opens the way paper opens.

   PROVENANCE. The turning surface in this file is ported from the registered
   ThreeUI `Sketchbook` component, revision 3938bc8def563f89ed587e52ac35ddc
   056c0a5f0. The bundle was fetched from threeui.com/source-code/sketchbook
   .json and all three registered files verified byte-for-byte against the
   SHA-256 digests in the integration brief:

     src/shaders/sketchbook/Sketchbook.tsx          17847ea5…c404af  MATCH
     src/shaders/sketchbook/sketchbookDocument.js   256ab28e…35df61  MATCH
     src/shaders/threeui.css                        efe44471…c8eccf  MATCH

   The component ships its interface as one canonical HTML document inside
   that renderer-source; it carries its own digest, and that verified too:

     canonical document                             2a97f4cc…a596d7  MATCH

   WHAT WAS TAKEN, AND WHAT WAS NOT.

   Taken: the turning surface itself. A leaf that pivots like a door is the
   giveaway of every CSS book on the internet. The registered component builds
   the leaf as a chain of N nested strips whose tangent sweeps through an arc,
   so the surface BENDS. Every constant below is the registered one --
   N = 18 strips, BETA = 0.60 radians of peak curl, the (1 - lit) * 0.62
   shading coefficient -- and applyTurn is the registered function.

   Not taken: the nine Singapore plates, the magnifying loupe, the riffle
   intro, the multi-page index, and the cream `--paper: #ece7dc` ground. Those
   are that component's content and its house style, not its mechanism. This
   project's own palette is in tokens.css and is not being replaced by
   somebody else's.

   ADAPTED, AND WHY. The registered leaf turns between two PNG spreads, so
   both of its faces are image slices and the gutter sits at 50% of the book.
   Here the thing that turns is a book's COVER: it is hinged at the spine
   rather than at a centre gutter, so `span` is the whole width and the front
   face carries the cover plate the shelf already painted for that volume --
   the same canvas, read straight off the WebGL texture. Nothing is redrawn
   and nothing is approximated. The back face is endpaper, because the inside
   of a cover is not a photograph.
   ======================================================================== */

import { reduced } from "./motion.js";

/* The inherited strip mechanism, tuned for a clothbound board: less curl
   than a paper leaf, and overlapping travel/swing rather than two stops. */
export const LEAF = Object.freeze({
  n: 18,            /* strips -- enough for a smooth curve                  */
  beta: 0.22,       /* peak curl of the arc, radians                        */
  shade: 0.62,      /* the registered shading coefficient on an unlit face  */
  travelMs: 560,    /* the volume's flight from where it was to the desk    */
  turnMs: 900,      /* the cover's own swing                                */
  revealAt: 0.22,   /* how far through the swing the page starts to show    */
  closeMs: 680,     /* the board swinging shut on the way out: quicker than
                       the opening, because nobody waits to watch a door close */
});

const el = (tag, cls) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
};

/* ---------------------------------------------------------- the chain ----
   Built once per open. The background offsets are pure geometry, so once a
   strip is dressed it never needs touching again while the cover swings.

   `--bw` is the leaf's own width in pixels and is the unit every strip is
   measured in, exactly as in the registered source. */
function buildChain(coverUrl, n) {
  const root = el("div", "lf__curl");
  root.style.setProperty("--n", n);
  root.style.setProperty("--span", 1);

  const strips = [];
  let host = root;
  for (let i = 0; i < n; i++) {
    const s = el("div", "lf__strip");
    s.style.setProperty("--i", i);

    /* The slice of the plate this strip is showing. The registered source
       offsets from a centre gutter; a cover is hinged at its own edge, so the
       gutter term is zero and the offset is just the strips already passed. */
    const sw = `calc(var(--bw) * ${(1 / n).toFixed(6)})`;
    const front = el("div", "lf__face lf__face--front");
    front.style.backgroundImage = `url(${coverUrl})`;
    front.style.backgroundPositionX = `calc(-1 * ${i} * ${sw})`;

    const back = el("div", "lf__face lf__face--back");

    for (const f of [front, back]) {
      f.appendChild(el("div", "lf__sh"));
      f.appendChild(el("div", "lf__gl"));
    }
    s.append(front, back);
    if (i === n - 1) s.classList.add("is-edge");

    host.appendChild(s);
    host = s;
    strips.push(s);
  }
  return { root, strips };
}

/* ----------------------------------------------------------- the maths ---
   The registered applyTurn, unchanged.

   `t` runs 0 → 1 across the whole swing. `th` is how far the leaf has gone;
   `beta` is the curl, scaled by sin(pi t) so the surface is FLAT at both ends
   and at its most bent halfway through -- which is what a real page does.
   `tt` is the root's rotation and `td` the delta each strip adds, so the
   chain's tangent sweeps the arc rather than every strip sharing an angle.

   The per-strip lighting reads the cosine of each strip's own facing at both
   of its edges, so one strip can be darker on one side than the other and the
   shading runs continuously along the curve instead of banding. */
export function applyTurn(scope, strips, t, n = LEAF.n, betaMax = LEAF.beta) {
  const th = Math.PI * t;
  const beta = betaMax * Math.sin(Math.PI * t);
  const D = 180 / Math.PI;
  const tt = th + beta;
  const td = (2 * beta) / n;

  scope.style.setProperty("--tt", `${(tt * D).toFixed(2)}deg`);
  scope.style.setProperty("--td", `${(td * D).toFixed(3)}deg`);
  scope.style.setProperty("--shade", Math.sin(Math.PI * t).toFixed(3));

  for (let i = 0; i < strips.length; i++) {
    const l1 = Math.abs(Math.cos(tt - i * td));
    const l2 = Math.abs(Math.cos(tt - (i + 1) * td));
    const st = strips[i].style;
    st.setProperty("--lit", l1.toFixed(3));
    st.setProperty("--a1", ((1 - l1) * LEAF.shade).toFixed(3));
    st.setProperty("--a2", ((1 - l2) * LEAF.shade).toFixed(3));
  }
}

/* --------------------------------------------------------- the sequence --
   Mounts a closed volume over the document at `from`, flies it to `to`, then
   swings its cover open and hands the page back.

   Every step is guarded. No stash, no cover, no measurable box, or reduced
   motion, and this returns false without drawing anything -- the caller then
   simply shows its page, which is the normal path and not a degraded one. */
export function openVolume(host, opts) {
  const { cover, from, to, page, onReveal, onDone, perspective, origin } = opts || {};
  if (!host || !cover || !from || !to || reduced()) return false;
  if (!(to.w > 0) || !(to.h > 0) || !(from.w > 0) || !(from.h > 0)) return false;

  const stageEl = el("div", "lf");
  stageEl.setAttribute("aria-hidden", "true");
  aim(stageEl, perspective, origin);
  const box = el("div", "lf__box");
  const casts = ["ambient", "contact", "hair"]
    .map((k) => el("div", `lf__cast lf__cast--${k}`));

  /* Starts as the closed volume, at the size and place it was on the shelf. */
  box.style.cssText =
    `left:${from.x}px;top:${from.y}px;width:${from.w}px;height:${from.h}px`;

  const { root: curl, strips } = buildChain(cover, LEAF.n);
  const under = el("div", "lf__under");          /* the leaf being uncovered */
  box.append(...casts, under, curl);
  stageEl.appendChild(box);
  host.appendChild(stageEl);

  const done = () => {
    stageEl.remove();
    if (onDone) onDone();
  };

  /* WHAT IS UNDER THE COVER IS THE DOCUMENT, NOT A SHEET OF PAPER.

     The backing exists only so the closed volume is not a window onto the
     page behind it. The moment the cover has lifted far enough to see past,
     the backing goes and the real report is what is underneath -- it opens
     out from the book's own footprint, which is the caller's job because the
     caller owns the document.

     The first build expanded this backing instead, which put a blank sheet on
     top of a finished report for half a second. The page has to BE the page. */
  let revealed = false;
  const reveal = () => {
    if (revealed) return;
    revealed = true;
    under.classList.add("is-gone");
    for (const c of casts) c.classList.add("is-gone");
    if (onReveal) onReveal(page || null);
  };

  /* One compositor-driven movement: the board begins opening as its flight
     settles. Dimensions stay fixed, avoiding layout on every flight frame. */
  box.style.cssText = `left:${to.x}px;top:${to.y}px;width:${to.w}px;height:${to.h}px`;
  box.style.setProperty("--bw", `${to.w}px`);
  box.style.transformOrigin = "0 0";
  const dx = from.x - to.x, dy = from.y - to.y;
  const sx = from.w / to.w, sy = from.h / to.h;
  const swingAt = LEAF.travelMs * 0.78;
  let raf = 0, ended = false;
  const cleanDone = () => {
    if (ended) return;
    ended = true;
    cancelAnimationFrame(raf);
    clearTimeout(guard);
    window.removeEventListener("resize", cleanDone);
    reveal(); done();
  };
  const guard = setTimeout(cleanDone, LEAF.travelMs + LEAF.turnMs + 650);
  window.addEventListener("resize", cleanDone, { once: true });
  const poseFlight = (e) => {
    box.style.transform = `translate3d(${dx * (1-e)}px,${dy * (1-e)}px,0) scale(${sx+(1-sx)*e},${sy+(1-sy)*e})`;
  };
  poseFlight(0);
  applyTurn(box, strips, 0);
  raf = requestAnimationFrame((start) => {
    const frame = (now) => {
      if (ended) return;
      if (reduced()) { cleanDone(); return; }
      const elapsed = now - start;
      const travel = Math.min(1, elapsed / LEAF.travelMs);
      poseFlight(1 - Math.pow(1 - travel, 3));
      const t = Math.max(0, Math.min(1, (elapsed - swingAt) / LEAF.turnMs));
      const e = t * t * t * (t * (6 * t - 15) + 10);
      applyTurn(box, strips, e);
      if (e >= LEAF.revealAt) reveal();
      if (t < 1) raf = requestAnimationFrame(frame);
      else {
        box.classList.add("is-open");
        setTimeout(cleanDone, 180);
      }
    };
    raf = requestAnimationFrame(frame);
  });

  return true;
}

/* THE PERSPECTIVE IS THE CALLER'S TO SOLVE.

   A board hinged at the spine brings its free edge toward the viewer as it
   swings, and at a fixed 1750px it grew by over a hundred pixels at each end
   -- through the masthead on a laptop screen. The caller knows how much room
   there is above the desk and passes the perspective that fits it, with the
   origin on the spine so the growth is symmetric about the board. Omitted,
   the registered values stand. */
function aim(stageEl, perspective, origin) {
  if (Number.isFinite(perspective) && perspective > 0) {
    stageEl.style.perspective = `${perspective.toFixed(0)}px`;
  }
  if (origin && Number.isFinite(origin.x) && Number.isFinite(origin.y)) {
    stageEl.style.perspectiveOrigin = `${origin.x.toFixed(1)}px ${origin.y.toFixed(1)}px`;
  }
}

/* --------------------------------------------------------- the close -----
   The opening, played backwards: the board comes up off the verso where the
   opening left it, swings back over the pages, and the closed volume leaves
   the desk. Same chain, same registered maths, run from t = 1 to t = 0.

   Returns false without drawing anything when it cannot run, so the caller
   can simply navigate. */
export function closeVolume(host, opts) {
  const { cover, to, onDone, onCover, perspective, origin } = opts || {};
  if (!host || !cover || !to || reduced()) return false;
  if (!(to.w > 0) || !(to.h > 0)) return false;

  const stageEl = el("div", "lf");
  stageEl.setAttribute("aria-hidden", "true");
  aim(stageEl, perspective, origin);
  const box = el("div", "lf__box is-closing");
  box.style.cssText = `left:${to.x}px;top:${to.y}px;width:${to.w}px;height:${to.h}px`;
  box.style.setProperty("--bw", `${to.w}px`);
  const { root: curl, strips } = buildChain(cover, LEAF.n);
  const under = el("div", "lf__under");
  under.classList.add("is-gone");
  box.append(under, curl);
  stageEl.appendChild(box);
  host.appendChild(stageEl);
  applyTurn(box, strips, 1, LEAF.n);

  let finished = false;
  let covered = false;
  const coverPage = () => { if (!covered) { covered = true; if (onCover) onCover(); } };
  const done = () => {
    if (finished) return;
    finished = true;
    coverPage();
    if (onDone) onDone();
  };

  requestAnimationFrame(() => {
    box.classList.add("is-shown");
    setTimeout(() => {
      const t0 = performance.now();
      const frame = (now) => {
        const t = Math.min(1, (now - t0) / LEAF.closeMs);
        const e = t * t * t * (t * (6 * t - 15) + 10);
        applyTurn(box, strips, 1 - e, LEAF.n);
        if (e > 0.48) coverPage();
        if (reduced()) { stageEl.remove(); done(); return; }
        if (t < 1) requestAnimationFrame(frame);
        else {
          box.classList.add("is-leaving");
          setTimeout(done, 260);
        }
      };
      requestAnimationFrame(frame);
    }, 70);
  });
  return true;
}

/* ------------------------------------------------------- the handoff -----
   The volume's identity, its cover plate and where it was standing, carried
   across a real page navigation.

   Same discipline as stashFlip/playFlip in motion.js, which carries the frame
   photograph between the same two documents: sessionStorage, one use only,
   and a short life so that a back-button return or a tab left open overnight
   never animates a volume in from somewhere it has not been for an hour. */
const KEY = "brandpulse-volume";
const TTL = 6000;

export function stashVolume(payload) {
  if (!payload || !payload.cover || reduced()) return;
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ ...payload, at: Date.now() }));
  } catch { /* storage unavailable or full; the navigation is still fine */ }
}

export function takeVolume() {
  let raw = null;
  try {
    raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
  } catch { return null; }
  if (!raw) return null;
  let v = null;
  try { v = JSON.parse(raw); } catch { return null; }
  if (!v || !v.cover || !v.rect) return null;
  if (Date.now() - (v.at || 0) > TTL) return null;
  return v;
}


/* ------------------------------------------------------- closing back ----
   WHICH VOLUME TO PUT BACK IN THE READER'S HAND.

   Closing a book should return you to the shelf with that book still out, not
   to a shelf with nothing selected — the volume did not go anywhere while you
   were reading it.

   Two ways out of a report and they are not equally certain:

     "close"  the reader used the close control. They meant to go back to the
              shelf, so the shelf honours it unconditionally.

     "leave"  the page is being unloaded for some other reason. That covers the
              browser's Back button, which is the case worth catching, but it
              also covers walking off to Analyse and arriving at the library
              ten minutes later by a different door. So it is honoured ONLY
              when the navigation that lands on the library is a back/forward
              one, which is exactly the case it was recorded for.

   Single use, like the volume stash above: a shelf should present a volume
   because you just put it down, never because you did an hour ago. */

const RETURN_KEY = "brandpulse-return";

export function stashReturn(id, via = "close") {
  if (!id) return;
  try {
    /* A "leave" must never overwrite a "close". Both fire on the way out of a
       report when the close control is used -- the click first, then pagehide
       as the document unloads -- so recording the weaker one second downgraded
       every deliberate close into an unload, and takeReturn() then refused it
       because a link click is not a back/forward navigation. The shelf opened
       with nothing in hand, which is the exact thing this was written for. */
    const held = sessionStorage.getItem(RETURN_KEY);
    if (held && via !== "close") {
      const prior = JSON.parse(held);
      if (prior && prior.id === id && prior.via === "close") return;
    }
    sessionStorage.setItem(RETURN_KEY, JSON.stringify({ id, via }));
  } catch { /* storage unavailable; the shelf simply opens unselected */ }
}

export function takeReturn() {
  let raw = null;
  try {
    raw = sessionStorage.getItem(RETURN_KEY);
    sessionStorage.removeItem(RETURN_KEY);
  } catch { return null; }
  if (!raw) return null;
  let v = null;
  try { v = JSON.parse(raw); } catch { return null; }
  if (!v || !v.id) return null;
  if (v.via === "close") return v.id;

  let how = "";
  try { how = (performance.getEntriesByType("navigation")[0] || {}).type || ""; }
  catch { how = ""; }
  return how === "back_forward" ? v.id : null;
}
