import { esc, pct, arrow } from './format.js';
import { CHANNEL_META } from './contract.js';
import '../styles/limits.css';

const NAMES = ['Accuracy', 'Threshold', 'Absence', 'Variance', 'Language'];
export function limitsMarkup(limits, figures) {
  const stats = [
    [pct(CHANNEL_META.facial.accuracy), 'Facial accuracy / held-out speakers'],
    ['0 / 62', 'Polar probes flagged by the specified rule'],
    [pct(figures.corpus.no_face_share_pct ?? 0), 'Segments without a facial reading'],
    ['49.08', 'Points of mean Authenticity movement'],
    ['EN', 'The only benchmarked language'],
  ];
  return `<section class="limits limits--atlas" data-limits aria-labelledby="atlas-heading">
    <header class="la-header"><div><p class="la-kicker">The boundary of the instrument</p><h3 id="atlas-heading">Five things<br><em>it cannot do.</em></h3></div><p>Precision starts with knowing<br>where it ends.</p></header>
    <div class="la-art" aria-hidden="true"><span class="la-orbit la-orbit--one"></span><span class="la-orbit la-orbit--two"></span><span class="la-index">01</span><canvas class="la-sculpture"></canvas><span class="la-art__note">Model / boundaries<br>Five independent limits</span><span class="la-cross">+</span></div>
    <ol class="la-readings">${limits.map((limit, i) => `<li class="la-reading" data-reading="${i}">
      <p class="la-location"><span>0${i + 1} / 05</span> ${esc(limit.where)}</p>
      <h4>${esc(typeof limit.title === "function" ? limit.title(figures) : limit.title)}</h4>
      <div class="la-metric"><strong>${esc(stats[i][0])}</strong><span>${esc(stats[i][1])}</span></div>
      <p class="la-claim">${limit.claim(figures)}</p><p class="la-body">${limit.body(figures)}</p>
    </li>`).join('')}</ol>
    <nav class="la-nav" aria-label="Explore the five limitations">${NAMES.map((name, i) => `<button type="button" data-limit-jump="${i}"><span>0${i + 1}</span><span>${name}</span><i></i></button>`).join('')}</nav>
    <div class="la-footer"><span>Limitations, not fine print.</span><span>Scroll to examine ${arrow("down")}</span></div>
  </section>`;
}

/* Five open helicoid ribbons, built as a real lit 3D mesh. The vacant centre
   and openings are illustrative; measured values are printed in the HTML. */
function mountSculpture(canvas) {
  const gl = canvas.getContext('webgl', { alpha: true, antialias: true, premultipliedAlpha: false });
  if (!gl) return null;
  const vertex = `
    precision mediump float;
    attribute vec3 aParam;
    uniform float uProgress;
    uniform float uAspect;
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec2 vUV;
    varying float vBand;
    vec3 surface(float t, float v, float band) {
      float phase = uProgress * 6.283185;
      float bandFocus = clamp(1.0 - abs(band - min(4.0, floor(uProgress * 5.0))) * .6, 0.0, 1.0);
      float a = t * 4.65 + band * 1.256637;
      float radius = .86 + v * .24 + .09 * sin(a * 2.0 + phase);
      float lift = .16 * sin(t * 3.14159) + bandFocus * .08;
      return vec3(cos(a) * radius, (band - 2.0) * .22 + (t - .5) * .74 + sin(v * 3.14159) * lift, sin(a) * radius);
    }
    mat3 ry(float a) { return mat3(cos(a),0.,-sin(a),0.,1.,0.,sin(a),0.,cos(a)); }
    mat3 rx(float a) { return mat3(1.,0.,0.,0.,cos(a),sin(a),0.,-sin(a),cos(a)); }
    void main() {
      float t = aParam.x, v = aParam.y, band = aParam.z;
      vec3 p = surface(t,v,band);
      vec3 dt = surface(t+.001,v,band)-p;
      vec3 dv = surface(t,v+.001,band)-p;
      mat3 rotation = rx(.58 + .13*sin(uProgress*6.283185)) * ry(-.55 + uProgress * 3.6);
      vec3 n = normalize(rotation * cross(dt,dv));
      p = rotation * p;
      p.z -= 4.0;
      float f = 2.65;
      gl_Position = vec4(p.x*f/uAspect,p.y*f,(-p.z-0.1)*1.02-0.202,-p.z);
      vNormal=n; vPosition=p; vUV=vec2(t,v); vBand=band;
    }`;
  const fragment = `
    precision mediump float;
    uniform float uProgress;
    uniform float uLight;
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec2 vUV;
    varying float vBand;
    void main() {
      vec3 n = normalize(vNormal); if(!gl_FrontFacing) n=-n;
      vec3 light = normalize(vec3(-.7,1.2,1.8));
      vec3 eye = normalize(-vPosition);
      float diffuse = max(0.,dot(n,light));
      float spec = pow(max(0.,dot(n,normalize(light+eye))),48.);
      float rim = pow(1.-abs(dot(n,eye)),3.);
      float focus = max(0.,1.-abs(vBand-min(4.,floor(uProgress*5.))));
      vec3 metal = mix(vec3(.18,.23,.25),vec3(.33,.48,.49),focus*.65);
      metal = mix(metal,vec3(.18,.24,.27),uLight*.7);
      vec3 col = metal*(.30+diffuse*.95)+vec3(.77,.86,.85)*spec*.9+vec3(.39,.59,.60)*rim*.38;
      float etch = step(.9,fract(vUV.x*150.));
      col *= 1.-etch*.26;
      float edge = step(vUV.y,.018)+step(.982,vUV.y);
      float cap = step(vUV.x,.004)+step(.996,vUV.x);
      col += (edge+cap)*vec3(.38,.52,.52)*(focus*.45+.40);
      float ruling = step(.972,fract(vUV.x*30.))*step(.76,vUV.y);
      col += ruling*vec3(.34,.42,.43);
      gl_FragColor=vec4(col,1.);
    }`;
  function shader(type, source) {
    const shader = gl.createShader(type); gl.shaderSource(shader, source); gl.compileShader(shader);
    if (!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) { console.warn('Limits sculpture shader:', gl.getShaderInfoLog(shader)); gl.deleteShader(shader); return null; }
    return shader;
  }
  const vs=shader(gl.VERTEX_SHADER,vertex), fs=shader(gl.FRAGMENT_SHADER,fragment);
  if (!vs || !fs) { if(vs)gl.deleteShader(vs); if(fs)gl.deleteShader(fs); return null; }
  const program=gl.createProgram(); gl.attachShader(program,vs); gl.attachShader(program,fs); gl.linkProgram(program);
  gl.deleteShader(vs); gl.deleteShader(fs);
  if (!gl.getProgramParameter(program,gl.LINK_STATUS)) { console.warn('Limits sculpture link:', gl.getProgramInfoLog(program)); gl.deleteProgram(program); return null; }
  const vertices=[];
  for(let b=0;b<5;b++) for(let t=0;t<160;t++) for(let v=0;v<10;v++) {
    for(const [dt,dv] of [[0,0],[1,0],[0,1],[0,1],[1,0],[1,1]]) vertices.push((t+dt)/160,(v+dv)/10,b);
  }
  const buffer=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,buffer); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);
  gl.useProgram(program);
  const attr=gl.getAttribLocation(program,'aParam'); gl.enableVertexAttribArray(attr); gl.vertexAttribPointer(attr,3,gl.FLOAT,false,0,0);
  const uniform = Object.fromEntries(['uProgress','uAspect','uLight'].map(n=>[n,gl.getUniformLocation(program,n)]));
  gl.enable(gl.DEPTH_TEST); gl.clearColor(0,0,0,0);
  return {
    draw(p) {
      const dpr=Math.min(devicePixelRatio||1,1.75), w=Math.round(canvas.clientWidth*dpr), h=Math.round(canvas.clientHeight*dpr);
      if(!w||!h)return;
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
      gl.viewport(0,0,w,h); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      gl.uniform1f(uniform.uProgress,p);gl.uniform1f(uniform.uAspect,w/h);gl.uniform1f(uniform.uLight,document.documentElement.dataset.theme==='field'?1:0);
      gl.drawArrays(gl.TRIANGLES,0,vertices.length/3);
    },
    destroy(){gl.deleteBuffer(buffer);gl.deleteProgram(program);}
  };
}

/* ---------------------------------------------------------------------------
   THE RAIL NO LONGER OWNS A SCROLLTRIGGER.

   It used to pin itself and scrub its own five panels, which was right while
   it was the only locked thing inside #proof. #proof is now one pinned screen
   in its own right (see the storyboard in proof.js), and a pin inside a pin is
   a fight: ScrollTrigger measures the inner trigger against a spacer the outer
   one has not finished inserting, and the two disagree on every refresh.

   So the rail exposes its render instead, and proof.js drives it from the
   master timeline. Everything the rail actually does -- the helicoid, the
   numeral, the nav fills, the dissolve at each panel boundary, the WebGL-loss
   path -- is unchanged and still lives here. What left is only the question of
   WHEN, which was never this file's to answer once it stopped being the only
   locked thing on the screen.

   `onJump` is how the nav gets its old behaviour back. The buttons used to
   seek this file's own trigger; they now hand an index up and proof.js seeks
   the master. The reader cannot tell the difference, which is the point.
   ------------------------------------------------------------------------ */
export function wireLimits(proof, { onJump } = {}) {
  const section=proof.querySelector('.limits--atlas'); if(!section)return null;
  /* BY CLASS, NOT BY POSITION.
     This used to read `section.querySelector('canvas')`, which was correct only
     for as long as the rail held exactly one canvas. proof.js PREPENDS the
     Predictive Arc's host as the rail's first child, and its note there says
     the prepend is safe because nothing in this file selects by position --
     true when it was written. It stopped being true the moment wireLimitsField
     ran before wireLimits, and the helicoid was then handed the arc's canvas:
     a canvas that already had a WebGL context, so mountSculpture failed, the
     rail took `la-no-gl`, and the 3D object simply was not there. Asking for
     the element by name costs nothing and cannot be broken by call order. */
  const canvas=section.querySelector('.la-sculpture');
  const sculpture=mountSculpture(canvas);
  if(!sculpture) section.classList.add('la-no-gl');
  const readings=[...section.querySelectorAll('.la-reading')];
  const buttons=[...section.querySelectorAll('[data-limit-jump]')];
  const numeral=section.querySelector('.la-index');
  const state={p:0}; let playing=false;
  const clamp=x=>Math.max(0,Math.min(1,x));
  function render() {
    const scaled=state.p*5, active=Math.min(4,Math.floor(scaled));
    numeral.textContent=`0${active+1}`;
    buttons.forEach((button,i)=>{
      button.setAttribute('aria-current',i===active?'step':'false');
      button.style.setProperty('--fill',clamp(scaled-i));
    });
    if(playing) readings.forEach((reading,i)=>{
      const d=scaled-i;
      // A held reading, with a short lens dissolve at the boundary. Text
      // remains in the accessibility tree; no invisible focusable controls.
      const enter=i===0?1:clamp(d/.12);
      const leave=i===4?1:clamp((1-d)/.12);
      const opacity=d>=0&&d<=1?Math.min(enter,leave):0;
      reading.style.opacity=opacity;
      reading.style.transform=`translateZ(${(1-opacity)*-35}px)`;
    });
    sculpture?.draw(playing?state.p:.08);
  }
  buttons.forEach((button,i)=>button.addEventListener('click',()=>onJump?.(i)));
  const resize=new ResizeObserver(render); resize.observe(canvas);
  const theme=new MutationObserver(render);theme.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();section.classList.add('la-no-gl');});
  const stop=()=>{resize.disconnect();theme.disconnect();sculpture?.destroy();};
  window.addEventListener('pagehide',stop,{once:true});
  render();
  return {
    /* The scalar proof.js tweens. Handed out rather than set through a method
       so the master can drive it with an ordinary gsap tween and no callback
       hop per frame. */
    state,
    render,
    /* Stacked, every panel is simply present and the sculpture rests at .08 --
       the same still frame the unpinned build has always shown. */
    setPlaying(on) {
      playing=on;
      section.classList.toggle('la-playing',on);
      if(!on) readings.forEach(reading=>{reading.style.opacity='';reading.style.transform='';});
      render();
    },
    destroy:stop,
  };
}
