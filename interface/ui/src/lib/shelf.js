/* ===========================================================================
   shelf.js — vendored from ThreeUI, "Ashen Press", and re-aimed at this corpus.

   PROVENANCE. Do not rewrite this file from what it looks like on screen.

     source   https://threeui.com/source-code/ashen-press.json
     revision SHA-256 5fe2554e578a
     fetched  22 Sep 2026, HTTP 200, 1,203,858 bytes
     bundle   SHA-256 a230ca61f59868d336bcfb4c567aa9b3cba0fbaa178ca31ab307e16e20e4a68e

     src/shaders/ashen-press/sources/ashen-press.html
       SHA-256 5fe2554e578acac5d55cb466a9564440e7767e38797981f8e829dfd2de0bc90f
       1,156,000 bytes, 1,693 lines
     src/shaders/ashen-press/AshenPress.tsx
       SHA-256 36b365f7a69223f1c3347bfcb3f2d1aa1ab20d30f2c31e5efb248e62ab4ddc90

   All three registered files were hashed on fetch and every one matched both
   the bundle's own .sha256 field and the integration brief. The bundle carries
   no licence file and the registered files carry no copyright notice; that is
   recorded here rather than assumed either way.

   Every GLSL program below -- the wall, the oak, the boards, the spine, the
   page block, the reflection and the golden-angle blur composite -- is the
   registered source, and so are the tween classes, the board height field, the
   hover and active choreography, the drag-to-turn and the two-layer render.
   What changed is listed under DEVIATIONS, and the reasons are specific.

   THE ONE DEPENDENCY THIS PROJECT HAS TAKEN
   -----------------------------------------
   three@0.181.0, pinned exactly to the registered runtime, installed with
   --save-exact. Before this the interface had no 3D library at all: the
   opening page's instrument, its four grounds and the report's transport are
   hand-written canvas and raw WebGL. This is the first 3D runtime dependency used
   by the interface; its exact version and purpose are recorded here and in package.json.

   DEVIATIONS FROM THE REGISTERED SOURCE, AND WHY
   ----------------------------------------------
   1. NOT AN IFRAME. AshenPress.tsx renders the canonical HTML into a sandboxed
      <iframe srcDoc> with `sandbox="allow-scripts"`. That is right for a
      documentation page and wrong here twice over: the volumes have to be
      built from this machine's own reports, which an isolated document cannot
      read, and opening one has to navigate the parent, which a sandbox
      without allow-top-navigation cannot do. The module is ported into the
      page as an ES module instead, which is also how the three sibling
      ThreeUI ports in this project are mounted.

   2. THE CATALOGUE IS DATA, NOT A LITERAL. The registered BOOKS array is ten
      hand-written art books with `shelf` and `slot` fixed on each. Here the
      volumes ARE the saved runs, so the array arrives as an argument and the
      geometry is derived from its length -- see LAYOUT. Nothing about a
      volume is invented: every line printed on a cover or a spine is read
      from the report it belongs to.

   3. THE PLATES ARE THIS MACHINE'S FRAMES. The registered covers are built
      over twenty generated WebP illustrations inlined as data URIs, 93% of
      that file. They are replaced by the frame the pipeline itself extracted
      at the run's most-conflicted second, served from /static/frames/. The
      brief's own reading was a YouTube thumbnail; that would have put a
      request to a third party on a page whose frames manifest states, in
      writing, that "nothing is fetched from off this machine at page load".
      The extracted frame costs nothing, is already on disk, and is a stronger
      claim: it is a frame the system actually read.

   4. DARK, AND ON THE THEME. The registered room is kraft paper (#c6ae8e)
      with limewashed walls and pale oak, lit warm. This page is BENCH or
      FIELD, and the room is rebuilt on the section's own tokens so it belongs
      to the product rather than sitting in it. The wall bake, the oak, the
      cloth and the clear colour are all driven from `palette` -- the shader
      maths is untouched, only what is fed into it.

   5. NO MOBILE FLICK STACK. The registered file carries a second complete
      layout for narrow viewports: a vertical stack you flick through, with
      its own camera, its own bar and its own menu. It is not ported. Below
      the breakpoint this component does not mount at all and the page keeps
      the rack it already had, which is a better narrow-screen answer than a
      3D shelf and is already built, tested and accessible.

   6. GRACEFUL DEGRADATION. mountShelf returns null when there is no WebGL
      context, no host or no volume; a narrow or short window and a request
      for reduced motion are refused by the caller (library.js shelfPossible)
      before this module is even fetched. Either way the page shows the list.
      This is the project's standing rule and the registered component has no
      equivalent -- it assumes it will run.

   LAYOUT, which is the part that is genuinely new
   -----------------------------------------------
   Three cases side by side, one per way of starting a run: a video, a brand,
   a product. Each case is PER_SHELF volumes wide and as many shelves tall as
   the fullest case needs, so all three share one datum and the whole unit
   grows a shelf when a case outgrows the one it has. A case with room left
   shows it as empty shelf rather than as a shrunken case, because an empty
   shelf in a library reads as room to grow and a short case reads as a
   mistake. Volumes fill left to right, top shelf first.
   =========================================================================== */

import * as THREE from "three";
import { SHELF_LAYOUT, shelfRows } from "./shelfgeom.js";
import { token } from "./theme.js";

/* ---------------------------------------------------------------- geometry */

/* The dimensions live in shelfgeom.js so that library.js can read the case's
   proportion -- which decides how tall the stage is -- without pulling this
   module, and with it three.js, into the page's entry chunk. Re-exported here
   because this is the module everything else imports the shelf from. */
export { SHELF_LAYOUT };

/* THE BOARD IS NOT THEMED, AND THE ROOM IS.

   The first build of this ran both through SHELF_PALETTE, so under FIELD the
   covers were printed in dark ink on light scrims over a lightened plate --
   and the photograph washed out to almost nothing while the type sat on it at
   a contrast it could not hold. It was also wrong on its own terms: a
   clothbound volume does not reprint itself when someone turns the lights on.
   The boards are one printed object in both themes, and what changes is the
   room they are standing in.

   Every value below is a token this page already uses; nothing is a new
   colour. */
export const SHELF_BOARD = {
  cloth: "#141a1e",
  edge: "#48535a",                       /* the page block at the fore-edge */
  foil: "#E7ECEE",                       /* --ink, blocked on the board */
  scrimTop: "rgba(4,6,7,.80)",
  scrimBot: "rgba(4,6,7,.86)",
  tear: "#FF2E88",                       /* --tear, and only on a flagged run */
};

export const SHELF_PALETTE = {
  bench: {
    clear: 0x101315,
    wallPeak: 62, wallTint: [1.0, 1.02, 1.06],   // the cool cast of --body
    oak: "#3a3129", oakGrainDark: [30, 23, 17], oakGrainLite: [112, 95, 74],
    vFall: 0.26,
    /* THE BOUNCE HAS TO FIT IN THE ROOM IT IS LIT.

       Every shelf throws light back up the wall behind it. At the registered
       0.34 that is +21 on a peak of 62 here, which is exactly the lift a dark
       room wants -- and +77 on FIELD's peak of 226, which is 48 units past
       white. It never showed while the cases were stepped, because two thirds
       of the wall had no shelves in front of it; now every shelf runs the full
       width and the light room clipped to a flat white slab on every bay.
       Each room gets the bounce its own headroom can take. */
    bounce: 0.34, shadow: 0.46,
    /* THE ROOM ENDS IN THE PAGE. Past the carcass the wall's light falls off
       into the page's own ground (--body, read live by envOf()), so the room
       is a pool of light on the case rather than a lit grey rectangle cut
       into a graphite page. `envReach` is how far past the case, in carcass
       units, the wall takes to become the page; the frame shows about 0.44
       of wall around the case (SHELF_LAYOUT.padX), so the corners land most
       of the way there and the edge of the canvas stops being a seam. */
    envReach: 0.95, envMix: 0.92,
  },
  field: {
    clear: 0xe3e2de,
    wallPeak: 226, wallTint: [1.0, 0.995, 0.985],
    oak: "#a28d72", oakGrainDark: [120, 104, 86], oakGrainLite: [206, 190, 168],
    /* Half the dark room's vertical falloff. At the registered weight it read
       as depth against near-black and as a smudge down the left of a pale
       wall, which is the same gradient doing two different jobs. */
    vFall: 0.13,
    /* 226 + 0.11*226 = 251, just inside white, so the bounce is still a bounce
       and not a clipped plateau. The shadow is deepened to carry the depth the
       bounce is no longer doing: in a light room a board reads by the shade it
       casts, not by the glow above it. */
    bounce: 0.11, shadow: 0.30,
    /* Daylight falls evenly, so the stone wall does not darken into grey
       corners; it simply becomes the stone of the page. */
    envReach: 0.80, envMix: 1.0,
  },
};

/* The page's ground as the bake needs it, [r, g, b] 0-255, read from the
   same token the page is painted with so the room and the page cannot
   disagree about what colour the building is. Falls back to each palette's
   clear colour if the token cannot be read. */
function envOf(pal) {
  const raw = token("--body");
  const m = /^#([0-9a-f]{6})$/i.exec(raw);
  if (m) {
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  return [(pal.clear >> 16) & 255, (pal.clear >> 8) & 255, pal.clear & 255];
}

/* ---------------------------------------------- canvas helpers, registered */

const TAU = Math.PI * 2;
const SANS = 'Archivo,"Helvetica Neue",Helvetica,Arial,sans-serif';
const SERIF = 'Newsreader,Georgia,"Times New Roman",serif';
const MONO = 'ui-monospace,"SF Mono",Menlo,Monaco,Consolas,monospace';

const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

/* ANISOTROPY. Every volume stands at K.yaw off square and leans back at
   K.lean, so every cover is a texture seen at a glancing angle -- the exact
   case isotropic mip filtering blurs, because it picks one mip level for both
   axes and the steep axis wins. The registered source hard-codes 8. This asks
   the GPU what it can actually do (16 on every desktop part checked here) and
   is reset by mountShelf before a texture is built. It is the cheapest single
   improvement to cover legibility in this file: no extra memory, no extra
   draw calls, one sampler state. */
let MAXA = 8;
const lerp = (a, b, t) => a + (b - a) * t;

function mulberry(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function C(w, h) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h === undefined ? w : h;
  return c;
}
function lg(g, x0, y0, x1, y1, stops) {
  const t = g.createLinearGradient(x0, y0, x1, y1);
  for (const s of stops) t.addColorStop(s[0], s[1]);
  return t;
}
function rg(g, x, y, r0, r1, stops, x1, y1) {
  const t = g.createRadialGradient(x, y, r0, x1 === undefined ? x : x1, y1 === undefined ? y : y1, r1);
  for (const s of stops) t.addColorStop(s[0], s[1]);
  return t;
}
function tracked(g, text, x, y, track, align) {
  let w = 0;
  for (const ch of text) w += g.measureText(ch).width + track;
  w -= track;
  let cx = align === "center" ? x - w / 2 : align === "right" ? x - w : x;
  const prev = g.textAlign; g.textAlign = "left";
  for (const ch of text) { g.fillText(ch, cx, y); cx += g.measureText(ch).width + track; }
  g.textAlign = prev;
  return w;
}
function fitTracked(g, text, w, weight, family, track) {
  let lo = 4, hi = 3000;
  const meas = (px) => {
    g.font = `${weight} ${px}px ${family}`;
    let t = 0;
    for (const ch of text) t += g.measureText(ch).width + track * px;
    return t - track * px;
  };
  for (let i = 0; i < 26; i++) { const m = (lo + hi) / 2; if (meas(m) > w) hi = m; else lo = m; }
  g.font = `${weight} ${lo}px ${family}`;
  return lo;
}
function grain(g, W, H, amount, seed) {
  const r = mulberry(seed || 7);
  const img = g.getImageData(0, 0, W, H), d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const n = (r() - 0.5) * amount; d[i] += n; d[i + 1] += n; d[i + 2] += n;
  }
  g.putImageData(img, 0, 0);
}
function rule(g, x0, y0, x1, y1, col, w) {
  g.strokeStyle = col; g.lineWidth = w;
  g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke();
}

/* ------------------------------------------------------- the printed board

   The registered paintCover, with its plate, its two house scrims, its
   hairline foil frame and its title block kept exactly; what is printed into
   that block is this run's own record. Nothing here is decorative text: the
   brand and product are the report's filename, the date is its mtime, and the
   two figures are `authenticity_score` and `brand_health_score` read from the
   report itself. `flagged` drives the one coloured rule, which is the same
   signal `.is-tear` carries on the rack this replaces.                        */

function paintCover(v, W, H) {
  const pal = SHELF_BOARD;
  const c = C(W, H), g = c.getContext("2d");
  const img = v.plateImage;
  if (img) {
    const k = Math.max(W / img.naturalWidth, H / img.naturalHeight);
    const dw = img.naturalWidth * k, dh = img.naturalHeight * k;
    g.drawImage(img, (W - dw) / 2, (H - dh) / 2, dw, dh);
  } else {
    g.fillStyle = pal.cloth; g.fillRect(0, 0, W, H);
    g.fillStyle = rg(g, W * 0.5, H * 0.62, W * 0.02, W * 0.9,
      [[0, pal.edge], [1, "rgba(0,0,0,0)"]]);
    g.fillRect(0, 0, W, H);
  }
  /* house scrims — the type reads on every plate without hiding the picture */
  g.fillStyle = lg(g, 0, 0, 0, H * 0.46,
    [[0, pal.scrimTop], [0.42, pal.scrimTop.replace(/[\d.]+\)$/, "0.34)")], [1, pal.scrimTop.replace(/[\d.]+\)$/, "0)")]]);
  g.fillRect(0, 0, W, H * 0.46);
  g.fillStyle = lg(g, 0, H * 0.62, 0, H,
    [[0, pal.scrimBot.replace(/[\d.]+\)$/, "0)")], [0.5, pal.scrimBot.replace(/[\d.]+\)$/, "0.42)")], [1, pal.scrimBot]]);
  g.fillRect(0, H * 0.62, W, H * 0.38);

  g.strokeStyle = pal.foil + "58"; g.lineWidth = W * 0.0032;
  g.strokeRect(W * 0.052, H * 0.038, W * 0.896, H * 0.924);

  g.textAlign = "center"; g.textBaseline = "alphabetic";
  const fam = SERIF;
  let y;
  if (v.sub) {
    const s1 = fitTracked(g, v.title, W * 0.80, "500", fam, 0.055);
    g.fillStyle = pal.foil; tracked(g, v.title, W * 0.5, H * 0.150, s1 * 0.055, "center");
    /* The product line is capped as well as fitted. Left to fitTracked alone a
       two-word product set larger than the brand above it, which inverts the
       hierarchy on exactly the volumes -- six runs of one video -- where the
       brand is the word doing the least work and the product the most. */
    const s2 = Math.min(fitTracked(g, v.sub, W * 0.84, "400", fam, 0.045), s1 * 0.74);
    g.font = `400 ${s2}px ${fam}`;
    g.fillStyle = pal.foil; tracked(g, v.sub, W * 0.5, H * 0.150 + s2 * 1.10, s2 * 0.045, "center");
    y = H * 0.150 + s2 * 1.10;
  } else {
    const s1 = fitTracked(g, v.title, W * 0.84, "500", fam, 0.055);
    g.fillStyle = pal.foil; tracked(g, v.title, W * 0.5, H * 0.178, s1 * 0.055, "center");
    y = H * 0.178;
  }
  rule(g, W * 0.26, y + H * 0.034, W * 0.74, y + H * 0.034, pal.foil + "80", W * 0.0034);

  /* The foot carries the two scores. They are the reason the volume exists,
     so they are set as the colophon rather than hidden on the back. Set a
     size up on 24 Sep 2026: three of five readers in the final user
     evaluation called the numbers on the covers tiny (figures 0.094W ->
     0.118W, labels 0.029W -> 0.042W at a stronger alpha), the block lifted
     so the frame's foot still clears the figures. */
  const fy = H * 0.815;
  g.globalAlpha = 0.82; g.fillStyle = pal.foil;
  g.font = `500 ${W * 0.042}px ${SANS}`;
  tracked(g, "AUTH", W * 0.285, fy, W * 0.042 * 0.2, "center");
  tracked(g, "HEALTH", W * 0.715, fy, W * 0.042 * 0.2, "center");
  g.globalAlpha = 1;
  g.font = `500 ${W * 0.118}px ${SANS}`;
  g.fillStyle = pal.foil;
  g.fillText(v.authText, W * 0.285, fy + H * 0.084);
  g.fillText(v.healthText, W * 0.715, fy + H * 0.084);
  rule(g, W * 0.5, fy - H * 0.022, W * 0.5, fy + H * 0.072, pal.foil + "3a", W * 0.0022);

  /* The date is NOT printed here. At shelf distance it was three pixels tall
     and read as a grey smear under the scores; it is blocked down the spine,
     where a real volume carries it, and the desk prints it in full the moment
     one is taken down. */
  grain(g, W, H, 6, v.seed);
  return c;
}

/* The back board: the run's own reading, set as a colophon page. This is the
   registered artBack's composition -- three lifted plates, a blurb, an
   imprint roundel and a rule -- carrying measured figures instead. */
function paintBack(v, W, H) {
  const pal = SHELF_BOARD;
  const c = C(W, H), g = c.getContext("2d");
  const ink = pal.foil;
  g.fillStyle = pal.cloth; g.fillRect(0, 0, W, H);
  g.fillStyle = rg(g, W * 0.5, H * 0.30, W * 0.05, W * 0.95,
    [[0, "rgba(255,255,255,.07)"], [1, "rgba(0,0,0,0)"]]);
  g.fillRect(0, 0, W, H);

  g.fillStyle = ink; g.globalAlpha = 0.55;
  g.font = `400 ${W * 0.019}px ${MONO}`; g.textAlign = "left";
  g.fillText(v.filename, W * 0.10, H * 0.118);
  g.globalAlpha = 1;
  rule(g, W * 0.10, H * 0.140, W * 0.90, H * 0.140, ink + "40", W * 0.002);

  /* The reading, as a ledger. Every row is read from the report. */
  let y = H * 0.205;
  for (const [k, val] of v.ledger) {
    g.globalAlpha = 0.6; g.fillStyle = ink;
    g.font = `400 ${W * 0.0205}px ${SANS}`; g.textAlign = "left";
    tracked(g, k.toUpperCase(), W * 0.10, y, W * 0.0205 * 0.22, "left");
    g.globalAlpha = 1;
    g.font = `500 ${W * 0.032}px ${SANS}`; g.textAlign = "right";
    g.fillText(val, W * 0.90, y);
    rule(g, W * 0.10, y + H * 0.018, W * 0.90, y + H * 0.018, ink + "22", W * 0.0014);
    y += H * 0.072;
  }

  g.textAlign = "left";
  g.font = `400 ${W * 0.026}px ${SERIF}`; g.fillStyle = ink;
  g.globalAlpha = 0.86;
  const words = v.blurb.split(" ");
  let line = ""; y += H * 0.028;
  for (const w0 of words) {
    const t = line ? line + " " + w0 : w0;
    if (g.measureText(t).width > W * 0.80) { g.fillText(line, W * 0.10, y); line = w0; y += W * 0.038; }
    else line = t;
  }
  g.fillText(line, W * 0.10, y);
  g.globalAlpha = 1;

  g.save(); g.translate(W * 0.145, H * 0.878);
  g.strokeStyle = ink; g.globalAlpha = 0.5; g.lineWidth = W * 0.0035;
  g.beginPath(); g.arc(0, 0, W * 0.056, 0, TAU); g.stroke();
  g.globalAlpha = 1; g.fillStyle = ink;
  g.font = `500 ${W * 0.030}px ${SERIF}`; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText("BP", 0, W * 0.002); g.restore();
  g.textAlign = "left"; g.textBaseline = "alphabetic";
  g.fillStyle = ink; g.font = `500 ${W * 0.022}px ${SANS}`;
  tracked(g, "BRANDPULSE AI", W * 0.225, H * 0.868, W * 0.022 * 0.30, "left");
  g.globalAlpha = 0.6; g.font = `400 ${W * 0.020}px ${SANS}`;
  g.fillText(v.foot, W * 0.225, H * 0.900);
  g.globalAlpha = 1;
  grain(g, W, H, 8, v.seed + 5);
  return c;
}

/* The spine. One video can be saved more than once (six of the eleven runs
   saved on 24 Sep 2026 were the same one), so the spine cannot lean on the
   picture to tell volumes apart: it carries the product and the date, which
   are what actually differ, and the flag rule. */
function paintSpine(v, W, H) {
  const pal = SHELF_BOARD;
  const c = C(W, H), g = c.getContext("2d");
  const ink = pal.foil;
  g.fillStyle = pal.cloth; g.fillRect(0, 0, W, H);
  g.fillStyle = lg(g, 0, 0, W, 0,
    [[0, "rgba(0,0,0,.34)"], [0.3, "rgba(0,0,0,0)"], [0.72, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,.30)"]]);
  g.fillRect(0, 0, W, H);

  g.strokeStyle = v.flagged ? pal.tear : ink + "66";
  g.globalAlpha = v.flagged ? 0.92 : 0.5; g.lineWidth = W * 0.05;
  g.beginPath(); g.moveTo(W * 0.22, H * 0.052); g.lineTo(W * 0.78, H * 0.052); g.stroke();
  g.beginPath(); g.moveTo(W * 0.22, H * 0.918); g.lineTo(W * 0.78, H * 0.918); g.stroke();
  g.globalAlpha = 1;

  g.save(); g.translate(W * 0.52, H * 0.105); g.rotate(Math.PI / 2);
  g.fillStyle = ink; g.textAlign = "left"; g.textBaseline = "middle";
  const t = v.spineTitle.toUpperCase();
  const ts = fitTracked(g, t, H * 0.54, "500", SERIF, 0.06);
  tracked(g, t, 0, 0, ts * 0.06, "left");
  g.globalAlpha = 0.66; g.font = `400 ${W * 0.20}px ${SANS}`;
  tracked(g, v.spineFoot.toUpperCase(), H * 0.58, 0, W * 0.20 * 0.2, "left");
  g.restore();

  g.globalAlpha = 1; g.fillStyle = ink;
  g.textAlign = "center"; g.textBaseline = "middle";
  g.font = `500 ${W * 0.30}px ${SERIF}`;
  g.fillText("BP", W * 0.52, H * 0.962);
  g.font = `400 ${W * 0.20}px ${SANS}`; g.globalAlpha = 0.72;
  g.fillText(v.authText, W * 0.52, H * 0.030);
  return c;
}

/* ------------------------------------------------- the room, as registered */

function woodTexture(pal, px) {
  const W = px, Hh = Math.round(px * 0.5);
  const c = C(W, Hh), g = c.getContext("2d"), r = mulberry(909);
  const [dr, dg, db] = pal.oakGrainDark;
  const [lr, lg2, lb] = pal.oakGrainLite;
  g.fillStyle = pal.oak; g.fillRect(0, 0, W, Hh);
  for (let i = 0; i < 14; i++) {
    g.fillStyle = `rgba(${lr * 0.7 + r() * 40 | 0},${lg2 * 0.7 + r() * 26 | 0},${lb * 0.7 + r() * 22 | 0},${0.06 + r() * 0.09})`;
    g.beginPath(); g.ellipse(r() * W, r() * Hh, W * (0.10 + r() * 0.30), Hh * (0.06 + r() * 0.20), 0, 0, TAU); g.fill();
  }
  for (let i = 0; i < 430; i++) {
    const y0 = r() * Hh, amp = Hh * (0.004 + r() * 0.020), f = 0.6 + r() * 2.2, ph = r() * TAU;
    const dark = r() < 0.34;
    g.strokeStyle = dark
      ? `rgba(${dr + r() * 26 | 0},${dg + r() * 16 | 0},${db + r() * 10 | 0},${0.36 + r() * 0.55})`
      : `rgba(${lr + r() * 40 | 0},${lg2 + r() * 32 | 0},${lb + r() * 26 | 0},${0.14 + r() * 0.32})`;
    g.lineWidth = dark ? (0.8 + r() * 1.8) : (0.8 + r() * 2.6);
    g.beginPath();
    for (let x = 0; x <= W; x += 8) {
      const y = y0 + Math.sin(x / W * TAU * f + ph) * amp + Math.sin(x / W * TAU * f * 2.7 + ph * 2) * amp * 0.4;
      x ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.stroke();
  }
  for (let k = 0; k < 4; k++) {
    const cx = W * (0.1 + r() * 0.8), cy = Hh * (0.15 + r() * 0.7), sw = W * (0.02 + r() * 0.05);
    for (let i = 0; i < 14; i++) {
      g.strokeStyle = `rgba(${dr + 24 + r() * 26 | 0},${dg + 16 + r() * 18 | 0},${db + 6 + r() * 12 | 0},${0.12 + r() * 0.20})`;
      g.lineWidth = 0.8 + r() * 1.6;
      g.beginPath();
      g.moveTo(cx - sw * (1 + i * 0.30), cy + Hh * 0.5);
      g.quadraticCurveTo(cx, cy - Hh * (0.12 + i * 0.05), cx + sw * (1 + i * 0.30), cy + Hh * 0.5);
      g.stroke();
    }
  }
  for (let i = 0; i < 520; i++) {
    g.fillStyle = `rgba(${lr + 20 + r() * 26 | 0},${lg2 + 18 + r() * 28 | 0},${lb + 16 + r() * 28 | 0},${0.05 + r() * 0.15})`;
    g.fillRect(r() * W, r() * Hh, 1 + r() * 2, Hh * (0.01 + r() * 0.05));
  }
  for (let i = 0; i < 9000; i++) {
    g.fillStyle = `rgba(${dr + r() * 28 | 0},${dg + r() * 16 | 0},${db + r() * 10 | 0},${0.12 + r() * 0.34})`;
    g.fillRect(r() * W, r() * Hh, 1 + r() * 4, 1);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = MAXA;
  return t;
}

function paperTexture(px) {
  const c = C(px, px), g = c.getContext("2d"), r = mulberry(2027);
  g.fillStyle = "#808080"; g.fillRect(0, 0, px, px);
  for (let i = 0; i < 70; i++) {
    g.fillStyle = `rgba(${r() < 0.5 ? 255 : 0},${r() < 0.5 ? 255 : 0},${r() < 0.5 ? 255 : 0},${0.012 + r() * 0.03})`;
    g.beginPath(); g.ellipse(r() * px, r() * px, px * (0.05 + r() * 0.28), px * (0.04 + r() * 0.22), r() * TAU, 0, TAU); g.fill();
  }
  for (let i = 0; i < 5200; i++) {
    const x = r() * px, y = r() * px, l = 1 + r() * px * 0.035, a = r() * TAU;
    g.strokeStyle = r() < 0.5 ? `rgba(255,255,255,${0.03 + r() * 0.11})` : `rgba(0,0,0,${0.03 + r() * 0.13})`;
    g.lineWidth = r() < 0.85 ? 1 : 2;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke();
  }
  const img = g.getImageData(0, 0, px, px), d = img.data;
  for (let i = 0; i < d.length; i += 4) { const n = (r() - 0.5) * 40; d[i] += n; d[i + 1] += n; d[i + 2] += n; }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = MAXA;
  t.minFilter = THREE.LinearMipmapLinearFilter; t.magFilter = THREE.LinearFilter;
  return t;
}

/* The registered wall bake, driven off the derived carcass rather than off two
   hard-coded shelf heights: every plank bounces light back up the wall, so the
   bake has to know where the planks actually ended up. */
function wallTexture(geom, pal, px) {
  const { wall, bands } = geom;
  const c = C(px, px), g = c.getContext("2d");
  const Ww = wall.x1 - wall.x0, Hh = wall.y1 - wall.y0;
  const img = g.createImageData(px, px), d = img.data;
  const sm = (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
  const r = mulberry(5);
  const PEAK = pal.wallPeak;
  const BOUNCE = pal.bounce, SHADE = pal.shadow;
  const FEATHER = 0.55;
  const ENV = envOf(pal);
  const halfW = geom.unitW / 2 + 0.10, halfH = geom.unitH / 2 + 0.10;
  for (let j2 = 0; j2 < px; j2++) {
    const y = wall.y1 - (j2 + 0.5) / px * Hh;
    for (let i2 = 0; i2 < px; i2++) {
      const x = wall.x0 + (i2 + 0.5) / px * Ww;
      const ax = Math.abs(x) / (geom.unitW * 0.62);
      let L = PEAK - PEAK * 0.34 * ax * ax + PEAK * 0.05 * clamp(x / 4, 0, 1);
      L -= PEAK * pal.vFall * sm((geom.shelfY[0] - y) / (geom.unitH * 0.9)) * sm((-x + 2.8) / 8.6);
      /* Every shelf bounces light up the wall behind it and drops a shadow
         under it, and BOTH are held to the shelf's own span. The first build
         of this took the bounce from the whole unit's half-width and the
         shadow from nothing at all, which drew a pair of bands straight across
         the wall past both ends of the case. `bands` is one merged span per
         row rather than one per case per row: the cases are the same height
         now, so the three planks of a row are one shelf. */
      for (const pk of bands) {
        const inX = sm((x - pk.x0) / FEATHER) * (1 - sm((x - pk.x1) / FEATHER));
        if (inX <= 0.002) continue;
        const up = y - pk.y;
        if (up >= 0 && up < 2.10) L += PEAK * BOUNCE * Math.pow(1 - up / 2.10, 2.6) * inX;
        const dn = (pk.y - SHELF_LAYOUT.plankThick) - y;
        if (dn > 0 && dn < 1.90) L *= 1 - SHADE * Math.pow(1 - dn / 1.90, 2.3) * inX;
      }
      const o = (j2 * px + i2) * 4;
      const n = (r() - 0.5) * 5;
      const out = Math.hypot(Math.max(0, Math.abs(x) - halfW), Math.max(0, Math.abs(y) - halfH));
      const e = sm(out / pal.envReach) * pal.envMix;
      d[o] = clamp(lerp((L + n) * pal.wallTint[0], ENV[0], e), 0, 255);
      d[o + 1] = clamp(lerp((L + n) * pal.wallTint[1], ENV[1], e), 0, 255);
      d[o + 2] = clamp(lerp((L + n) * pal.wallTint[2], ENV[2], e), 0, 255);
      d[o + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = MAXA;
  t.minFilter = THREE.LinearMipmapLinearFilter; t.magFilter = THREE.LinearFilter;
  return t;
}

function shadowTex() {
  const P = 256, c = C(P), g = c.getContext("2d");
  g.fillStyle = "#000"; g.filter = `blur(${P * 0.135}px)`;
  const pad = P * 0.225; g.fillRect(pad, pad, P - pad * 2, P - pad * 2); g.filter = "none";
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function contactTex() {
  const W = 256, H = 96, c = C(W, H), g = c.getContext("2d");
  g.fillStyle = lg(g, 0, 0, 0, H, [[0, "rgba(0,0,0,1)"], [0.06, "rgba(0,0,0,.98)"], [0.16, "rgba(0,0,0,.80)"],
    [0.38, "rgba(0,0,0,.42)"], [0.70, "rgba(0,0,0,.13)"], [1, "rgba(0,0,0,0)"]]);
  g.fillRect(0, 0, W, H);
  g.globalCompositeOperation = "destination-out";
  g.fillStyle = lg(g, 0, 0, W, 0, [[0, "rgba(0,0,0,1)"], [0.05, "rgba(0,0,0,.70)"], [0.11, "rgba(0,0,0,.24)"],
    [0.18, "rgba(0,0,0,0)"], [0.82, "rgba(0,0,0,0)"], [0.89, "rgba(0,0,0,.24)"],
    [0.95, "rgba(0,0,0,.70)"], [1, "rgba(0,0,0,1)"]]);
  g.fillRect(0, 0, W, H);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function creaseTex() {
  const W = 256, H = 64, c = C(W, H), g = c.getContext("2d");
  g.fillStyle = lg(g, 0, H, 0, 0, [[0, "rgba(0,0,0,1)"], [0.22, "rgba(0,0,0,.66)"],
    [0.55, "rgba(0,0,0,.22)"], [1, "rgba(0,0,0,0)"]]);
  g.fillRect(0, 0, W, H);
  g.globalCompositeOperation = "destination-out";
  g.fillStyle = lg(g, 0, 0, W, 0, [[0, "rgba(0,0,0,1)"], [0.14, "rgba(0,0,0,.35)"], [0.30, "rgba(0,0,0,0)"],
    [0.70, "rgba(0,0,0,0)"], [0.86, "rgba(0,0,0,.35)"], [1, "rgba(0,0,0,1)"]]);
  g.fillRect(0, 0, W, H);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

/* ----------------------------------------- the registered GLSL, unmodified */

const BOARD_FN = `
  float board(vec2 t){
    vec2 c=t*2.0-1.0;
    float bulge=(1.0-c.x*c.x)*(1.0-0.55*c.y*c.y);
    float e=clamp(min(min(t.x,1.0-t.x),min(t.y,1.0-t.y))/uER,0.0,1.0);
    float roll=sqrt(max(1.0-(1.0-e)*(1.0-e),0.0));
    return uBow*bulge*roll-uChamf*(1.0-roll);
  }`;
const COVER_VS = `
  uniform float uBow, uChamf, uER, uW, uH;
  varying vec2 vUv; varying vec3 vT, vB2, vNf; varying vec3 vWV;
  ${BOARD_FN}
  void main(){
    vUv=uv;
    vec3 pos=position; pos.z+=board(uv);
    mat3 M=mat3(modelMatrix);
    vT=normalize(M*vec3(1.0,0.0,0.0));
    vB2=normalize(M*vec3(0.0,1.0,0.0));
    vNf=normalize(M*vec3(0.0,0.0,1.0));
    vec4 wp=modelMatrix*vec4(pos,1.0);
    vWV=cameraPosition-wp.xyz;
    gl_Position=projectionMatrix*viewMatrix*wp; }`;
const COVER_FS = `
  uniform sampler2D uTex; uniform float uSatin; uniform float uOpacity; uniform float uSeed;
  uniform float uBow, uChamf, uER, uW, uH;
  varying vec2 vUv; varying vec3 vT, vB2, vNf; varying vec3 vWV;
  ${BOARD_FN}
  float hash(vec2 p){ vec3 p3=fract(vec3(p.xyx)*vec3(0.1031,0.1030,0.0973));
    p3+=dot(p3,p3.yxz+33.33); return fract((p3.x+p3.y)*p3.z); }
  float vnoise(vec2 p){ vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y); }
  void main(){
    vec2 uv=clamp(vUv,0.0008,0.9992);
    vec4 tex=texture2D(uTex,uv);
    float d=0.0016;
    float hx=(board(uv+vec2(d,0.0))-board(uv-vec2(d,0.0)))/(2.0*d*uW);
    float hy=(board(uv+vec2(0.0,d))-board(uv-vec2(0.0,d)))/(2.0*d*uH);
    vec2 q=uv*vec2(58.0,78.0)+uSeed;
    float tooth=vnoise(q)*0.6+vnoise(q*2.7)*0.4;
    vec2 g2=uv*9.0+uSeed;
    float n1=vnoise(g2), e=0.02;
    vec2 grain=vec2(vnoise(g2+vec2(e,0.0))-n1, vnoise(g2+vec2(0.0,e))-n1)/e;
    vec3 N=normalize(vNf
      - vT*(hx + (grain.x*0.0022+(tooth-0.5)*0.009)*uSatin)
      - vB2*(hy + (grain.y*0.0022+(tooth-0.5)*0.009)*uSatin));
    vec3 V=normalize(vWV);
    vec3 L=normalize(vec3(0.52,0.70,0.55));
    vec3 F=normalize(vec3(-0.35,-0.18,0.92));
    float key=max(dot(N,L),0.0);
    float fill=max(dot(N,F),0.0);
    float shade=0.70+0.34*key+0.14*fill;
    vec3 col=tex.rgb*shade;
    vec3 Hv=normalize(L+V);
    float nh=max(dot(N,Hv),0.0);
    col+=vec3(pow(nh,110.0)*0.85*uSatin);
    col+=vec3(pow(nh,14.0)*0.045*uSatin);
    float fres=pow(1.0-max(dot(N,V),0.0),3.4);
    col+=vec3(fres*0.055*uSatin);
    col+=vec3((tooth-0.5)*0.010*uSatin);
    gl_FragColor=vec4(min(col,vec3(1.0)),uOpacity);
    #include <colorspace_fragment>
  }`;
const SPINE_VS = `
  uniform float uHD;
  varying vec2 vUv; varying vec3 vNw, vTw, vBw, vWV; varying float vZ;
  void main(){
    vUv=uv;
    mat3 M=mat3(modelMatrix);
    vNw=normalize(M*normal);
    vTw=normalize(M*vec3(0.0,0.0,1.0));
    vBw=normalize(M*vec3(0.0,1.0,0.0));
    vZ=position.z/uHD;
    vec4 wp=modelMatrix*vec4(position,1.0);
    vWV=cameraPosition-wp.xyz;
    gl_Position=projectionMatrix*viewMatrix*wp; }`;
const SPINE_FS = `
  uniform sampler2D uTex; uniform float uOpacity; uniform float uSeed; uniform float uSatin;
  varying vec2 vUv; varying vec3 vNw, vTw, vBw, vWV; varying float vZ;
  float hash(vec2 p){ vec3 p3=fract(vec3(p.xyx)*vec3(0.1031,0.1030,0.0973));
    p3+=dot(p3,p3.yxz+33.33); return fract((p3.x+p3.y)*p3.z); }
  float vnoise(vec2 p){ vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y); }
  void main(){
    vec4 tex=texture2D(uTex,clamp(vUv,0.0015,0.9985));
    float t=clamp(vZ,-1.0,1.0);
    float ang=1.15*sign(t)*pow(abs(t),1.25);
    vec2 q=vUv*vec2(11.0,78.0)+uSeed;
    float tooth=vnoise(q)*0.6+vnoise(q*2.7)*0.4;
    vec3 N=normalize(vNw*cos(ang) + vTw*sin(ang)
                     + (vTw*0.009+vBw*0.009)*(tooth-0.5)*uSatin);
    vec3 V=normalize(vWV);
    vec3 L=normalize(vec3(0.52,0.70,0.55));
    vec3 F=normalize(vec3(-0.35,-0.18,0.92));
    float shade=0.70+0.34*max(dot(N,L),0.0)+0.14*max(dot(N,F),0.0);
    shade*=1.0-0.16*smoothstep(0.78,1.0,abs(t));
    vec3 col=tex.rgb*shade;
    vec3 Hv=normalize(L+V), Hf=normalize(F+V);
    float nh=max(dot(N,Hv),0.0), nf=max(dot(N,Hf),0.0);
    col+=vec3(pow(nh,110.0)*0.55*uSatin);
    col+=vec3(pow(nh,14.0)*0.045*uSatin);
    col+=vec3(pow(nf,46.0)*0.150*uSatin);
    col+=vec3(pow(nf,9.0)*0.032*uSatin);
    col+=vec3(pow(1.0-max(dot(N,V),0.0),3.4)*0.055*uSatin);
    col+=vec3((tooth-0.5)*0.010*uSatin);
    gl_FragColor=vec4(min(col,vec3(1.0)),uOpacity);
    #include <colorspace_fragment>
  }`;

function pagesMaterial(col, halfH) {
  return new THREE.ShaderMaterial({
    transparent: true,
    uniforms: { uCol: { value: new THREE.Color(col) }, uOpacity: { value: 0 }, uH: { value: halfH } },
    vertexShader: `
      varying vec3 vP; varying vec3 vNw; varying vec3 vWV;
      void main(){ vP=position; vNw=normalize(mat3(modelMatrix)*normal);
        vec4 wp=modelMatrix*vec4(position,1.0);
        vWV=cameraPosition-wp.xyz;
        gl_Position=projectionMatrix*viewMatrix*wp; }`,
    fragmentShader: `
      uniform vec3 uCol; uniform float uOpacity; uniform float uH;
      varying vec3 vP; varying vec3 vNw; varying vec3 vWV;
      void main(){
        float f=vP.z*210.0;
        float w=fwidth(f);
        float line=0.5+0.5*cos(f*6.2831853);
        line=mix(0.5,line,clamp(1.0-w*1.6,0.0,1.0));
        vec3 col=uCol*0.88*mix(0.76,1.04,line);
        col*=1.0-0.16*smoothstep(0.25,1.0,abs(vP.y)/uH);
        col*=0.90+0.10*smoothstep(-0.09,0.09,vP.z);
        vec3 N=normalize(vNw), V=normalize(vWV);
        vec3 L=normalize(vec3(0.52,0.70,0.55));
        vec3 F=normalize(vec3(-0.35,-0.18,0.92));
        float shade=0.70+0.34*max(dot(N,L),0.0)+0.14*max(dot(N,F),0.0);
        shade*=1.0-0.36*max(-N.y,0.0);
        col*=shade/0.871;
        col+=uCol*pow(1.0-max(dot(N,V),0.0),3.2)*max(dot(N,L),0.0)*0.11;
        gl_FragColor=vec4(min(col,vec3(1.0)),uOpacity);
        #include <colorspace_fragment>
      }`,
  });
}

/* ---- the registered tweens ---- */
const easeOutQuart = (t) => 1 - Math.pow(1 - t, 4);
const easeSettle = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const activeEase = (t) => (t < 0.3 ? 0.3 * Math.pow(t / 0.3, 3) : 0.3 + 0.7 * (1 - Math.pow(1 - (t - 0.3) / 0.7, 3)));

class Tw {
  constructor(v) { this.v = v.slice(); this.from = v.slice(); this.to = v.slice(); this.t0 = 0; this.d = 0; this.e = easeOutQuart; this.now = 0; }
  start(to, d, e, delay) { this.from = this.v.slice(); this.to = to.slice(); this.t0 = this.now + (delay || 0); this.d = Math.max(d, 1); this.e = e || easeOutQuart; }
  set(to) { this.v = to.slice(); this.from = to.slice(); this.to = to.slice(); this.d = 0; }
  update(now) {
    this.now = now;
    if (this.d <= 0) return;
    let t = (now - this.t0) / this.d;
    if (t < 0) return;
    if (t >= 1) { t = 1; this.d = 0; }
    const k = this.e(t);
    for (let i = 0; i < this.v.length; i++) this.v[i] = this.from[i] + (this.to[i] - this.from[i]) * k;
  }
}
class Spring {
  constructor(v, tension, friction, mass) {
    this.v = v.slice(); this.tgt = v.slice(); this.vel = v.map(() => 0);
    this.k = tension; this.c = friction; this.m = mass || 1;
  }
  start(t) { this.tgt = t.slice(); }
  update(dt) {
    dt = Math.min(dt, 1 / 30);
    for (let i = 0; i < this.v.length; i++) {
      const a = (this.k * (this.tgt[i] - this.v[i]) - this.c * this.vel[i]) / this.m;
      this.vel[i] += a * dt; this.v[i] += this.vel[i] * dt;
    }
  }
}

/**
 * Derive the carcass from the catalogue. This is the "shrinks or extends"
 * part and it is pure arithmetic — no magic numbers beyond SHELF_LAYOUT.
 */
export function deriveGeometry(bays, K = SHELF_LAYOUT) {
  /* ONE HEIGHT FOR ALL THREE CASES.

     The first build gave each case only as many shelves as its own catalogue
     needed, so the unit stepped 4-2-2 and the top right two thirds of the
     frame were bare wall. It was defensible -- the step was a reading of the
     corpus -- and it was wrong as furniture: three cases of three heights is
     a unit that looks unfinished, and the eye spends its time re-finding the
     datum instead of reading the volumes.

     Every case is now a whole carcass of `rows` shelves. A case with two
     volumes shows the room it has left, which is a true statement about this
     machine and a better one than a short case. When any case outgrows its
     shelves all three gain one together, so the unit is always a rectangle. */
  const rows = shelfRows(bays.map((b) => b.items.length), K);
  const bayRows = bays.map(() => rows);
  const bayW = K.perShelf * K.slot;
  const unitW = bays.length * bayW + (bays.length + 1) * K.bayGap;
  const unitH = rows * K.rowH;
  const x0 = -unitW / 2;
  const bayLeft = (b) => x0 + K.bayGap + b * (bayW + K.bayGap);

  const yBase = -unitH / 2;
  const shelfY = [];
  for (let r = 0; r < rows; r++) shelfY.push(yBase + (rows - 1 - r) * K.rowH + K.plankThick);

  /* One plank per shelf per case. Adjacent cases' planks meet exactly at the
     shared upright -- bay b's x1 and bay b+1's x0 are the same number -- so
     the three read as one continuous shelf with dividers standing on it,
     which is what a three-bay carcass is. */
  const planks = [];
  bays.forEach((b, bi) => {
    for (let r = 0; r < rows; r++) {
      planks.push({ y: shelfY[r], x0: bayLeft(bi) - K.bayGap / 2, x1: bayLeft(bi) + bayW + K.bayGap / 2 });
    }
  });

  /* The wall bake asks, for every one of its million texels, which boards are
     over and under it. Now that every shelf runs the whole width there is one
     span per row rather than three, so the bake does a third of the work and
     -- more to the point -- no two feathered spans overlap at an upright,
     where the sum of two half-strength edges is not quite one full one. */
  const bands = shelfY.map((y) => ({ y, x0: x0 - K.bayGap / 2, x1: -x0 + K.bayGap / 2 }));

  /* Adjacent cases share the upright between them, so the same x is asked for
     twice -- once by each neighbour. Two boards in the same place z-fight into
     a sliver. One board per position is both correct and what a real carcass
     is; with the cases now equal they are all one height. */
  const byX = new Map();
  const h = rows * K.rowH;
  const cy = shelfY[rows - 1] - K.plankThick + h / 2 - K.plankThick / 2;
  bays.forEach((b, bi) => {
    for (const x of [bayLeft(bi) - K.bayGap / 2, bayLeft(bi) + bayW + K.bayGap / 2]) {
      byX.set(x.toFixed(4), { x, h, cy });
    }
  });
  const uprights = [...byX.values()];

  return {
    rows, bayRows, bayW, unitW, unitH, x0, bayLeft, shelfY, planks, bands, uprights,
    plankHalf: unitW / 2,
    wallZ: -1.43, bookZ: -1.18,
    wall: { x0: -unitW * 1.35, x1: unitW * 1.35, y0: yBase - unitH * 1.2, y1: yBase + unitH * 1.6 },
    boxX: unitW + K.padX, boxY: unitH + K.padY,
    /* Volumes fill the top shelf first, left to right, as books are shelved.
       With every case the same height there is no per-case offset to make. */
    slotOf(bayIndex, i) {
      const row = Math.min(Math.floor(i / K.perShelf), rows - 1);
      const col = i % K.perShelf;
      return { row, x: bayLeft(bayIndex) + (col + 0.5) * K.slot, y: shelfY[row] };
    },
    /* The centre of each case, in scene units. The masthead's three labels are
       positioned from these, so a label sits over its own case exactly rather
       than over a third of the frame -- the two differ by about 7px at this
       width, which is the difference between aligned and nearly aligned. */
    bayCentre(bayIndex) { return bayLeft(bayIndex) + bayW / 2; },
  };
}

/** Is there a context to draw into at all? Checked before anything is built. */
export function shelfAvailable() {
  try {
    const c = document.createElement("canvas");
    return Boolean(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { return false; }
}

/**
 * Build the room and the volumes.
 *
 * @param {HTMLElement} host     the element the canvas fills
 * @param {object} opts
 *   bays     [{ key, label, items: [volume] }]
 *   theme    "bench" | "field"
 *   onFocus  (volume|null) => void   a volume was taken off the shelf
 *   onOpen   (volume) => void        the reader asked to open it
 * @returns {{focus, lift, flip, clear, open, activeId, activeVolume, setTheme, destroy}|null}
 */
export function mountShelf(host, opts = {}) {
  const K = SHELF_LAYOUT;
  const bays = opts.bays || [];
  const volumes = [];
  bays.forEach((b, bi) => b.items.forEach((it, i) => volumes.push({ ...it, bay: bi, slotIndex: i })));
  if (!host || !volumes.length || !shelfAvailable()) return null;

  let pal = SHELF_PALETTE[opts.theme === "field" ? "field" : "bench"];
  const geom = deriveGeometry(bays, K);

  const canvas = document.createElement("canvas");
  canvas.className = "bk__canvas";
  /* The canvas alone is hidden from assistive technology, not the stage around
     it: the stage also holds the reading desk, whose three controls are the
     only way out of a lifted volume and have to stay reachable. The equivalent
     of the canvas is .bk__index, a real list of buttons that take each volume
     down (library.js). */
  canvas.setAttribute("aria-hidden", "true");
  host.appendChild(canvas);

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: "high-performance" });
  } catch { canvas.remove(); return null; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  MAXA = renderer.capabilities.getMaxAnisotropy();
  renderer.setClearColor(pal.clear, 1);
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.autoClear = false;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(K.fov, 1, 0.2, 100);
  const LAY_BG = 0, LAY_FG = 1;
  const books = [];

  /* ---- wall ---- */
  const wallMat = new THREE.ShaderMaterial({
    transparent: true,
    uniforms: { uBake: { value: wallTexture(geom, pal, 1024) }, uPaper: { value: paperTexture(512) }, uOpacity: { value: 0 } },
    vertexShader: `varying vec2 vUv; void main(){vUv=uv;
      gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `
      uniform sampler2D uBake; uniform sampler2D uPaper; uniform float uOpacity;
      varying vec2 vUv;
      void main(){
        vec3 bake=texture2D(uBake,vUv).rgb;
        float fine=texture2D(uPaper,vUv*13.0).r;
        float mid =texture2D(uPaper,vUv*3.1+vec2(0.37,0.19)).r;
        vec3 col=bake*(0.86+0.28*fine)*(0.93+0.14*mid);
        gl_FragColor=vec4(col,uOpacity);
        #include <colorspace_fragment>
      }`,
  });
  const wall = new THREE.Mesh(
    new THREE.PlaneGeometry(geom.wall.x1 - geom.wall.x0, geom.wall.y1 - geom.wall.y0), wallMat);
  wall.position.set(0, (geom.wall.y0 + geom.wall.y1) / 2, geom.wallZ);
  scene.add(wall);

  /* ---- oak ---- */
  let WOOD_TEX = woodTexture(pal, 1024);
  function oakMaterial(axis) {
    return new THREE.ShaderMaterial({
      transparent: true,
      uniforms: { uWood: { value: WOOD_TEX }, uOpacity: { value: 0 }, uAxis: { value: axis || 0 },
                  uHalf: { value: geom.plankHalf } },
      vertexShader: `
        varying vec3 vP; varying vec3 vN;
        void main(){ vP=position; vN=normalize(normalMatrix*normal);
          gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
      fragmentShader: `
        uniform sampler2D uWood; uniform float uOpacity; uniform float uAxis; uniform float uHalf;
        varying vec3 vP; varying vec3 vN;
        void main(){
          vec3 n=normalize(vN), an=abs(n);
          vec2 uvH, uvV, uvE;
          if(uAxis<0.5){
            uvH=vec2(vP.x*0.140, vP.z*0.30);
            uvV=vec2(vP.x*0.140, vP.y*0.44);
            uvE=vec2(vP.z*0.30,  vP.y*0.44);
          } else {
            uvH=vec2(vP.y*0.100, vP.z*0.30);
            uvV=vec2(vP.y*0.100, vP.x*0.55);
            uvE=vec2(vP.z*0.30,  vP.x*0.55);
          }
          vec2 uv=mix(mix(uvV,uvH,an.y),uvE,an.x);
          vec3 wood=texture2D(uWood,uv).rgb;
          float up=max(n.y,0.0), dn=max(-n.y,0.0), fwd=max(n.z,0.0), side=abs(n.x);
          float t = 1.22*up + 0.14*dn + 0.86*fwd + 0.48*side;
          float ao = mix(0.66,1.0, clamp((vP.z+0.42)/0.66,0.0,1.0));
          t *= mix(1.0, ao, up);
          t *= mix(0.88,1.0, 1.0-pow(clamp(abs(vP.x)/uHalf,0.0,1.0),8.0));
          vec3 col = wood*t;
          float arris = smoothstep(0.30,0.50,vP.z*2.0+0.5)*pow(clamp(n.z,0.0,1.0),1.5);
          col += vec3(0.10,0.082,0.055)*arris;
          col += vec3(0.05,0.040,0.026)*pow(clamp(n.z,0.0,1.0),5.0);
          gl_FragColor=vec4(col,uOpacity);
          #include <colorspace_fragment>
        }`,
    });
  }
  const oakH = oakMaterial(0), oakV = oakMaterial(1);
  const furniture = new THREE.Group();
  scene.add(furniture);
  for (const pk of geom.planks) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(pk.x1 - pk.x0, K.plankThick, K.plankDepth), oakH);
    m.position.set((pk.x0 + pk.x1) / 2, pk.y - K.plankThick / 2, geom.wallZ + K.plankDepth / 2);
    furniture.add(m);
  }
  for (const up of geom.uprights) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(K.bayGap * 0.62, up.h + K.plankThick, K.plankDepth), oakV);
    m.position.set(up.x, up.cy, geom.wallZ + K.plankDepth / 2);
    furniture.add(m);
  }

  const SHADOW_TEX = shadowTex(), CONTACT_TEX = contactTex(), CREASE_TEX = creaseTex();

  /* ---- one volume ---- */
  const SZW = K.bookW, SZH = K.bookH, SZD = K.bookD;
  const bodyGeo = new THREE.BoxGeometry(SZW, SZH, SZD);
  const faceGeo = new THREE.PlaneGeometry(SZW, SZH, 44, 44);
  const hitGeo = new THREE.PlaneGeometry(SZW * 1.06, SZH * 0.98);

  function basePosOf(B) {
    const s = geom.slotOf(B.data.bay, B.data.slotIndex);
    return [s.x, s.y + (SZH / 2) * Math.cos(B._lean), geom.bookZ];
  }

  function buildBook(data, index) {
    const rnd = mulberry(index * 7919 + 13);
    const B = { data, index, flipped: false };
    B._lean = K.lean + (rnd() - 0.5) * 0.075;
    B._yaw = K.yaw + (rnd() - 0.5) * 0.045;
    B._roll = (rnd() - 0.5) * 0.018;
    B.rest = [B._lean, B._yaw, B._roll];
    B.base = [0, 0, 0.01];
    B.basePos = basePosOf(B);
    const shelfTopY = geom.slotOf(data.bay, data.slotIndex).y;

    const gRoot = new THREE.Group(); gRoot.position.set(...B.basePos);
    const gHover = new THREE.Group(); gHover.position.set(...B.base);
    const gWob = new THREE.Group();
    const gTilt = new THREE.Group(); gTilt.rotation.set(...B.rest);
    const gScl = new THREE.Group(); gScl.scale.setScalar(1);
    gRoot.add(gHover); gHover.add(gWob); gWob.add(gTilt); gTilt.add(gScl);
    scene.add(gRoot);

    const coverTex = new THREE.CanvasTexture(paintCover(data, 768, 1152));
    coverTex.colorSpace = THREE.SRGBColorSpace; coverTex.anisotropy = MAXA;
    const spineTex = new THREE.CanvasTexture(paintSpine(data, 142, 1152));
    spineTex.colorSpace = THREE.SRGBColorSpace; spineTex.anisotropy = MAXA;

    const pages = pagesMaterial(SHELF_BOARD.edge, SZH * 0.5);
    const spineMat = new THREE.ShaderMaterial({
      transparent: true,
      uniforms: { uTex: { value: spineTex }, uOpacity: { value: 0 }, uSeed: { value: index * 5.7 },
                  uSatin: { value: 1.0 }, uHD: { value: SZD * 0.5 } },
      vertexShader: SPINE_VS, fragmentShader: SPINE_FS,
    });
    const clothMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(SHELF_BOARD.cloth), transparent: true, opacity: 0 });
    const body = new THREE.Mesh(bodyGeo, [pages, spineMat, pages, pages, clothMat, clothMat]);
    gScl.add(body);

    const mk = (tex, satin, seed) => new THREE.ShaderMaterial({
      transparent: true,
      uniforms: { uTex: { value: tex }, uSatin: { value: satin }, uOpacity: { value: 0 }, uSeed: { value: seed },
                  uBow: { value: K.bow }, uChamf: { value: K.chamf }, uER: { value: K.chamfR },
                  uW: { value: SZW }, uH: { value: SZH } },
      vertexShader: COVER_VS, fragmentShader: COVER_FS,
    });
    const coverMat = mk(coverTex, 1.0, index * 7.3);
    const cover = new THREE.Mesh(faceGeo, coverMat);
    cover.position.z = SZD / 2 + K.chamf + 0.0008; gScl.add(cover);
    const backMat = mk(coverTex, 0.55, index * 3.1 + 11);
    const back = new THREE.Mesh(faceGeo, backMat);
    back.position.z = -SZD / 2 - K.chamf - 0.0008; back.rotation.y = Math.PI; gScl.add(back);
    B.backLoaded = false;
    B.loadBack = () => {
      if (B.backLoaded) return;
      B.backLoaded = true;
      const t = new THREE.CanvasTexture(paintBack(data, 768, 1152));
      t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = MAXA;
      backMat.uniforms.uTex.value = t;
    };

    const hit = new THREE.Mesh(hitGeo, new THREE.MeshBasicMaterial({ visible: false }));
    hit.position.set(B.basePos[0], B.basePos[1], B.basePos[2] - 0.04);
    hit.rotation.x = B._lean; hit.rotation.y = B._yaw;
    hit.userData.book = B;
    scene.add(hit);

    const wallSh = new THREE.Mesh(new THREE.PlaneGeometry(2.20, 2.70),
      new THREE.MeshBasicMaterial({ map: SHADOW_TEX, transparent: true, opacity: 0, depthWrite: false, color: 0x05080a }));
    wallSh.position.set(B.basePos[0] - 0.05, B.basePos[1] - 0.04, geom.wallZ + 0.004);
    scene.add(wallSh);

    const footZ = geom.bookZ + (SZH / 2) * Math.sin(-B._lean);
    const csBack = footZ - SZD * 0.5 - 0.045;
    const csFront = geom.wallZ + K.plankDepth - 0.035;
    const csDepth = csFront - csBack;
    const cs = new THREE.Mesh(new THREE.PlaneGeometry(SZW * 1.42, csDepth),
      new THREE.MeshBasicMaterial({ map: CONTACT_TEX, transparent: true, opacity: 0, depthWrite: false, color: 0x04070a }));
    cs.rotation.x = -Math.PI / 2;
    cs.position.set(B.basePos[0], shelfTopY + 0.0022, csBack + csDepth * 0.5);
    scene.add(cs);
    const crease = new THREE.Mesh(new THREE.PlaneGeometry(SZW * 1.16, 0.075),
      new THREE.MeshBasicMaterial({ map: CREASE_TEX, color: 0x03060a, transparent: true, opacity: 0, depthWrite: false }));
    crease.position.set(B.basePos[0], shelfTopY + 0.030, footZ + SZD * 0.5 + 0.004);
    scene.add(crease);

    const reflMat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false,
      uniforms: { uTex: { value: coverTex }, uOpacity: { value: 0 } },
      vertexShader: `varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
      fragmentShader: `
        uniform sampler2D uTex; uniform float uOpacity; varying vec2 vUv;
        float hash(vec2 p){vec3 p3=fract(vec3(p.xyx)*vec3(0.1031,0.1030,0.0973));
          p3+=dot(p3,p3.yxz+33.33);return fract((p3.x+p3.y)*p3.z);}
        void main(){
          float mappedY=mix(0.0,0.22,1.0-vUv.y);
          float edge=min(min(smoothstep(0.0,0.06,vUv.y),smoothstep(0.0,0.12,1.0-vUv.y)),
                         min(smoothstep(0.0,0.06,vUv.x),smoothstep(0.0,0.06,1.0-vUv.x)));
          float b=0.004+0.02*(1.0-edge);
          vec4 col=(texture2D(uTex,vec2(vUv.x+b,mappedY))+texture2D(uTex,vec2(vUv.x-b,mappedY))
                   +texture2D(uTex,vec2(vUv.x,mappedY+b*0.5))+texture2D(uTex,vec2(vUv.x,mappedY-b*0.5)))*0.25;
          float fade=vUv.y*vUv.y*1.7;
          float sp=hash(vUv*220.0);
          gl_FragColor=vec4(col.rgb,uOpacity*fade*(1.0-sp*0.34)*edge);
          #include <colorspace_fragment>
        }`,
    });
    const refl = new THREE.Mesh(new THREE.PlaneGeometry(SZW, 0.60), reflMat);
    refl.rotation.x = -Math.PI / 2;
    refl.position.set(B.basePos[0], shelfTopY + 0.0012, footZ + 0.24);
    scene.add(refl);

    Object.assign(B, {
      gRoot, gHover, gWob, gTilt, gScl, body, cover, back, coverMat, backMat, spineMat,
      clothMat, pages, hit, wallSh, cs, crease, refl, reflMat, coverTex, spineTex, footZ,
      tHover: new Tw([...B.base]), tTilt: new Tw([...B.rest]),
      sWob: new Spring([0, 0, 0], 80, 6, 1),
      tActiveP: new Tw([...B.basePos]), tActiveR: new Tw([0, 0, 0]),
      tRefl: new Tw([0.34]), tFade: new Tw([0]), tSeat: new Tw([1]),
    });
    return B;
  }

  /* ---- state ---- */
  const S = { anim: "intro", active: null, lifted: null };
  const setLayer = (B, l) => B.gRoot.traverse((o) => o.layers.set(l));

  function hoverIn(B, dur) {
    const d = dur === undefined ? K.hoverLift : dur;
    B.tHover.start([B.base[0], B.base[1] + 0.085, B.base[2] + 0.075], d, easeOutQuart);
    B.tTilt.start([0, 0, 0], d, easeOutQuart);
    B.sWob.start([0, 0, 0]);
    B.tRefl.start([0], d * 0.45, easeOutQuart);
    B.loadBack();
  }
  function hoverOut(B) {
    const d = K.hoverDrop;
    B.tHover.start([...B.base], d, easeSettle);
    B.tTilt.start([...B.rest], d, easeSettle, d * 0.22);
    B.tRefl.start([0.34], d, easeSettle);
    B.sWob.start([0, 0, 0]);
  }
  function activeZ() {
    const camZ = camera.position.z;
    const fill = 0.60;
    const halfH = (SZH * 0.5) / fill;
    const dv = halfH / Math.tan(K.fov * Math.PI / 360);
    const halfW = (SZW * 0.5) / fill;
    const dh = halfW / (Math.tan(K.fov * Math.PI / 360) * camera.aspect);
    return camZ - Math.max(dv, dh);
  }
  function toActive(B) {
    S.anim = "animatingForward"; hoverIn(B);
    B.tSeat.start([0], K.activeDuration * 0.55, easeSettle, K.activeDuration * 0.12);
    /* Registered: the volume comes to rest at boxCY - 0.02, which is the
       camera's own target height less a hair. Resting it at 0 while the
       camera looked 1.8 units higher is what put it off the canvas. */
    B.tActiveP.start([K.activeX, K.boxCY - 0.02, activeZ()], K.activeDuration, activeEase);
    B.tActiveR.start([...K.activeRot], K.activeDuration, activeEase);
    B.gRoot.renderOrder = 10; setLayer(B, LAY_FG);
    setTimeout(() => { if (S.active === B) S.anim = "active"; }, K.activeDuration);
  }
  function toInactive(B) {
    S.anim = "animatingBackward"; B.flipped = false;
    B.tSeat.start([1], K.activeDuration * 0.62, easeSettle, K.activeDuration * 0.38);
    B.tHover.start([B.base[0], B.base[1] + 0.06, B.base[2]], K.activeDuration, easeOutQuart);
    B.tActiveP.start([...B.basePos], K.activeDuration, activeEase);
    B.tActiveR.start([...K.activeRot], K.activeDuration, activeEase);
    setTimeout(() => hoverOut(B), K.activeDuration);
    setTimeout(() => {
      S.anim = "inactive"; setLayer(B, LAY_BG); B.gRoot.renderOrder = 0;
      if (S.lifted === B) S.lifted = null;
    }, K.activeDuration + 20);
  }
  function setLifted(B) {
    if (S.lifted === B) return;
    if (S.lifted && S.lifted !== S.active) hoverOut(S.lifted);
    S.lifted = B;
    if (B) hoverIn(B);
  }
  function setActive(B) {
    if (S.anim === "intro" || S.anim === "animatingForward" || S.anim === "animatingBackward") return;
    if (S.active === B) return;
    if (S.active) { toInactive(S.active); S.active = null; if (opts.onFocus) opts.onFocus(null); return; }
    S.active = B; S.lifted = B; toActive(B);
    if (opts.onFocus) opts.onFocus(B.data);
  }
  function clearActive() {
    if (!S.active) return;
    const B = S.active; S.active = null;
    dragReset(); toInactive(B);
    if (opts.onFocus) opts.onFocus(null);
  }
  function flipActive() {
    const B = S.active;
    if (!B || S.anim !== "active") return;
    B.flipped = !B.flipped; B.loadBack();
    B.tActiveR.start([K.activeRot[0], K.activeRot[1] + (B.flipped ? Math.PI : 0), K.activeRot[2]],
      K.activeDuration, activeEase);
  }

  /* ---- camera ---- */
  /* REGISTERED, restored 22 Sep 2026.

     What was here instead: a target aimed at geom.boxY * compositionLift
     (0.255, about 1.8 world units) with a matching horizontal shift and a
     distance multiplier, all added so a masthead could sit in the top of the
     frame. The masthead is gone, and so is every one of those: the camera
     looks where the source says to look, from the distance the source says
     to use. K.boxCY is 0.06 -- the registered nudge is thirty times smaller
     than the one that replaced it. */
  let VW = 1, VH = 1, DIST = 12;
  const ORB = { tx: 0, ty: 0, x: 0, y: 0 };
  const TGT = new THREE.Vector3();
  function applyCamera() {
    const damp = S.active ? K.activeOrbitDamp : 1;
    const az = ORB.x * K.orbitAz * damp;
    const el = 0.0025 - ORB.y * K.orbitEl * damp;
    TGT.set(0, K.boxCY, 0);
    camera.position.set(
      TGT.x + Math.sin(az) * Math.cos(el) * DIST,
      TGT.y + Math.sin(el) * DIST,
      TGT.z + Math.cos(az) * Math.cos(el) * DIST);
    camera.lookAt(TGT);
  }
  function frameCamera() {
    const aspect = VW / VH, tan = Math.tan(K.fov * Math.PI / 360);
    camera.aspect = aspect;
    const distV = geom.boxY / (2 * tan), distH = geom.boxX / (2 * tan * aspect);
    let d = K.offset * Math.max(distV, distH);
    const projW = VW * geom.boxX / (2 * d * tan * aspect);
    if (projW > K.maxWidthPx) d = VW * geom.boxX / (2 * K.maxWidthPx * tan * aspect);
    DIST = d;
    const maxDim = Math.max(geom.boxX, geom.boxY);
    camera.near = Math.max(DIST - maxDim * 2 - 2, 0.1);
    camera.far = DIST + maxDim * 2 + 16;
    applyCamera();
    camera.updateProjectionMatrix();
  }

  /* ---- the registered blur composite ---- */
  /* SUPERSAMPLING, and why it is nearly free here.

     Every frame is already drawn into this target and then blitted to the
     canvas through a full-screen quad, because the registered component
     blurs the room behind a lifted volume. That blit is a resample the page
     pays for whether or not it is doing anything useful. Drawing the target
     LARGER than the canvas and box-filtering it down on the way through turns
     that wasted resample into the sharpest antialiasing available: unlike
     MSAA, which multisamples coverage and shades once, supersampling raises
     the sample rate of the TEXTURES too -- so every cover drops most of a mip
     level and the type on it stops being a smudge.

     SS is 2 or 1 and never anything between. A non-integer downsample with a
     bilinear tap skips source texels, which does not blur an image so much as
     alias it, and aliasing on a shelf of thin foil rules is worse than the
     softness being fixed. At SS 2 the four taps below land exactly on the
     four source texels of each destination pixel: an exact box filter.

     MSAA is switched off when SS is on. 2x supersampling already gives four
     shaded samples per pixel on geometry edges; keeping 4x MSAA as well would
     ask for sixteen and quadruple the target's memory for no visible gain.

     MEASURED, 22 Sep 2026, before adopting. Same page, same 1438x702 canvas at
     dpr 1, headless Chrome on SwiftShader, 4s of frames each:

       SS 1   8.25 fps   Laplacian variance over the top three covers 1487.2
       SS 2   7.25 fps   ...                                          2258.4

     +51.9% edge energy on the covers for -12.1% frame rate. Four times the
     fragments cost only an eighth of the frame rate even in software, which
     says the loop is not fill-bound here, so a real GPU should pay less again.
     Both numbers are SOFTWARE rendering and are a ratio, not a frame budget --
     nothing here has been run on a real GPU. The first real-GPU figures are in
     the note on the blur below, and they are why the blur no longer runs
     through this resolve. */
  const SS = (window.devicePixelRatio || 1) >= 2 ? 1 : 2;
  const rt = new THREE.WebGLRenderTarget(2, 2, {
    type: THREE.HalfFloatType, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
    depthBuffer: true, stencilBuffer: false, samples: SS > 1 ? 0 : 4,
  });
  const NOISE_N = 256, noiseData = new Uint8Array(NOISE_N * NOISE_N * 4);
  { const r = mulberry(4242);
    for (let i = 0; i < NOISE_N * NOISE_N; i++) {
      noiseData[i * 4] = (r() * 255) | 0; noiseData[i * 4 + 1] = (r() * 255) | 0;
      noiseData[i * 4 + 2] = (r() * 255) | 0; noiseData[i * 4 + 3] = 255;
    } }
  const noiseTex = new THREE.DataTexture(noiseData, NOISE_N, NOISE_N);
  noiseTex.wrapS = noiseTex.wrapT = THREE.RepeatWrapping;
  noiseTex.minFilter = noiseTex.magFilter = THREE.LinearFilter; noiseTex.needsUpdate = true;

  /* THE BLUR IS DRAWN AT HALF RESOLUTION, AND FADED IN RATHER THAN SWITCHED ON.

     MEASURED, 23 Sep 2026, on this machine's own GPU -- Apple M1 Pro through
     ANGLE Metal, Chrome at devicePixelRatio 2, which is the first time this
     loop was timed on real hardware; the figures above are SwiftShader. GPU
     time per frame, forced to completion by a one-pixel readPixels after the
     loop has drawn, median over each phase of taking one volume down:

                             1512x860 window        1728x1000 window
                            rest  flight  held     rest  flight  held
       as it was             8.9   15.4   16.7     11.0   19.4   23.8
       blur taps 1 each      8.7   12.0   13.3     11.4   15.2   19.1
       blur switched off     8.8    8.5    9.3     10.3    9.6    9.6

     Taking a volume down doubled the cost of a frame, and the whole of the
     increase was the blur: the registered composite reads thirty taps for
     every pixel of the canvas, four and a half million of them at Retina,
     every frame the volume is moving. The resolve below made that four times
     worse, by putting a 2x2 box behind each of the thirty -- including on
     the Retina path, where SS is 1 and all four reads land on one texel. On a
     120 Hz panel the budget is 8.3 ms, so the volume's own flight ran at half
     the rate of the hover just before it, which is what read as lag.

     So the golden-angle blur -- the registered one, one read per tap as in
     the source -- is drawn into its own target at half the canvas's
     resolution, and the composite reads it back. Its radius runs to 16/1024
     of the canvas width; nothing survives a blur that size that half
     resolution could lose. What half resolution WOULD lose is the first
     frames, where the registered radius is a pixel or two and the room is
     meant to look almost sharp: cutting straight to a half-resolution image
     there reads as the shelf dropping out of focus in one step. So the
     composite mixes from the full-resolution image into the blurred one over
     the first BLUR_HANDOFF units of the registered intensity, which at the
     registered rate is the first ~90 ms of the blur. */
  const BLUR_HANDOFF = 3;
  /* Half, and not a quarter. Both were rendered at the held state on the M1
     Pro and compared against the full-resolution blur: at a quarter the
     noise the registered blur rotates its taps by is upsampled into a coarse
     speckle across the blurred volumes, plainly visible at 1:1; at half it
     is within a hair of the original. */
  const BLUR_DIV = 2;
  const rtBlur = new THREE.WebGLRenderTarget(2, 2, {
    type: THREE.HalfFloatType, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
    depthBuffer: false, stencilBuffer: false,
  });
  /* THE ROOM ITSELF, AT THE BLUR'S RESOLUTION.

     While a volume is flying out and the hand-off is complete, the full-size
     room is drawn -- four and a half million multisampled half-float pixels
     at Retina -- only to be read back thirty times over and averaged into a
     half-resolution blur. Drawing it at the blur's resolution instead costs a
     quarter of that and changes nothing on screen: its sharp detail is never
     shown. Multisampled, so what the blur averages is an antialiased image
     and not a point-sampled one that would crawl under the pointer orbit. */
  const rtRoom = new THREE.WebGLRenderTarget(2, 2, {
    type: THREE.HalfFloatType, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
    depthBuffer: true, stencilBuffer: false, samples: 4,
  });
  const QUAD_VS = `varying vec2 vUv; void main(){vUv=uv;gl_Position=vec4(position.xy,0.0,1.0);}`;

  const blurMat = new THREE.ShaderMaterial({
    depthTest: false, depthWrite: false,
    uniforms: {
      backgroundTexture: { value: rt.texture }, noiseTexture: { value: noiseTex },
      noiseScale: { value: 6 }, intensity: { value: 0 },
      samples: { value: 30 }, resolution: { value: new THREE.Vector2(1, 1) },
    },
    vertexShader: QUAD_VS,
    /* Linear in, linear out: this writes a half-float target, and the
       composite applies the output colour space once, after the mix. */
    fragmentShader: `
      uniform sampler2D backgroundTexture; uniform sampler2D noiseTexture;
      uniform float noiseScale; uniform float intensity;
      uniform float samples; uniform vec2 resolution;
      varying vec2 vUv;
      const float pi=3.14159265359;
      const float goldenAngle=pi*(3.0-sqrt(5.0));
      vec4 goldenBlur(vec2 uv,sampler2D tex){
        float noise=texture2D(noiseTexture,uv*noiseScale).r;
        float angle=pi+(noise-0.5)*2.0*pi*2.0;
        vec2 polar=vec2(cos(angle),sin(angle));
        vec4 sum=vec4(0.0);
        vec2 a=vec2(1024.)*vec2(1.,resolution.x/resolution.y);
        for(int i=1;i<=32;i++){
          if(float(i)>samples)break;
          float r=intensity*sqrt(float(i)/samples);
          float theta=float(i)*goldenAngle;
          vec2 off=vec2(polar.x*cos(theta)-polar.y*sin(theta),
                        polar.y*cos(theta)+polar.x*sin(theta));
          sum+=texture2D(tex,uv+(off*r/a));
        }
        return sum/samples;
      }
      void main(){
        gl_FragColor=goldenBlur(vUv,backgroundTexture);
        gl_FragColor.a=1.0;
      }`,
  });

  const passMat = new THREE.ShaderMaterial({
    depthTest: false, depthWrite: false,
    uniforms: {
      backgroundTexture: { value: rt.texture }, blurTexture: { value: rtBlur.texture },
      blurMix: { value: 0 }, texel: { value: new THREE.Vector2(0, 0) },
    },
    vertexShader: QUAD_VS,
    fragmentShader: `
      uniform sampler2D backgroundTexture; uniform sampler2D blurTexture;
      uniform float blurMix; uniform vec2 texel;
      varying vec2 vUv;
      /* An exact 2x2 box over the four source texels that make up this
         destination pixel. texel is 0 when the target is the same size as
         the canvas, and then this is the single read the registered source
         does -- four reads of one texel would cost four for nothing. */
      vec4 resolveTex(sampler2D tex, vec2 uv){
        if(texel.x==0.0) return texture2D(tex,uv);
        return 0.25*(texture2D(tex,uv+vec2(-texel.x,-texel.y))
                    +texture2D(tex,uv+vec2( texel.x,-texel.y))
                    +texture2D(tex,uv+vec2(-texel.x, texel.y))
                    +texture2D(tex,uv+vec2( texel.x, texel.y)));
      }
      void main(){
        /* Once the hand-off is complete the sharp image is wholly covered,
           so it is not read at all. */
        vec4 c=blurMix<1.0?resolveTex(backgroundTexture,vUv):vec4(0.0);
        if(blurMix>0.0) c=mix(c,texture2D(blurTexture,vUv),blurMix);
        gl_FragColor=vec4(c.rgb,1.0);
        #include <colorspace_fragment>
      }`,
  });
  const quadGeo = new THREE.BufferGeometry();
  quadGeo.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  quadGeo.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  const quad = new THREE.Mesh(quadGeo, passMat); quad.frustumCulled = false;
  const quadScene = new THREE.Scene(); quadScene.add(quad);
  const blurQuad = new THREE.Mesh(quadGeo, blurMat); blurQuad.frustumCulled = false;
  const blurScene = new THREE.Scene(); blurScene.add(blurQuad);
  const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const blurTw = { i: new Tw([0]), n: new Tw([1]), _w: false };

  function resize() {
    const box = host.getBoundingClientRect();
    VW = Math.max(1, Math.round(box.width)); VH = Math.max(1, Math.round(box.height));
    renderer.setSize(VW, VH, false);
    const pr = renderer.getPixelRatio();
    const RW = Math.round(VW * pr) * SS, RH = Math.round(VH * pr) * SS;
    rt.setSize(RW, RH);
    /* Half the canvas, not half the supersampled target: the blur is sized to
       what the reader sees. `resolution` is only ever read for its aspect. */
    const BW = Math.max(1, Math.round((VW * pr) / BLUR_DIV)), BH = Math.max(1, Math.round((VH * pr) / BLUR_DIV));
    rtBlur.setSize(BW, BH);
    rtRoom.setSize(BW, BH);
    blurMat.uniforms.resolution.value.set(BW, BH);
    /* Half a source texel, so the four taps sit on texel centres. Zero when
       the target is 1:1 with the canvas and the blit should stay a blit. */
    passMat.uniforms.texel.value.set(SS > 1 ? 0.5 / RW : 0, SS > 1 ? 0.5 / RH : 0);
    frameCamera();
    publishBays();
  }

  /* WHERE THE CASES ARE, IN PAGE PIXELS.

     The masthead's three labels are HTML, not texture, so they stay crisp and
     a screen reader can read them -- but that only helps if each one sits over
     its own case. Rather than guess with thirds, the camera is asked where the
     centre of each case projects to, and the answer is published as custom
     properties the stylesheet positions from. Recomputed on resize only: the
     pointer orbit moves these by a pixel or two and is not worth a style
     write every frame. */
  const PROJ = new THREE.Vector3();
  const anchor = opts.anchor || host;
  /* Projected at the carcass's FRONT face, not at the volumes' plane. A
     perspective camera spreads a point further from the centre the nearer it
     is, so the two depths do not land on the same pixel: the front edge of the
     uprights -- which is the line the eye reads a case's width from -- is
     about 9px further out at this size than the books standing 0.55 behind it.
     Aligning to the books would have put every label inside its own case. */
  const FACE_Z = geom.wallZ + K.plankDepth;
  const frameEl = opts.frame || null;
  function publishBays() {
    for (let b = 0; b < bays.length; b++) {
      PROJ.set(geom.bayCentre(b), geom.shelfY[0], FACE_Z).project(camera);
      anchor.style.setProperty(`--bk-bay-${b}`, `${(PROJ.x * 0.5 * VW).toFixed(2)}px`);
    }
    anchor.dataset.aligned = "yes";

    /* WHERE THE BOOKS ACTUALLY START, IN REAL PIXELS.

       The masthead used to sit at a guessed 36% down the stage. That number
       has no relationship to the geometry: it doesn't know the row count, the
       viewport's aspect, or compositionLift, so at some width or some corpus
       size it was always going to either overlap a book or leave a gap. This
       projects the tallest point a standing volume on the TOP shelf actually
       reaches -- not the plank, the book standing on it, lean and all -- so
       "above this pixel" is provably empty wall on every viewport this page
       supports, and "below it" is where the furniture begins. Published on
       `opts.frame`, the shared ancestor of the masthead, the case labels and
       the stage, so one number positions all three. */
    if (frameEl) {
      const topOfBooks = geom.shelfY[0] + K.bookH * Math.cos(K.lean);
      PROJ.set(0, topOfBooks, geom.bookZ).project(camera);
      frameEl.style.setProperty("--bk-top", `${((0.5 - PROJ.y * 0.5) * VH).toFixed(2)}px`);
    }
  }

  /* ---- pointer ---- */
  const ray = new THREE.Raycaster();
  ray.layers.enable(LAY_BG); ray.layers.enable(LAY_FG);
  const ptr = new THREE.Vector2();
  const DRAG = { on: false, moved: 0, lx: 0, ly: 0, rx: 0, ry: 0 };
  function dragReset() { DRAG.on = false; DRAG.moved = 0; DRAG.rx = 0; DRAG.ry = 0; }
  const local = (e) => {
    const b = host.getBoundingClientRect();
    return { x: e.clientX - b.left, y: e.clientY - b.top, inside: e.clientX >= b.left && e.clientX <= b.right && e.clientY >= b.top && e.clientY <= b.bottom };
  };

  function onMove(e) {
    const p = local(e);
    ORB.tx = (p.x / VW - 0.5) * 2; ORB.ty = (p.y / VH - 0.5) * 2;
    if (S.anim === "intro") return;
    ptr.x = (p.x / VW) * 2 - 1; ptr.y = -(p.y / VH) * 2 + 1;
    ray.setFromCamera(ptr, camera);
    const hits = ray.intersectObjects(books.map((b) => b.hit), false);
    const B = hits.length && p.inside ? hits[0].object.userData.book : null;
    if (S.active) {
      if (DRAG.on) {
        const dx = e.clientX - DRAG.lx, dy = e.clientY - DRAG.ly;
        DRAG.lx = e.clientX; DRAG.ly = e.clientY;
        DRAG.moved += Math.abs(dx) + Math.abs(dy);
        DRAG.ry += dx * 0.0090;
        DRAG.rx = clamp(DRAG.rx + dy * 0.0062, -0.62, 0.62);
        S.active.sWob.start([DRAG.rx, DRAG.ry, 0]);
        host.style.cursor = "grabbing";
        return;
      }
      if (B === S.active && S.anim === "active") {
        if (hits[0].uv) {
          const uv = hits[0].uv;
          S.active.sWob.start([DRAG.rx + Math.PI / 46 * (uv.y - 0.5) * 2 * (S.active.flipped ? -1 : 1),
            DRAG.ry + Math.PI / 36 * ((S.active.flipped ? 1 - uv.x : uv.x) - 0.5) * 2, 0]);
        }
        host.style.cursor = "grab";
      } else {
        host.style.cursor = "default";
        S.active.sWob.start([DRAG.rx, DRAG.ry, 0]);
      }
      return;
    }
    if (S.anim !== "inactive") return;
    setLifted(B);
    host.style.cursor = B ? "pointer" : "default";
    if (B && hits[0].uv) {
      const uv = hits[0].uv;
      B.sWob.start([Math.PI / 50 * (uv.y - 0.5) * 2, Math.PI / 40 * (uv.x - 0.5) * 2, 0]);
    }
  }
  function onLeave() { ORB.tx = 0; ORB.ty = 0; if (!S.active && S.anim === "inactive") setLifted(null); }
  function onDown(e) {
    const p = local(e);
    if (!p.inside) return;
    ptr.x = (p.x / VW) * 2 - 1; ptr.y = -(p.y / VH) * 2 + 1;
    ray.setFromCamera(ptr, camera);
    if (S.active) {
      const h = ray.intersectObject(S.active.body, false);
      if (h.length) {
        DRAG.on = true; DRAG.moved = 0; DRAG.lx = e.clientX; DRAG.ly = e.clientY;
        host.style.cursor = "grabbing";
        try { canvas.setPointerCapture(e.pointerId); } catch { /* not captureable */ }
        e.preventDefault();
      } else clearActive();
      return;
    }
    const hits = ray.intersectObjects(books.map((b) => b.hit), false);
    if (hits.length) setActive(hits[0].object.userData.book);
  }
  function onUp(e) {
    if (!DRAG.on) return;
    DRAG.on = false;
    try { canvas.releasePointerCapture(e.pointerId); } catch { /* never captured */ }
    host.style.cursor = "grab";
    if (DRAG.moved < 10) flipActive();
  }
  /* Space turns the volume in hand -- unless the reader is on a control, where
     Space is that control's own key. Until 25 Sep 2026 this took Space at the
     window for as long as a volume was out, so the desk's own buttons (Delete,
     Keep it, Put it back) could not be pressed with it (INCLUSIVE_DESIGN.md A3). */
  const ON_A_CONTROL = "a[href], button, input, select, textarea, summary, [role='button'], [contenteditable]";
  function onKey(e) {
    if (e.key === "Escape" && S.active) clearActive();
    if ((e.key === " " || e.code === "Space") && S.active) {
      const t = e.target;
      if (t && t.closest && t.closest(ON_A_CONTROL)) return;
      e.preventDefault();
      flipActive();
    }
  }
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerleave", onLeave);
  window.addEventListener("blur", onLeave);
  canvas.addEventListener("pointerdown", onDown);
  window.addEventListener("pointerup", onUp);
  const onCancel = () => { DRAG.on = false; };
  window.addEventListener("pointercancel", onCancel);
  window.addEventListener("keydown", onKey);

  /* ---- loop ---- */
  const wallFade = new Tw([0]);
  let frame = 0, last = performance.now(), visible = true, painted = false;
  function tick(now) {
    frame = visible && !document.hidden ? requestAnimationFrame(tick) : 0;
    const dt = Math.min((now - last) / 1000, 0.05); last = now;

    const k = (S.anim === "intro") ? 1 : Math.min(1, dt * 3.4);
    ORB.x += (ORB.tx - ORB.x) * k; ORB.y += (ORB.ty - ORB.y) * k;
    applyCamera();

    wallFade.update(now);
    const wf = wallFade.v[0];
    wallMat.uniforms.uOpacity.value = wf;
    oakH.uniforms.uOpacity.value = wf; oakV.uniforms.uOpacity.value = wf;

    for (const B of books) {
      B.tHover.update(now); B.tTilt.update(now); B.tActiveP.update(now); B.tActiveR.update(now);
      B.tRefl.update(now); B.tFade.update(now); B.tSeat.update(now); B.sWob.update(dt);
      B.gHover.position.set(B.tHover.v[0], B.tHover.v[1], B.tHover.v[2]);
      B.gTilt.rotation.set(B.tTilt.v[0], B.tTilt.v[1], B.tTilt.v[2]);
      B.gWob.rotation.set(B.sWob.v[0], B.sWob.v[1], B.sWob.v[2]);
      B.gRoot.position.set(B.tActiveP.v[0], B.tActiveP.v[1], B.tActiveP.v[2]);
      B.gRoot.rotation.set(B.tActiveR.v[0], B.tActiveR.v[1], B.tActiveR.v[2]);
      const op = B.tFade.v[0] * wf;
      B.clothMat.opacity = op;
      B.spineMat.uniforms.uOpacity.value = op;
      B.pages.uniforms.uOpacity.value = op;
      B.coverMat.uniforms.uOpacity.value = op;
      B.backMat.uniforms.uOpacity.value = op;
      const lift = B.tHover.v[1], away = clamp((B.tHover.v[2] - B.base[2]) / 0.075, 0, 1);
      B.wallSh.position.x = B.basePos[0] - 0.09 - away * 0.05;
      B.wallSh.position.y = B.basePos[1] + lift - 0.04 + away * 0.02;
      B.wallSh.scale.setScalar(1 + away * 0.13);
      const seat = B.tSeat.v[0];
      B.wallSh.material.opacity = (0.50 - away * 0.15) * op * seat;
      B.cs.material.opacity = (0.92 * (1 - away * 0.55)) * op * seat;
      B.crease.material.opacity = (0.55 * (1 - away)) * op * seat;
      B.reflMat.uniforms.uOpacity.value = B.tRefl.v[0] * op * seat;
      B.refl.position.z = B.footZ + 0.24 + B.tHover.v[2] * 2;
    }

    const wantBlur = (S.anim === "animatingForward" || S.anim === "active");
    if (blurTw._w !== wantBlur) {
      blurTw._w = wantBlur;
      blurTw.i.start([wantBlur ? 16 : 0], 460, (t) => t, 100);
      blurTw.n.start([wantBlur ? 6 : 1], 400, (t) => t, 100);
    }
    blurTw.i.update(now); blurTw.n.update(now);

    const act = (S.anim === "animatingForward" || S.anim === "active" || S.anim === "animatingBackward");
    /* The registered switch was ignoreBlur = !act: no volume in hand, no blur,
       whatever the tween says. Kept as that, and the half-resolution pass is
       skipped entirely on any frame where it would be mixed in at zero. */
    const intensity = act ? blurTw.i.v[0] : 0;
    const blurMix = clamp(intensity / BLUR_HANDOFF, 0, 1);
    /* Once the hand-off is complete not one sharp pixel of the room is on
       screen, only its blur -- so while the volume is flying out, the room is
       drawn at the blur's resolution. See rtRoom.

       ONLY while it is flying out, and not for as long as the blur holds.
       The first build kept the small room for the whole time a volume was in
       hand, and going back to the full-size target on the way down cost one
       frame of 15 to 34 ms, measured on the M1 Pro -- longer the longer the
       volume had been held, and still there with the GPU held at full clock
       by a second context, so it is the idle target being brought back and
       not the clock. It landed 470 ms into putting the volume back, in the
       middle of the movement. Switching back the moment the volume arrives
       puts that one frame where nothing on screen is moving: the flight has
       ended, the blur finished 140 ms earlier, and the hover tween has under
       one per cent of its travel left. The volume then leaves from a warm
       target. */
    const room = (blurMix >= 1 && S.anim === "animatingForward") ? rtRoom : rt;
    camera.layers.set(LAY_BG);
    renderer.setRenderTarget(room);
    renderer.clear(true, true, false);
    renderer.render(scene, camera);
    if (blurMix > 0) {
      blurMat.uniforms.backgroundTexture.value = room.texture;
      blurMat.uniforms.intensity.value = intensity;
      blurMat.uniforms.noiseScale.value = blurTw.n.v[0];
      renderer.setRenderTarget(rtBlur);
      renderer.render(blurScene, quadCam);
    }
    renderer.setRenderTarget(null);
    passMat.uniforms.blurMix.value = blurMix;
    renderer.clear(true, true, false);
    renderer.render(quadScene, quadCam);
    if (act) {
      renderer.clearDepth();
      camera.layers.set(LAY_FG);
      renderer.render(scene, camera);
    }

    /* THE ROOM IS ON THE CANVAS.

       Announced once, from inside the loop, after a real render rather than
       after mountShelf returns. Those are not the same moment: building the
       context, compiling the passes and uploading every cover texture is
       over a second of blocking work on a machine without a GPU, and for all
       of it the canvas exists at full size with nothing drawn on it. The page
       holds its loading state over this stage until this fires. */
    if (!painted) {
      painted = true;
      if (opts.onReady) opts.onReady();
      setTimeout(warm, 0);
    }
  }

  /* THE FIRST VOLUME TAKEN DOWN USED TO STALL.

     A volume in hand is drawn a second time, straight to the canvas, over the
     blurred room -- and the program that draws a material to the canvas is
     not the one that drew it into the half-float target, because the output
     colour space is part of what three.js compiles. So the first volume
     anyone took down compiled that whole set on the spot: a 56 ms long task
     12 ms after the click and a 50 ms frame at the very start of the flight,
     measured on the M1 Pro on 23 Sep 2026. The second volume reused the
     programs and did not stall at all.

     Compiled here instead, once the room is on screen and while the intro is
     still running -- setActive refuses a click until it ends. The order is
     deliberate: before the first frame, these would have queued ahead of the
     programs that frame is waiting on and held the loading state longer.
     Under KHR_parallel_shader_compile the driver links them off the main
     thread, and nothing waits on one until it is first drawn with. */
  let alive = true;
  function warm() {
    if (!alive) return;
    renderer.setRenderTarget(null);
    for (const B of books) renderer.compile(B.gRoot, camera, scene);
    renderer.setRenderTarget(rtBlur);
    renderer.compile(blurScene, quadCam);
    renderer.setRenderTarget(null);
    /* And the two small targets are allocated now rather than on the frame
       that first draws into them. A resize frees them again; they are then
       allocated lazily, as three.js would anyway. */
    renderer.initRenderTarget(rtBlur);
    renderer.initRenderTarget(rtRoom);
  }

  /* ---- build, then the registered intro ---- */
  volumes.forEach((v, i) => books.push(buildBook(v, i)));
  resize();
  wallFade.start([1], K.introWallFade, easeOutQuart);
  books.forEach((B, i) => { B.tFade.set([0]); B.tFade.start([1], K.introFade, easeOutQuart, i * K.introStagger); });
  setTimeout(() => { if (S.anim === "intro") S.anim = "inactive"; },
    K.introWallFade + books.length * K.introStagger);
  frame = requestAnimationFrame(tick);
  host.dataset.shelf = "on";

  const ro = new ResizeObserver(resize);
  ro.observe(host);
  const io = new IntersectionObserver(([entry]) => {
    visible = entry?.isIntersecting ?? true;
    if (visible && !frame) { last = performance.now(); frame = requestAnimationFrame(tick); }
  });
  io.observe(host);
  const onVis = () => {
    if (document.hidden && frame) { cancelAnimationFrame(frame); frame = 0; }
    else if (!document.hidden && visible && !frame) { last = performance.now(); frame = requestAnimationFrame(tick); }
  };
  document.addEventListener("visibilitychange", onVis);

  return {
    focus(id) {
      const B = books.find((b) => b.data.id === id);
      if (!B) return;
      if (S.active && S.active !== B) { clearActive(); setTimeout(() => setActive(B), K.activeDuration + 40); }
      else setActive(B);
    },
    lift(id) { if (S.anim === "inactive") setLifted(books.find((b) => b.data.id === id) || null); },
    flip() { flipActive(); },
    clear() { clearActive(); },
    open() { if (S.active && opts.onOpen) opts.onOpen(S.active.data); },
    activeId() { return S.active ? S.active.data.id : null; },

    /* THE VOLUME IN HAND, AS THE REST OF THE INTERFACE CAN SEE IT.

       The report page opens by continuing this volume's own movement rather
       than by replacing it with a document, so it needs two things this
       module is the only holder of: the cover plate that was actually painted
       for this run, and where that cover is standing on screen right now.

       The plate is read straight off the canvas the cover texture was built
       from -- the same pixels the shader samples, not a re-render. The
       rectangle is measured by projecting the cover mesh's own world corners
       through the live camera, so it survives the orbit, the lean, the yaw
       and whatever activeZ() has done to the depth. Returns null when no
       volume is out, which is the caller's cue to navigate plainly. */
    activeVolume() {
      const B = S.active;
      if (!B || !B.cover || !B.coverTex || !B.coverTex.image) return null;

      B.cover.updateWorldMatrix(true, false);
      const g = B.cover.geometry;
      if (!g.boundingBox) g.computeBoundingBox();
      const bb = g.boundingBox;

      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (let c = 0; c < 8; c++) {
        PROJ.set(c & 1 ? bb.max.x : bb.min.x,
          c & 2 ? bb.max.y : bb.min.y,
          c & 4 ? bb.max.z : bb.min.z)
          .applyMatrix4(B.cover.matrixWorld).project(camera);
        const px = (PROJ.x * 0.5 + 0.5) * VW;
        const py = (0.5 - PROJ.y * 0.5) * VH;
        if (px < minX) minX = px;
        if (px > maxX) maxX = px;
        if (py < minY) minY = py;
        if (py > maxY) maxY = py;
      }
      if (!(maxX > minX) || !(maxY > minY)) return null;

      /* The projection's origin is the canvas; the caller works in the
         viewport, so hand it viewport pixels. */
      const box = canvas.getBoundingClientRect();
      let cover = "";
      try {
        cover = B.coverTex.image.toDataURL("image/jpeg", 0.9);
      } catch { return null; }   /* tainted canvas: navigate plainly instead */

      return {
        id: B.data.id,
        cover,
        rect: {
          x: box.left + minX, y: box.top + minY,
          w: maxX - minX, h: maxY - minY,
        },
      };
    },

    /* RE-LIGHT THE ROOM WITHOUT MOVING ANYTHING.

       Promised by this function's own doc comment since the day it was
       written and never implemented; the page rebuilt the whole room
       instead. Only three things in the scene depend on the theme -- the
       clear colour, the wall bake and the oak -- and all three are
       textures or a colour, so they are swapped in place: the context, the
       covers, the camera and the volume in hand are untouched. The boards
       themselves are not themed (see SHELF_BOARD). */
    setTheme(theme) {
      const next = SHELF_PALETTE[theme === "field" ? "field" : "bench"];
      if (!alive || next === pal) return;
      pal = next;
      renderer.setClearColor(pal.clear, 1);
      const oldBake = wallMat.uniforms.uBake.value;
      wallMat.uniforms.uBake.value = wallTexture(geom, pal, 1024);
      oldBake.dispose();
      const oldWood = WOOD_TEX;
      WOOD_TEX = woodTexture(pal, 1024);
      oakH.uniforms.uWood.value = WOOD_TEX;
      oakV.uniforms.uWood.value = WOOD_TEX;
      oldWood.dispose();
      if (!frame && visible && !document.hidden) {
        last = performance.now();
        frame = requestAnimationFrame(tick);
      }
    },

    destroy() {
      alive = false;
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("blur", onLeave);
      canvas.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onCancel);
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("visibilitychange", onVis);
      ro.disconnect(); io.disconnect();
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
        for (const m of mats) {
          for (const u of Object.values(m.uniforms || {})) if (u.value && u.value.isTexture) u.value.dispose();
          if (m.map) m.map.dispose();
          m.dispose();
        }
      });
      rt.dispose(); rtRoom.dispose(); rtBlur.dispose(); blurMat.dispose(); renderer.dispose();
      canvas.remove();
      delete host.dataset.shelf;
    },
  };
}
