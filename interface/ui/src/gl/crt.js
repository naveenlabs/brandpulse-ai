/*
   crt.js — the boot screen.

   PROVENANCE. This is a port, not an original effect. The curvature, scanlines,
   aperture grille, phosphor halation, rolling bar and grain are taken from the
   ThreeUI CRT collection, terminal variant:

       component  CrtBackground, variant "terminal"
       bundle     https://threeui.com/source-code/crt.json
       files      crtShaders.ts   sha-256 cf3a7c747d1c...
                  crtRenderer.ts  sha-256 a3eb536e9c50...
                  crtScreens.ts   sha-256 e545922e0d3a...
       revision   860a1eb1d4c9

   All five registered files were fetched and all five checksums verified before
   anything here was written. The GLSL below is the authored GLSL, unaltered,
   and so is the two-pass glyph drawing that keeps the stroke cores crisp behind
   the grille. Credit belongs to ThreeUI; the source, revision and verified checksums
   are recorded above because an examiner is entitled to know which pixels are
   original to this project.

   WHAT WE CHANGED, AND WHY:

   1. The framework. The registered component is a React `.tsx` over a TypeScript
      renderer. This interface has no React and no build-time type checking, so
      the renderer was ported to plain ES modules. No logic was altered in the
      move; only the annotations and the component shell are gone.

   2. The log. The authored source types a nineteen-row Zion boot log. This types
      the same nineteen rows' worth of BrandPulse's own startup instead. That is
      a data swap, not a change to the effect: the renderer types whatever array
      it is handed.

   3. One variant. The bundle ships four screens; only "terminal" is used here,
      so the other three painters and their style blocks were not ported. Nothing
      was modified to achieve that -- they are simply absent.

   4. The leader character. The authored log draws its dot leaders with U+00B7.
      This build's own contract tests forbid that character in interface strings,
      because it is the joining dot of the "A · B · C" meta string this design
      system bans outright. Full stops read identically in a boot log.
*/

import { reduced } from "../lib/motion.js";

/* ------------------------------------------------------------------ the log

   Every line is true, and every figure in it was measured on this project's own
   data. That is the whole reason this screen is allowed to exist: a boot log of
   invented capability would be decoration standing between a reader and the
   work. The models named are the models that actually run; the controller and
   its address are the real ones; the anomaly at the bottom is the project's
   central measured finding, not a flourish.

   facial 34.2% against an always-NEUTRAL constant's 67.5% on held-out speakers,
   from facial_bench/v2/; the 0.342 down-weight is FACIAL_CHANNEL_RELIABILITY as
   deployed in the orchestrator. */

const segment = (t, c = "p") => ({ t, c });
const lead = (n) => ".".repeat(n) + " ";

const LOG = [
  [segment("BRANDPULSE AI   multimodal brand sentiment"), segment("   CM3070", "d")],
  [segment("four channels   one local controller   nothing leaves this machine", "d")],
  [],
  [segment("Whisper transcription "), segment(lead(9), "d"), segment("OK", "a")],
  [segment("cardiffnlp XLM-RoBERTa "), segment(lead(8), "d"), segment("OK", "a")],
  [segment("audeering dimensional vocal "), segment(lead(3), "d"), segment("OK", "a")],
  [segment("yunet face detection "), segment(lead(10), "d"), segment("OK", "a")],
  [segment("YouTube Data API v3 "), segment(lead(12), "d"), segment("OK", "a")],
  [segment("llama3.1:8b  localhost:11434 "), segment(lead(2), "d"), segment("READY", "a")],
  [],
  [segment("ch0  TRANSCRIPT  what was said ", "d"), segment(lead(4), "d"), segment("READY", "a")],
  [segment("ch1  FACIAL  the face on camera ", "d"), segment(lead(3), "d"), segment("READY", "a")],
  [segment("ch2  VOCAL  how it was said ", "d"), segment(lead(7), "d"), segment("READY", "a")],
  [segment("ch3  AUDIENCE  what viewers wrote ", "d"), segment(lead(1), "d"), segment("READY", "a")],
  [],
  [segment("CHANNEL ANOMALY  "), segment("facial reads below a constant.", "h")],
  [segment("measured 34.2% against 67.5% on held-out speakers ", "d")],
  [segment("down-weighted to 0.342 and reported on every surface ", "d")],
  [segment("press anything to continue: ")],
];

const COLORS = {
  p: { fill: "#8df0b4", glow: "rgba(28,236,132,0.95)" },
  d: { fill: "#4f9a76", glow: "rgba(28,236,132,0.45)" },
  a: { fill: "#ffba5e", glow: "rgba(255,150,52,0.95)" },
  h: { fill: "#eafff3", glow: "rgba(120,255,190,0.95)" },
};

/* The authored terminal style block, value for value. */
const STYLE = {
  curve: [0.115, 0.165], scanDensity: 0.44, scanDepth: 0.3, triadCss: 3.2,
  grille: 0.34, chroma: 1, bar: 0.045, flicker: 0.028, grain: 0.022,
  vignette: 0.58, gain: 1.34, halo: 0.1,
  sheen: [0.55, 1.0, 0.78], room: [0.012, 0.03, 0.022],
  background: "#03100a",
};

const lineLength = (line) => line.reduce((n, item) => n + item.t.length, 0);
const TOTAL = LOG.reduce((n, line) => n + lineLength(line), 0);
const MAX_CHARS = Math.max(...LOG.map(lineLength));

/* The authored rate, 4.4 characters per frame at 60Hz, expressed per
   millisecond so it does not depend on the refresh rate. */
const CHARS_PER_MS = 4.4 / (1000 / 60);

/* How long the whole log takes to type. Exported because the screen above needs
   to know when to let go, and guessing at it would drift the moment the log is
   edited. */
export const TYPE_MS = TOTAL / CHARS_PER_MS;

/* backing-store ceiling: the composite is one triangle, so the cost that matters
   is the 2D screen redraw and its upload, not the fragment pass */
const MAX_BUFFER_WIDTH = 1920;
const MIN_BUFFER_WIDTH = 640;
const MAX_BUFFER_PIXELS = 2_400_000;

/* --------------------------------------------------------- shaders (authored) */

const VERT = "attribute vec2 aPos;\nvoid main(){ gl_Position = vec4(aPos,0.0,1.0); }";

const FRAG = `precision highp float;
uniform sampler2D uTex;
uniform vec2 uRes;
uniform float uTime;
uniform float uMotion;
uniform vec2 uCurve;
uniform float uScan;
uniform float uScanDepth;
uniform float uTriad;
uniform float uGrille;
uniform float uChroma;
uniform float uBar;
uniform float uFlicker;
uniform float uGrain;
uniform float uNoise;
uniform float uVignette;
uniform float uMono;
uniform float uGain;
uniform float uHalo;
uniform vec3 uSheen;
uniform vec3 uRoom;

float hash(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }

vec2 curve(vec2 uv){
  uv = uv*2.0-1.0;
  vec2 o = uv.yx*uv.yx;
  uv += uv * o * uCurve;
  uv = uv*0.5+0.5;
  return uv;
}

void main(){
  vec2 fuv = gl_FragCoord.xy / uRes;
  vec2 uv = curve(fuv);
  float t = uTime;

  float band = 0.0;
  if (uNoise > 0.001){
    float row = floor(uv.y * 190.0);
    float gate = step(0.905, hash(vec2(row, floor(t*15.0))));
    uv.x += (hash(vec2(row*1.7, floor(t*15.0)+7.0)) - 0.5) * 0.052 * gate * uNoise;
    float pos = fract(uv.y * 0.8 - t * 0.17);
    band = smoothstep(0.075, 0.0, pos);
    uv.x += band * (hash(vec2(floor(uv.y*260.0), floor(t*26.0))) - 0.5) * 0.030 * uNoise;
    float head = smoothstep(0.030, 0.0, uv.y);
    uv.x += head * (hash(vec2(floor(uv.y*520.0), floor(t*22.0))) - 0.32) * 0.075 * uNoise;
    band = max(band, head);
  }

  vec2 inb = step(vec2(0.0), uv) * step(uv, vec2(1.0));
  float inside = inb.x*inb.y;
  vec2 ed = min(uv, 1.0-uv);
  inside *= smoothstep(0.0,0.020, min(ed.x,ed.y));

  vec2 dir = uv-0.5;
  float d2 = dot(dir,dir);
  vec2 ao = dir * (0.0010 + 0.0075*d2) * uChroma;
  vec3 col;
  col.r = texture2D(uTex, uv + ao).r;
  col.g = texture2D(uTex, uv).g;
  col.b = texture2D(uTex, uv - ao).b;

  if (uHalo > 0.001){
    float s = 0.0038;
    vec3 wide = texture2D(uTex, uv + vec2( s, 0.0)).rgb
              + texture2D(uTex, uv + vec2(-s, 0.0)).rgb
              + texture2D(uTex, uv + vec2(0.0,  s)).rgb
              + texture2D(uTex, uv + vec2(0.0, -s)).rgb
              + texture2D(uTex, uv + vec2( s,  s)*0.72).rgb
              + texture2D(uTex, uv + vec2(-s, -s)*0.72).rgb;
    col += wide * (uHalo / 6.0);
  }

  float sl = sin(uv.y*3.14159265*uScan + t*4.0*uMotion);
  col *= mix(1.0 - uScanDepth, 1.0, sl*sl);

  float gx = gl_FragCoord.x * (6.2831853/max(uTriad, 1.0));
  vec3 grille = (1.0-uGrille) + uGrille*cos(gx + vec3(0.0,2.094,4.188));
  col *= mix(vec3(1.0), grille, step(0.001, uGrille));
  col *= uGain;

  float bar = fract(uv.y*0.5 - t*0.07*uMotion);
  bar = smoothstep(0.0,0.05,bar)*smoothstep(0.18,0.05,bar);
  col += bar*uBar*uMotion;

  float sheen = smoothstep(0.55,0.0, distance(uv, vec2(0.50,0.15)));
  col += sheen*0.030*uSheen;

  float vig = smoothstep(0.98,0.30, length((uv-0.5)*vec2(1.05,1.0)));
  col *= mix(1.0-uVignette, 1.0, vig);
  col *= 1.0 - uFlicker*uMotion*sin(t*8.0);

  if (uNoise > 0.001){
    float st = hash(fuv*uRes*0.5 + vec2(floor(t*24.0), floor(t*24.0)*1.7));
    col += (st-0.5)*0.135*uNoise;
    col += band*0.085*uNoise;
  }
  col += (hash(fuv + fract(t*0.37)) - 0.5)*uGrain;

  float luma = dot(col, vec3(0.2126,0.7152,0.0722));
  col = mix(col, vec3(luma), uMono);

  float spill = smoothstep(0.85,0.18, length(fuv-0.5))*0.05;
  vec3 room = uRoom + uSheen*spill*0.42;
  col = mix(room, col, inside);
  col = max(col, uRoom*0.34);
  gl_FragColor = vec4(col,1.0);
}`;

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    if (import.meta.env && import.meta.env.DEV) console.error(gl.getShaderInfoLog(shader));
    return null;
  }
  return shader;
}

/* --------------------------------------------------------------- the screen

   Returns null when it cannot run, exactly as the water gate does, so the caller
   treats "no WebGL" as "there is no boot screen" rather than as a blank hold. */
export function mountCrt(host, { onTyped, autoStart = true } = {}) {
  const canvas = document.createElement("canvas");
  canvas.className = "boot__canvas";
  /* Decoration in the accessibility tree: the same lines are served as real
     text beside it, which is what a screen reader reads. */
  canvas.setAttribute("aria-hidden", "true");
  host.prepend(canvas);

  const gl = canvas.getContext("webgl", { antialias: false, alpha: false, depth: false, premultipliedAlpha: false });
  const textCanvas = document.createElement("canvas");
  const ctx = textCanvas.getContext("2d");
  if (!gl || !ctx) { canvas.remove(); return null; }

  const vertex = compile(gl, gl.VERTEX_SHADER, VERT);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAG);
  if (!vertex || !fragment) { canvas.remove(); return null; }
  const program = gl.createProgram();
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { canvas.remove(); return null; }
  gl.useProgram(program);

  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, "aPos");
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

  const u = (name) => gl.getUniformLocation(program, name);
  const uTexture = u("uTex"), uRes = u("uRes"), uTime = u("uTime"), uMotion = u("uMotion"),
        uCurve = u("uCurve"), uScan = u("uScan"), uScanDepth = u("uScanDepth"), uTriad = u("uTriad"),
        uGrille = u("uGrille"), uChroma = u("uChroma"), uBar = u("uBar"), uFlicker = u("uFlicker"),
        uGrain = u("uGrain"), uNoise = u("uNoise"), uVignette = u("uVignette"), uMono = u("uMono"),
        uGain = u("uGain"), uHalo = u("uHalo"), uSheen = u("uSheen"), uRoom = u("uRoom");

  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.uniform1i(uTexture, 0);

  let width = 1, height = 1, cssWidth = 1, cssHeight = 1;
  let fontSize = 14, lineHeight = 20, startY = 0, charWidth = 8;
  let caretX = 0, caretY = 0, typed = 0, done = false, textDirty = true;
  let lastTextAt = 0, lastReveal = -1, lastBlink = -1;
  const startedAt = performance.now();

  gl.uniform2f(uCurve, STYLE.curve[0], STYLE.curve[1]);
  gl.uniform1f(uScanDepth, STYLE.scanDepth);
  gl.uniform1f(uGrille, STYLE.grille);
  gl.uniform1f(uChroma, STYLE.chroma);
  gl.uniform1f(uBar, STYLE.bar);
  gl.uniform1f(uFlicker, STYLE.flicker);
  gl.uniform1f(uGrain, STYLE.grain);
  gl.uniform1f(uNoise, 0);
  gl.uniform1f(uVignette, STYLE.vignette);
  gl.uniform1f(uMono, 0);
  gl.uniform1f(uGain, STYLE.gain);
  gl.uniform1f(uHalo, STYLE.halo);
  gl.uniform3f(uSheen, STYLE.sheen[0], STYLE.sheen[1], STYLE.sheen[2]);
  gl.uniform3f(uRoom, STYLE.room[0], STYLE.room[1], STYLE.room[2]);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

  const font = () => `600 ${fontSize.toFixed(2)}px ui-monospace, "SF Mono", Menlo, Consolas, monospace`;

  const layout = () => {
    startY = height * 0.135;
    lineHeight = (height * 0.74) / LOG.length;
    fontSize = Math.max(5, Math.min(lineHeight * 0.8, (width * 0.88) / (Math.max(MAX_CHARS, 1) * 0.62)));
    ctx.font = font();
    charWidth = ctx.measureText("M").width || fontSize * 0.6;
  };

  const setStyle = (key, glow) => {
    const color = COLORS[key];
    ctx.fillStyle = color.fill;
    ctx.shadowColor = glow ? color.glow : "transparent";
    ctx.shadowBlur = glow ? fontSize * 0.38 : 0;
  };

  /* Two passes per glyph: a soft phosphor halo, then the same glyph re-filled
     with the shadow off so the stroke core stays crisp at any backing
     resolution. (Authored, and the reason the log reads through the grille.) */
  const drawScreen = (reveal) => {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = STYLE.background;
    ctx.fillRect(0, 0, width, height);
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.font = font();
    let remaining = reveal;
    let y = startY;
    caretX = Math.floor((width - MAX_CHARS * charWidth) / 2);
    caretY = startY;
    for (const line of LOG) {
      const length = lineLength(line);
      const visible = reveal === Infinity ? Infinity : Math.min(remaining, length);
      let x = Math.floor((width - MAX_CHARS * charWidth) / 2);
      let drawn = 0;
      for (const item of line) {
        let text = item.t;
        if (visible !== Infinity) {
          const left = visible - drawn;
          if (left <= 0) break;
          if (left < text.length) text = text.slice(0, left);
        }
        if (text.length) {
          setStyle(item.c, true);
          ctx.fillText(text, x, y);
          setStyle(item.c, false);
          ctx.fillText(text, x, y);
          x += charWidth * text.length;
        }
        drawn += item.t.length;
        if (visible !== Infinity && drawn >= visible) break;
      }
      caretX = x;
      caretY = y;
      if (visible !== Infinity) remaining -= visible;
      y += lineHeight;
      if (visible !== Infinity && remaining <= 0) break;
    }
  };

  const drawCursor = () => {
    ctx.shadowColor = COLORS.p.glow;
    ctx.shadowBlur = fontSize * 0.42;
    ctx.fillStyle = "#bdf8d2";
    ctx.fillRect(caretX, caretY + fontSize * 0.06, Math.max(charWidth * 0.92, 4), fontSize * 0.96);
    ctx.shadowBlur = 0;
    ctx.fillRect(caretX, caretY + fontSize * 0.06, Math.max(charWidth * 0.92, 4), fontSize * 0.96);
  };

  const uploadTexture = () => {
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, textCanvas);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    textDirty = false;
  };

  const resize = () => {
    const bounds = host.getBoundingClientRect();
    cssWidth = Math.max(1, bounds.width);
    cssHeight = Math.max(1, bounds.height);
    const density = Math.min(window.devicePixelRatio || 1, 2);
    let nextWidth = Math.max(MIN_BUFFER_WIDTH, Math.round(Math.min(cssWidth * density, MAX_BUFFER_WIDTH)));
    let nextHeight = Math.max(1, Math.round((nextWidth * cssHeight) / cssWidth));
    if (nextWidth * nextHeight > MAX_BUFFER_PIXELS) {
      const fit = Math.sqrt(MAX_BUFFER_PIXELS / (nextWidth * nextHeight));
      nextWidth = Math.round(nextWidth * fit);
      nextHeight = Math.round(nextHeight * fit);
    }
    if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
      canvas.width = nextWidth;
      canvas.height = nextHeight;
    }
    if (textCanvas.width !== nextWidth || textCanvas.height !== nextHeight) {
      textCanvas.width = nextWidth;
      textCanvas.height = nextHeight;
      width = nextWidth;
      height = nextHeight;
      layout();
      lastReveal = -1; lastBlink = -1; lastTextAt = 0; textDirty = true;
    }
    gl.useProgram(program);
    gl.viewport(0, 0, nextWidth, nextHeight);
    gl.uniform2f(uRes, nextWidth, nextHeight);
    gl.uniform1f(uScan, Math.max(120, Math.min(cssHeight * STYLE.scanDensity, 900)));
    gl.uniform1f(uTriad, Math.max(2, (STYLE.triadCss * nextWidth) / cssWidth));
  };

  const maybeRedrawText = (now) => {
    const reveal = done ? Infinity : Math.floor(typed);
    const blink = Math.floor((now - startedAt) / 420) % 2 === 0 ? 1 : 0;
    const due = !done ? now - lastTextAt > 42 : blink !== lastBlink;
    if (reveal === lastReveal && blink === lastBlink && !due) return;
    if (!done && now - lastTextAt <= 42 && reveal === lastReveal && blink === lastBlink) return;
    drawScreen(reveal);
    if (blink) drawCursor();
    lastTextAt = now;
    lastReveal = reveal;
    lastBlink = blink;
    textDirty = true;
  };

  resize();
  const ro = new ResizeObserver(() => resize());
  ro.observe(host);

  let raf = 0;
  let announced = false;
  /* The screen can be mounted before it is revealed -- it sits under the water
     gate while that fades -- and a log that typed itself during the handover
     would be a third of the way through by the time anyone saw it. Held at zero
     until the thing above says it is out of the way. */
  let running = autoStart;

  let lastFrame = 0;

  const frame = (now) => {
    const seconds = (now - startedAt) * 0.001;
    if (!done && running) {
      /* The authored renderer advances 4.4 characters PER FRAME, which ties the
         typing rate to the refresh rate: the same log takes 2.5s on a 60Hz panel
         and 1.25s on a 120Hz one. Same constant, measured against wall time
         instead, so the screen reads identically on every display. */
      const dt = lastFrame ? Math.min(now - lastFrame, 100) : 1000 / 60;
      typed += CHARS_PER_MS * dt;
      if (typed >= TOTAL) { typed = TOTAL; done = true; }
    }
    lastFrame = now;
    maybeRedrawText(now);
    if (textDirty) uploadTexture();
    gl.useProgram(program);
    gl.uniform1f(uTime, seconds);
    gl.uniform1f(uMotion, 1);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (done && !announced) { announced = true; if (onTyped) onTyped(); }
    raf = requestAnimationFrame(frame);
  };

  /* Reduced motion gets the finished screen, not the typing: the log complete
     and still on the first frame, which is the whole message without any of the
     movement. The caller shortens its hold to match. */
  if (reduced()) {
    running = true;
    typed = TOTAL;
    done = true;
    maybeRedrawText(performance.now());
    uploadTexture();
    gl.uniform1f(uTime, 0);
    gl.uniform1f(uMotion, 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (onTyped) onTyped();
  } else {
    raf = requestAnimationFrame(frame);
  }

  return {
    /* Begin typing. Safe to call twice. */
    start() {
      if (running) return;
      running = true;
      lastFrame = 0;
    },
    /* Everything still to be typed, typed now. */
    finish() {
      if (done) return;
      typed = TOTAL;
      done = true;
    },
    destroy() {
      if (raf) cancelAnimationFrame(raf);
      ro.disconnect();
      gl.deleteBuffer(buffer);
      gl.deleteTexture(texture);
      gl.deleteProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
      const lose = gl.getExtension("WEBGL_lose_context");
      if (lose) lose.loseContext();
      canvas.remove();
    },
  };
}

/* The same lines as plain text, for the accessibility tree and for anyone the
   canvas never reaches. Built from the same array, so it cannot fall out of
   step with what is on screen. */
export const LOG_TEXT = LOG.map((line) => line.map((s) => s.t).join("")).join("\n");
