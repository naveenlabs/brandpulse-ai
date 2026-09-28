import{c as Pe,o as $e,g as L,r as j,M as xt,S as Ae,a as Ot,m as Nt}from"./chrome-Bbzm0knH.js";import{e as w,C as Ne,n as Y,q as nt,r as rt,m as ke,t as ge,a as qt,p as V,F as be,c as ue,u as zt,k as Ht,v as Xt,w as Gt,l as Vt,g as Wt,i as Yt}from"./contract-wMVeQDZg.js";import{m as jt,v as Kt,s as wt}from"./frames-Dx4w5fNa.js";const Zt={mode:"dark",speed:1,pixelSize:8,arcCenter:.4,arcDrop:.9,thickness:.35,brightness:1,hue:0,saturation:1,maxPixelRatio:2};function Qt(o){return o==="light"||o===1||o==="1"?"light":"dark"}function Jt(o,a){const t=o.getContext("2d",{alpha:!0});if(!t)return null;let n=1,e=1,r=0,s=null;return{resize:(l,d)=>{n=Math.max(1,l),e=Math.max(1,d);const m=Math.min(window.devicePixelRatio||1,a().maxPixelRatio??2);o.width=Math.round(n*m),o.height=Math.round(e*m),t.setTransform(m,0,0,m,0,0),s=t.createLinearGradient(0,0,0,e),s.addColorStop(0,"#f8faf6"),s.addColorStop(.58,"#f3f6f1"),s.addColorStop(1,"#edf1ec")},render:()=>{const l=a(),d=Qt(l.mode)==="light";t.clearRect(0,0,n,e);const m=Math.ceil(n/l.pixelSize),f=Math.ceil(e/l.pixelSize),g=e*l.arcCenter,b=e*l.arcDrop,u=e*l.thickness;for(let h=0;h<m;h+=1)for(let y=0;y<f;y+=1){const _=h*l.pixelSize,M=y*l.pixelSize,F=_/n*2-1,p=g+Math.pow(Math.abs(F),1.8)*b;let v=Math.max(0,1-Math.abs(M-p)/u);if(v<=.01)continue;const U=Math.sin(F*4-r*1.5)*.1,T=Math.cos(M*.01+r)*.1;if(v=Math.max(0,Math.min(1,v+U+T)),v*=Math.max(0,1-Math.pow(Math.abs(F),2.5)),v<=.02)continue;const R=Math.pow(v,3),I=Math.pow(v,1.5);let z,K,ne;if(d){const re=Math.pow(v,.78),D=Math.max(.45,Math.min(1.35,l.brightness)),B=[238,242,237],ie=[192-172*re-10*R,204-88*re+18*R,193-132*re+4*R];z=Math.max(0,Math.min(255,Math.round(B[0]+(ie[0]-B[0])*D))),K=Math.max(0,Math.min(255,Math.round(B[1]+(ie[1]-B[1])*D))),ne=Math.max(0,Math.min(255,Math.round(B[2]+(ie[2]-B[2])*D)))}else z=Math.floor((30*v+100*R)*l.brightness),K=Math.floor((220*I+40*R)*l.brightness),ne=Math.floor((80*v+50*R)*l.brightness);t.fillStyle=`rgb(${z}, ${K}, ${ne})`,t.globalAlpha=d?Math.min(1,.22+Math.pow(v,.68)*.78):v,t.fillRect(_,M,l.pixelSize-1,l.pixelSize-1)}t.globalAlpha=1,r+=.02*l.speed}}}function eo(o,a={}){if(!o)return null;const t={...Zt,...a};let n=!!a.still;const e=document.createElement("canvas");o.appendChild(e);const r=Jt(e,()=>t);if(!r)return e.remove(),null;let s=0,i=!0;const c=()=>{const h=o.getBoundingClientRect();r.resize(h.width,h.height),r.render()},l=()=>{r.render(),s=i&&!document.hidden?requestAnimationFrame(l):0},d=()=>{n||s||!i||document.hidden||(s=requestAnimationFrame(l))},m=()=>{s&&cancelAnimationFrame(s),s=0},f=new ResizeObserver(c),g=new IntersectionObserver(([h])=>{i=h?.isIntersecting??!0,i?d():m()}),b=()=>{document.hidden?m():d()};f.observe(o),g.observe(o),document.addEventListener("visibilitychange",b),c(),n||(s=requestAnimationFrame(l));const u=h=>{n=!!(h.detail&&h.detail.reduced),n?(m(),r.render()):d()};return window.addEventListener("motionchange",u),e.style.opacity=String(t.opacity??1),e.style.filter=`hue-rotate(${t.hue}deg) saturate(${t.saturation})`,()=>{m(),window.removeEventListener("motionchange",u),f.disconnect(),g.disconnect(),document.removeEventListener("visibilitychange",b),e.remove()}}function to(o){const a=o.flagged||o.segment,t=(a.start_s+a.end_s)/2,n=o.strip.seconds.reduce((r,s)=>Math.abs(s-t)<Math.abs(r-t)?s:r),e=`/static/frames/${o.videoId}/p/${n}.jpg`;return`<section id="film" class="film film--chamber" aria-labelledby="film-heading">
    <div class="f-chamber">
      <div class="f-field" data-film-field aria-hidden="true"></div>
      <div class="f-atmosphere" aria-hidden="true"></div>
      <div class="f-topline"><span><i></i> BrandPulse / The signal chamber</span><span>One real analysis<span class="sep" aria-hidden="true"></span>${w(o.report.brand_name||"Local video")}</span></div>
      <div class="f-space" aria-hidden="true">
        <canvas class="f-orbits"></canvas>
        <div class="f-optics"><div class="f-object">
          ${Ne.map((r,s)=>`<div class="f-plate" style="--channel:var(--ch-${r});--i:${s}">
            <div class="f-plate__image"><img src="${w(e)}" alt=""><span class="f-plate__scan"></span></div>
            <div class="f-plate__label"><span>0${s+1} / ${w(Y[r].short)}</span><span>${w(nt(rt(a,r,o.report.comment_sentiment))||"Not measured")}</span></div>
            <span class="f-plate__corner"></span>
          </div>`).join("")}
        </div></div>
        <span class="f-coordinate f-coordinate--a">Signal / ${w(ke(a.start_s))}</span>
        <span class="f-coordinate f-coordinate--b">Four independent readings</span>
      </div>
      <div class="f-story">
        <article class="f-beat is-current" data-beat="0">
          <p class="f-eyebrow">01 / Look beneath the surface</p>
          <h2 id="film-heading">A second.<br><em>Four sides.</em></h2>
          <p class="f-body">A video gives you one impression.<br>Turn it over. There’s more underneath.</p>
          <p class="f-invitation">${ge("down")} Scroll to pull the moment apart</p>
        </article>
        <article class="f-beat" data-beat="1">
          <p class="f-eyebrow">02 / Separate the signals</p>
          <h2>The words.<br>The <em>undertow.</em></h2>
          <p class="f-body">What was said. The face. The voice.<br>Three readings of the same moment.<br>And one account from the audience.</p>
          <p class="f-aside">The audience is read across the whole video.<br>Comments cannot be pinned to a second.</p>
        </article>
        <article class="f-beat" data-beat="2">
          <p class="f-eyebrow">03 / ${o.flagged?"The point of disagreement":"Inside the measurement"}</p>
          <h2>${o.flagged?"The signal<br><em>splits here.</em>":"Every signal.<br><em>Accounted for.</em>"}</h2>
          <div class="f-measure"><span>${w(ke(a.start_s))}</span><div>Conflict score<strong>${w(qt(a.conflict_score))}</strong></div></div>
          <p class="f-body">${o.flagged?"This moment was flagged by the local model. Different channels told different stories.":"The local model compares the channels. This report has no flagged moments."}</p>
        </article>
        <article class="f-beat" data-beat="3">
          <p class="f-eyebrow">04 / Evidence, with its edges intact</p>
          <h2>Nothing hidden.<br><em>Nothing sent.</em></h2>
          <p class="f-body">Every reading stays on this machine.<br>Every weakness stays in the report.</p>
          <p class="f-aside">Facial accuracy: ${w(V(Y.facial.accuracy))} on held-out speakers.<br>Always-neutral baseline: ${w(V(be.constant.value))}. We publish both.</p>
          <a class="f-link" href="${w(o.href)}">Open this analysis ${ge("next")}</a>
        </article>
      </div>
      <div class="f-evidence" role="group" aria-label="Readings for the selected moment">
        ${Ne.map((r,s)=>`<div style="--channel:var(--ch-${r})"><span class="f-evidence__name"><i></i>${w(Y[r].short)}<small>${r==="audience"?"Video-level":ke(a.start_s)}</small></span><strong>${w(nt(rt(a,r,o.report.comment_sentiment))||"Not measured")}</strong></div>`).join("")}
      </div>
      <div class="f-bottom"><span class="f-step">01 / 04</span><div class="f-track"><i></i></div><span>Scroll to explore ${ge("down")}</span><a href="#proof">Skip sequence ${ge("down")}</a></div>
    </div>
  </section>`}function oo(){const o=document.getElementById("film");if(!o)return;const a=o.querySelector(".f-orbits"),t=a.getContext("2d"),n=[...o.querySelectorAll(".f-plate")],e=[...o.querySelectorAll(".f-beat")],r=o.querySelector(".f-object"),s=o.querySelector(".f-space"),i=o.querySelector(".f-evidence"),c=o.querySelector(".f-track i"),l=o.querySelector(".f-step"),d={p:0};let m=1,f=1,g=[],b="",u=-1;const h=x=>Math.max(0,Math.min(1,x)),y=(x,A,O)=>{const S=h((O-x)/(A-x));return S*S*(3-2*S)},_=(x,A)=>A?1:y(.16,.43,x)*(1-y(.77,.96,x));function M(x,A){if(!t)return;t.clearRect(0,0,m,f);const O=_(x,A),S=A?-.28:-.28+x*2.5,k=A?.65:.65+Math.sin(x*Math.PI)*.38,ce=Math.min(m*.39,f*.4),se=(N,G,Z)=>{const q=N*Math.cos(S)+Z*Math.sin(S),C=-N*Math.sin(S)+Z*Math.cos(S),le=G*Math.cos(k)-C*Math.sin(k),Q=G*Math.sin(k)+C*Math.cos(k),te=1e3/(1e3+Q);return[m*.5+q*te,f*.5+le*te,Q,te]};for(let N=0;N<4;N++){const G=ce*(.72+N*.105),Z=(N-1.5)*(14+O*52);for(let q=0;q<6;q++){t.beginPath();for(let C=0;C<=180;C++){const le=C/180*Math.PI*2,Q=G+q*1.8,te=se(Math.cos(le)*Q,Z+Math.sin(le*3+N)*O*13,Math.sin(le)*Q);C?t.lineTo(te[0],te[1]):t.moveTo(te[0],te[1])}t.strokeStyle=g[N],t.globalAlpha=q===0?.7:.12,t.lineWidth=q===0?1:.65,t.stroke()}for(let q=0;q<140;q++){const C=q/140*Math.PI*2,le=q%5===0?18:6,Q=se(Math.cos(C)*(G+12),Z,Math.sin(C)*(G+12)),te=se(Math.cos(C)*(G+12+le),Z,Math.sin(C)*(G+12+le));t.beginPath(),t.moveTo(...Q.slice(0,2)),t.lineTo(...te.slice(0,2)),t.strokeStyle=g[N],t.globalAlpha=.22+(Q[2]<0?.32:0),t.stroke(),q%35===0&&(t.fillStyle=g[N],t.globalAlpha=.9,t.beginPath(),t.arc(Q[0],Q[1],2.3*Q[3],0,Math.PI*2),t.fill())}}for(let N=0;N<240;N++){const G=1-N/239*2,Z=Math.sqrt(1-G*G),q=N*2.399963,C=se(Math.cos(q)*Z*ce*1.3,G*ce*1.3,Math.sin(q)*Z*ce*1.3);t.globalAlpha=C[2]<0?.35:.12,t.fillStyle=b,t.fillRect(C[0],C[1],1.2*C[3],1.2*C[3])}t.globalAlpha=1}let F=!1,p=!1,v=!1;const U=[.1,.36,.63,.88];let T=null;function R(){const x=d.p,A=_(x,F),O=F?0:y(.78,1,x),S=o.clientWidth<760,k=v?-1:x<.23?0:x<.49?1:x<.77?2:3;k!==u&&(e.forEach((ce,se)=>ce.classList.toggle("is-current",v||se===k)),l.textContent=v?"04 / 04":`0${k+1} / 04`,u=k),c.style.transform=`scaleX(${v?1:x})`,i.style.opacity=F||v?"1":String(y(.27,.4,x)*(1-y(.76,.85,x))),s.style.setProperty("--separation",A),s.style.transform=F?"none":`scale(${1+y(.45,.72,x)*.12-O*.12})`,r.style.transform=F?"none":`rotateX(${-8+A*9}deg) rotateY(${-22+x*75}deg) rotateZ(${-8+A*12-O*4}deg)`,n.forEach((ce,se)=>{const N=(se-1.5)*(F?0:3+A*105),G=(se-1.5)*A*(S?23:42),Z=(se-1.5)*A*(S?18:32);ce.style.transform=`translate3d(${G}px,${Z}px,${N}px)`,ce.style.opacity="1"}),M(x,F)}function I(){const x=a.getBoundingClientRect();m=x.width,f=x.height;const A=Math.min(window.devicePixelRatio||1,2);a.width=Math.round(m*A),a.height=Math.round(f*A),t&&t.setTransform(A,0,0,A,0,0);const O=getComputedStyle(o);g=Ne.map(S=>O.getPropertyValue(`--ch-${S}`).trim()),b=O.getPropertyValue("--ink").trim(),R()}const z=new ResizeObserver(I);z.observe(s);const K=new MutationObserver(I);K.observe(document.documentElement,{attributes:!0,attributeFilter:["data-theme"]}),o.addEventListener("focusin",x=>{const A=x.target.closest&&x.target.closest(".f-beat");if(!A||v||!T)return;const O=e.indexOf(A);if(O<0||O===u)return;const S=T.start+U[O]*(T.end-T.start);window.scrollTo({top:S,behavior:"instant"}),d.p=U[O],R()});const ne=Pe({motion:"(prefers-reduced-motion: no-preference)",reduce:"(prefers-reduced-motion: reduce)",fits:"(min-width: 760px) and (min-height: 640px), (max-width: 759.98px) and (min-height: 720px)"},x=>{if(v=!x.conditions.fits||p,F=!!x.conditions.reduce||v,o.classList.toggle("film--stacked",v),u=-2,v)return T=null,d.p=1,I(),()=>{o.classList.remove("film--stacked")};const A=L.fromTo(d,{p:0},{p:1,ease:"none",onUpdate:R,scrollTrigger:{trigger:o,start:"top top",end:()=>`+=${window.innerHeight*(F?3:4.8)}`,pin:!0,scrub:F?!0:.65,anticipatePin:1,invalidateOnRefresh:!0}});return T=A.scrollTrigger,I(),()=>{T=null,A.scrollTrigger?.kill(),A.kill()}}),re=o.querySelector(".f-chamber"),D=()=>{const x=re.getBoundingClientRect().bottom;return e.some(A=>[...A.querySelectorAll("*")].some(O=>O.getBoundingClientRect().bottom>x+1))};let B=0;const ie=new ResizeObserver(()=>{v||p||B||(B=requestAnimationFrame(()=>{B=0,!v&&!p&&D()&&(p=!0,ne.rebuild())}))});for(const x of e)for(const A of x.children)ie.observe(A);ro(o),window.addEventListener("pagehide",()=>{ne.revert(),z.disconnect(),K.disconnect(),ie.disconnect()},{once:!0})}const ao={dark:.5,light:.45},no={dark:.55,light:.18};function ro(o){const a=o.querySelector("[data-film-field]");if(!a)return;let t=null;const n=()=>{t&&(t(),t=null);const e=document.documentElement.dataset.theme==="field"?"light":"dark";t=eo(a,{mode:e,still:j(),arcCenter:.82,arcDrop:.9,thickness:.4,pixelSize:10,speed:.55,brightness:ao[e],opacity:no[e],hue:0,saturation:.3})};n(),window.addEventListener("themechange",n),$e(n)}const At=[[[4.46,3],[10.68,7],[4.46,7]],[[4.46,7.6],[11.62,7.6],[17.84,11.6],[4.46,11.6]],[[6.16,12.4],[19.54,12.4],[13.32,16.4],[6.16,16.4]],[[4.46,17],[10.68,17],[4.46,21]]],so=At.map(o=>"M"+o.map(([a,t])=>`${a} ${t}`).join("L")+"Z").join(""),Et=.6,io=(1-Et)/2,st=Et/24;function co(o){return`vec2(${o[0].toFixed(4)},${o[1].toFixed(4)})`}const lo=At.map(o=>{const a=o.map(co).join(",");return o.length===3?`  d = min(d, sdTri(q, ${a}));`:`  d = min(d, sdQuad(q, ${a}));`}).join(`
`),ve=512;function uo(o){const a=document.createElement("canvas");a.width=a.height=ve;const t=a.getContext("2d"),n=ve*.6,e=n/24,r=(ve-n)/2;return t.setTransform(e,0,0,e,r,r),t.fillStyle="#fff",t.fill(new Path2D(o)),t.getImageData(0,0,ve,ve)}function fo(o){const a=ve,t=[],n=(e,r)=>o.data[(r*a+e)*4+3]>127;for(let e=1;e<a-1;e++)for(let r=1;r<a-1;r++){if(!n(r,e))continue;const s=n(r-1,e),i=n(r+1,e),c=n(r,e-1),l=n(r,e+1);if(s&&i&&c&&l)continue;const d=(i?1:0)-(s?1:0),m=(l?1:0)-(c?1:0);let f=-d,g=m;const b=Math.hypot(f,g);b?(f/=b,g/=b):(f=0,g=1),t.push((r+.5)/a,1-(e+.5)/a,f,g)}return t}function ho(o,a){const t=new Float32Array(a*5),n=o.length/4;for(let e=0;e<a;e++){const r=Math.random()*n|0;t[e*5]=o[r*4],t[e*5+1]=o[r*4+1],t[e*5+2]=o[r*4+2],t[e*5+3]=o[r*4+3],t[e*5+4]=Math.random()*100+e*.618}return t}const it=`#version 300 es
out vec2 vUv;
void main(){
  vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  vUv = p;
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`,mo=`
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
  vec2 q = (vec2(m.x, 1.0 - m.y) - ${io.toFixed(4)}) / ${st.toFixed(6)};
  float d = 1e9;
${lo}
  return d * ${st.toFixed(6)};
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
`,po=`#version 300 es
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
}`,vo=`#version 300 es
${mo}
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
}`,go=`#version 300 es
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
}`,bo=`#version 300 es
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
}`;function ct(o,a,t){const n=o.createShader(a);return o.shaderSource(n,t),o.compileShader(n),o.getShaderParameter(n,o.COMPILE_STATUS)?n:null}function Ue(o,a,t){const n=o.createProgram(),e=ct(o,o.VERTEX_SHADER,a),r=ct(o,o.FRAGMENT_SHADER,t);return!e||!r||(o.attachShader(n,e),o.attachShader(n,r),o.linkProgram(n),!o.getProgramParameter(n,o.LINK_STATUS))?null:n}const De=Math.min(window.devicePixelRatio||1,1.75),he=512,yo={zoom:1.22,shift:[.012,.055],particles:{count:160,travel:.1,lifeMin:4,lifeMax:8,alongNormal:.15,wiggle:.02,sizeMin:1.5,sizeMax:3.5,sparse:.5,colA:[.1,.24,.3],colB:[.22,.4,.48]}};class _o{constructor(a,t,n,e,r){this.el=a,this.canvas=t,this.opts=r,this.pointer={x:.5,y:.5,active:0},this.wind=0,this.windTarget=0,this.dropQueue=[],this.nextAutoDrop=.6,this.needsResize=!1,this.ok=!1,this.listeners=[];const s=t.getContext("webgl2",{alpha:!1,antialias:!1});if(!s||(this.gl=s,this.prog=Ue(s,it,n),!this.prog))return;this.uni={};for(const c of["uTime","uAspect","uScale","uShift","uPointer","uState","uSimTexel","uWind"])this.uni[c]=s.getUniformLocation(this.prog,c);if(!s.getExtension("EXT_color_buffer_float")||(this.simProg=Ue(s,it,po),!this.simProg))return;this.simUni={uState:s.getUniformLocation(this.simProg,"uState"),uTexel:s.getUniformLocation(this.simProg,"uTexel"),uDrop:s.getUniformLocation(this.simProg,"uDrop")},this.simTex=[],this.simFbo=[];for(let c=0;c<2;c++){const l=s.createTexture();s.bindTexture(s.TEXTURE_2D,l),s.texImage2D(s.TEXTURE_2D,0,s.RG16F,he,he,0,s.RG,s.HALF_FLOAT,null),s.texParameteri(s.TEXTURE_2D,s.TEXTURE_MIN_FILTER,s.LINEAR),s.texParameteri(s.TEXTURE_2D,s.TEXTURE_MAG_FILTER,s.LINEAR),s.texParameteri(s.TEXTURE_2D,s.TEXTURE_WRAP_S,s.CLAMP_TO_EDGE),s.texParameteri(s.TEXTURE_2D,s.TEXTURE_WRAP_T,s.CLAMP_TO_EDGE);const d=s.createFramebuffer();s.bindFramebuffer(s.FRAMEBUFFER,d),s.framebufferTexture2D(s.FRAMEBUFFER,s.COLOR_ATTACHMENT0,s.TEXTURE_2D,l,0),this.simTex.push(l),this.simFbo.push(d)}s.bindFramebuffer(s.FRAMEBUFFER,null),this.simSrc=0;const i=r.particles;if(i){if(this.partProg=Ue(s,go,bo),!this.partProg)return;this.partUni={};for(const d of["uTime","uScale","uShift","uDpr","uWind","uCfgA","uCfgB","uColA","uColB"])this.partUni[d]=s.getUniformLocation(this.partProg,d);const c=ho(e.edges,i.count);this.partVao=s.createVertexArray(),s.bindVertexArray(this.partVao);const l=s.createBuffer();s.bindBuffer(s.ARRAY_BUFFER,l),s.bufferData(s.ARRAY_BUFFER,c,s.STATIC_DRAW),s.enableVertexAttribArray(0),s.vertexAttribPointer(0,2,s.FLOAT,!1,20,0),s.enableVertexAttribArray(1),s.vertexAttribPointer(1,2,s.FLOAT,!1,20,8),s.enableVertexAttribArray(2),s.vertexAttribPointer(2,1,s.FLOAT,!1,20,16),s.bindVertexArray(null)}this.resize(),this.ro=new ResizeObserver(()=>{j()?this.resize():this.needsResize=!0}),this.ro.observe(a),this.bindPointer(),this.ok=!0}on(a,t,n){a.addEventListener(t,n),this.listeners.push([a,t,n])}resize(){const a=this.el.getBoundingClientRect(),t=Math.max(2,Math.round(a.width*De)),n=Math.max(2,Math.round(a.height*De));(this.canvas.width!==t||this.canvas.height!==n)&&(this.canvas.width=t,this.canvas.height=n),this.aspect=t/n,j()&&this.ok&&this.draw(.001)}bindPointer(){const a=e=>{const r=this.el.getBoundingClientRect();return{x:(e.clientX-r.left)/r.width,y:1-(e.clientY-r.top)/r.height}};let t=null,n=0;this.on(this.el,"pointermove",e=>{const r=a(e),s=performance.now();if(this.pointer.x=r.x,this.pointer.y=r.y,this.pointer.active=1,t){const i=Math.max(8,s-n),c=r.x-t.x,l=r.y-t.y,d=Math.hypot(c,l)/(i/1e3);d>.05&&this.dropQueue.length<6&&this.dropQueue.push({x:r.x,y:r.y,s:Math.min(d*.14,.55)}),this.windTarget=Math.max(-1,Math.min(1,c/(i/1e3)*.55))}t=r,n=s}),this.on(this.el,"pointerdown",e=>{const r=a(e);this.dropQueue.push({x:r.x,y:r.y,s:.9}),this.pointer.x=r.x,this.pointer.y=r.y,this.pointer.active=1.6}),this.on(this.el,"pointerup",()=>{this.pointer.active=1}),this.on(this.el,"pointerleave",()=>{this.pointer.active=0,t=null,this.windTarget=0})}toSimUV(a,t){const n=this.aspect,e=Math.max(n,1);return{x:.5+(a-.5)*n/e,y:.5+(t-.5)/e}}stepSim(a){const t=this.gl;a>this.nextAutoDrop&&(this.dropQueue.push({x:.12+Math.random()*.76,y:.12+Math.random()*.76,s:.12+Math.random()*.3}),this.nextAutoDrop=a+.5+Math.random()*1.4),t.useProgram(this.simProg),t.viewport(0,0,he,he),t.uniform2f(this.simUni.uTexel,1/he,1/he);for(let n=0;n<2;n++){const e=this.dropQueue.shift();if(e){const r=this.toSimUV(e.x,e.y);t.uniform3f(this.simUni.uDrop,r.x,r.y,e.s)}else t.uniform3f(this.simUni.uDrop,0,0,0);t.bindFramebuffer(t.FRAMEBUFFER,this.simFbo[1-this.simSrc]),t.activeTexture(t.TEXTURE1),t.bindTexture(t.TEXTURE_2D,this.simTex[this.simSrc]),t.uniform1i(this.simUni.uState,1),t.drawArrays(t.TRIANGLES,0,3),this.simSrc=1-this.simSrc}t.bindFramebuffer(t.FRAMEBUFFER,null)}scaleVec(){const a=this.opts.zoom,t=this.aspect,n=Math.min(t,1);return[t/n*a,1/n*a]}draw(a){const t=this.gl;this.needsResize&&(this.needsResize=!1,this.resize()),this.stepSim(a),this.wind+=(this.windTarget-this.wind)*.04,this.windTarget*=.97,t.useProgram(this.prog),t.viewport(0,0,this.canvas.width,this.canvas.height);const n=this.scaleVec();t.uniform1f(this.uni.uTime,a),t.uniform1f(this.uni.uAspect,this.aspect),t.uniform2f(this.uni.uScale,n[0],n[1]),t.uniform2f(this.uni.uShift,this.opts.shift[0],this.opts.shift[1]),t.uniform3f(this.uni.uPointer,this.pointer.x,this.pointer.y,this.pointer.active),this.uni.uWind&&t.uniform1f(this.uni.uWind,this.wind),t.activeTexture(t.TEXTURE1),t.bindTexture(t.TEXTURE_2D,this.simTex[this.simSrc]),t.uniform1i(this.uni.uState,1),t.uniform2f(this.uni.uSimTexel,1/he,1/he),t.drawArrays(t.TRIANGLES,0,3);const e=this.opts.particles;e&&(t.useProgram(this.partProg),t.uniform1f(this.partUni.uTime,a),t.uniform2f(this.partUni.uScale,n[0],n[1]),t.uniform2f(this.partUni.uShift,this.opts.shift[0],this.opts.shift[1]),t.uniform1f(this.partUni.uDpr,De),t.uniform1f(this.partUni.uWind,this.wind),t.uniform4f(this.partUni.uCfgA,e.travel,e.lifeMin,e.lifeMax,e.alongNormal),t.uniform4f(this.partUni.uCfgB,e.wiggle,e.sizeMin,e.sizeMax,e.sparse),t.uniform3f(this.partUni.uColA,e.colA[0],e.colA[1],e.colA[2]),t.uniform3f(this.partUni.uColB,e.colB[0],e.colB[1],e.colB[2]),t.enable(t.BLEND),t.blendFunc(t.ONE,t.ONE),t.bindVertexArray(this.partVao),t.drawArrays(t.POINTS,0,e.count),t.bindVertexArray(null),t.disable(t.BLEND))}destroy(){for(const[t,n,e]of this.listeners)t.removeEventListener(n,e);this.listeners=[],this.ro&&this.ro.disconnect();const a=this.gl&&this.gl.getExtension("WEBGL_lose_context");a&&a.loseContext(),this.gl=null}}function xo(o,{mark:a=so}={}){let t,n;try{t=document.createElement("canvas"),t.className="gate__canvas",t.setAttribute("aria-hidden","true"),o.prepend(t);const d=uo(a);n=new _o(o,t,vo,{edges:fo(d)},yo)}catch{n=null}if(!n||!n.ok)return n&&n.destroy(),t&&t.remove(),null;let e=0,r=!1;const s=performance.now(),i=()=>{n.draw((performance.now()-s)/1e3),e=requestAnimationFrame(i)},c=()=>{if(!r){if(r=!0,j()){n.draw(.001),r=!1;return}e=requestAnimationFrame(i)}},l=()=>{r=!1,e&&cancelAnimationFrame(e),e=0};return c(),{stop:l,destroy(){l(),n.destroy(),t.remove()}}}const wo=1e4,Ao=4e3,Eo=4e3,To=()=>xt.slow;function So(){return`
    <h1 class="gate__name">BrandPulse AI</h1>
    <button class="gate__begin" type="button">
      <span class="gate__begin__say">Click anywhere to begin</span>
      <span class="gate__begin__key">or press space</span>
      <span class="gate__hold" aria-hidden="true"><i></i></span>
    </button>
  `}function Mo({onEnter:o}={}){const a=document.createElement("div");a.className="gate",a.dataset.gate="",a.setAttribute("role","dialog"),a.setAttribute("aria-modal","true"),a.setAttribute("aria-label","BrandPulse AI"),a.innerHTML=So();const t=xo(a);if(!t)return null;const n=document.querySelector(".chassis");document.body.append(a),document.documentElement.classList.add("gated"),n&&(n.inert=!0);const e=a.querySelector(".gate__begin"),r=a.querySelector(".gate__hold"),s=r.querySelector("i"),i=document.activeElement;a.dataset.quiet="",e.focus({preventScroll:!0});let c,l=null,d=!1,m=0,f=0;function g(){if(d)return;d=!0,clearTimeout(m),clearTimeout(f),t.stop(),l=o?o():null,a.classList.add("is-going"),n&&!l&&(n.inert=!1),document.documentElement.classList.remove("gated");const u=()=>{if(document.removeEventListener("keydown",c),t.destroy(),a.remove(),l&&l.start){l.start();return}const h=document.getElementById("main");h?(h.setAttribute("tabindex","-1"),h.focus({preventScroll:!0})):i&&i.focus&&i.focus({preventScroll:!0})};j()?u():setTimeout(u,To())}a.addEventListener("click",u=>{u.target.closest(".gate__begin")||g()}),e.addEventListener("click",g),c=u=>{if(delete a.dataset.quiet,u.key==="Escape"){g();return}u.key==="Tab"&&(u.preventDefault(),e.focus({preventScroll:!0}))},document.addEventListener("keydown",c);function b(){if(d||m)return;const u=j()?Ao:wo;r.classList.add("is-running"),s.style.transitionDuration=`${u}ms`,requestAnimationFrame(()=>{s.style.transform="scaleX(1)"}),m=setTimeout(g,u)}return f=setTimeout(b,Eo),{ready(){clearTimeout(f),b()},dismiss:g}}const E=(o,a="p")=>({t:o,c:a}),fe=o=>".".repeat(o)+" ",we=[[E("BRANDPULSE AI   multimodal brand sentiment"),E("   CM3070","d")],[E("four channels   one local controller   nothing leaves this machine","d")],[],[E("Whisper transcription "),E(fe(9),"d"),E("OK","a")],[E("cardiffnlp XLM-RoBERTa "),E(fe(8),"d"),E("OK","a")],[E("audeering dimensional vocal "),E(fe(3),"d"),E("OK","a")],[E("yunet face detection "),E(fe(10),"d"),E("OK","a")],[E("YouTube Data API v3 "),E(fe(12),"d"),E("OK","a")],[E("llama3.1:8b  localhost:11434 "),E(fe(2),"d"),E("READY","a")],[],[E("ch0  TRANSCRIPT  what was said ","d"),E(fe(4),"d"),E("READY","a")],[E("ch1  FACIAL  the face on camera ","d"),E(fe(3),"d"),E("READY","a")],[E("ch2  VOCAL  how it was said ","d"),E(fe(7),"d"),E("READY","a")],[E("ch3  AUDIENCE  what viewers wrote ","d"),E(fe(1),"d"),E("READY","a")],[],[E("CHANNEL ANOMALY  "),E("facial reads below a constant.","h")],[E("measured 34.2% against 67.5% on held-out speakers ","d")],[E("down-weighted to 0.342 and reported on every surface ","d")],[E("press anything to continue: ")]],lt={p:{fill:"#8df0b4",glow:"rgba(28,236,132,0.95)"},d:{fill:"#4f9a76",glow:"rgba(28,236,132,0.45)"},a:{fill:"#ffba5e",glow:"rgba(255,150,52,0.95)"},h:{fill:"#eafff3",glow:"rgba(120,255,190,0.95)"}},X={curve:[.115,.165],scanDensity:.44,scanDepth:.3,triadCss:3.2,grille:.34,chroma:1,bar:.045,flicker:.028,grain:.022,vignette:.58,gain:1.34,halo:.1,sheen:[.55,1,.78],room:[.012,.03,.022],background:"#03100a"},Ge=o=>o.reduce((a,t)=>a+t.t.length,0),xe=we.reduce((o,a)=>o+Ge(a),0),Be=Math.max(...we.map(Ge)),Tt=4.4/(1e3/60),Ro=xe/Tt,Lo=1920,Fo=640,dt=24e5,Po=`attribute vec2 aPos;
void main(){ gl_Position = vec4(aPos,0.0,1.0); }`,$o=`precision highp float;
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
}`;function ut(o,a,t){const n=o.createShader(a);return o.shaderSource(n,t),o.compileShader(n),o.getShaderParameter(n,o.COMPILE_STATUS)?n:null}function Co(o,{onTyped:a,autoStart:t=!0}={}){const n=document.createElement("canvas");n.className="boot__canvas",n.setAttribute("aria-hidden","true"),o.prepend(n);const e=n.getContext("webgl",{antialias:!1,alpha:!1,depth:!1,premultipliedAlpha:!1}),r=document.createElement("canvas"),s=r.getContext("2d");if(!e||!s)return n.remove(),null;const i=ut(e,e.VERTEX_SHADER,Po),c=ut(e,e.FRAGMENT_SHADER,$o);if(!i||!c)return n.remove(),null;const l=e.createProgram();if(e.attachShader(l,i),e.attachShader(l,c),e.linkProgram(l),!e.getProgramParameter(l,e.LINK_STATUS))return n.remove(),null;e.useProgram(l);const d=e.createBuffer();e.bindBuffer(e.ARRAY_BUFFER,d),e.bufferData(e.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),e.STATIC_DRAW);const m=e.getAttribLocation(l,"aPos");e.enableVertexAttribArray(m),e.vertexAttribPointer(m,2,e.FLOAT,!1,0,0);const f=H=>e.getUniformLocation(l,H),g=f("uTex"),b=f("uRes"),u=f("uTime"),h=f("uMotion"),y=f("uCurve"),_=f("uScan"),M=f("uScanDepth"),F=f("uTriad"),p=f("uGrille"),v=f("uChroma"),U=f("uBar"),T=f("uFlicker"),R=f("uGrain"),I=f("uNoise"),z=f("uVignette"),K=f("uMono"),ne=f("uGain"),re=f("uHalo"),D=f("uSheen"),B=f("uRoom"),ie=e.createTexture();e.bindTexture(e.TEXTURE_2D,ie),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),e.uniform1i(g,0);let x=1,A=1,O=1,S=1,k=14,ce=20,se=0,N=8,G=0,Z=0,q=0,C=!1,le=!0,Q=0,te=-1,_e=-1;const je=performance.now();e.uniform2f(y,X.curve[0],X.curve[1]),e.uniform1f(M,X.scanDepth),e.uniform1f(p,X.grille),e.uniform1f(v,X.chroma),e.uniform1f(U,X.bar),e.uniform1f(T,X.flicker),e.uniform1f(R,X.grain),e.uniform1f(I,0),e.uniform1f(z,X.vignette),e.uniform1f(K,0),e.uniform1f(ne,X.gain),e.uniform1f(re,X.halo),e.uniform3f(D,X.sheen[0],X.sheen[1],X.sheen[2]),e.uniform3f(B,X.room[0],X.room[1],X.room[2]),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR);const Ke=()=>`600 ${k.toFixed(2)}px ui-monospace, "SF Mono", Menlo, Consolas, monospace`,Ut=()=>{se=A*.135,ce=A*.74/we.length,k=Math.max(5,Math.min(ce*.8,x*.88/(Math.max(Be,1)*.62))),s.font=Ke(),N=s.measureText("M").width||k*.6},Ze=(H,oe)=>{const $=lt[H];s.fillStyle=$.fill,s.shadowColor=oe?$.glow:"transparent",s.shadowBlur=oe?k*.38:0},Dt=H=>{s.setTransform(1,0,0,1,0,0),s.fillStyle=X.background,s.fillRect(0,0,x,A),s.textAlign="left",s.textBaseline="top",s.font=Ke();let oe=H,$=se;G=Math.floor((x-Be*N)/2),Z=se;for(const J of we){const Me=Ge(J),me=H===1/0?1/0:Math.min(oe,Me);let Re=Math.floor((x-Be*N)/2),Ce=0;for(const Le of J){let pe=Le.t;if(me!==1/0){const Ie=me-Ce;if(Ie<=0)break;Ie<pe.length&&(pe=pe.slice(0,Ie))}if(pe.length&&(Ze(Le.c,!0),s.fillText(pe,Re,$),Ze(Le.c,!1),s.fillText(pe,Re,$),Re+=N*pe.length),Ce+=Le.t.length,me!==1/0&&Ce>=me)break}if(G=Re,Z=$,me!==1/0&&(oe-=me),$+=ce,me!==1/0&&oe<=0)break}},Bt=()=>{s.shadowColor=lt.p.glow,s.shadowBlur=k*.42,s.fillStyle="#bdf8d2",s.fillRect(G,Z+k*.06,Math.max(N*.92,4),k*.96),s.shadowBlur=0,s.fillRect(G,Z+k*.06,Math.max(N*.92,4),k*.96)},Qe=()=>{e.bindTexture(e.TEXTURE_2D,ie),e.pixelStorei(e.UNPACK_FLIP_Y_WEBGL,!0),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,r),e.pixelStorei(e.UNPACK_FLIP_Y_WEBGL,!1),le=!1},Je=()=>{const H=o.getBoundingClientRect();O=Math.max(1,H.width),S=Math.max(1,H.height);const oe=Math.min(window.devicePixelRatio||1,2);let $=Math.max(Fo,Math.round(Math.min(O*oe,Lo))),J=Math.max(1,Math.round($*S/O));if($*J>dt){const Me=Math.sqrt(dt/($*J));$=Math.round($*Me),J=Math.round(J*Me)}(n.width!==$||n.height!==J)&&(n.width=$,n.height=J),(r.width!==$||r.height!==J)&&(r.width=$,r.height=J,x=$,A=J,Ut(),te=-1,_e=-1,Q=0,le=!0),e.useProgram(l),e.viewport(0,0,$,J),e.uniform2f(b,$,J),e.uniform1f(_,Math.max(120,Math.min(S*X.scanDensity,900))),e.uniform1f(F,Math.max(2,X.triadCss*$/O))},et=H=>{const oe=C?1/0:Math.floor(q),$=Math.floor((H-je)/420)%2===0?1:0,J=C?$!==_e:H-Q>42;oe===te&&$===_e&&!J||!C&&H-Q<=42&&oe===te&&$===_e||(Dt(oe),$&&Bt(),Q=H,te=oe,_e=$,le=!0)};Je();const tt=new ResizeObserver(()=>Je());tt.observe(o);let Ee=0,ot=!1,Te=t,Se=0;const at=H=>{const oe=(H-je)*.001;if(!C&&Te){const $=Se?Math.min(H-Se,100):16.666666666666668;q+=Tt*$,q>=xe&&(q=xe,C=!0)}Se=H,et(H),le&&Qe(),e.useProgram(l),e.uniform1f(u,oe),e.uniform1f(h,1),e.drawArrays(e.TRIANGLES,0,3),C&&!ot&&(ot=!0,a&&a()),Ee=requestAnimationFrame(at)};return j()?(Te=!0,q=xe,C=!0,et(performance.now()),Qe(),e.uniform1f(u,0),e.uniform1f(h,0),e.drawArrays(e.TRIANGLES,0,3),a&&a()):Ee=requestAnimationFrame(at),{start(){Te||(Te=!0,Se=0)},finish(){C||(q=xe,C=!0)},destroy(){Ee&&cancelAnimationFrame(Ee),tt.disconnect(),e.deleteBuffer(d),e.deleteTexture(ie),e.deleteProgram(l),e.deleteShader(i),e.deleteShader(c);const H=e.getExtension("WEBGL_lose_context");H&&H.loseContext(),n.remove()}}}const Io=we.map(o=>o.map(a=>a.t).join("")).join(`
`),ko=1600,Uo=2600,ft=()=>Ro+4e3;function Do({onDone:o,autoStart:a=!0}={}){const t=document.createElement("div");t.className="boot",t.dataset.boot="",t.setAttribute("role","dialog"),t.setAttribute("aria-modal","true"),t.setAttribute("aria-label","BrandPulse AI starting up"),t.innerHTML=`
    <pre class="boot__text sr-only" id="boot-log">${Io.replace(/[&<>]/g,u=>({"&":"&amp;","<":"&lt;",">":"&gt;"})[u])}</pre>
    <button class="boot__go" type="button" data-boot-go aria-describedby="boot-log">Continue</button>
  `;const n=t.querySelector("[data-boot-go]");let e=null,r=0,s=0,i=!1,c;function l(){if(i)return;i=!0,clearTimeout(r),clearTimeout(s),document.removeEventListener("keydown",c),t.classList.add("is-going");const u=()=>{e&&e.destroy(),t.remove(),f&&(f.inert=!1),document.documentElement.classList.remove("booting");const h=document.getElementById("main");h&&(h.setAttribute("tabindex","-1"),h.focus({preventScroll:!0})),o&&o()};j()?u():setTimeout(u,xt.slow)}let d=!1;function m(){if(d||!e){l();return}d=!0,e.finish()}document.documentElement.classList.add("booting"),document.body.append(t);const f=document.querySelector(".chassis");f&&(f.inert=!0),n.focus({preventScroll:!0});const g=n.matches(":focus-visible");if(e=Co(t,{autoStart:a,onTyped(){i||(clearTimeout(s),!g&&(r=setTimeout(l,j()?Uo:ko)))}}),!e)return document.documentElement.classList.remove("booting"),t.remove(),f&&(f.inert=!1),o&&o(),null;t.addEventListener("click",m);const b=["Shift","Control","Alt","Meta","CapsLock","Fn","OS"];return c=u=>{if(u.key==="Escape"){l();return}if(u.key==="Tab"){u.preventDefault(),n.focus({preventScroll:!0});return}b.includes(u.key)||u.ctrlKey||u.altKey||u.metaKey||u.target===n&&(u.key==="Enter"||u.key===" ")||m()},document.addEventListener("keydown",c),a&&!g&&(s=setTimeout(l,ft())),{leave:l,start(){e&&e.start(),g||(s=setTimeout(l,ft()))}}}const Bo='<svg class="hero__glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M4.46 3L10.68 7L4.46 7ZM4.46 7.6L11.62 7.6L17.84 11.6L4.46 11.6ZM6.16 12.4L19.54 12.4L13.32 16.4L6.16 16.4ZM4.46 17L10.68 17L4.46 21Z"/></svg>',St=[["transcript","Words","What was said"],["facial","Face","The face on camera"],["vocal","Voice","How it was said"],["audience","Audience","What viewers wrote"]];function Mt(o="open"){const a=Array.from({length:96},(t,n)=>{const e=n*Math.PI/48,r=n%8===0?210:n%4===0?216:222;return`<line x1="${250+Math.cos(e)*r}" y1="${250+Math.sin(e)*r}" x2="${250+Math.cos(e)*230}" y2="${250+Math.sin(e)*230}"/>`}).join("");return`<div class="signal-object signal-object--${o}" aria-hidden="true">
    <div class="signal-object__halo"></div>
    <div class="signal-object__shadow"></div>
    <div class="signal-object__rig">
      ${St.map(([t],n)=>`<div class="signal-object__layer" style="--layer:${n};--signal:var(--ch-${t})">
        <div class="signal-object__rim"></div>
        <svg class="signal-object__dial" viewBox="0 0 500 500"><g>${a}</g><circle cx="250" cy="250" r="198"/><circle class="signal-object__trace" cx="250" cy="250" r="188"/><text x="250" y="48" text-anchor="middle">0${n+1} / ${t.toUpperCase()}</text></svg>
        <i class="signal-object__point"></i>
      </div>`).join("")}
      <div class="signal-object__core"><span>BP</span><i></i><small>FOUR READINGS<br>ONE PERSPECTIVE</small></div>
    </div>
  </div>`}function Oo(){return`<section class="hero" aria-labelledby="hero-title">
    <div class="hero__edition"><span>BRANDPULSE / INDEPENDENT PERSPECTIVES</span><span><i></i> BUILT TO LOOK CLOSER</span></div>
    <div class="hero__stage">
      <div class="hero__copy">
        <p class="hero__eyebrow">ONE VIDEO. FOUR WAYS OF SEEING.</p>
        <h1 class="hero__title" id="hero-title"><span>Words are only</span><em>one reading.</em></h1>
        <p class="hero__sub">So this takes four, side by side.<br>And finds where they disagree.</p>
        <div class="hero__actions"><a class="btn hero__cta" data-variant="solid" href="#film">See it on a real video <span aria-hidden="true">↗</span></a><span class="hero__scroll">SCROLL TO LOOK BENEATH <span aria-hidden="true">↓</span></span></div>
      </div>
      <div class="hero__instrument">${Mt()}<div class="hero__spec" aria-hidden="true"><span>FIG. 01 / THE FOUR-CHANNEL INSTRUMENT</span><span>INDEPENDENT BY DESIGN</span></div></div>
    </div>
    <ul class="hero__feats">${St.map(([o,a,t],n)=>`<li style="--signal:var(--ch-${o})"><span class="hero__channel-no">0${n+1}<i></i></span><div><strong>${a}</strong><span>${t}</span></div></li>`).join("")}</ul>
    <footer class="hero__foot"><span>Every model runs on this machine. Nothing is uploaded.</span><span>CM3070 / FINAL YEAR PROJECT</span></footer>
  </section>`}let Rt=!1,Lt=!1;function Ft(){document.documentElement.classList.add("hero-in")}function Ve(){Rt=!0,Lt&&Ft()}function Pt(o,a=!1){if(!o)return;const t=new IntersectionObserver(([e])=>{o.dataset.inView=String(e.isIntersecting)},{rootMargin:"100px"});t.observe(o);const n=Pe("(prefers-reduced-motion: no-preference)",()=>{const e=o.querySelector(".signal-object__rig");L.fromTo(e,{rotationZ:a?-24:-28},{rotationZ:a?4:-8,ease:"none",scrollTrigger:{trigger:o,start:a?"top bottom":"top top",end:"bottom top",scrub:1,refreshPriority:a?-2:0}})});window.addEventListener("pagehide",e=>{e.persisted||(t.disconnect(),n.revert())},{once:!0})}function No(){document.documentElement.classList.add("has-hero");const o=document.querySelector(".hero");Ae.create({trigger:o,start:"bottom top+=80",onEnter:()=>document.documentElement.classList.add("is-past-hero"),onLeaveBack:()=>document.documentElement.classList.remove("is-past-hero")}),Pt(o),Lt=!0,Rt?Ft():setTimeout(Ve,3e4)}const qo=`
        attribute vec2 position;
        void main() {
          gl_Position = vec4(position, 0.0, 1.0);
        }
      `,zo=`
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
      `,Ho=Object.freeze({speed:1,pointerAmount:1,smoothing:.035,brightness:1,opacity:1,hue:0,saturation:1});function ht(o,a,t){const n=o.createShader(a);if(!n)throw new Error("Unable to create Axiom shader");if(o.shaderSource(n,t),o.compileShader(n),!o.getShaderParameter(n,o.COMPILE_STATUS))throw new Error(o.getShaderInfoLog(n)??"Axiom shader compilation failed");return n}function Xo(o,a={}){if(!o)return null;const t={...Ho,...a};let n=!!a.still;const e=document.createElement("canvas");o.appendChild(e);let r=null;try{r=e.getContext("webgl",{alpha:!0,antialias:!1,premultipliedAlpha:!1})}catch{r=null}if(!r)return e.remove(),null;let s,i,c;try{if(s=ht(r,r.VERTEX_SHADER,qo),i=ht(r,r.FRAGMENT_SHADER,zo),c=r.createProgram(),!c)throw new Error("Axiom program could not be created");if(r.attachShader(c,s),r.attachShader(c,i),r.linkProgram(c),!r.getProgramParameter(c,r.LINK_STATUS))throw new Error(r.getProgramInfoLog(c)??"Axiom program link failed")}catch{return e.remove(),null}r.useProgram(c);const l=r.createBuffer();r.bindBuffer(r.ARRAY_BUFFER,l),r.bufferData(r.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),r.STATIC_DRAW);const d=r.getAttribLocation(c,"position");r.enableVertexAttribArray(d),r.vertexAttribPointer(d,2,r.FLOAT,!1,0,0);const m=r.getUniformLocation(c,"resolution"),f=r.getUniformLocation(c,"time"),g=r.getUniformLocation(c,"pointer");let b=.72,u=.42,h=.72,y=.42,_=0,M=!0;const F=performance.now(),p=D=>{const B=o.getBoundingClientRect();h=.72+((D.clientX-B.left)/Math.max(B.width,1)-.72)*t.pointerAmount,y=.42+(1-(D.clientY-B.top)/Math.max(B.height,1)-.42)*t.pointerAmount},v=D=>{b+=(h-b)*t.smoothing,u+=(y-u)*t.smoothing,r.uniform1f(f,(D-F)*.001*t.speed),r.uniform2f(g,b,u),r.drawArrays(r.TRIANGLES,0,6)},U=()=>{const D=o.getBoundingClientRect(),B=Math.min(window.devicePixelRatio||1,2);e.width=Math.max(1,Math.floor(D.width*B)),e.height=Math.max(1,Math.floor(D.height*B)),r.viewport(0,0,e.width,e.height),r.uniform2f(m,e.width,e.height),n&&v(performance.now())},T=D=>{v(D),_=M&&!document.hidden?requestAnimationFrame(T):0},R=()=>{n||_||!M||document.hidden||(_=requestAnimationFrame(T))},I=()=>{_&&cancelAnimationFrame(_),_=0},z=new ResizeObserver(U),K=new IntersectionObserver(([D])=>{M=D?.isIntersecting??!0,M?R():I()}),ne=()=>{document.hidden?I():R()};z.observe(o),K.observe(o),o.addEventListener("pointermove",p,{passive:!0}),document.addEventListener("visibilitychange",ne),U(),n?v(performance.now()):_=requestAnimationFrame(T);const re=D=>{n=!!(D.detail&&D.detail.reduced),n?(I(),v(performance.now())):R()};return window.addEventListener("motionchange",re),e.style.opacity=String(t.opacity),e.style.filter=`hue-rotate(${t.hue}deg) saturate(${t.saturation}) brightness(${t.brightness})`,()=>{I(),window.removeEventListener("motionchange",re),z.disconnect(),K.disconnect(),o.removeEventListener("pointermove",p),document.removeEventListener("visibilitychange",ne),r.deleteBuffer(l),r.deleteShader(s),r.deleteShader(i),r.deleteProgram(c),e.remove()}}const ye=[{channel:"vocal",cy:5.66667,d:"M4.46 3L10.68 7L4.46 7Z"},{channel:"transcript",cy:9.80188,d:"M4.46 7.6L11.62 7.6L17.84 11.6L4.46 11.6Z"},{channel:"audience",cy:14.19812,d:"M6.16 12.4L19.54 12.4L13.32 16.4L6.16 16.4Z"},{channel:"facial",cy:18.33333,d:"M4.46 17L10.68 17L4.46 21Z"}],mt="4.46 3 15.08 18",$t="facial",Go=[.8,.7,.6,.5,.4,.3,.2,.1];function Vo(o,a){const t=(12-o.cy)/18,n=a-1.5,e=`${Math.abs(t).toFixed(5)} * var(--mh)`,r=`${Math.abs(n).toFixed(1)} * var(--row)`;return`calc(${t<0?"0px - ":""}${e} ${n<0?"-":"+"} ${r})`}function Wo(o={}){(o&&o.pipeline||{}).facial_only_conflict_weight;const t=be.constant,n=c=>Go.map((l,d)=>`<path d="${c}" transform="translate(${l.toFixed(2)} ${(l*1.35).toFixed(2)})"
           opacity="${(.96-d*.085).toFixed(3)}"/>`).join(""),e=`
      <svg class="seam__ghost" viewBox="${mt}" aria-hidden="true" focusable="false">
        <path d="${ye.map(c=>c.d).join(" ")}"/>
      </svg>
      ${ye.map((c,l)=>`
      <svg class="seam__piece" data-piece="${c.channel}" viewBox="${mt}"
           style="--dy: ${Vo(c,l)}" aria-hidden="true" focusable="false">
        <g class="seam__extrude">${n(c.d)}</g>
        <g class="seam__top">
          <path class="seam__face" d="${c.d}" fill="url(#seam-chrome)"/>
          <path class="seam__tint" d="${c.d}"/>
        </g>
      </svg>`).join("")}`,r=`
    <svg class="seam__defs" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="seam-chrome" gradientUnits="userSpaceOnUse"
                        x1="2.2" y1="1.4" x2="21.8" y2="22.6"
                        data-chrome>
          <stop offset="0"    stop-color="#20262f"/>
          <stop offset="0.11" stop-color="#75808f"/>
          <stop offset="0.21" stop-color="#e6eefa"/>
          <stop offset="0.30" stop-color="#9dabbc"/>
          <stop offset="0.44" stop-color="#ffffff"/>
          <stop offset="0.55" stop-color="#93a1b3"/>
          <stop offset="0.68" stop-color="#3e4653"/>
          <stop offset="0.82" stop-color="#c8d4e4"/>
          <stop offset="1"    stop-color="#2a313b"/>
        </linearGradient>
      </defs>
    </svg>`,s=c=>{const l=Y[c.channel],d=c.channel===$t?`${l.sample} — ${l.worseThanConstant}`:l.sample;return`
      <li class="seam__row" data-channel="${c.channel}">
        <span class="seam__rule" aria-hidden="true"></span>
        <p class="seam__name">${w(l.label)}</p>
        <b class="seam__num">${w(V(l.accuracy))}</b>
        <p class="seam__note">${w(d)}</p>
      </li>`},i=`
        Averaging the four would hide the one thing worth seeing. The face reads
        ${w(V(Y.facial.accuracy))} here, below an always-NEUTRAL
        constant at ${w(V(t.value))}; the words read
        ${w(V(Y.transcript.accuracy))}. Blend them and the face&rsquo;s
        error is carried into the answer while the disagreement that produced it
        disappears. So they are never fused. They are kept apart, compared, and
        the seconds where they contradict each other are what gets scored.`;return`
  <section class="seam" id="seam" aria-labelledby="seam-h" data-seam>
    <div class="seam__field" data-field aria-hidden="true"></div>
    <div class="seam__air" aria-hidden="true"></div>
    ${r}

    <div class="seam__open" data-beat="open">
      <h2 class="seam__h" id="seam-h">The mark is four pieces.</h2>
      <p class="seam__sub">
        So is every second this system scores: four readings, taken
        separately, never merged into one. Keep going and it comes apart.
      </p>
    </div>

    <div class="seam__stage">
      <div class="seam__glyph" data-glyph>${e}</div>
      <ol class="seam__rows" data-rows>${ye.map(s).join("")}</ol>
    </div>

    <div class="seam__shut" data-beat="shut">
      <h3 class="seam__h2">One piece never closes.</h3>
      <p class="seam__body">${i}</p>
    </div>
  </section>`}const ae={openOut:.06,apart:.12,rowsIn:.24,rowsOut:.62,home:.68,shutIn:.84},pt={y:-21,x:8},We=260,ee=o=>o*(We/100),P=o=>o*(We/100);function Yo(){const o=document.querySelector("[data-seam]");if(!o)return;const a=o.querySelector("[data-glyph]"),t=[...o.querySelectorAll(".seam__piece")],n=t.map(u=>u.querySelector(".seam__tint")),e=o.querySelector(".seam__ghost"),r=[...o.querySelectorAll(".seam__row")],s=o.querySelector('[data-beat="open"]'),i=o.querySelector('[data-beat="shut"]'),c=o.querySelector("[data-chrome]");if(!a||t.length!==ye.length)return;Xo(o.querySelector("[data-field]"),{still:j()});const l=(u,h)=>{const y=parseFloat(getComputedStyle(o).getPropertyValue(u));return Number.isFinite(y)?y:h},d=t.map(()=>0);function m(){L.set(a,{scale:1,rotationX:0,rotationY:0}),L.set(t,{clearProps:"transform"});const u=t.map(y=>y.getBoundingClientRect().top);L.set(t,{y:0});const h=t.map(y=>y.getBoundingClientRect().top);for(let y=0;y<t.length;y+=1)d[y]=u[y]-h[y];L.set(a,{scale:l("--pop",1.45),rotationY:pt.y,rotationX:pt.x,transformPerspective:1100,transformOrigin:"50% 50%"})}const f=()=>l("--mh",190)/14,g=u=>getComputedStyle(o).getPropertyValue(`--s-${u}`).trim()||"#ffffff",b=(u,h)=>{const y=h?g(h):"";return function(){const M=h?this.progress():1-this.progress();u.style.filter=M<.02?"none":`drop-shadow(0 0 ${(M*15).toFixed(1)}px ${y||g(u.dataset.piece)})`}};Pe({play:"(prefers-reduced-motion: no-preference) and (min-height: 640px)",still:"(prefers-reduced-motion: reduce), (max-height: 639px)"},u=>{if(u.conditions.still)return;o.classList.add("is-play"),m();const h=L.timeline({scrollTrigger:{trigger:o,start:"top top",end:`+=${We}%`,scrub:.5,pin:!0,anticipatePin:1,invalidateOnRefresh:!0,refreshPriority:1,onRefreshInit:m}});if(h.set({},{},ee(1)),h.to(s,{autoAlpha:0,y:-18,duration:P(.08),ease:"power2.in"},ee(ae.openOut)),h.to(a,{scale:1,rotationY:0,rotationX:0,duration:P(.22),ease:"power3.inOut"},ee(ae.apart)),c){const y={s:-1};h.to(y,{s:1,duration:P(1),ease:"none",onUpdate:()=>{c.setAttribute("gradientTransform",`translate(${(y.s*7).toFixed(3)} ${(y.s*7.6).toFixed(3)})`)}},0)}return t.forEach((y,_)=>{h.to(y,{y:()=>d[_],duration:P(.2),ease:"power3.inOut"},ee(ae.apart)+P(.035*_)),h.to(n[_],{opacity:.88,duration:P(.16),ease:"none"},ee(ae.apart)+P(.035*_)),h.fromTo(y,{rotationX:0},{rotationX:-16,duration:P(.1),ease:"power2.out",transformPerspective:900},ee(ae.apart)+P(.035*_)),h.to(y,{rotationX:0,duration:P(.1),ease:"power2.inOut"},ee(ae.apart)+P(.035*_)+P(.1)),h.to(y,{duration:P(.16),ease:"none",onUpdate:b(y,ye[_].channel)},ee(ae.apart)+P(.035*_))}),r.forEach((y,_)=>{const M=y.querySelector(".seam__rule");h.fromTo(M,{scaleX:0},{scaleX:1,duration:P(.1),ease:"power2.out"},ee(ae.rowsIn)+P(.045*_)),h.fromTo(y.querySelectorAll(".seam__name, .seam__num, .seam__note"),{autoAlpha:0,y:10},{autoAlpha:1,y:0,duration:P(.09),ease:"power2.out",stagger:P(.012)},ee(ae.rowsIn)+P(.045*_)+P(.02))}),h.to(e,{opacity:.34,duration:P(.08),ease:"none"},ee(ae.rowsOut)),h.to(r,{autoAlpha:0,y:-12,duration:P(.08),ease:"power2.in",stagger:P(.015)},ee(ae.rowsOut)),t.forEach((y,_)=>{const M=ye[_].channel===$t;h.to(y,{y:()=>M?f():0,duration:P(M?.16:.14),ease:M?"power4.out":"power3.inOut"},ee(ae.home)+P(.02*_)),h.to(n[_],{opacity:0,duration:P(.12),ease:"none"},ee(ae.home)+P(.02*_)),h.to(y,{duration:P(.12),ease:"none",onUpdate:b(y,null)},ee(ae.home)+P(.02*_))}),h.fromTo(i,{autoAlpha:0,y:18},{autoAlpha:1,y:0,duration:P(.1),ease:"power2.out"},ee(ae.shutIn)),()=>{o.classList.remove("is-play"),L.set([a,...t,...n,e,...r,s,i],{clearProps:"all"}),t.forEach(y=>{y.style.filter=""}),c&&c.removeAttribute("gradientTransform")}}),Ae.refresh()}function jo(o={},a=null){const t=o.report_count??0,n=a?.href?`<a class="close__quiet" href="${w(a.href)}">Open the one in the film ${ge("next")}</a>`:"";return`<section class="close" id="close" aria-labelledby="close-h" data-close>
    <div class="close__edition"><span>THE NEXT PERSPECTIVE</span><span>YOUR VIDEO / YOUR MACHINE</span></div>
    <div class="close__display">
      <div class="close__stage">
        <p class="close__badge"><i></i>${t>0?`${w(ue(t))} runs measured on this machine`:"Your first reading starts here"}</p>
        <h2 class="close__h" id="close-h">Now bring<br><em>your perspective.</em></h2>
        <p class="close__sub">Point it at a video of your own. Four independent readings. The agreement, the contradictions, and everything in between.</p>
        <a class="btn close__cta" data-variant="solid" href="/run">Analyse a video <span aria-hidden="true">↗</span></a>
        <p class="close__note">Four to nine minutes · Ollama running locally<br>Every score carries its limitations with it.</p>
      </div>
      <div class="close__instrument">${Mt("close")}<span class="close__inscription" aria-hidden="true">ONE VIDEO. A WIDER VIEW.</span></div>
    </div>
    <div class="close__promise"><span>Nothing uploaded.</span><span>Every model local.</span><em>All four readings, kept in view.</em></div>
    <footer class="close__bar end" role="contentinfo">
      <a class="close__mark end__sig" href="/">${Bo}<span>BrandPulse</span></a>
      <div class="close__ends">${n}<a class="btn" href="/library">Read ${ue(t)} saved runs</a></div>
    </footer>
  </section>`}function Ko(){Pt(document.querySelector("[data-close]"),!0)}const Zo=`
            attribute vec3 position;
            attribute vec2 uv;

            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = vec4(position, 1.0);
            }
        `,Qo=`
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
        `,Jo={dark:{shaderCore:"#FFFFFF",shaderFringe:"#1e3a8a"},light:{shaderCore:"#020202",shaderFringe:"#94a3b8"}},ea={speed:1,opacity:1,hue:0,saturation:1,brightness:1};function vt(o){const a=parseInt(o.slice(1),16);return[(a>>16&255)/255,(a>>8&255)/255,(a&255)/255]}function gt(o,a,t){const n=o.createShader(a);if(!n)throw new Error("Portal shader could not be created");if(o.shaderSource(n,t),o.compileShader(n),!o.getShaderParameter(n,o.COMPILE_STATUS))throw new Error(o.getShaderInfoLog(n)??"Portal shader compilation failed");return n}function ta(o,a={}){if(!o)return null;const t={...ea,...a};let n=!!a.still;const e=Jo[a.mode==="light"?"light":"dark"],r=a.mode==="light"?1:0,s=document.createElement("canvas");o.appendChild(s);let i=null;try{i=s.getContext("webgl",{alpha:!0,antialias:!0,premultipliedAlpha:!0})}catch{i=null}if(!i)return s.remove(),null;let c,l,d;try{if(c=gt(i,i.VERTEX_SHADER,Zo),l=gt(i,i.FRAGMENT_SHADER,Qo),d=i.createProgram(),!d)throw new Error("Portal program could not be created");if(i.attachShader(d,c),i.attachShader(d,l),i.linkProgram(d),!i.getProgramParameter(d,i.LINK_STATUS))throw new Error(i.getProgramInfoLog(d)??"Portal program link failed")}catch{return s.remove(),null}i.useProgram(d);const m=i.createBuffer();i.bindBuffer(i.ARRAY_BUFFER,m),i.bufferData(i.ARRAY_BUFFER,new Float32Array([-1,-1,0,1,-1,0,-1,1,0,-1,1,0,1,-1,0,1,1,0]),i.STATIC_DRAW);const f=i.getAttribLocation(d,"position");i.enableVertexAttribArray(f),i.vertexAttribPointer(f,3,i.FLOAT,!1,0,0);const g=i.createBuffer();i.bindBuffer(i.ARRAY_BUFFER,g),i.bufferData(i.ARRAY_BUFFER,new Float32Array([0,0,1,0,0,1,0,1,1,0,1,1]),i.STATIC_DRAW);const b=i.getAttribLocation(d,"uv");b>=0&&(i.enableVertexAttribArray(b),i.vertexAttribPointer(b,2,i.FLOAT,!1,0,0)),i.enable(i.BLEND),i.blendFunc(i.SRC_ALPHA,i.ONE),i.clearColor(0,0,0,0);const u=i.getUniformLocation(d,"u_time"),h=i.getUniformLocation(d,"u_resolution"),y=i.getUniformLocation(d,"u_mouse"),_=vt(e.shaderCore),M=vt(e.shaderFringe);i.uniform3f(i.getUniformLocation(d,"u_colorCore"),_[0],_[1],_[2]),i.uniform3f(i.getUniformLocation(d,"u_colorFringe"),M[0],M[1],M[2]),i.uniform1f(i.getUniformLocation(d,"u_isLightMode"),r);let F=.5,p=.5,v=.5,U=.5,T=0,R=!0;const I=performance.now(),z=S=>{const k=o.getBoundingClientRect();v=(S.clientX-k.left)/Math.max(k.width,1),U=1-(S.clientY-k.top)/Math.max(k.height,1)},K=S=>{F+=(v-F)*.03,p+=(U-p)*.03,i.uniform1f(u,(S-I)*.001*t.speed),i.uniform2f(y,F,p),i.clear(i.COLOR_BUFFER_BIT),i.drawArrays(i.TRIANGLES,0,6)},ne=()=>{const S=o.getBoundingClientRect(),k=Math.min(window.devicePixelRatio||1,2);s.width=Math.max(1,Math.floor(S.width*k)),s.height=Math.max(1,Math.floor(S.height*k)),i.viewport(0,0,s.width,s.height),i.uniform2f(h,s.width,s.height),n&&K(performance.now())},re=S=>{K(S),T=R&&!document.hidden?requestAnimationFrame(re):0},D=()=>{n||T||!R||document.hidden||(T=requestAnimationFrame(re))},B=()=>{T&&cancelAnimationFrame(T),T=0},ie=new ResizeObserver(ne),x=new IntersectionObserver(([S])=>{R=S?.isIntersecting??!0,R?D():B()}),A=()=>{document.hidden?B():D()};ie.observe(o),x.observe(o),o.addEventListener("pointermove",z,{passive:!0}),document.addEventListener("visibilitychange",A),ne(),n?K(performance.now()):T=requestAnimationFrame(re);const O=S=>{n=!!(S.detail&&S.detail.reduced),n?(B(),K(performance.now())):D()};return window.addEventListener("motionchange",O),s.style.opacity=String(t.opacity),s.style.filter=`hue-rotate(${t.hue}deg) saturate(${t.saturation}) brightness(${t.brightness})`,()=>{B(),window.removeEventListener("motionchange",O),ie.disconnect(),x.disconnect(),o.removeEventListener("pointermove",z),document.removeEventListener("visibilitychange",A),i.deleteBuffer(m),i.deleteBuffer(g),i.deleteShader(c),i.deleteShader(l),i.deleteProgram(d);const S=i.getExtension("WEBGL_lose_context");S&&S.loseContext(),s.remove()}}const oa={mode:"dark",speed:1,spacing:5,dotSize:6,archHeight:.7,thickness:1,brightness:1,hue:0,saturation:1};function aa(o){return o==="light"||o===1||o==="1"?"light":"dark"}function na(o,a){const t=o.getContext("2d",{alpha:!0});if(!t)return null;let n=1,e=1,r=0;return{resize:(c,l)=>{n=Math.max(1,c),e=Math.max(1,l);const d=Math.min(window.devicePixelRatio||1,2);o.width=Math.round(n*d),o.height=Math.round(e*d),t.setTransform(d,0,0,d,0,0)},render:()=>{const c=a(),d=aa(c.mode)==="light";t.clearRect(0,0,n,e),r+=.015*c.speed;const m=n/2,f=e*.35,g=n*1.5,b=e*c.archHeight;t.globalCompositeOperation=d?"source-over":"lighter";for(let u=0;u<n;u+=c.spacing){const h=(u-m)/(g/2),y=f+h*h*b;for(let _=0;_<e;_+=c.spacing){const M=Math.abs(_-y),F=(140+(1-Math.abs(h))*80)*c.thickness;if(M>=F)continue;let p=1-M/F;const v=Math.sin(u*.015+r),U=Math.cos(_*.02+r);if(p=p*.7+v*U*.3*p,p*=Math.max(0,1-Math.pow(Math.abs(h),2.5)),p<=.02)continue;let T,R,I;if(d){if(T=Math.min(255,48*p+70*Math.pow(p,3)),R=Math.min(255,28*p+45*Math.pow(p,4)),I=Math.min(255,120*p+110*Math.pow(p,2)),p>.7){const z=(p-.7)*3.3;T=Math.min(255,T+90*z),R=Math.min(255,R+70*z),I=Math.min(255,I+110*z)}}else if(T=Math.min(255,60*p+100*Math.pow(p,3)),R=Math.min(255,20*p+60*Math.pow(p,4)),I=Math.min(255,120*p+135*Math.pow(p,2)),p>.7){const z=(p-.7)*3.3;T=Math.min(255,T+150*z),R=Math.min(255,R+150*z),I=Math.min(255,I+150*z)}t.fillStyle=`rgb(${Math.floor(T*c.brightness)}, ${Math.floor(R*c.brightness)}, ${Math.floor(I*c.brightness)})`,t.fillRect(u,_,c.dotSize*p,c.dotSize*p)}}t.globalCompositeOperation="source-over"}}}function ra(o,a={}){if(!o)return null;const t={...oa,...a};let n=!!a.still;const e=document.createElement("canvas");o.appendChild(e);const r=na(e,()=>t);if(!r)return e.remove(),null;let s=0,i=!0;const c=()=>{const h=o.getBoundingClientRect();r.resize(h.width,h.height),r.render()},l=()=>{r.render(),s=i&&!document.hidden?requestAnimationFrame(l):0},d=()=>{n||s||!i||document.hidden||(s=requestAnimationFrame(l))},m=()=>{s&&cancelAnimationFrame(s),s=0},f=new ResizeObserver(c),g=new IntersectionObserver(([h])=>{i=h?.isIntersecting??!0,i?d():m()}),b=()=>{document.hidden?m():d()};f.observe(o),g.observe(o),document.addEventListener("visibilitychange",b),c(),n||(s=requestAnimationFrame(l));const u=h=>{n=!!(h.detail&&h.detail.reduced),n?(m(),r.render()):d()};return window.addEventListener("motionchange",u),e.style.opacity=String(t.opacity??1),e.style.filter=`hue-rotate(${t.hue}deg) saturate(${t.saturation})`,()=>{m(),window.removeEventListener("motionchange",u),f.disconnect(),g.disconnect(),document.removeEventListener("visibilitychange",b),e.remove()}}const sa=["Accuracy","Threshold","Absence","Variance","Language"];function ia(o,a){const t=[[V(Y.facial.accuracy),"Facial accuracy / held-out speakers"],["0 / 62","Polar probes flagged by the specified rule"],[V(a.corpus.no_face_share_pct??0),"Segments without a facial reading"],["49.08","Points of mean Authenticity movement"],["EN","The only benchmarked language"]];return`<section class="limits limits--atlas" data-limits aria-labelledby="atlas-heading">
    <header class="la-header"><div><p class="la-kicker">The boundary of the instrument</p><h3 id="atlas-heading">Five things<br><em>it cannot do.</em></h3></div><p>Precision starts with knowing<br>where it ends.</p></header>
    <div class="la-art" aria-hidden="true"><span class="la-orbit la-orbit--one"></span><span class="la-orbit la-orbit--two"></span><span class="la-index">01</span><canvas class="la-sculpture"></canvas><span class="la-art__note">Model / boundaries<br>Five independent limits</span><span class="la-cross">+</span></div>
    <ol class="la-readings">${o.map((n,e)=>`<li class="la-reading" data-reading="${e}">
      <p class="la-location"><span>0${e+1} / 05</span> ${w(n.where)}</p>
      <h4>${w(typeof n.title=="function"?n.title(a):n.title)}</h4>
      <div class="la-metric"><strong>${w(t[e][0])}</strong><span>${w(t[e][1])}</span></div>
      <p class="la-claim">${n.claim(a)}</p><p class="la-body">${n.body(a)}</p>
    </li>`).join("")}</ol>
    <nav class="la-nav" aria-label="Explore the five limitations">${sa.map((n,e)=>`<button type="button" data-limit-jump="${e}"><span>0${e+1}</span><span>${n}</span><i></i></button>`).join("")}</nav>
    <div class="la-footer"><span>Limitations, not fine print.</span><span>Scroll to examine ${ge("down")}</span></div>
  </section>`}function ca(o){const a=o.getContext("webgl",{alpha:!0,antialias:!0,premultipliedAlpha:!1});if(!a)return null;const t=`
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
    }`,n=`
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
    }`;function e(f,g){const b=a.createShader(f);return a.shaderSource(b,g),a.compileShader(b),a.getShaderParameter(b,a.COMPILE_STATUS)?b:(console.warn("Limits sculpture shader:",a.getShaderInfoLog(b)),a.deleteShader(b),null)}const r=e(a.VERTEX_SHADER,t),s=e(a.FRAGMENT_SHADER,n);if(!r||!s)return r&&a.deleteShader(r),s&&a.deleteShader(s),null;const i=a.createProgram();if(a.attachShader(i,r),a.attachShader(i,s),a.linkProgram(i),a.deleteShader(r),a.deleteShader(s),!a.getProgramParameter(i,a.LINK_STATUS))return console.warn("Limits sculpture link:",a.getProgramInfoLog(i)),a.deleteProgram(i),null;const c=[];for(let f=0;f<5;f++)for(let g=0;g<160;g++)for(let b=0;b<10;b++)for(const[u,h]of[[0,0],[1,0],[0,1],[0,1],[1,0],[1,1]])c.push((g+u)/160,(b+h)/10,f);const l=a.createBuffer();a.bindBuffer(a.ARRAY_BUFFER,l),a.bufferData(a.ARRAY_BUFFER,new Float32Array(c),a.STATIC_DRAW),a.useProgram(i);const d=a.getAttribLocation(i,"aParam");a.enableVertexAttribArray(d),a.vertexAttribPointer(d,3,a.FLOAT,!1,0,0);const m=Object.fromEntries(["uProgress","uAspect","uLight"].map(f=>[f,a.getUniformLocation(i,f)]));return a.enable(a.DEPTH_TEST),a.clearColor(0,0,0,0),{draw(f){const g=Math.min(devicePixelRatio||1,1.75),b=Math.round(o.clientWidth*g),u=Math.round(o.clientHeight*g);!b||!u||((o.width!==b||o.height!==u)&&(o.width=b,o.height=u),a.viewport(0,0,b,u),a.clear(a.COLOR_BUFFER_BIT|a.DEPTH_BUFFER_BIT),a.uniform1f(m.uProgress,f),a.uniform1f(m.uAspect,b/u),a.uniform1f(m.uLight,document.documentElement.dataset.theme==="field"?1:0),a.drawArrays(a.TRIANGLES,0,c.length/3))},destroy(){a.deleteBuffer(l),a.deleteProgram(i)}}}function la(o,{onJump:a}={}){const t=o.querySelector(".limits--atlas");if(!t)return null;const n=t.querySelector(".la-sculpture"),e=ca(n);e||t.classList.add("la-no-gl");const r=[...t.querySelectorAll(".la-reading")],s=[...t.querySelectorAll("[data-limit-jump]")],i=t.querySelector(".la-index"),c={p:0};let l=!1;const d=u=>Math.max(0,Math.min(1,u));function m(){const u=c.p*5,h=Math.min(4,Math.floor(u));i.textContent=`0${h+1}`,s.forEach((y,_)=>{y.setAttribute("aria-current",_===h?"step":"false"),y.style.setProperty("--fill",d(u-_))}),l&&r.forEach((y,_)=>{const M=u-_,F=_===0?1:d(M/.12),p=_===4?1:d((1-M)/.12),v=M>=0&&M<=1?Math.min(F,p):0;y.style.opacity=v,y.style.transform=`translateZ(${(1-v)*-35}px)`}),e?.draw(l?c.p:.08)}s.forEach((u,h)=>u.addEventListener("click",()=>a?.(h)));const f=new ResizeObserver(m);f.observe(n);const g=new MutationObserver(m);g.observe(document.documentElement,{attributes:!0,attributeFilter:["data-theme"]}),n.addEventListener("webglcontextlost",u=>{u.preventDefault(),t.classList.add("la-no-gl")});const b=()=>{f.disconnect(),g.disconnect(),e?.destroy()};return window.addEventListener("pagehide",b,{once:!0}),m(),{state:c,render:m,setPlaying(u){l=u,t.classList.toggle("la-playing",u),u||r.forEach(h=>{h.style.opacity="",h.style.transform=""}),m()},destroy:b}}const da=[[.5,"Half of"],[.4,"Two in five"],[1/3,"A third of"],[.25,"A quarter of"],[.2,"A fifth of"],[.1,"A tenth of"]];function ua(o){const a=(Number(o)||0)/100,t=da.find(([r])=>a>=r-.02);if(!t)return"Some";const[n,e]=t;return a-n>.02?`Over ${e.charAt(0).toLowerCase()}${e.slice(1)}`:e}const fa=[{where:"channels",title:"Two of the four are near guessing",claim:()=>`Facial ${V(Y.facial.accuracy)} and vocal ${V(Y.vocal.accuracy)} on held-out speakers.`,body:()=>`The facial channel scores ${V(Y.facial.accuracy)} on
      held-out speakers, ${Y.facial.worseThanConstant}. The vocal
      channel reaches ${V(Y.vocal.accuracy)}. Both are
      down-weighted in the controller by those measured accuracies rather than
      removed, and both are labelled wherever they are shown.`},{where:"controller",title:"The flag threshold may be unreachable",claim:()=>"A perfect implementation of the scoring rule flags 0 of 62 polar probes.",body:o=>`A deterministic implementation of the controller's own
      specification flags none of the constructed polar disagreements. The
      threshold sits at ${o.pipeline.conflict_flag_threshold??.75} and is
      documented as possibly unattainable at four channels. It has not been
      changed, because moving it would move every score this system has ever
      reported.`},{where:"corpus",title:o=>`${ua(o.corpus.no_face_share_pct)} segments have no face at all`,claim:o=>`${V(o.corpus.no_face_share_pct??0)} of segments carry no facial reading.`,body:o=>`${V(o.corpus.no_face_share_pct??0)} of segments in the
      corpus carry no facial reading &mdash; b-roll, cutaways, hands on a
      product. Those are drawn as absences on every report rather than
      defaulted to neutral.`},{where:"controller",title:"A score is partly a claim about which model is installed",claim:()=>"Swapping only the controller moved mean Authenticity by 49.08 points.",body:()=>`Swapping only the controller, on byte-identical channel
      inputs, moved the mean Authenticity across this corpus by 49.08 points.
      Scores are not comparable between videos, and only comparable between
      runs of the same video when the same controller wrote them. A combined
      report records which one did; a single report does not yet.`},{where:"scope",title:"It only reads English",claim:()=>'Transcription is fixed to <code>language="en"</code>.',body:()=>`Transcription runs with <code>language="en"</code> fixed, and
      transcript and comment sentiment were both benchmarked on English. A
      video in any other language will still produce numbers, and those numbers
      are not evidence of anything.`}];function Fe({id:o,label:a,note:t,channel:n=null,tone:e=null,ratio:r,to:s,kind:i,final:c,band:l=null,absent:d=!1}){return{id:o,label:a,note:t,channel:n,tone:e,ratio:r,to:s,kind:i,final:c,band:l,absent:d}}function ha(o){const a=o.corpus||{},t=a.channel_readings||{},n=a.segments_total||0,e=[];for(const r of["transcript","vocal","facial"]){const s=t[r];typeof s!="number"||!n||e.push(Fe({id:r,label:Y[r].short,note:`${ue(s)} of ${ue(n)} segments`,channel:r,ratio:s/n,to:s,kind:"int",final:ue(s)}))}return e.push(Fe({id:"audience",label:Y.audience.short,note:"one reading for the whole video, by design",channel:"audience",ratio:1,to:0,kind:"int",final:"—",absent:!0})),e}function ma(){return[["audience",Y.audience],["transcript",Y.transcript],["vocal",Y.vocal],["facial",Y.facial]].map(([a,t])=>Fe({id:a,label:t.short,note:t.sample,channel:a,ratio:t.accuracy/100,to:t.accuracy,kind:"pct",final:V(t.accuracy),band:a==="facial"?{from:be.constant.value/100,to:be.ceiling.value/100,label:`${V(be.constant.value)} always-NEUTRAL constant to ${V(be.ceiling.value)} human ceiling`}:null}))}function pa(o){return(o.controller_references||[]).map((t,n)=>Fe({id:`ctl-${n}`,label:`${t.model} — ${t.role.split(" ")[0]}`,note:t.probe,tone:t.role.startsWith("adopted")?"adopted":"replaced",ratio:t.total?t.detected/t.total:0,to:t.detected,kind:"int",final:`${ue(t.detected)} of ${ue(t.total)}`}))}const de=[{id:"coverage",tab:"How often it spoke",title:"Segments carrying a reading",axis:"share of every segment in the corpus",comparable:"One question asked of all four, so these four are comparable.",bars:ha},{id:"accuracy",tab:"How often it was right",title:"Accuracy on held-out data",axis:"percent correct — each on its own task",comparable:"Four different tasks against four different baselines. The axis is shared; the measurement is not.",bars:ma},{id:"controller",tab:"What the controller changed",title:"Polar disagreements detected",axis:"share of polar probes detected",comparable:"Byte-identical payloads under one prompt — the one comparison here that a shared axis fully earns.",bars:pa}];function va(o){const a=o.corpus||{};return`
    <ol class="ledger">
      ${[{to:a.report_count,label:"reports on disk",note:`across ${ue(a.distinct_videos)} videos`},{to:a.segments_total,label:"segments",note:"the spine every channel attaches to"},{to:a.comments_total,label:"comments",note:"classified one at a time"},{to:a.controller_calls_total,label:"controller calls",note:"one local LLM call per segment"}].filter(n=>typeof n.to=="number").map(n=>`
        <li class="ledger__cell">
          <span class="ledger__n" data-count="${n.to}" data-kind="int">
            <span class="ledger__run" aria-hidden="true">0</span>
            <span class="sr-only">${w(ue(n.to))}</span>
          </span>
          <span class="ledger__label">${w(n.label)}</span>
          <span class="ledger__note">${w(n.note)}</span>
        </li>`).join("")}
    </ol>`}function ga(o,a){const t=o.band?`<span class="bar__band" style="--from:${o.band.from};--to:${o.band.to}"
         aria-hidden="true"></span>`:"",n=o.band?`<p class="bar__gap">
         <span class="bar__gap-k">did not reach</span>
         ${w(o.band.label)}
       </p>`:"",e=o.absent?'<span class="bar__fill bar__fill--absent"></span>':'<span class="bar__fill"></span>',r=o.absent||o.ratio>.8;return`
    <li class="bar" style="--i:${a};--ratio:${o.absent?1:o.ratio}"${o.channel?` data-channel="${w(o.channel)}"`:""}${o.tone?` data-tone="${w(o.tone)}"`:""}>
      <div class="bar__id">
        <span class="bar__mark" data-channel="${w(o.channel||"")}"${o.tone?` data-tone="${w(o.tone)}"`:""} aria-hidden="true"></span>
        <span class="bar__name">${w(o.label)}</span>
        <span class="bar__note">${w(o.note)}</span>
      </div>
      <div class="bar__track">
        ${t}
        ${e}
        <span class="bar__value" data-inside="${r}"${o.absent?"":` data-count="${o.to}" data-kind="${o.kind}"`} data-final="${w(o.final)}">
          <span class="bar__run" aria-hidden="true">${o.absent?w(o.final):""}</span>
          <span class="sr-only">${w(o.final)}</span>
        </span>
      </div>
      ${n}
    </li>`}function Ye(o,a){const t=o.bars(a),n=[0,20,40,60,80,100];return`
    <div class="chart__head">
      <h4 class="chart__title">${w(o.title)}</h4>
      <p class="chart__axis">${w(o.axis)}</p>
    </div>
    <ol class="chart__bars">${t.map(ga).join("")}</ol>
    <div class="chart__foot">
      <div class="chart__scale" aria-hidden="true">
        ${n.map(e=>`<span>${e}</span>`).join("")}
      </div>
      <p class="chart__note">${w(o.comparable)}</p>
    </div>`}function ba(o){const a={corpus:o&&o.corpus||{},pipeline:o&&o.pipeline||{},controller_references:o&&o.controller_references||[]},t=de.map((n,e)=>`
    <button class="bench__tab${e===0?" is-active":""}" type="button"
            role="tab" id="bench-tab-${n.id}" data-tab="${n.id}"
            aria-selected="${e===0}" aria-controls="bench-panel"
            tabindex="${e===0?0:-1}">${w(n.tab)}</button>`).join("");return`
    <section class="proof" id="proof" data-proof aria-labelledby="proof-h">
      <div class="proof__field" data-proof-field aria-hidden="true"></div>

      <div class="proof__stage" data-proof-stage>
        <div class="proof__inner" data-proof-reading>
          <header class="proof__head">
            <h2 class="proof__h" id="proof-h">Everything the film just claimed, with its working.</h2>
            <p class="proof__lede">
              Every figure below was measured on this project's own data, and is
              re-derived from its source by <code>ui_evidence/extract_figures.py</code>.
              Nothing here is quoted from a paper.
            </p>
          </header>

          <div class="proof__well" data-well>
            ${va(a)}

            <div class="bench" data-bench>
              <div class="bench__tabs" role="tablist" aria-label="What was measured">${t}</div>
              <div class="bench__chart" id="bench-panel" role="tabpanel"
                   aria-labelledby="bench-tab-${de[0].id}"
                   data-chart>${Ye(de[0],a)}</div>
            </div>
          </div>
        </div>

        ${ia(fa,a)}
      </div>
    </section>`}const ya=1.05;function qe(o,{delay:a=0}={}){const t=o.querySelector("[aria-hidden]"),n=Number(o.dataset.count),e=o.dataset.kind,r=o.dataset.final??(e==="pct"?V(n):ue(n));if(!t||!Number.isFinite(n))return null;const s=c=>e==="pct"?V(c):ue(Math.round(c));if(j())return t.textContent=r,null;const i={v:0};return t.textContent=s(0),L.to(i,{v:n,duration:ya,delay:a,ease:"power2.out",onUpdate:()=>{t.textContent=s(i.v)},onComplete:()=>{t.textContent=r}})}function Ct(o,{entrance:a=!1}={}){const t=[...o.querySelectorAll(".bar")],n=[...o.querySelectorAll(".bar__fill:not(.bar__fill--absent)")],e=[...o.querySelectorAll(".bar__fill--absent")],r=[...o.querySelectorAll(".bar__band")],s=[...o.querySelectorAll(".bar__value[data-count]")];L.killTweensOf([...t,...n,...e,...r]);const i=(c,l)=>{c.length&&l(c)};if(j()){i(t,c=>L.set(c,{opacity:1,y:0})),i(n,c=>L.set(c,{scaleX:1})),i(e,c=>L.set(c,{scaleX:1,opacity:1})),i(r,c=>L.set(c,{opacity:1,scaleX:1})),s.forEach(c=>qe(c));return}i(t,c=>a?L.fromTo(c,{opacity:0,y:18},{opacity:1,y:0,duration:.52,ease:"power3.out",stagger:.09}):L.set(c,{opacity:1,y:0})),i(n,c=>L.set(c,{scaleX:0,transformOrigin:"left center"})),i(e,c=>L.set(c,{scaleX:0,opacity:0,transformOrigin:"left center"})),i(r,c=>L.set(c,{opacity:0,scaleX:.6,transformOrigin:"left center"})),i(r,c=>L.to(c,{opacity:1,scaleX:1,duration:.62,ease:"power3.out",stagger:.09,delay:.06})),i(n,c=>L.to(c,{scaleX:1,duration:.9,ease:"power3.out",stagger:.09,delay:.11})),i(e,c=>L.to(c,{scaleX:1,opacity:1,duration:.9,ease:"power3.out",stagger:.09,delay:.11})),s.forEach((c,l)=>qe(c,{delay:.11+l*.09}))}const _a={seekTab:()=>!1,locked:()=>!1};function xa(o,a,t,n=_a){const e=o.querySelector("[data-bench]"),r=o.querySelector("[data-chart]");if(!e||!r)return null;const s=[...e.querySelectorAll("[data-tab]")],i=(l,{focus:d=!1}={})=>{const m=de.find(g=>g.id===l);if(!m||t.current===l)return;t.current=l,s.forEach(g=>{const b=g.dataset.tab===l;g.classList.toggle("is-active",b),g.setAttribute("aria-selected",String(b)),g.tabIndex=b?0:-1,b&&d&&g.focus()}),r.setAttribute("aria-labelledby",`bench-tab-${l}`);const f=()=>{r.innerHTML=Ye(m,a),requestAnimationFrame(()=>Ct(r,{entrance:!0})),n.locked()||Ae.refresh()};if(j()){f();return}L.to(r,{opacity:0,duration:.14,ease:"power1.in",onComplete:()=>{f(),L.to(r,{opacity:1,duration:.2,ease:"power1.out"})}})},c=(l,d)=>{const m=de.findIndex(f=>f.id===l);m<0||n.seekTab(m)||i(l,d)};return e.addEventListener("click",l=>{const d=l.target.closest("[data-tab]");d&&c(d.dataset.tab)}),e.addEventListener("keydown",l=>{const d=s.indexOf(document.activeElement);if(d<0)return;let m=-1;l.key==="ArrowRight"&&(m=(d+1)%s.length),l.key==="ArrowLeft"&&(m=(d-1+s.length)%s.length),l.key==="Home"&&(m=0),l.key==="End"&&(m=s.length-1),!(m<0)&&(l.preventDefault(),s[m].focus(),c(s[m].dataset.tab,{focus:!0}))}),{select:i,tabs:s}}function wa(o){const a=o.querySelector("[data-proof-field]");if(!a)return;let t=null;const n=()=>{t&&(t(),t=null);const e=document.documentElement.dataset.theme==="field"?"light":"dark";t=ta(a,{mode:e,still:j(),opacity:e==="light"?.42:.62,brightness:.46,saturation:.3,hue:0,speed:1})};n(),window.addEventListener("themechange",n),$e(n)}function Aa(o){const a=o.querySelector("[data-limits]");if(!a)return;let t=a.querySelector("[data-limits-field]");t||(t=document.createElement("div"),t.className="la-field",t.setAttribute("data-limits-field",""),t.setAttribute("aria-hidden","true"),a.prepend(t));let n=null;const e=()=>{n&&(n(),n=null);const r=document.documentElement.dataset.theme==="field"?"light":"dark";n=ra(t,{mode:r,still:j(),hue:20,saturation:.25,spacing:7,dotSize:6,speed:.6,brightness:bt.brightness[r],opacity:bt.opacity[r]})};e(),window.addEventListener("themechange",e),$e(e)}const bt={brightness:{dark:.58,light:.9},opacity:{dark:.72,light:.38}},Oe=7.45,W={ledgerOut:.85,benchIn:.95,tabsFrom:1.2,tabsTo:2.7,crossFrom:2.75,crossTo:3.2,limitsFrom:3.2,limitsTo:7.2},Ea=.55,yt=.45,Ta=o=>W.tabsFrom+(W.tabsTo-W.tabsFrom)*(o+.4)/de.length,Sa=o=>W.limitsFrom+(W.limitsTo-W.limitsFrom)*(o+.4)/5;function Ma(o){const a=document.querySelector("[data-proof]");if(!a)return;const t={corpus:o&&o.corpus||{},pipeline:o&&o.pipeline||{},controller_references:o&&o.controller_references||[]},n={current:de[0].id},e={reading:a.querySelector("[data-proof-reading]"),ledger:a.querySelector(".ledger"),bench:a.querySelector("[data-bench]"),atlas:a.querySelector("[data-limits]"),portal:a.querySelector("[data-proof-field]"),chart:a.querySelector("[data-chart]")},r=[...a.querySelectorAll(".ledger__n")];let s=null;const i=()=>!!s,c=p=>{if(!s)return!1;const{start:v,end:U}=s;return window.scrollTo({top:v+(U-v)*(p/Oe),behavior:j()?"auto":"smooth"}),!0};wa(a),Aa(a);const l=la(a,{onJump:p=>c(Sa(p))}),d=xa(a,t,n,{locked:i,seekTab:p=>c(Ta(p))}),m=()=>{const p=a.querySelector("[data-well]");if(!p||!e.chart||!e.bench)return;const v=e.chart.innerHTML;p.style.removeProperty("min-block-size");let U=0;for(const T of de)e.chart.innerHTML=Ye(T,t),U=Math.max(U,e.bench.offsetHeight);e.chart.innerHTML=v,p.style.setProperty("min-block-size",`${Math.ceil(U)}px`)},f=()=>{a.querySelector("[data-well]")?.style.removeProperty("min-block-size")},g=new Set,b=(p,v)=>{g.has(p)||(g.add(p),v())},u=()=>b("ledger",()=>{r.forEach((p,v)=>qe(p,{delay:v*.08}))}),h=()=>b("chart",()=>Ct(e.chart)),y=(p,v)=>{if(p){if(j()){v();return}Ae.create({trigger:p,start:"top bottom-=18%",once:!0,onEnter:v})}};let _=null;const M=()=>{_=Pe({lock:"(min-width: 860px) and (min-height: 740px) and (prefers-reduced-motion: no-preference)",stack:"(max-width: 859px), (max-height: 739px), (prefers-reduced-motion: reduce)"},p=>{if(!p.conditions.lock){delete a.dataset.locked,delete a.dataset.stage,delete a.dataset.grounds,l?.setPlaying(!1),L.set([e.reading,e.ledger,e.bench,e.atlas,e.portal],{clearProps:"opacity,visibility,transform"}),f(),y(e.ledger,u),y(e.chart,h);return}a.dataset.locked="",a.dataset.stage="reading",a.dataset.grounds="reading",l?.setPlaying(!0);const v=L.timeline({scrollTrigger:{trigger:a,start:"top top",end:()=>`+=${window.innerHeight*Oe}`,scrub:.55,pin:!0,anticipatePin:1,invalidateOnRefresh:!0,refreshPriority:-1,onRefresh:m}});s=v.scrollTrigger,m(),v.set({},{},Oe),v.set(e.atlas,{opacity:0},0),v.call(u,null,.05),v.to(e.ledger,{autoAlpha:0,y:-28,duration:.32,ease:"power2.in"},W.ledgerOut),v.fromTo(e.bench,{autoAlpha:0,y:30},{autoAlpha:1,y:0,duration:.38,ease:"power2.out"},W.benchIn),v.call(h,null,W.benchIn+.22);const U={i:0};v.to(U,{i:de.length,duration:W.tabsTo-W.tabsFrom,ease:"none",onUpdate:()=>{const R=Math.min(de.length-1,Math.max(0,Math.floor(U.i)));d?.select(de[R].id)}},W.tabsFrom);const T={t:0};return v.to(T,{t:1,duration:W.crossTo-W.crossFrom,ease:"power2.inOut",onUpdate:()=>{const R=1-Math.min(1,T.t/Ea),I=Math.max(0,(T.t-yt)/(1-yt));L.set(e.reading,{opacity:R}),L.set(e.portal,{opacity:R}),L.set(e.atlas,{opacity:I}),a.dataset.stage=I>=R?"limits":"reading",a.dataset.grounds=I>0?R>0?"both":"limits":"reading"}},W.crossFrom),l&&v.fromTo(l.state,{p:0},{p:1,ease:"none",duration:W.limitsTo-W.limitsFrom,onUpdate:l.render},W.limitsFrom),()=>{s=null,f(),delete a.dataset.locked,delete a.dataset.stage,delete a.dataset.grounds}})};M();const F=()=>{L.globalTimeline.progress(1),r.forEach(p=>{const v=p.querySelector("[aria-hidden]"),U=p.querySelector(".sr-only");v&&U&&(v.textContent=U.textContent)}),a.querySelectorAll(".bar__value[data-final]").forEach(p=>{const v=p.querySelector(".bar__run");v&&(v.textContent=p.dataset.final)}),a.querySelectorAll(".bar").forEach(p=>L.set(p,{opacity:1,y:0})),a.querySelectorAll(".bar__fill, .bar__band").forEach(p=>L.set(p,{scaleX:1,opacity:1})),L.set([e.reading,e.ledger,e.bench,e.atlas,e.portal],{clearProps:"opacity,visibility,transform"})};window.addEventListener("beforeprint",()=>{_&&(_.revert(),_=null),l?.setPlaying(!1),F()}),window.addEventListener("afterprint",()=>{_||M()}),$e(p=>{p&&F()})}const ze=document.querySelector("[data-opening]"),_t=["Apple (iPhone 18 Pro Max).json"];async function*Ra(o){let a=[];try{const r=await Xt();a=(r.reports||r||[]).map(i=>typeof i=="string"?i:i.filename).filter(Boolean)}catch{a=[]}const t=[..._t.filter(r=>a.includes(r)),...a.filter(r=>!_t.includes(r))];for(const r of t)yield{href:`/library/${encodeURIComponent(r)}`,load:()=>Gt(r)};let n=[];try{n=await Vt()}catch{n=[]}const e=new Set;for(const r of Array.isArray(n)?n:[]){let s;try{s=await Wt(r.sweep_id)}catch{continue}for(const i of s.members||[]){const c=i.video_id;!c||i.analysed===!1||e.has(c)||(e.add(c),It(wt(o,c))&&(yield{href:`/brand/${encodeURIComponent(r.sweep_id)}/${encodeURIComponent(c)}`,load:()=>Yt(r.sweep_id,c)}))}}}const It=o=>!!(o&&o.seconds&&o.seconds.length>=8);async function La(o){for await(const a of Ra(o)){let t;try{t=await a.load()}catch{continue}const n=Kt(t),e=n?wt(o,n):null;if(!It(e))continue;const r=(t.all_segments||[]).slice().sort((d,m)=>d.start_s-m.start_s);if(!r.length)continue;for(const d of r)d.__v=Ht(d,t.comment_sentiment);const s=r.filter(d=>d.flagged),i=s.length?s.reduce((d,m)=>m.conflict_score>d.conflict_score?m:d):null,c=r.filter(d=>(d.__v||{}).facial),l=(()=>{for(const d of c){const m=e.seconds.find(f=>f>=d.start_s&&f<d.end_s);if(m!==void 0)return m}return e.seconds[0]})();return{href:a.href,report:t,videoId:n,strip:e,segments:r,flagged:i,openAt:l,segment:r[Math.floor(r.length/3)],duration:r[r.length-1].end_s||1}}return null}function kt(o){ze.innerHTML=`
    <section class="state state--error">
      <p class="state__tag">Unavailable</p>
      <h1 class="t-l">${w(o)}</h1>
      <p>
        The interface could not read this machine's own analyses. The API is
        still reachable at <code>/reports</code>, and
        <a href="/library">the library</a> lists what is on disk.
      </p>
    </section>`}const He=Mo({onEnter:()=>Do({autoStart:!1,onDone:Ve})});He||Ve();function Xe(){He&&He.ready()}async function Fa(){if(!ze)return;Ot({here:"opening"}),Nt();let o={};try{o=await zt()}catch{o={}}const a=await jt(),t=await La(a);if(!t){kt("There is no analysed video on this machine to open with."),clearTimeout(window.__bpFallback),Xe();return}ze.innerHTML=Oo()+Wo(o)+to(t)+ba(o)+jo(o.corpus||{},t),clearTimeout(window.__bpFallback),requestAnimationFrame(()=>{No(),Yo(),oo(),Ma(o),Ko(),Ae.refresh(),Xe()})}Fa().catch(o=>{kt("This page could not be drawn."),clearTimeout(window.__bpFallback),Xe()});
