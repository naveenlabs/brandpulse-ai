/* ===========================================================================
   portalfield.js — vendored from ThreeUI, "Portal Field".

   PROVENANCE. Do not rewrite this file from what it looks like on screen.

     source   https://threeui.com/source-code/portal-field.json
     revision SHA-256 f90e34f83d51
     fetched  21 Sep 2026, HTTP 200, 262,542 bytes
     bundle   SHA-256 6935031441e996f35a94d4e2d1c0714f6bf54fff95edd5e45f310e3ca527a386

     src/shaders/neuform-isolated/sources/portal-field.html
       SHA-256 f90e34f83d5179217c6f0928d633ec4a8201b00cfb980b374b5df76a9f167a6e
       verified three ways on fetch: recomputed locally, against the bundle's
       own .sha256 field, and against the integration brief. All three agree.
     src/shaders/portal-field/PortalFieldCollection.tsx
       SHA-256 6ebff251f315e07d65205504b10a87dfa5b3cab8beb163af804fea137a7b2379
     src/shaders/neuform-isolated/NeuformBatchEffects.tsx
       SHA-256 dc68c51bea26b922965de44b4fb8d6c432607508fb2b61e16ed60d245da1a69f

   The two GLSL programs below are the registered source, character for
   character, apart from the prologue noted in deviation 3. Nothing in them is
   adapted, retuned or re-derived. The bundle carried no licence file and the
   registered files carry no copyright notice; that is recorded here rather
   than assumed either way.

   WHY THIS ONE, OF THE FOUR
   -------------------------
   Ribbon Field is already spent on #seam. Predictive Arc is violet at a
   measured median hue of 260.0, against --ch-vocal at 252.2 -- under 8 degrees
   apart, and additively blended so it stacks bright; it would eat a channel
   hue that this page uses to carry meaning. Portal Field's fringe is #1e3a8a,
   a deep navy that is darker and far more saturated than any of the four
   channel hues, so it sits underneath them instead of competing.

   CORRECTION, 21 Sep 2026. This paragraph also rejected Data Pixel Arc as
   "emerald next door to --ch-transcript". That was read off the brief's prose
   and never measured, and it is wrong: the renderer peaks at rgb(130,255,130),
   hue 120.0, which is 50 degrees from --ch-transcript at 170.2. The component
   was re-examined when the limits rail needed a ground of its own and is now
   vendored in datapixelarc.js, which carries the measurements. Portal Field
   remains the right choice for the chart above -- an arc rather than a band
   that would have run parallel to the bars -- but it was not chosen over a
   sound objection to the alternative.

   Its form is an arc, not a horizon. This section is a horizontal bar chart,
   and Data Pixel Arc's band would have run parallel to the bars.

   WHERE ITS LIGHT ACTUALLY FALLS — MEASURED, NOT READ OFF THE BRIEF
   ----------------------------------------------------------------
   The brief calls it "pointer-reactive fringe light", which suggested a dark
   centre. That is not what the shader does. Evaluating the fragment program
   over a pixel grid at four values of u_time shows the composition is driven
   entirely by the aspect ratio handed to u_resolution, because main() stretches
   st.x by resolution.x/resolution.y and then places the arc at a fixed
   center = vec2(0.5, 0.5) in that stretched space. The visible limb therefore
   lands at screen x = 1.1 / aspect:

     aspect 1.00  ->  x 0.99      aspect 1.60  ->  x 0.65
     aspect 1.15  ->  x 0.91      aspect 1.80  ->  x 0.58
     aspect 1.30  ->  x 0.80      aspect 2.20  ->  x 0.47
     aspect 1.45  ->  x 0.72      aspect 2.60  ->  x 0.40

   At the section's natural 1.8 the arc would burn straight through the reading
   column at a peak luminance of 0.517, which no amount of type colour rescues.
   The host is therefore given a fixed 1.15 aspect by CSS so the limb falls at
   x 0.91 — in the right-hand gutter, beside the type rather than under it.
   That is a hosting decision. The shader is untouched.

   FIVE DEVIATIONS FROM THE REGISTERED COMPONENT, EACH FORCED
   ---------------------------------------------------------
   1. NO REACT, AND NO IFRAME. The registered component renders the HTML source
      into <iframe srcDoc sandbox="allow-scripts">. That document pulls
      Tailwind, Iconify, Three.js r134 and GSAP from four CDNs at runtime. This
      project forbids any external runtime fetch, font host or CDN, so the
      iframe route is not available at any price. An iframe would also put the
      background outside the theme system, where BENCH/FIELD could not reach it.

   2. NO THREE.JS. Three is not a dependency here and this component does not
      need it to be. It is used for exactly one fullscreen quad: Scene,
      OrthographicCamera(-1,1,1,-1), PlaneGeometry(2,2), ShaderMaterial, Mesh.
      The vertex program writes gl_Position = vec4(position, 1.0) directly, so
      the camera never transforms anything and the scene graph holds one node.
      It is replaced by the six-vertex buffer this project already uses, with
      every observable behaviour reproduced rather than approximated:

        THREE.AdditiveBlending      -> blendFunc(SRC_ALPHA, ONE), BLEND enabled
        renderer alpha: true        -> context alpha: true
        renderer premultipliedAlpha -> context premultipliedAlpha: true (Three's
                                       default, and correct: SRC_ALPHA,ONE
                                       writes colour already scaled by alpha)
        setPixelRatio(min(dpr, 2))  -> the same cap
        new THREE.Clock()           -> elapsed seconds since first paint
        u_mouse.lerp(target, 0.03)  -> the same constant, the same per frame
        new THREE.Color('#rrggbb')  -> channel/255, which is exact: r134 has no
                                       colour management (that arrives in r152)
                                       and outputEncoding defaults to Linear, so
                                       the hex reaches the uniform untouched

   3. THE GLSL PROLOGUE IS WRITTEN OUT. Three prepends every ShaderMaterial with
      a generated prologue declaring the attributes it supplies and a precision
      qualifier. Without Three those declarations have to be present in the
      source, so `attribute vec3 position; attribute vec2 uv;` and
      `precision highp float;` appear below. The shader bodies are unchanged;
      these lines replace what Three would have inserted above them.

   4. REDUCED MOTION. The registered component always animates. This build
      treats prefers-reduced-motion as a hard contract, so under it the field
      paints one frame and stops. A still frame of this shader is a complete
      picture, not a broken one.

   5. THE POINTER IS SCOPED TO THE HOST. The registered source listens on
      `document` and divides by window.innerWidth, because there it is a
      page-wide background. Here it is one section's background, so it reads
      the host's own rect. The 0.03 smoothing and the 0.5,0.5 origin are the
      registered values.
   ======================================================================== */

/* --- registered source, verbatim below the prologue --------------------- */

export const PORTAL_FIELD_VERTEX_SHADER = `
            attribute vec3 position;
            attribute vec2 uv;

            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = vec4(position, 1.0);
            }
        `;

export const PORTAL_FIELD_FRAGMENT_SHADER = `
            precision highp float;

            uniform float u_time;
            uniform vec2 u_resolution;
            uniform vec2 u_mouse;
            uniform vec3 u_colorCore;
            uniform vec3 u_colorFringe;
            uniform float u_isLightMode;
            varying vec2 vUv;

            vec2 hash( vec2 p ) {
                p = vec2( dot(p,vec2(127.1,311.7)), dot(p,vec2(269.5,183.3)) );
                return -1.0 + 2.0*fract(sin(p)*43758.5453123);
            }
            float noise( in vec2 p ) {
                const float K1 = 0.366025404;
                const float K2 = 0.211324865;
                vec2 i = floor( p + (p.x+p.y)*K1 );
                vec2 a = p - i + (i.x+i.y)*K2;
                vec2 o = (a.x>a.y) ? vec2(1.0,0.0) : vec2(0.0,1.0);
                vec2 b = a - o + K2;
                vec2 c = a - 1.0 + 2.0*K2;
                vec3 h = max( 0.5-vec3(dot(a,a), dot(b,b), dot(c,c) ), 0.0 );
                vec3 n = h*h*h*h*vec3( dot(a,hash(i+0.0)), dot(b,hash(i+o)), dot(c,hash(i+1.0)));
                return dot( n, vec3(70.0) );
            }

            float sdArc(vec2 p, vec2 center, float radius, float width, float warp) {
                p.y += sin(p.x * 2.0 + u_time * 0.3) * warp;
                p.x += noise(p * 1.5 + u_time * 0.1) * (warp * 0.8);
                float d = length(p - center) - radius;
                return abs(d) - width;
            }

            void main() {
                vec2 uv = gl_FragCoord.xy / u_resolution.xy;
                vec2 st = uv;
                st.x *= u_resolution.x / u_resolution.y;
                
                vec2 mouseOffset = (u_mouse - 0.5) * 0.05;
                st += mouseOffset;

                // Center organic form behind the content area
                vec2 center = vec2(0.5, 0.5);
                
                float d1 = sdArc(st, center, 0.6, 0.02, 0.15);
                float d2 = sdArc(st, center, 0.65, 0.06, 0.2);
                
                float coreGlow = exp(-d1 * 30.0);
                float fringeGlow = exp(-d2 * 10.0);
                float wash = smoothstep(1.5, -0.5, length(st - center)) * 0.15;

                vec3 finalColor = vec3(0.0);
                finalColor += u_colorCore * coreGlow;
                finalColor += u_colorFringe * fringeGlow;
                finalColor += u_colorFringe * wash * (sin(u_time * 0.5) * 0.2 + 0.8);

                float alpha = clamp(coreGlow + fringeGlow + wash, 0.0, 1.0);
                finalColor = vec3(1.0) - exp(-finalColor * 1.5);
                
                if(u_isLightMode > 0.5) {
                    alpha = clamp((coreGlow * 1.2 + fringeGlow + wash * 0.4), 0.0, 0.4);
                }

                gl_FragColor = vec4(finalColor, alpha * 0.6);
            }
        `;

/* --- the registered themes, verbatim ------------------------------------ */

export const PORTAL_FIELD_THEMES = {
  dark: { shaderCore: "#FFFFFF", shaderFringe: "#1e3a8a" },
  light: { shaderCore: "#020202", shaderFringe: "#94a3b8" },
};

/* The registered component's own prop defaults (NeuformBatchEffects.tsx). */
export const PORTAL_FIELD_DEFAULTS = {
  speed: 1,
  opacity: 1,
  hue: 0,
  saturation: 1,
  brightness: 1,
};

/* new THREE.Color('#rrggbb') in r134: no colour management, no decode. */
function rgbOf(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("Portal shader could not be created");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader) ?? "Portal shader compilation failed");
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
export function mountPortalField(host, props = {}) {
  if (!host) return null;

  const options = { ...PORTAL_FIELD_DEFAULTS, ...props };
  let still = Boolean(props.still);
  const theme = PORTAL_FIELD_THEMES[props.mode === "light" ? "light" : "dark"];
  const isLightMode = props.mode === "light" ? 1 : 0;

  const canvas = document.createElement("canvas");
  host.appendChild(canvas);

  let gl = null;
  try {
    /* Three's WebGLRenderer defaults: alpha as configured, premultipliedAlpha
       true, antialias as configured. The registered call passes antialias
       true, which a fullscreen quad with no geometry edges cannot use. */
    gl = canvas.getContext("webgl", {
      alpha: true, antialias: true, premultipliedAlpha: true,
    });
  } catch { gl = null; }
  if (!gl) { canvas.remove(); return null; }

  let vertex;
  let fragment;
  let program;
  try {
    vertex = compile(gl, gl.VERTEX_SHADER, PORTAL_FIELD_VERTEX_SHADER);
    fragment = compile(gl, gl.FRAGMENT_SHADER, PORTAL_FIELD_FRAGMENT_SHADER);
    program = gl.createProgram();
    if (!program) throw new Error("Portal program could not be created");
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program) ?? "Portal program link failed");
    }
  } catch {
    canvas.remove();
    return null;
  }
  gl.useProgram(program);

  /* THREE.PlaneGeometry(2, 2) is two triangles spanning clip space, with uv
     running 0..1. The vertex program consumes position directly, so the six
     vertices are written out rather than indexed. */
  const quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1, -1, 0, 1, -1, 0, -1, 1, 0,
    -1, 1, 0, 1, -1, 0, 1, 1, 0,
  ]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, "position");
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 3, gl.FLOAT, false, 0, 0);

  const uvs = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, uvs);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    0, 0, 1, 0, 0, 1,
    0, 1, 1, 0, 1, 1,
  ]), gl.STATIC_DRAW);
  const uvAttribute = gl.getAttribLocation(program, "uv");
  if (uvAttribute >= 0) {
    gl.enableVertexAttribArray(uvAttribute);
    gl.vertexAttribPointer(uvAttribute, 2, gl.FLOAT, false, 0, 0);
  }

  /* THREE.AdditiveBlending, with transparent: true. */
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
  gl.clearColor(0, 0, 0, 0);

  const uTime = gl.getUniformLocation(program, "u_time");
  const uResolution = gl.getUniformLocation(program, "u_resolution");
  const uMouse = gl.getUniformLocation(program, "u_mouse");

  const core = rgbOf(theme.shaderCore);
  const fringe = rgbOf(theme.shaderFringe);
  gl.uniform3f(gl.getUniformLocation(program, "u_colorCore"), core[0], core[1], core[2]);
  gl.uniform3f(gl.getUniformLocation(program, "u_colorFringe"), fringe[0], fringe[1], fringe[2]);
  gl.uniform1f(gl.getUniformLocation(program, "u_isLightMode"), isLightMode);

  let mouseX = 0.5;
  let mouseY = 0.5;
  let targetX = 0.5;
  let targetY = 0.5;
  let frame = 0;
  let visible = true;
  const startedAt = performance.now();

  /* Deviation 5: the host's rect, not the window's. */
  const pointer = (event) => {
    const bounds = host.getBoundingClientRect();
    targetX = (event.clientX - bounds.left) / Math.max(bounds.width, 1);
    targetY = 1 - (event.clientY - bounds.top) / Math.max(bounds.height, 1);
  };

  const paint = (now) => {
    mouseX += (targetX - mouseX) * 0.03;
    mouseY += (targetY - mouseY) * 0.03;
    gl.uniform1f(uTime, (now - startedAt) * 0.001 * options.speed);
    gl.uniform2f(uMouse, mouseX, mouseY);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  };

  const resize = () => {
    const bounds = host.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.floor(bounds.width * ratio));
    canvas.height = Math.max(1, Math.floor(bounds.height * ratio));
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(uResolution, canvas.width, canvas.height);
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


  /* The registered component applies exactly these four props as CSS on the
     element it renders (NeuformBatchEffects.tsx: element.style.opacity, and
     `hue-rotate(...) saturate(...) brightness(...)`). Same place, same order. */
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
    gl.deleteBuffer(quad);
    gl.deleteBuffer(uvs);
    gl.deleteShader(vertex);
    gl.deleteShader(fragment);
    gl.deleteProgram(program);
    /* A project deviation, added 24 Sep 2026: the proof remounts this field
       on every theme switch, and a removed canvas keeps its context until
       the collector gets to it. Browsers cap live WebGL contexts and evict
       the OLDEST when the cap is hit, which on this page would be a scene
       still on screen. Releasing it here makes the teardown actually free. */
    const lose = gl.getExtension("WEBGL_lose_context");
    if (lose) lose.loseContext();
    canvas.remove();
  };
}
