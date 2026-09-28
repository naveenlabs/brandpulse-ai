const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/shelf-D40xAc3S.js","assets/chrome-Bbzm0knH.js","assets/chrome-Cpgf7-kA.css","assets/preload-helper-wn6Ki-z9.js","assets/contract-wMVeQDZg.js","assets/leaf-vrvMp2mH.js","assets/frames-Dx4w5fNa.js","assets/transport-DtqCW5-H.css"])))=>i.map(i=>d[i]);
import{m as Ie,a as Fe,o as ue,r as he,d as He,b as k,s as fe}from"./chrome-Bbzm0knH.js";import{_ as je}from"./preload-helper-wn6Ki-z9.js";/* empty css                  */import{l as De,v as Oe,e as i,x as Ne,f as pe,w as Ue,j as Pe,C as Be,n as me,s as m,c as u,p as We,g as Ye,y as be,z as ge,m as ke}from"./contract-wMVeQDZg.js";import{a as Ve,c as ze,m as Ge,b as Xe}from"./leaf-vrvMp2mH.js";import{m as Je,p as Qe,v as ie}from"./frames-Dx4w5fNa.js";const ye={perShelf:3,minRows:4,bookW:.887,bookH:1.33,bookD:.17,slot:1.235,rowH:1.62,bayGap:.16,plankThick:.105,plankDepth:.8,lean:-.2,yaw:.155,bow:.008,chamf:.0135,chamfR:.022,boxCY:.06,padX:.44,padY:.42,fov:20,offset:1.25,maxWidthPx:1550,orbitAz:.085,orbitEl:.052,activeOrbitDamp:.22,activeX:.72,activeRot:[.075,.285,0],activeDuration:700,hoverDrop:400,hoverLift:1e3,introStagger:26,introWallFade:450,introFade:300};function Ze(e,t=ye){const a=e.reduce((n,o)=>Math.max(n,Math.ceil(o/t.perShelf)),0);return Math.max(t.minRows,a)}function Ke(e,t=ye){const a=Ze(e,t),n=3*(t.perShelf*t.slot)+4*t.bayGap,o=a*t.rowH,s=n+t.padX,l=o+t.padY;return{rows:a,unitW:n,unitH:o,w:s,h:l,ratio:s/l}}const d=document.querySelector("[data-library]"),H=[{key:"conflict",label:"Most disagreement",of:e=>-(e.flaggedShare??-1)},{key:"auth",label:"Authenticity",of:e=>-(e.authenticity??-1)},{key:"health",label:"Brand health",of:e=>-(e.health??-1)},{key:"covered",label:"Least measured",of:e=>e.facialShare??2},{key:"size",label:"Longest run",of:e=>-(e.segments??-1)}],j=[{key:"all",label:"All",of:()=>!0},{key:"flagged",label:"Has flagged moments",of:e=>(e.flagged||0)>0},{key:"thin",label:"Thin facial coverage",of:e=>(e.facialShare??1)<.5}];function V(e,t,a,n=""){d.innerHTML=`
    <section class="state${e==="Unreachable"?" state--error":""}">
      <p class="t-label state__tag">${i(e)}</p>
      <h1 class="t-l">${i(t)}</h1>
      <p class="t-body">${a}</p>${n}
    </section>`,clearTimeout(window.__bpFallback)}async function et(e,t){const{brand:a,product:n}=Ne(e.filename),o={filename:e.filename,brand:a,product:n,ok:!1,savedOn:pe(e.saved_at)};try{const s=await Ue(e.filename),l=(s.all_segments||[]).filter(p=>typeof p.start_s=="number"&&typeof p.end_s=="number");if(!l.length)return{...o,empty:!0};const f=l.filter(p=>p.flagged).length,y=Pe(l,s.comment_sentiment),v=Math.max(...l.map(p=>p.end_s)),S=l.reduce((p,c)=>(c.conflict_score??-1)>(p.conflict_score??-1)?c:p,l[0]);return{...o,ok:!0,report:s,segments:l,duration:v,segmentCount:l.length,flagged:f,flaggedShare:l.length?f/l.length:0,authenticity:s.authenticity_score,health:s.brand_health_score,comments:(s.all_comments||[]).length,room:(s.comment_sentiment||{}).label||null,facialShare:y.facial.share,thinChannels:Be.filter(p=>me[p].perSegment&&y[p].thin),videoId:ie(s),plate:Qe(t,ie(s),S),worst:S,hasCaveat:!!s.bias_caveat}}catch(s){return{...o,error:s&&s.message||"could not be read"}}}const tt=900,at=600,Z=`(min-width: ${tt}px) and (min-height: ${at}px)`,G="brandpulse-library-view";function nt(){try{return localStorage.getItem(G)==="list"}catch{return!1}}function _e(e){try{e?localStorage.setItem(G,"list"):localStorage.removeItem(G)}catch{}}function X(){return st()&&!he()&&window.matchMedia(Z).matches}let E=null;function st(){if(E!==null)return E;try{const e=document.createElement("canvas");E=!!(e.getContext("webgl2")||e.getContext("webgl"))}catch{E=!1}return E}function ot(e){const t=(e.flagged||0)>0;return{id:`run:${e.filename}`,kind:"run",href:`/library/${encodeURIComponent(e.filename)}`,title:e.brand||"Untitled",sub:e.product||"",kicker:"One video",authText:m(e.authenticity),healthText:m(e.health),foot:e.savedOn||"",filename:e.filename,spineTitle:e.product||e.brand||"Untitled",spineFoot:e.savedOn||"",flagged:t,seed:e.filename.length*37+5,plateUrl:e.plate||null,ledger:[["Authenticity",m(e.authenticity)],["Brand health",m(e.health)],["Segments",u(e.segmentCount)],["Flagged",u(e.flagged)],["Facial coverage",We((e.facialShare||0)*100)]],blurb:t?`${u(e.flagged)} of ${u(e.segmentCount)} segments were flagged as disagreeing across the four channels.`:"No segment in this run crossed the conflict threshold.",listLine:`${e.brand}${e.product?" "+e.product:""} — ${m(e.authenticity)} authenticity`}}function z(e){const t=e.sweep_id||e.id||"";return{id:`sweep:${t}`,kind:e.subject_kind||"unfiled",href:`/brand/${encodeURIComponent(t)}`,title:e.subject||"Untitled sweep",sub:"",kicker:`${u(e.video_count||0)} videos combined`,authText:m(e.authenticity),healthText:m(e.brand_health),foot:pe(e.finished_at)||"",filename:t,videoCount:e.video_count||0,spineTitle:e.subject||"Sweep",spineFoot:e.window?`${e.window}${Number(e.offset_days||0)?`, ${u(Number(e.offset_days))}d earlier`:""}`:"",flagged:!1,seed:t.length*53+11,plateUrl:null,ledger:[["Mean authenticity",m(e.authenticity)],["Mean brand health",m(e.brand_health)],["Videos",u(e.video_count||0)],["Window",e.window?ve(e):"—"],["Controller",e.controller||"—"]],blurb:"Five videos about one subject, combined. The spread is the finding, not the average.",listLine:`${e.subject} — ${m(e.authenticity)} mean authenticity`}}async function it(e){return await Promise.all(e.map(t=>new Promise(a=>{if(!t.plateUrl)return a();const n=new Image;n.onload=()=>{t.plateImage=n,a()},n.onerror=()=>a(),n.src=t.plateUrl}))),e}const re=e=>`t-${encodeURIComponent(e)}`;function rt(e){return e.ok?`
  <li class="rk__card" data-file="${i(e.filename)}">
    <label class="rk__pick">
      <input type="checkbox" data-compare value="${i(e.filename)}">
      <span class="sr-only">Hold ${i(e.brand)} ${i(e.product)} against another run</span>
    </label>

    <a class="rk__open" href="/library/${encodeURIComponent(e.filename)}"
       data-open aria-labelledby="${i(re(e.filename))}">
      <span class="rk__frame" data-flip-id="library-frame">
        ${e.plate?`<img src="${e.plate}" alt="" loading="lazy">`:'<span class="rk__noframe"></span>'}
      </span>
    </a>

    <div class="rk__body">
      <h3 class="t-panel" id="${i(re(e.filename))}">
        <a href="/library/${encodeURIComponent(e.filename)}" data-open>
          ${i(e.brand)}${e.product?` <span class="u-dim">${i(e.product)}</span>`:""}
        </a>
      </h3>

      <div class="rk__sig" data-sig="${i(e.filename)}"></div>

      <dl class="rk__nums">
        <div><dt class="t-micro u-faint">Authenticity</dt>
          <dd class="t-read">${m(e.authenticity)}</dd></div>
        <div><dt class="t-micro u-faint">Brand health</dt>
          <dd class="t-read">${m(e.health)}</dd></div>
        <div><dt class="t-micro u-faint">Flagged</dt>
          <dd class="t-read${e.flagged?" is-tear":""}">${u(e.flagged)}</dd></div>
        <div><dt class="t-micro u-faint">Segments</dt>
          <dd class="t-read">${u(e.segmentCount)}</dd></div>
      </dl>

      <p class="rk__meta t-micro u-faint">
        ${ke(e.duration)} of video
        <span class="rk__sep" aria-hidden="true"></span>
        ${u(e.comments)} comments
        ${e.savedOn?`<span class="rk__sep" aria-hidden="true"></span>${i(e.savedOn)}`:""}
      </p>

      ${e.thinChannels.length?`
        <p class="rk__thin t-micro">
          Thin coverage: ${e.thinChannels.map(t=>i(me[t].short.toLowerCase())).join(", ")}. Under half this
          run carries a reading on ${e.thinChannels.length===1?"it":"them"}.
        </p>`:""}
      ${Se({kind:"report",target:e.filename,name:`${e.brand}${e.product?` ${e.product}`:""}`})}
    </div>
  </li>`:`
    <li class="rk__card is-broken">
      <div class="rk__body">
        <h3 class="t-panel">${i(e.brand)}${e.product?` ${i(e.product)}`:""}</h3>
        <p class="t-small u-dim">${e.empty?"This report has no segments. Transcription produced nothing to align the other three channels to, so there is nothing to draw and nothing to score.":`Could not be read. ${i(e.error||"")}`}</p>
        <p class="t-micro u-faint"><code>${i(e.filename)}</code></p>
      </div>
    </li>`}const lt={week:"the last week",month:"the last month",half:"the last six months",year:"the last year"};function ve(e){const t=lt[e.window]||e.window||"",a=Number(e.offset_days||0);return a?`${t}, ending ${u(a)} days ago`:t}function $e(e){return Promise.all(e.map(t=>Ye(t.sweep_id).then(a=>({...t,summary:a&&a.summary||t.summary})).catch(()=>t)))}function le(e){return e.length?`
  <section class="sw" aria-labelledby="sw-h">
    <h2 id="sw-h" class="t-m">Combined runs</h2>
    <p class="t-lede">
      Each of these analysed up to five videos about one subject and reported
      both the average and how far apart they ended up. A combined score is an
      average of facial-derived ones, so every caveat on a single report applies
      to it too.
    </p>
    <ul class="sw__list">
      ${e.map(t=>{const a=t.summary||{},n=a.authenticity||{},o=a.video_count??t.video_count??(t.members||[]).length;return`
        <li class="sw__one">
          <a class="sw__link" href="/brand/${encodeURIComponent(t.sweep_id||t.id||"")}">
            <h3 class="t-panel">${i(t.subject||"Untitled sweep")}</h3>
          </a>
          <p class="t-micro u-faint">
            ${u(o)} videos
            ${t.window?`over ${i(ve(t))}`:""}
          </p>
          <dl class="sw__nums">
            <div><dt class="t-micro u-faint">Mean authenticity</dt>
              <dd class="t-read">${m(n.mean??t.authenticity)}</dd></div>
            <div><dt class="t-micro u-faint">Range</dt>
              <dd class="t-read">${m(n.min)} to ${m(n.max)}</dd></div>
          </dl>
          ${a.spread_verdict?`<p class="t-small u-dim">${i(a.spread_verdict)}</p>`:""}
          ${Se({kind:"sweep",target:t.sweep_id||t.id||"",name:t.subject||"this combined run",videos:o})}
        </li>`}).join("")}
    </ul>
  </section>`:""}function Se({kind:e,target:t,name:a,videos:n=0}){const o=e==="sweep"?`Delete ${a} and the ${u(n)} video report${n===1?"":"s"} inside it? This cannot be undone.`:`Delete ${a}? This cannot be undone.`;return`
    <div class="rk__del" data-del data-kind="${e}" data-target="${i(t)}" data-name="${i(a)}">
      <button class="btn rk__delbtn" data-variant="quiet" type="button" data-del-ask>Delete</button>
      <div class="rk__delq" data-del-confirm hidden>
        <p class="t-small" data-del-text>${i(o)}</p>
        <div class="rk__delacts">
          <button class="btn" data-variant="danger" type="button" data-del-yes>Delete permanently</button>
          <button class="btn" data-variant="quiet" type="button" data-del-no>Keep it</button>
        </div>
      </div>
    </div>`}function dt(e){e&&(e.addEventListener("click",async t=>{const a=t.target.closest("[data-del]");if(!a)return;const n=a.querySelector("[data-del-ask]"),o=a.querySelector("[data-del-confirm]"),s=a.querySelector("[data-del-text]"),l=a.querySelector("[data-del-yes]"),f=a.querySelector("[data-del-no]");if(t.target.closest("[data-del-ask]"))n.hidden=!0,o.hidden=!1,l.focus(),k(s.textContent);else if(t.target.closest("[data-del-no]"))o.hidden=!0,n.hidden=!1,n.focus();else if(t.target.closest("[data-del-yes]")){const y=a.dataset.name;l.disabled=!0,f.disabled=!0,s.textContent=`Deleting ${y}…`;try{a.dataset.kind==="sweep"?await be(a.dataset.target):await ge(a.dataset.target),k(`${y} deleted. Reopening the library.`),window.location.reload()}catch(v){s.textContent=`${y} was not deleted. ${v.message}`,l.disabled=!1,f.disabled=!1,k(s.textContent)}}}),e.addEventListener("keydown",t=>{if(t.key!=="Escape")return;const a=t.target.closest("[data-del]"),n=a&&a.querySelector("[data-del-confirm]");if(!n||n.hidden)return;n.hidden=!0;const o=a.querySelector("[data-del-ask]");o.hidden=!1,o.focus()}))}function de(){return`
  <aside class="cmp" data-cmp hidden aria-label="Two runs compared">
    <div class="cmp__inner">
      <p class="cmp__tag t-label" data-cmp-tag></p>
      <div class="cmp__pair" data-cmp-pair></div>
      <button class="btn" type="button" data-cmp-clear>Clear</button>
    </div>
  </aside>`}function ct(e){const t=Math.max(...e.map(a=>a.duration));return e.map(a=>`
    <div class="cmp__one">
      <p class="t-label">${i(a.brand)} <span class="u-dim">${i(a.product)}</span></p>
      <div class="cmp__scale">
        <div class="cmp__trace" style="width:${(a.duration/t*100).toFixed(2)}%"
             data-cmp-sig="${i(a.filename)}"></div>
      </div>
      <dl class="cmp__nums t-micro">
        <div><dt>Authenticity</dt><dd class="t-read">${m(a.authenticity)}</dd></div>
        <div><dt>Brand health</dt><dd class="t-read">${m(a.health)}</dd></div>
        <div><dt>Flagged</dt><dd class="t-read">${u(a.flagged)} of ${u(a.segmentCount)}</dd></div>
        <div><dt>Runs for</dt><dd class="t-read">${ke(a.duration)}</dd></div>
      </dl>
    </div>`).join("")+`<p class="cmp__note t-micro u-faint">
         Both traces are drawn on one scale, so the shorter run stops where it
         actually stops. Neither score is comparable between videos: a score is a
         statement about one run of one video with one controller model installed.
       </p>`}let $=[],C=[],D=H[0],O=j[0];const T=new Set,J={rack:[],compare:[]};function we(e){for(const t of J[e])t.destroy();J[e]=[]}function Te(e,t,a){if(!e||!t.ok)return;const n=ze(t.duration,t.segments);J[a].push(Ge(e,{report:t.report,segments:t.segments,clock:n,compact:!0,label:`${t.brand}${t.product?` ${t.product}`:""}`}))}function F(){if(!d.querySelector("[data-rack]"))return;const t=[...$.filter(o=>!o.ok||O.of(o))].sort((o,s)=>o.ok?s.ok?D.of(o)-D.of(s):-1:1),a=d.querySelector("[data-rack]");we("rack"),a.innerHTML=t.map(rt).join("");for(const o of t)o.ok&&Te(a.querySelector(`[data-sig="${CSS.escape(o.filename)}"]`),o,"rack");const n=d.querySelector("[data-rack-empty]");n.hidden=t.length>0,t.length||(n.textContent=`No saved run matches "${O.label}". That is a fact about this machine's corpus rather than an empty page.`),ut()}function ut(){for(const e of d.querySelectorAll("[data-compare]"))e.checked=T.has(e.value),e.addEventListener("change",()=>{if(e.checked){if(T.size>=2){e.checked=!1,k("Two runs at a time. Clear one first.",{urgent:!1});return}T.add(e.value)}else T.delete(e.value);Ce()});for(const e of d.querySelectorAll("[data-open]"))e.addEventListener("click",()=>{const t=e.closest(".rk__card");fe(t?t.querySelector("[data-flip-id]"):null)})}function Ce(){const e=d.querySelector("[data-cmp]"),t=d.querySelector("[data-cmp-tag]"),a=d.querySelector("[data-cmp-pair]"),n=$.filter(o=>T.has(o.filename)&&o.ok);if(we("compare"),!n.length){e.hidden=!0;return}if(e.hidden=!1,n.length===1){t.textContent="Pick one more to hold them against each other",a.innerHTML="";return}t.textContent="Two runs, one scale",a.innerHTML=ct(n);for(const o of n)Te(a.querySelector(`[data-cmp-sig="${CSS.escape(o.filename)}"]`),o,"compare");k(`Comparing ${n[0].brand} ${n[0].product} and ${n[1].brand} ${n[1].product}.`)}async function ht(){Ie(),Fe({here:"/library"});const e=X()&&!nt(),t=De().catch(()=>[]),a=Je(),n=e?je(()=>import("./shelf-D40xAc3S.js"),__vite__mapDeps([0,1,2,3,4,5,6,7])):null;n&&n.catch(()=>{});let o=[],s=[];try{o=await Oe()}catch(c){c&&c.status>=500?V("Unreadable","The reports directory could not be read.",`The server answered: ${i(c.message)}. The reports are plain JSON in <code>brandpulse_ai/outputs/</code>; a permissions problem there is the usual cause.`,'<a class="btn" href="/run">Analyse a video</a>'):V("Unreachable","Nothing answered on this machine.","The interface is served by the same Flask process that reads the reports, so if this page loaded and the listing did not, the server is part-way up. Start it with <code>python -m flask --app app run --port 5001</code> from <code>brandpulse_ai/</code>.");return}s=await t,C=s;const l=()=>{const c=d.querySelector("[data-view-shelf]");c&&(c.hidden=!X())};if(window.matchMedia(Z).addEventListener("change",l),ue(l),!o.length&&!s.length){V("Empty","Nothing has been analysed on this machine yet.","Reports are written to <code>outputs/</code> when a run finishes. The first one takes four to nine minutes.",'<a class="btn" data-variant="solid" href="/run">Analyse a video</a>');return}const f=await a;$=await Promise.all(o.map(c=>et(c,f)));const y=$.filter(c=>c.ok),v=[{key:"video",label:"A video",items:y.map(ot)},{key:"brand",label:"A brand",items:s.filter(c=>c.subject_kind==="brand").map(z)},{key:"product",label:"A product",items:s.filter(c=>c.subject_kind==="product").map(z)}],S=s.filter(c=>c.subject_kind!=="brand"&&c.subject_kind!=="product");S.length&&v[0].items.push(...S.map(z));const p=Ke(v.map(c=>c.items.length));if(e){const[{mountShelf:c}]=await Promise.all([n,it(v.flatMap(A=>A.items))]),N=d.querySelector("[data-boot]");d.insertAdjacentHTML("beforeend",pt(v,p,y,s));const L=d.querySelector(".bk");L.dataset.settling="yes",d.querySelector("[data-stage]").style.setProperty("--bk-ratio",p.ratio.toFixed(4)),mt(v,p,c,()=>ft(L,N))}else C=await $e(s),d.innerHTML=qe(y,C),xe();clearTimeout(window.__bpFallback)}function ft(e,t){if(delete e.dataset.settling,!!t){if(he()){t.remove();return}t.dataset.leaving="yes",setTimeout(()=>t.remove(),420)}}function Q(){const e=[...document.querySelectorAll("[data-fallback] .fallback__caveat")];return e.length?`
    <aside class="lcav" id="caveats" data-caveat aria-label="Caveats that apply to every score on this page">
      ${e.map(t=>{const a=t.querySelector("h2"),n=t.querySelector("p");return`<p class="lcav__item"><b class="lcav__k">${i(a?a.textContent:"")}</b>
          ${i(n?n.textContent:"")}</p>`}).join("")}
    </aside>`:""}function pt(e,t,a,n){const o=a.length+n.length,s=e.reduce((l,f)=>l+f.items.length,0);return`
    <section class="bk" data-bk>
      <!-- The page's only heading is here, and it is not drawn. Nothing is
           meant to be read above the shelf -- the room, the volumes and the
           three case labels are the whole interface. An <h1> still has to
           exist for the document to have an outline a screen reader and the
           browser's own heading navigation can use, so it is carried
           off-screen rather than deleted. -->
      <h1 class="sr-only">${u(o)} ${o===1?"analysis":"analyses"} saved on this machine</h1>

      <div class="bk__frame">
        <div class="bk__cases" data-cases aria-hidden="true">
          ${e.map((l,f)=>`<span class="bk__case" style="--i:${f}">
            <b>${i(l.label)}</b>
            <span>${u(l.items.length)} volume${l.items.length===1?"":"s"}</span>
          </span>`).join("")}
        </div>

        <div class="bk__stage" data-stage>
          <div class="bk__desk" data-desk>
            <p class="bk__kicker" data-desk-kicker></p>
            <h2 class="bk__title" data-desk-title></h2>
            <p class="bk__blurb" data-desk-blurb></p>
            <dl class="bk__ledger" data-desk-ledger></dl>
            <div class="bk__acts">
              <a class="bk__act bk__act--solid" data-desk-open href="#">Open the report
                <svg viewBox="0 0 16 11" width="15" height="11" aria-hidden="true" fill="none"
                     stroke="currentColor" stroke-width="1.2"><path d="M0 5.5H14.6M10.3 1.2 14.9 5.5 10.3 9.8"/></svg></a>
              <button class="bk__act" type="button" data-desk-flip>Turn it over</button>
              <button class="bk__act bk__act--quiet" type="button" data-desk-close>Put it back</button>
              <button class="bk__act bk__act--danger" type="button" data-desk-delete>Delete</button>
            </div>

            <!-- The second step. It replaces the row above rather than sitting
                 beside it, so the destructive button is never next to the one
                 that cancels it, and so the question is the only thing being
                 answered at that moment. -->
            <div class="bk__confirm" data-desk-confirm hidden>
              <p class="bk__confirmq" data-desk-confirm-text></p>
              <div class="bk__confirmacts">
                <button class="bk__act bk__act--danger" type="button" data-desk-confirm-yes>
                  Delete permanently</button>
                <button class="bk__act bk__act--quiet" type="button" data-desk-confirm-no>
                  Keep it</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- The shared page ending (chassis.css .end): what this room is on the
           left, how to use it on the right, on the page grid. -->
      <p class="bk__rail end">
        <span class="end__sig">${u(o)} ${o===1?"analysis":"analyses"} on this machine, read by a local model</span>
        <span class="bk__hint">Click a volume to take it down, drag to turn it, press Esc to put it back</span>
        <button class="bk__aslist" type="button" data-as-list>Show as a list</button>
      </p>

      ${Q()}

      <!-- The keyboard's way onto the shelf. Each entry takes that volume down
           exactly as a click on it does -- the same shelf.focus() -- so the desk,
           its report link, Turn it over, Put it back and Delete are all one Tab
           away. Until 25 Sep 2026 these were links straight to the report, which
           left a keyboard reader no way to reach the desk at all, and so no way
           to delete anything (INCLUSIVE_DESIGN.md A2). -->
      <nav class="bk__index" aria-label="Every run on the shelf">
        <p>The shelf above is a canvas and cannot be read aloud or tabbed into.
          These are the same ${u(s)} volumes; each one takes its volume down.</p>
        <ul>
          ${e.flatMap(l=>l.items.map(f=>`<li><button type="button" data-take="${i(f.id)}">
            Take down ${i(l.label)}: ${i(f.title)}${f.sub?` ${i(f.sub)}`:""} —
            authenticity ${i(f.authText)}, brand health ${i(f.healthText)}</button></li>`)).join("")}
        </ul>
      </nav>
    </section>`}function ce(){return`<p class="lb__view" data-view-shelf${X()?"":" hidden"}>
    <button class="btn" data-variant="quiet" type="button" data-as-shelf>Show as a shelf</button></p>`}function qe(e,t){return $.length?`
    <div class="lb">
      <header class="lb__head">
        <h1 class="t-l">${u($.length)} run${$.length===1?"":"s"}
          saved on this machine.</h1>
        <p class="t-lede">
          Every one of them was analysed here and is stored here. Each card
          carries that run&rsquo;s own trace, drawn from its own data, so the
          rack can be read by picture before it is read by name.
        </p>
        ${ce()}
      </header>

      ${Q()}

      <div class="lb__controls">
        <div class="lb__group" role="group" aria-label="Filter the runs">
          ${j.map((a,n)=>`
            <button class="chip" type="button" data-filter="${a.key}"
                    aria-pressed="${n===0}">${i(a.label)}
              <span class="chip__n t-read">${u(e.filter(a.of).length)}</span>
            </button>`).join("")}
        </div>
        <div class="lb__group" role="group" aria-label="Order the runs">
          ${H.map((a,n)=>`
            <button class="chip" type="button" data-order="${a.key}"
                    aria-pressed="${n===0}">${i(a.label)}</button>`).join("")}
        </div>
      </div>

      <p class="lb__empty t-small u-dim" data-rack-empty hidden></p>
      <ul class="rk" data-rack></ul>

      ${le(t)}
    </div>
    ${de()}`:`
    <div class="lb">
      <header class="lb__head">
        <h1 class="t-l">${u(t.length)} combined run${t.length===1?"":"s"}
          saved on this machine.</h1>
        <p class="t-lede">
          Every one of them was analysed here and is stored here. No single
          video is saved at the moment; each run below opens as a report of its
          own, with its videos inside it.
        </p>
        ${ce()}
      </header>

      ${Q()}

      ${le(t)}
    </div>
    ${de()}`}function xe(){dt(d.querySelector(".lb"));const e=d.querySelector("[data-as-shelf]");e&&e.addEventListener("click",()=>{_e(!1),window.location.reload()});for(const t of d.querySelectorAll("[data-filter]"))t.addEventListener("click",()=>{O=j.find(a=>a.key===t.dataset.filter)||j[0];for(const a of d.querySelectorAll("[data-filter]"))a.setAttribute("aria-pressed",String(a===t));F(),k(`${O.label}.`)});for(const t of d.querySelectorAll("[data-order]"))t.addEventListener("click",()=>{D=H.find(a=>a.key===t.dataset.order)||H[0];for(const a of d.querySelectorAll("[data-order]"))a.setAttribute("aria-pressed",String(a===t));F(),k(`Ordered by ${D.label.toLowerCase()}.`)});d.querySelector("[data-cmp-clear]").addEventListener("click",()=>{T.clear(),F(),Ce()}),F()}function mt(e,t,a,n){const o=d.querySelector("[data-stage]"),s=d.querySelector("[data-desk]"),l=d.querySelector("[data-cases]"),f=d.querySelector(".bk__frame");if(!o||!s)return;const y=s.querySelector("[data-desk-kicker]"),v=s.querySelector("[data-desk-title]"),S=s.querySelector("[data-desk-blurb]"),p=s.querySelector("[data-desk-ledger]"),c=s.querySelector("[data-desk-open]"),N=s.querySelector("[data-desk-flip]"),L=s.querySelector("[data-desk-close]"),A=s.querySelector(".bk__acts"),K=s.querySelector("[data-desk-delete]"),ee=s.querySelector("[data-desk-confirm]"),q=s.querySelector("[data-desk-confirm-text]"),x=s.querySelector("[data-desk-confirm-yes]"),M=s.querySelector("[data-desk-confirm-no]");let h=null,b=null,R=null,U=!1;const P=Ve(),Ee=r=>{if(b=r,B(),!r){const _=s.contains(document.activeElement);s.classList.remove("is-open"),_&&R&&R.isConnected&&R.focus({preventScroll:!0});return}const g=document.createElement("span");g.textContent=r.kicker;const w=[g];if(r.foot){const _=document.createElement("span");_.className="bk__kfoot",_.textContent=r.foot,w.push(_)}y.replaceChildren(...w),v.innerHTML=`${i(r.title)}${r.sub?` <em>${i(r.sub)}</em>`:""}`,S.textContent=r.blurb,p.innerHTML=r.ledger.map(([_,I])=>`<div>
      <dt>${i(_)}</dt>
      <dd${_==="Flagged"&&I!=="0"?' class="is-tear"':""}>${i(I)}</dd></div>`).join(""),c.setAttribute("href",r.href),s.classList.add("is-open"),U&&(U=!1,c.focus({preventScroll:!0})),k(`${r.title}${r.sub?" "+r.sub:""} taken down. Authenticity ${r.authText}, brand health ${r.healthText}.`)},Le=()=>{h&&(h.destroy(),h=null),s.classList.remove("is-open"),h=a(o,{bays:e,theme:document.documentElement.dataset.theme==="field"?"field":"bench",anchor:l,frame:f,onFocus:Ee,onOpen:r=>{te(),window.location.href=r.href},onReady:()=>{if(n(),!P)return;const r=performance.now()+2500,g=()=>{if(h){if(h.activeId()===P){k("Back on the shelf, with the volume you were reading still out.");return}performance.now()>r||(h.focus(P),setTimeout(g,120))}};setTimeout(g,120)}})},B=()=>{ee.hidden=!0,A.hidden=!1,x.disabled=!1,M.disabled=!1,delete s.dataset.confirming},Ae=()=>{if(!b)return;const r=b.id.startsWith("sweep:"),g=`${b.title}${b.sub?` ${b.sub}`:""}`;q.textContent=r?`Delete ${g} and the ${u(b.videoCount)} video report${b.videoCount===1?"":"s"} inside it? This cannot be undone.`:`Delete ${g}? This cannot be undone.`,A.hidden=!0,ee.hidden=!1,s.dataset.confirming="yes",x.focus(),k(q.textContent)},Me=async()=>{if(!b)return;const r=b.id.startsWith("sweep:"),g=`${b.title}${b.sub?` ${b.sub}`:""}`;x.disabled=!0,M.disabled=!0,q.textContent=`Deleting ${g}…`;try{r?await be(b.filename):await ge(b.filename),k(`${g} deleted. Reopening the shelf.`),window.location.reload()}catch(w){q.textContent=`${g} was not deleted. ${w.message}`,x.disabled=!1,M.disabled=!1,k(q.textContent)}},te=()=>{if(fe(null),!h)return;const r=h.activeVolume();r&&Xe(r)};for(const r of d.querySelectorAll("[data-take]"))r.addEventListener("click",()=>{h&&(R=r,U=!0,h.focus(r.dataset.take))});c.addEventListener("click",te),N.addEventListener("click",()=>h&&h.flip()),L.addEventListener("click",()=>h&&h.clear()),K.addEventListener("click",Ae),M.addEventListener("click",B),x.addEventListener("click",Me);const ae=r=>{r.key!=="Escape"||!s.dataset.confirming||(r.stopPropagation(),B(),K.focus())};window.addEventListener("keydown",ae,!0),Le();const Re=He(r=>{h&&h.setTheme(r)});let ne=!1;const W=async r=>{if(!h||ne)return;ne=!0;const g=await $e(C);if(!h)return;C=g,h.destroy(),h=null,Re(),Y.removeEventListener("change",se),window.removeEventListener("keydown",ae,!0);const w=d.contains(document.activeElement);d.innerHTML=qe($.filter(I=>I.ok),C),xe();const _=w&&d.querySelector("h1");_&&(_.setAttribute("tabindex","-1"),_.focus({preventScroll:!0})),k(r)};ue(r=>{r&&W("Reduced motion. The shelf has been replaced by the list of runs.")});const Y=window.matchMedia(Z),se=()=>{Y.matches||W("The window is too small for the shelf, so the runs are shown as a list.")};Y.addEventListener("change",se);const oe=d.querySelector("[data-as-list]");oe&&oe.addEventListener("click",()=>{_e(!0),W("The runs are shown as a list. Show as a shelf brings the room back.")})}ht();export{ye as S,Ze as s};
