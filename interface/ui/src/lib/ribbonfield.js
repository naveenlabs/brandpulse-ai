/* ===========================================================================
   ribbonfield.js — vendored from ThreeUI, "Ribbon Field".

   PROVENANCE. Do not rewrite this file from what it looks like on screen.

     source   https://threeui.com/source-code/ribbon-field.json
     revision SHA-256 fa86582fc870
     fetched  21 Sep 2026, HTTP 200, 51,216 bytes

     src/shaders/ribbon-field/ribbonFieldShaders.ts
       SHA-256 ab578acab44bbff7f3cf67f1c82b3e2e1d03689de3fcbdc23681e8b5a0a3536c
     src/shaders/ribbon-field/RibbonFieldBackground.tsx
       SHA-256 fab02cb57c44c7307afd29cd03d01141372ad90163632b9a6a77910a245a5996

   The two GLSL programs below are the registered source, character for
   character. Nothing in them is adapted, retuned or re-derived. The bundle
   carried no licence file and the two registered files carry no copyright
   notice; that is recorded here rather than assumed either way.

   WHY THIS ONE, OF THE THREE
   --------------------------
   Its own composition lands on this section's layout when mirrored, which is
   the whole reason it was chosen over the two arcs:

     rightFade = smoothstep(0.28, 0.72, uv.x)   the effect lives on one side
     centerDark around vec2(0.18, 0.48)         and is actively suppressed on
                                                the other
     two blooms at uv 0.76,0.40 and 0.71,0.75   sit inside the lit side

   Flipped with scaleX(-1) at the CSS layer -- the shader itself untouched --
   the lit side falls under the glyph column and the suppressed side falls
   under the ledger, where measured type has to stay legible. The blooms land
   behind the mark.

   Its base colour is vec3(0.005), so it stays black where it has nothing to
   say, and its palette (teal, cyan, indigo, blue, purple) sits under the four
   channel hues without competing with any of them. Its 7px dot lattice is the
   same instrument grammar as the film's lanes.

   THREE DEVIATIONS FROM THE REGISTERED COMPONENT, EACH FORCED
   ----------------------------------------------------------
   1. NO REACT. The registered file is a React component: two refs, one
      useEffect, and a <div><canvas/></div>. This application has no React,
      no react-dom and no TypeScript -- it is vanilla ES modules through Vite.
      Everything inside that useEffect is framework-agnostic and is reproduced
      here unchanged: context attributes, compile and link, the six-vertex
      buffer, the three uniforms, the 0.72/0.42 pointer origin and its
      smoothing, the devicePixelRatio cap of 2, both observers, and the full
      teardown. Only the React shell became a function call.

   2. REDUCED MOTION. The registered component always animates. This build
      treats prefers-reduced-motion as a hard contract, so under it the field
      paints one frame and stops. A still frame of this shader is a complete
      picture, not a broken one.

   3. THE TAB-SWITCH RESTART. The registered render loop stops itself on
      `document.hidden` and nothing ever restarts it, so the field dies
      permanently the first time the reader changes tab. The sibling component
      in the same bundle (PredictiveArcCanvas.tsx) carries a visibilitychange
      listener that does exactly this. That listener is adopted here, from the
      bundle's own source.
   ======================================================================== */

/* --- registered source, verbatim ---------------------------------------- */

export const RIBBON_FIELD_VERTEX_SHADER = `
        attribute vec2 position;
        void main() {
          gl_Position = vec4(position, 0.0, 1.0);
        }
      `;

export const RIBBON_FIELD_FRAGMENT_SHADER = `
        precision highp float;
        uniform vec2 resolution;
        uniform float time;
        uniform vec2 pointer;

        float hash(vec2 p) {
          p = fract(p * vec2(123.34, 456.21));
          p += dot(p, p + 45.32);
          return fract(p.x * p.y);
        }

        float ribbon(vec2 uv, float offset, float width, float phase) {
          float y = 0.55 + 0.20 * sin((uv.x * 2.15) + phase) + 0.045 * sin((uv.x * 7.0) - phase * 0.7);
          float d = abs(uv.y - y - offset);
          return exp(-(d * d) / width);
        }

        void main() {
          vec2 uv = gl_FragCoord.xy / resolution.xy;
          vec2 p = uv;
          p.x *= resolution.x / resolution.y;

          float t = time * 0.22;
          float drift = (pointer.x - 0.5) * 0.06;

          float rightFade = smoothstep(0.28, 0.72, uv.x);
          float centerDark = 1.0 - smoothstep(0.0, 0.88, distance(uv, vec2(0.18, 0.48)));

          float r1 = ribbon(vec2(uv.x + drift, uv.y), 0.03, 0.0065, t + 0.9);
          float r2 = ribbon(vec2(uv.x - drift * 0.7, uv.y), -0.23, 0.0085, t + 3.25);
          float r3 = ribbon(vec2(uv.x + drift * 0.4, uv.y), 0.25, 0.014, t + 1.85);

          float glow = r1 * 1.14 + r2 * 1.05 + r3 * 0.48;

          vec3 teal = vec3(0.17, 0.83, 0.75);
          vec3 cyan = vec3(0.22, 0.82, 0.96);
          vec3 indigo = vec3(0.39, 0.38, 0.92);
          vec3 purple = vec3(0.66, 0.33, 0.98);
          vec3 blue = vec3(0.23, 0.51, 0.96);

          vec3 col = vec3(0.0);
          col += cyan * r1 * 0.92;
          col += teal * r1 * 0.62;
          col += indigo * r3 * 0.42;
          col += blue * r2 * 0.66;
          col += purple * (r2 + r3) * 0.30;

          float bloom = exp(-pow(distance(uv, vec2(0.76, 0.40 + 0.035 * sin(t))), 2.0) / 0.050);
          bloom += exp(-pow(distance(uv, vec2(0.71, 0.75 + 0.025 * cos(t))), 2.0) / 0.030);
          col += vec3(0.42, 0.85, 1.0) * bloom * 0.34;

          vec2 grid = fract(gl_FragCoord.xy / 7.0) - 0.5;
          float dotShape = smoothstep(0.29, 0.11, length(grid));
          float noise = hash(floor(gl_FragCoord.xy / 7.0));
          float scan = 0.72 + 0.28 * sin((uv.x + uv.y) * 38.0 + time * 1.3);
          float dots = dotShape * (0.48 + 0.52 * noise) * scan;

          float micro = hash(gl_FragCoord.xy + time) * 0.035;
          float alpha = clamp((glow * 1.55 + bloom * 0.50) * dots * rightFade, 0.0, 1.0);
          alpha *= 1.0 - centerDark * 0.56;

          vec3 base = vec3(0.005, 0.005, 0.005);
          vec3 finalColor = mix(base, col, clamp(alpha * 1.55, 0.0, 1.0));
          finalColor += micro * rightFade;

          gl_FragColor = vec4(finalColor, 1.0);
        }
      `;

/** The registered defaults, unchanged. */
export const RIBBON_FIELD_DEFAULTS = Object.freeze({
  speed: 1,
  pointerAmount: 1,
  smoothing: 0.035,
  brightness: 1,
  opacity: 1,
  hue: 0,
  saturation: 1,
});

/* The registered compile step, including its own error strings. */
function compile(gl, type, source) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("Unable to create Axiom shader");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader) ?? "Axiom shader compilation failed");
  }
  return shader;
}

/**
 * Mount the field into a host element, in place of the React component.
 *
 * Returns a teardown, or null if this machine cannot give us a WebGL context —
 * in which case the host simply stays the colour it already was, which is the
 * correct outcome and not a degraded one.
 */
export function mountRibbonField(host, props = {}) {
  if (!host) return null;

  const options = { ...RIBBON_FIELD_DEFAULTS, ...props };
  let still = Boolean(props.still);

  const canvas = document.createElement("canvas");
  host.appendChild(canvas);

  let gl = null;
  try {
    gl = canvas.getContext("webgl", { alpha: true, antialias: false, premultipliedAlpha: false });
  } catch { gl = null; }
  if (!gl) { canvas.remove(); return null; }

  let vertex;
  let fragment;
  let program;
  try {
    vertex = compile(gl, gl.VERTEX_SHADER, RIBBON_FIELD_VERTEX_SHADER);
    fragment = compile(gl, gl.FRAGMENT_SHADER, RIBBON_FIELD_FRAGMENT_SHADER);
    program = gl.createProgram();
    if (!program) throw new Error("Axiom program could not be created");
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program) ?? "Axiom program link failed");
    }
  } catch {
    canvas.remove();
    return null;
  }
  gl.useProgram(program);

  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, "position");
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

  const resolution = gl.getUniformLocation(program, "resolution");
  const time = gl.getUniformLocation(program, "time");
  const pointerUniform = gl.getUniformLocation(program, "pointer");

  let mouseX = 0.72;
  let mouseY = 0.42;
  let targetX = 0.72;
  let targetY = 0.42;
  let frame = 0;
  let visible = true;
  const startedAt = performance.now();

  const pointer = (event) => {
    const bounds = host.getBoundingClientRect();
    targetX = 0.72 + (((event.clientX - bounds.left) / Math.max(bounds.width, 1)) - 0.72)
      * options.pointerAmount;
    targetY = 0.42 + ((1 - (event.clientY - bounds.top) / Math.max(bounds.height, 1)) - 0.42)
      * options.pointerAmount;
  };

  const paint = (now) => {
    mouseX += (targetX - mouseX) * options.smoothing;
    mouseY += (targetY - mouseY) * options.smoothing;
    gl.uniform1f(time, (now - startedAt) * 0.001 * options.speed);
    gl.uniform2f(pointerUniform, mouseX, mouseY);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  };

  const resize = () => {
    const bounds = host.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.floor(bounds.width * ratio));
    canvas.height = Math.max(1, Math.floor(bounds.height * ratio));
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(resolution, canvas.width, canvas.height);
    if (still) paint(performance.now());
  };

  const render = (now) => {
    paint(now);
    frame = visible && !document.hidden ? requestAnimationFrame(render) : 0;
  };

  const start = () => {
    if (still || frame || !visible || document.hidden) return;
    frame = requestAnimationFrame(render);
  };
  const stop = () => {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  };

  const resizeObserver = new ResizeObserver(resize);
  const intersection = new IntersectionObserver(([entry]) => {
    visible = entry?.isIntersecting ?? true;
    if (visible) start(); else stop();
  });

  /* Deviation 3: the registered loop stops on document.hidden and never comes
     back. This is the sibling component's own listener. */
  const visibility = () => { if (document.hidden) stop(); else start(); };

  resizeObserver.observe(host);
  intersection.observe(host);
  host.addEventListener("pointermove", pointer, { passive: true });
  document.addEventListener("visibilitychange", visibility);

  resize();
  if (still) paint(performance.now()); else frame = requestAnimationFrame(render);
  /* Follows the reader's motion setting live -- the OS preference or the
     in-page switch -- through the one event lib/motion.js sends, so a reader
     who turns motion off mid-page stops this loop too, and one who turns it
     back on gets it back (25 Sep 2026, INCLUSIVE_DESIGN.md I1). An event rather
     than an import keeps this vendored module free of the project's own. */
  const onMotion = (event) => {
    still = Boolean(event.detail && event.detail.reduced);
    if (still) { stop(); paint(performance.now()); } else start();
  };
  window.addEventListener("motionchange", onMotion);


  canvas.style.opacity = String(options.opacity);
  canvas.style.filter =
    `hue-rotate(${options.hue}deg) saturate(${options.saturation}) brightness(${options.brightness})`;

  return () => {
    stop();
    window.removeEventListener("motionchange", onMotion);
    resizeObserver.disconnect();
    intersection.disconnect();
    host.removeEventListener("pointermove", pointer);
    document.removeEventListener("visibilitychange", visibility);
    gl.deleteBuffer(buffer);
    gl.deleteShader(vertex);
    gl.deleteShader(fragment);
    gl.deleteProgram(program);
    canvas.remove();
  };
}
