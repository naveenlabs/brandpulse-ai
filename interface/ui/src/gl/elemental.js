/*
   elemental.js — the water gate.

   PROVENANCE. This is a port, not an original effect. The shaders, the
   simulation, the SDF construction and the particle system are taken from the
   ThreeUI "elemental" collection, water variant:

       component  ElementsCollection, variant "water" (elemental-water)
       bundle     https://threeui.com/source-code/elemental-water.json
       canonical  src/shaders/elements/sources/elemental-marks.html
       sha-256    7a6871fe99fa5e1551b27b2601f2a22dd23320ea2c90b5432c9c8e071f0b1d1d

   All three registered files were fetched and their checksums verified before
   anything here was written. The water fragment shader, the ping-pong height
   field and the point-sprite particles are the authored GLSL. Two functions in
   it are ours and are marked as such where they appear: sdf(), which computes
   the mark analytically instead of sampling a chamfer texture, and the one line
   of edge antialiasing that feeds it. Both are explained at the point of change.
   Credit belongs to ThreeUI; the source and verified checksum are recorded above
   because an examiner is entitled to know which pixels are original to this project.

   WHAT WE CHANGED, AND WHY:

   1. The framework. The registered component is a React `.tsx`. The canonical
      source it is generated from is standalone WebGL2 + Canvas 2D with no
      imports at all, so that is what was ported. This interface has no React
      and adding it for one screen would have been a new runtime dependency for
      a decorative surface. The effect is identical; only the mounting differs.

   2. The mark, and how it reaches the GPU. The authored source rasterises an
      OpenAI glyph into a 512x512 chamfer distance field and samples it. This
      draws the BrandPulse mark, and computes its distance exactly in the
      fragment shader rather than looking it up. The reasoning is written out in
      full above markSDF(); the short version is that a sampled field caps the
      mark's sharpness at the field's resolution, and four convex pieces do not
      need a field at all. The refraction, the glow and the particles are
      unchanged -- they consume a distance, and they still get one.

   Nothing else was touched. The water fragment shader, the ping-pong height
   field and the point-sprite particles are as authored. The chamfer distance
   field is gone, not modified: with the mark computed exactly there is nothing
   left for it to store.
*/

import { reduced } from "../lib/motion.js";

/* ---------------------------------------------------------------- the mark

   Four bars, one per channel, cut by a vertical fault and knocked out of
   register across it. The bars are the four readings; the fault is the tear.

   The bar lengths are COMPOSITIONAL, not encoded. Only two of the four channel
   reliabilities have been measured on this project's own data (facial 0.342,
   vocal 0.489), so a mark whose four lengths claimed to be accuracies would be
   asserting two figures that do not exist. It says "these four do not agree",
   which is the measured finding, and it does not say by how much.

   viewBox 0 0 24 24, filled with the nonzero rule, matching the convention the
   authored rasteriser expects. Solid and chunky on purpose: a signed distance
   field measures distance to an edge, so hairlines and wordmarks refract into
   nothing. */
/* The four slices, as geometry rather than as a drawing.

   This array is the single source of truth for the mark. The SVG path handed to
   the rasteriser and the GLSL the shader runs are BOTH generated from it below,
   so the shape the particles spawn along and the shape the water refracts can
   never drift apart.

   Wound consistently (clockwise in this y-down space). The inside test in the
   shader is "all four edge cross-products share a sign", which is only true for
   a convex polygon with consistent winding -- reverse one and it renders
   inside-out. */
export const MARK_POLYS = [
  [[4.46, 3], [10.68, 7], [4.46, 7]],
  [[4.46, 7.6], [11.62, 7.6], [17.84, 11.6], [4.46, 11.6]],
  [[6.16, 12.4], [19.54, 12.4], [13.32, 16.4], [6.16, 16.4]],
  [[4.46, 17], [10.68, 17], [4.46, 21]],
];

/* The play triangle, sliced across into the four channels, with the third slice
   pushed out of line. Press play and the picture comes apart into the four
   things being read; one of them does not agree with the rest.

   The slip is COMPOSITIONAL, not encoded. Only two of the four channel
   reliabilities have ever been measured here -- facial 0.342, vocal 0.489 -- so
   a mark that claimed to show all four would be asserting two figures that do
   not exist. It says the four come apart, which is the measured finding, and it
   does not say by how much.

   Geometry: the triangle runs (6,3) to (20,12) to (6,21). Slices are cut at y
   bands that never straddle the apex row, so each piece stays a clean convex
   quadrilateral rather than folding round the point. The third slice carries a
   +1.7 x offset, and the 0.8 gaps between bands keep it from touching its
   neighbours. Every x is then shifted -1.54 so the SHAPE is centred in the
   24-box: the box is centred, not the ink, and a triangle whose own bounds run
   6 to 21.08 otherwise sits visibly right of frame. */
export const MARK = MARK_POLYS
  .map((poly) => "M" + poly.map(([x, y]) => `${x} ${y}`).join("L") + "Z")
  .join("");

/* ------------------------------------------------------- the mark, in the GPU

   WHY THIS IS NOT A TEXTURE.

   The authored implementation rasterises the glyph into a 512x512 chamfer
   distance field and samples it. That is the standard approach and it is what
   shipped here first, but it has a hard ceiling: only 60% of the field holds the
   shape, so the mark is really drawn at about 307 pixels and then magnified
   roughly four and a half times to fill a screen. Store that in R8 and the
   distances quantise in steps of about one pixel as well. Both show up as a soft,
   slightly stepped edge -- exactly the "not sharp" this was reported as.

   Four straight-sided convex pieces do not need any of that. The distance to
   them can be computed exactly, per pixel, from seven vertices. There is no
   resolution to run out of: it is as sharp on a 6K display as on a phone, the
   texture and its two chamfer passes disappear from load entirely, and the
   rectangular clamp artefacts the authored version had to work around cannot
   occur because nothing is being clamped.

   The rasteriser below survives, but only to scatter particle spawn points along
   the contour. Those want a few hundred sample positions, not a precise field,
   so its resolution stops mattering. */

const MARK_FILL = 0.6;                        // share of the field the 24-box uses
const MARK_ORIGIN = (1 - MARK_FILL) / 2;      // 0.2
const MARK_SCALE = MARK_FILL / 24;            // 0.025 mask-uv per mark unit

function glslVec(p) {
  return `vec2(${p[0].toFixed(4)},${p[1].toFixed(4)})`;
}

/* One min() per piece. The union of non-overlapping shapes under min() is exact,
   which is why the slices must never touch: two that shared an edge would report
   a near-zero interior distance along it and draw a hairline seam through the
   mark. */
const MARK_CALLS = MARK_POLYS.map((poly) => {
  const v = poly.map(glslVec).join(",");
  return poly.length === 3 ? `  d = min(d, sdTri(q, ${v}));`
                           : `  d = min(d, sdQuad(q, ${v}));`;
}).join("\n");

/* ----------------------------------------------- rasterise -> SDF (authored) */

/* Only the particle spawn points are rasterised now, so this is a scatter
   resolution rather than the mark's resolution. The mark itself has none. */
const SDF_SIZE = 512;

function rasterizeLogo(pathStr) {
  const c = document.createElement("canvas");
  c.width = c.height = SDF_SIZE;
  const ctx = c.getContext("2d");
  const box = SDF_SIZE * 0.6;
  const s = box / 24;
  const off = (SDF_SIZE - box) / 2;
  ctx.setTransform(s, 0, 0, s, off, off);
  ctx.fillStyle = "#fff";
  ctx.fill(new Path2D(pathStr));
  return ctx.getImageData(0, 0, SDF_SIZE, SDF_SIZE);
}

/* contour pixels + outward normals, in y-up mask uv */
function edgePoints(img) {
  const S = SDF_SIZE;
  const pts = [];
  const a = (x, y) => img.data[(y * S + x) * 4 + 3] > 127;
  for (let y = 1; y < S - 1; y++) {
    for (let x = 1; x < S - 1; x++) {
      if (!a(x, y)) continue;
      const l = a(x - 1, y);
      const r = a(x + 1, y);
      const u = a(x, y - 1);
      const dn = a(x, y + 1);
      if (l && r && u && dn) continue;
      const gx = (r ? 1 : 0) - (l ? 1 : 0);
      const gy = (dn ? 1 : 0) - (u ? 1 : 0);
      let nx = -gx;
      let ny = gy;                              // outward, y flipped to y-up
      const len = Math.hypot(nx, ny);
      if (!len) { nx = 0; ny = 1; } else { nx /= len; ny /= len; }
      pts.push((x + 0.5) / S, 1 - (y + 0.5) / S, nx, ny);
    }
  }
  return pts;
}

function makeParticleData(pts, count) {
  const data = new Float32Array(count * 5);
  const nPts = pts.length / 4;
  for (let i = 0; i < count; i++) {
    const j = (Math.random() * nPts) | 0;
    data[i * 5] = pts[j * 4];
    data[i * 5 + 1] = pts[j * 4 + 1];
    data[i * 5 + 2] = pts[j * 4 + 2];
    data[i * 5 + 3] = pts[j * 4 + 3];
    data[i * 5 + 4] = Math.random() * 100 + i * 0.618;
  }
  return data;
}

/* ------------------------------------------------------- shaders (authored) */

const VERT = `#version 300 es
out vec2 vUv;
void main(){
  vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  vUv = p;
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

const GLSL_COMMON = `
precision highp float;
uniform float uTime;
uniform float uAspect;
uniform vec2  uScale;
uniform vec2  uShift;
uniform vec3  uPointer;
in vec2 vUv;
out vec4 frag;

float hash21(vec2 p){
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash21(i), b = hash21(i + vec2(1,0));
  float c = hash21(i + vec2(0,1)), d = hash21(i + vec2(1,1));
  return mix(mix(a,b,f.x), mix(c,d,f.x), f.y);
}
float fbm(vec2 p){
  float v = 0.0, a = 0.5;
  mat2 r = mat2(0.8, -0.6, 0.6, 0.8);
  for (int i = 0; i < 5; i++){ v += a * vnoise(p); p = r * p * 2.03; a *= 0.5; }
  return v;
}
/* Exact signed distance to a convex polygon: nearest point on each edge, then
   the sign from whether every edge cross-product agrees. */
float sgn2(vec2 e, vec2 v){ return e.x * v.y - e.y * v.x; }

float sdTri(vec2 p, vec2 a, vec2 b, vec2 c){
  vec2 e0 = b - a, e1 = c - b, e2 = a - c;
  vec2 v0 = p - a, v1 = p - b, v2 = p - c;
  vec2 q0 = v0 - e0 * clamp(dot(v0,e0)/dot(e0,e0), 0.0, 1.0);
  vec2 q1 = v1 - e1 * clamp(dot(v1,e1)/dot(e1,e1), 0.0, 1.0);
  vec2 q2 = v2 - e2 * clamp(dot(v2,e2)/dot(e2,e2), 0.0, 1.0);
  float d = min(min(dot(q0,q0), dot(q1,q1)), dot(q2,q2));
  float s0 = sgn2(e0,v0), s1 = sgn2(e1,v1), s2 = sgn2(e2,v2);
  float inside = (min(min(s0,s1),s2) > 0.0 || max(max(s0,s1),s2) < 0.0) ? -1.0 : 1.0;
  return inside * sqrt(d);
}

float sdQuad(vec2 p, vec2 a, vec2 b, vec2 c, vec2 e){
  vec2 e0 = b - a, e1 = c - b, e2 = e - c, e3 = a - e;
  vec2 v0 = p - a, v1 = p - b, v2 = p - c, v3 = p - e;
  vec2 q0 = v0 - e0 * clamp(dot(v0,e0)/dot(e0,e0), 0.0, 1.0);
  vec2 q1 = v1 - e1 * clamp(dot(v1,e1)/dot(e1,e1), 0.0, 1.0);
  vec2 q2 = v2 - e2 * clamp(dot(v2,e2)/dot(e2,e2), 0.0, 1.0);
  vec2 q3 = v3 - e3 * clamp(dot(v3,e3)/dot(e3,e3), 0.0, 1.0);
  float d = min(min(dot(q0,q0), dot(q1,q1)), min(dot(q2,q2), dot(q3,q3)));
  float s0 = sgn2(e0,v0), s1 = sgn2(e1,v1), s2 = sgn2(e2,v2), s3 = sgn2(e3,v3);
  float inside = (min(min(s0,s1),min(s2,s3)) > 0.0
               || max(max(s0,s1),max(s2,s3)) < 0.0) ? -1.0 : 1.0;
  return inside * sqrt(d);
}

/* Mask uv -> the 24-unit space the mark is drawn in. y is flipped because the
   path is written y-down, the way a canvas draws, while mask uv runs y-up. */
float markSDF(vec2 m){
  vec2 q = (vec2(m.x, 1.0 - m.y) - ${MARK_ORIGIN.toFixed(4)}) / ${MARK_SCALE.toFixed(6)};
  float d = 1e9;
${MARK_CALLS}
  return d * ${MARK_SCALE.toFixed(6)};
}

/* Exact everywhere, including far outside the shape, so there is nothing to
   clamp and no rectangular artefact to correct for. */
float sdf(vec2 uv){
  vec2 m = 0.5 + (uv - 0.5 - uShift) * uScale;
  return markSDF(m);
}
float edgeFade(vec2 uv){
  return smoothstep(0.0, 0.05, uv.x) * smoothstep(1.0, 0.95, uv.x)
       * smoothstep(0.0, 0.05, uv.y) * smoothstep(1.0, 0.95, uv.y);
}
`;

/* water simulation step (ping-pong, r = h, g = h_prev) */
const FRAG_SIM = `#version 300 es
precision highp float;
uniform sampler2D uState;
uniform vec2 uTexel;
uniform vec3 uDrop;
in vec2 vUv;
out vec4 frag;
void main(){
  vec2 s = texture(uState, vUv).rg;
  float l = texture(uState, vUv - vec2(uTexel.x, 0.0)).r;
  float r = texture(uState, vUv + vec2(uTexel.x, 0.0)).r;
  float u = texture(uState, vUv + vec2(0.0, uTexel.y)).r;
  float d = texture(uState, vUv - vec2(0.0, uTexel.y)).r;
  float next = (l + r + u + d) * 0.5 - s.g;
  next *= 0.984;
  if (uDrop.z != 0.0){
    float dd = distance(vUv, uDrop.xy);
    next += uDrop.z * exp(-dd * dd * 3800.0);
  }
  frag = vec4(next, s.r, 0.0, 1.0);
}`;

const FRAG_WATER = `#version 300 es
${GLSL_COMMON}
uniform sampler2D uState;
uniform vec2 uSimTexel;
vec2 simUV(vec2 uv){
  return 0.5 + (uv - 0.5) * vec2(uAspect, 1.0) / max(uAspect, 1.0);
}
void main(){
  vec2 suv = simUV(vUv);
  float h  = texture(uState, suv).r;
  float hx = texture(uState, suv + vec2(uSimTexel.x, 0.0)).r - texture(uState, suv - vec2(uSimTexel.x, 0.0)).r;
  float hy = texture(uState, suv + vec2(0.0, uSimTexel.y)).r - texture(uState, suv - vec2(0.0, uSimTexel.y)).r;
  vec2 grad = vec2(hx, hy);
  vec3 nrm = normalize(vec3(-grad * 30.0, 1.0));

  vec2 ruv = vUv + grad * 0.22;
  float d  = sdf(ruv);

  vec3 col = mix(vec3(0.006, 0.030, 0.055), vec3(0.012, 0.078, 0.125), vUv.y * 0.8 + h * 0.25);
  col += vec3(0.02, 0.10, 0.13) * fbm(vUv * vec2(uAspect, 1.0) * 3.0 + uTime * 0.05) * 0.3;

  /* One pixel of edge, whatever the mark's size on screen. The authored
     constant 0.005 is a fixed width in uv, so it read as a clean edge on a
     third-width panel and as several soft pixels filling a display. The
     ceiling keeps a steep ripple, whose gradient inflates fwidth, from
     smearing the outline instead of refracting it. */
  float aa = clamp(fwidth(d), 0.00015, 0.006);
  float logo = smoothstep(aa, -aa, d);
  float glow = exp(-max(d, 0.0) / 0.09) * 0.26;
  vec3 markCol = mix(vec3(0.55, 0.92, 1.0), vec3(0.95, 1.0, 1.0), logo * 0.6);
  col += markCol * (logo * 0.92 + glow);

  col += vec3(0.09, 0.30, 0.40) * clamp(h * 1.8, -0.06, 1.0);
  col += vec3(0.25, 0.55, 0.65) * pow(clamp(h * 2.6, 0.0, 1.0), 2.0) * 0.5;

  vec3 L = normalize(vec3(-0.35, 0.55, 0.75));
  vec3 H = normalize(L + vec3(0.0, 0.0, 1.0));
  float spec = pow(max(dot(nrm, H), 0.0), 150.0);
  col += spec * vec3(0.65, 0.9, 1.0) * 0.9;

  col *= 0.35 + 0.65 * edgeFade(vUv);
  col += (hash21(vUv * 617.0 + uTime) - 0.5) / 128.0;
  frag = vec4(col, 1.0);
}`;

const PART_VERT = `#version 300 es
precision highp float;
layout(location=0) in vec2 aPos;
layout(location=1) in vec2 aNorm;
layout(location=2) in float aSeed;
uniform float uTime;
uniform vec2  uScale;
uniform vec2  uShift;
uniform float uDpr;
uniform float uWind;
uniform vec4  uCfgA;
uniform vec4  uCfgB;
out float vFade;
out float vMixC;
float h1(float n){ return fract(sin(n) * 43758.5453); }
void main(){
  float hs   = h1(aSeed * 1.31);
  float life = mix(uCfgA.y, uCfgA.z, hs);
  float tt   = uTime / life + aSeed * 13.7;
  float ph   = fract(tt);
  float cyc  = floor(tt);
  float r1 = h1(aSeed + cyc * 0.317);
  float r2 = h1(aSeed * 2.13 + cyc * 0.771);
  float on = step(uCfgB.w, r2);

  vec2 dir = normalize(mix(vec2(0.0, 1.0), aNorm, uCfgA.w) + (vec2(r1, h1(r1 * 7.0)) - 0.5) * 0.8);
  float trav = uCfgA.x * (0.45 + 0.9 * r1);
  vec2 p = aPos + aNorm * 0.004 + dir * trav * ph;
  p.x += sin(ph * 10.0 + r1 * 40.0 + uTime * 0.5) * uCfgB.x * ph;
  p.x += uWind * 0.08 * ph;

  vec2 uv = 0.5 + uShift + (p - 0.5) / uScale;
  vFade = on * smoothstep(0.0, 0.12, ph) * smoothstep(1.0, 0.5, ph) * mix(0.35, 1.0, r2);
  vMixC = h1(aSeed * 3.7 + cyc);
  gl_Position = vec4(uv * 2.0 - 1.0, 0.0, 1.0);
  gl_PointSize = mix(uCfgB.y, uCfgB.z, h1(aSeed * 5.11 + cyc)) * uDpr * (1.0 - 0.45 * ph);
}`;

const PART_FRAG = `#version 300 es
precision highp float;
uniform vec3 uColA;
uniform vec3 uColB;
in float vFade;
in float vMixC;
out vec4 frag;
void main(){
  vec2 q = gl_PointCoord * 2.0 - 1.0;
  float r2 = dot(q, q);
  if (r2 > 1.0) discard;
  float a = exp(-r2 * 3.5) * (1.0 - r2);
  frag = vec4(mix(uColA, uColB, vMixC) * a * vFade, 1.0);
}`;

/* ----------------------------------------------------- GL helpers (authored) */

function compile(gl, type, src) {
  const sh = gl.createShader(type);
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    if (import.meta.env && import.meta.env.DEV) console.error(gl.getShaderInfoLog(sh));
    return null;
  }
  return sh;
}

function program(gl, vertSrc, fragSrc) {
  const p = gl.createProgram();
  const vs = compile(gl, gl.VERTEX_SHADER, vertSrc);
  const fs = compile(gl, gl.FRAGMENT_SHADER, fragSrc);
  if (!vs || !fs) return null;
  gl.attachShader(p, vs);
  gl.attachShader(p, fs);
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    if (import.meta.env && import.meta.env.DEV) console.error(gl.getProgramInfoLog(p));
    return null;
  }
  return p;
}

const DPR = Math.min(window.devicePixelRatio || 1, 1.75);
const SIM_RES = 512;

/* The water panel's authored settings. Left at the registered defaults, which
   is what the configured usage asks for: speed 1, size 1, particleAmount 1,
   hue 0, saturation 1, brightness 1. */
const WATER = {
  /* Two layout values differ from the authored panel, and only these two.
     The source composes for a third-width column beside two siblings; this is
     a full screen with the product's own words along the bottom. zoom sets how
     much of the frame the mark takes (larger number, smaller mark) and shift
     lifts it clear of the type. The effect itself is untouched. */
  zoom: 1.22,
  /* x is an optical correction, not a centring one: the path is already
     centred on its bounds, but a triangle pointing right carries its mass on
     the left and reads off-centre when it is measured dead centre. */
  shift: [0.012, 0.055],
  particles: {
    count: 160, travel: 0.1, lifeMin: 4.0, lifeMax: 8.0, alongNormal: 0.15,
    wiggle: 0.02, sizeMin: 1.5, sizeMax: 3.5, sparse: 0.5,
    colA: [0.1, 0.24, 0.3], colB: [0.22, 0.4, 0.48],
  },
};

/* --------------------------------------------------------------- the panel */

class Panel {
  constructor(el, canvas, fragSrc, logo, opts) {   // logo: { edges }
    this.el = el;
    this.canvas = canvas;
    this.opts = opts;
    this.pointer = { x: 0.5, y: 0.5, active: 0 };
    this.wind = 0;
    this.windTarget = 0;
    this.dropQueue = [];
    this.nextAutoDrop = 0.6;
    this.needsResize = false;
    this.ok = false;
    this.listeners = [];

    const gl = canvas.getContext("webgl2", { alpha: false, antialias: false });
    if (!gl) return;
    this.gl = gl;

    this.prog = program(gl, VERT, fragSrc);
    if (!this.prog) return;
    this.uni = {};
    for (const n of ["uTime", "uAspect", "uScale", "uShift", "uPointer", "uState", "uSimTexel", "uWind"]) {
      this.uni[n] = gl.getUniformLocation(this.prog, n);
    }

    /* The height field needs a float-renderable target. Without the extension
       the ripples cannot run, and a gate that cannot draw must not be shown:
       ok stays false and the caller skips straight to the page. */
    if (!gl.getExtension("EXT_color_buffer_float")) return;
    this.simProg = program(gl, VERT, FRAG_SIM);
    if (!this.simProg) return;
    this.simUni = {
      uState: gl.getUniformLocation(this.simProg, "uState"),
      uTexel: gl.getUniformLocation(this.simProg, "uTexel"),
      uDrop: gl.getUniformLocation(this.simProg, "uDrop"),
    };
    this.simTex = [];
    this.simFbo = [];
    for (let i = 0; i < 2; i++) {
      const t = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG16F, SIM_RES, SIM_RES, 0, gl.RG, gl.HALF_FLOAT, null);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      const f = gl.createFramebuffer();
      gl.bindFramebuffer(gl.FRAMEBUFFER, f);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
      this.simTex.push(t);
      this.simFbo.push(f);
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    this.simSrc = 0;

    const P = opts.particles;
    if (P) {
      this.partProg = program(gl, PART_VERT, PART_FRAG);
      if (!this.partProg) return;
      this.partUni = {};
      for (const n of ["uTime", "uScale", "uShift", "uDpr", "uWind", "uCfgA", "uCfgB", "uColA", "uColB"]) {
        this.partUni[n] = gl.getUniformLocation(this.partProg, n);
      }
      const data = makeParticleData(logo.edges, P.count);
      this.partVao = gl.createVertexArray();
      gl.bindVertexArray(this.partVao);
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 20, 0);
      gl.enableVertexAttribArray(1);
      gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 20, 8);
      gl.enableVertexAttribArray(2);
      gl.vertexAttribPointer(2, 1, gl.FLOAT, false, 20, 16);
      gl.bindVertexArray(null);
    }

    this.resize();
    /* Resize inside the rAF, before drawing, never in the RO callback — RO
       fires after rAF, so resizing there clears the canvas post-draw and every
       transition frame paints black. (Authored comment, and it still holds.) */
    this.ro = new ResizeObserver(() => {
      if (reduced()) this.resize(); else this.needsResize = true;
    });
    this.ro.observe(el);
    this.bindPointer();
    this.ok = true;
  }

  on(target, type, fn) {
    target.addEventListener(type, fn);
    this.listeners.push([target, type, fn]);
  }

  resize() {
    const r = this.el.getBoundingClientRect();
    const w = Math.max(2, Math.round(r.width * DPR));
    const h = Math.max(2, Math.round(r.height * DPR));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this.aspect = w / h;
    if (reduced() && this.ok) this.draw(0.001);
  }

  bindPointer() {
    const uv = (e) => {
      const r = this.el.getBoundingClientRect();
      return { x: (e.clientX - r.left) / r.width, y: 1 - (e.clientY - r.top) / r.height };
    };
    let last = null;
    let lastT = 0;
    this.on(this.el, "pointermove", (e) => {
      const p = uv(e);
      const now = performance.now();
      this.pointer.x = p.x;
      this.pointer.y = p.y;
      this.pointer.active = 1;
      if (last) {
        const dt = Math.max(8, now - lastT);
        const dx = p.x - last.x;
        const dy = p.y - last.y;
        const speed = Math.hypot(dx, dy) / (dt / 1000);
        if (speed > 0.05 && this.dropQueue.length < 6) {
          this.dropQueue.push({ x: p.x, y: p.y, s: Math.min(speed * 0.14, 0.55) });
        }
        this.windTarget = Math.max(-1, Math.min(1, (dx / (dt / 1000)) * 0.55));
      }
      last = p;
      lastT = now;
    });
    this.on(this.el, "pointerdown", (e) => {
      const p = uv(e);
      this.dropQueue.push({ x: p.x, y: p.y, s: 0.9 });
      this.pointer.x = p.x;
      this.pointer.y = p.y;
      this.pointer.active = 1.6;
    });
    this.on(this.el, "pointerup", () => { this.pointer.active = 1; });
    this.on(this.el, "pointerleave", () => {
      this.pointer.active = 0;
      last = null;
      this.windTarget = 0;
    });
  }

  /* panel uv -> square sim uv (must match simUV() in the water shader) */
  toSimUV(x, y) {
    const a = this.aspect;
    const m = Math.max(a, 1);
    return { x: 0.5 + ((x - 0.5) * a) / m, y: 0.5 + (y - 0.5) / m };
  }

  stepSim(t) {
    const gl = this.gl;
    if (t > this.nextAutoDrop) {
      this.dropQueue.push({
        x: 0.12 + Math.random() * 0.76,
        y: 0.12 + Math.random() * 0.76,
        s: 0.12 + Math.random() * 0.3,
      });
      this.nextAutoDrop = t + 0.5 + Math.random() * 1.4;
    }
    gl.useProgram(this.simProg);
    gl.viewport(0, 0, SIM_RES, SIM_RES);
    gl.uniform2f(this.simUni.uTexel, 1 / SIM_RES, 1 / SIM_RES);
    for (let i = 0; i < 2; i++) {
      const drop = this.dropQueue.shift();
      if (drop) {
        const s = this.toSimUV(drop.x, drop.y);
        gl.uniform3f(this.simUni.uDrop, s.x, s.y, drop.s);
      } else {
        gl.uniform3f(this.simUni.uDrop, 0, 0, 0);
      }
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.simFbo[1 - this.simSrc]);
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, this.simTex[this.simSrc]);
      gl.uniform1i(this.simUni.uState, 1);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      this.simSrc = 1 - this.simSrc;
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }

  scaleVec() {
    const zoom = this.opts.zoom;
    const a = this.aspect;
    const fit = Math.min(a, 1);
    return [(a / fit) * zoom, (1 / fit) * zoom];
  }

  draw(t) {
    const gl = this.gl;
    if (this.needsResize) { this.needsResize = false; this.resize(); }
    this.stepSim(t);

    this.wind += (this.windTarget - this.wind) * 0.04;
    this.windTarget *= 0.97;

    gl.useProgram(this.prog);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);

    const sc = this.scaleVec();
    gl.uniform1f(this.uni.uTime, t);
    gl.uniform1f(this.uni.uAspect, this.aspect);
    gl.uniform2f(this.uni.uScale, sc[0], sc[1]);
    gl.uniform2f(this.uni.uShift, this.opts.shift[0], this.opts.shift[1]);
    gl.uniform3f(this.uni.uPointer, this.pointer.x, this.pointer.y, this.pointer.active);
    if (this.uni.uWind) gl.uniform1f(this.uni.uWind, this.wind);

    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.simTex[this.simSrc]);
    gl.uniform1i(this.uni.uState, 1);
    gl.uniform2f(this.uni.uSimTexel, 1 / SIM_RES, 1 / SIM_RES);
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    const P = this.opts.particles;
    if (P) {
      gl.useProgram(this.partProg);
      gl.uniform1f(this.partUni.uTime, t);
      gl.uniform2f(this.partUni.uScale, sc[0], sc[1]);
      gl.uniform2f(this.partUni.uShift, this.opts.shift[0], this.opts.shift[1]);
      gl.uniform1f(this.partUni.uDpr, DPR);
      gl.uniform1f(this.partUni.uWind, this.wind);
      gl.uniform4f(this.partUni.uCfgA, P.travel, P.lifeMin, P.lifeMax, P.alongNormal);
      gl.uniform4f(this.partUni.uCfgB, P.wiggle, P.sizeMin, P.sizeMax, P.sparse);
      gl.uniform3f(this.partUni.uColA, P.colA[0], P.colA[1], P.colA[2]);
      gl.uniform3f(this.partUni.uColB, P.colB[0], P.colB[1], P.colB[2]);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.ONE, gl.ONE);
      gl.bindVertexArray(this.partVao);
      gl.drawArrays(gl.POINTS, 0, P.count);
      gl.bindVertexArray(null);
      gl.disable(gl.BLEND);
    }
  }

  destroy() {
    for (const [target, type, fn] of this.listeners) target.removeEventListener(type, fn);
    this.listeners = [];
    if (this.ro) this.ro.disconnect();
    /* Drop the drawing buffer rather than leaving it resident. The gate is
       dismissed once and never comes back, and the page behind it wants the
       memory for 2560px film frames. */
    const lose = this.gl && this.gl.getExtension("WEBGL_lose_context");
    if (lose) lose.loseContext();
    this.gl = null;
  }
}

/* -------------------------------------------------------------------- mount

   Returns null when the effect cannot run — no WebGL2, no float render target,
   or a shader that would not compile. The caller treats null as "there is no
   gate" and shows the page directly. Nobody is ever held behind a canvas that
   failed to draw. */
export function mountElemental(el, { mark = MARK } = {}) {
  let canvas;
  let panel;
  try {
    canvas = document.createElement("canvas");
    canvas.className = "gate__canvas";
    /* Decoration. The gate states its purpose in real text next to this. */
    canvas.setAttribute("aria-hidden", "true");
    el.prepend(canvas);
    const img = rasterizeLogo(mark);
    panel = new Panel(el, canvas, FRAG_WATER, { edges: edgePoints(img) }, WATER);
  } catch (error) {
    if (import.meta.env && import.meta.env.DEV) console.error(error);
    panel = null;
  }
  if (!panel || !panel.ok) {
    if (panel) panel.destroy();
    if (canvas) canvas.remove();
    return null;
  }

  let raf = 0;
  let running = false;
  const t0 = performance.now();

  const loop = () => {
    panel.draw((performance.now() - t0) / 1000);
    raf = requestAnimationFrame(loop);
  };

  const start = () => {
    if (running) return;
    running = true;
    /* Reduced motion gets the picture, not the animation: one frame, drawn
       once, with the mark legible in still water. */
    if (reduced()) { panel.draw(0.001); running = false; return; }
    raf = requestAnimationFrame(loop);
  };

  const stop = () => {
    running = false;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
  };

  start();

  return {
    stop,
    destroy() {
      stop();
      panel.destroy();
      canvas.remove();
    },
  };
}
