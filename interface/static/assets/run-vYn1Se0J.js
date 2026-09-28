import{m as ae,a as se,b as f}from"./chrome-Bbzm0knH.js";/* empty css                  */import{K as ne,e as c,C as D,n as I,L as ie,M as oe,N as re,O as ce,p as de,P as le,Q as ue,c as v,R as he,s as g,m as pe}from"./contract-wMVeQDZg.js";const d=document.querySelector("[data-run]"),V=1500,m=5,z="Analyse — BrandPulse",F=Object.freeze({video:{key:"video",tab:"One video",title:"Look closer.",lede:"The words. The expression. The voice. The audience. Read one video from four perspectives—and find where they disagree."},brand:{key:"brand",tab:"A brand",title:"Beyond the brand.",lede:"It finds five recent reviews of whatever that maker has shipped, runs all five through the same four channels, and reports both the average and how far apart the five ended up.",label:"Brand",placeholder:"Samsung",hint:"A maker. Five of their recent reviews will be found."},product:{key:"product",tab:"A product",title:"Every perspective.",lede:"It finds five recent reviews of the same thing, runs all five through the same four channels, and reports both the average and how far apart the five reviewers ended up.",label:"Product",placeholder:"iPhone 18 Pro Max",hint:"One product. Five reviews of it will be found."}}),A=[["week","Last week",7],["month","Last month",30],["half","Last 6 months",182],["year","Last year",365]],x=[["0","Today"],["7","A week ago"],["30","A month ago"],["91","Three months ago"],["182","Six months ago"],["365","A year ago"]],_=[{records:["audience"],label:"Fetching and classifying audience comments",spoken:"fetching and classifying audience comments",what:"The Data API returns the video's comments, relevance-ranked, and each one is classified on its own. Author identifiers are never stored.",reaches:"The YouTube Data API, for the comments."},{records:["transcript","facial","vocal"],label:"Downloading, transcribing, reading the face and the voice",spoken:"downloading the video, transcribing it, and reading the face and the voice. This is the long stage",what:"yt-dlp fetches the video and Whisper transcribes it, which is what sets the segment boundaries every other channel aligns to. The face and the voice are then read against those boundaries. This is the long one.",reaches:"YouTube, for the video itself."},{records:[],label:"Scoring cross-modal conflicts",spoken:"scoring cross-modal conflicts, one local model call per segment",what:"Every segment goes to the local controller as four separate readings and it answers where they stop agreeing. One call per segment, on this machine.",reaches:null},{records:[],label:"Computing the final scores",spoken:"computing the final scores",what:"Flagged segments count twice toward Authenticity; Brand Health is 60% of the audience reading and 40% of that.",reaches:null},{records:[],label:"Writing the report",spoken:"writing the report with the local model",what:"The local model reads the finished run and writes what the reviewer liked and disliked, what the audience talks about and whether the two agree. Every figure comes from the run, and every sentence is checked against it before it is kept.",reaches:"The YouTube Data API, once, for the video's own paid-promotion label and its description. The report is written on this machine."}];function B(e){document.title=e?`${e} — ${z}`:z}function fe(){const e={transcript:`<div class="optic optic--transcript">
      <div class="optic__grooves"></div><div class="optic__words">Words / phrases / sentiment / context</div>
      <div class="optic__hub"><i></i><b></b></div></div>`,facial:`<div class="optic optic--facial"><div class="optic__aperture">
      ${Array.from({length:8},(t,a)=>`<i style="--n:${a}"></i>`).join("")}
      <div class="optic__focus"><span></span><b></b></div></div></div>`,vocal:`<div class="optic optic--vocal"><div class="optic__diaphragm">
      ${Array.from({length:5},(t,a)=>`<i style="--n:${a}"></i>`).join("")}
      <span class="optic__needle"></span></div></div>`,audience:`<div class="optic optic--audience"><div class="optic__crowd">
      ${Array.from({length:28},(t,a)=>`<i style="--n:${a}"></i>`).join("")}
      <div class="optic__core">Audience</div></div></div>`};return`<div class="optics" aria-hidden="true">
    <div class="optics__halo"></div>
    <div class="optics__coordinates"><span>BP / Optical array</span><span>04 channels<span class="sep" aria-hidden="true"></span>read locally</span></div>
    <div class="optics__assembly">
      ${D.map((t,a)=>`<div class="optics__plate" data-optic="${t}" style="--i:${a};--optic:var(--ch-${t})">
        <span class="optics__serial">0${a+1} / ${c(I[t].short)}</span>
        ${e[t]}
        <span class="optics__etch">Independent signal / ${String(a+1).padStart(2,"0")}</span>
      </div>`).join("")}
      <div class="optics__beam"></div>
    </div>
    <div class="optics__caption"><span class="optics__cross">+</span><p>Every review.<br><em>Four ways of seeing.</em></p><span>The signal chamber</span></div>
  </div>`}function y(e){return`<div class="rn"><div class="rn__edition"><span>BrandPulse / Analysis studio</span><span><i></i> Local intelligence</span></div>${fe()}${e}<div class="rn__colophon end"><span class="end__sig">Independent readings. A clearer perspective.</span><span>Words / face / voice / audience</span></div></div>`}function me(e){return`
  <div class="rn__modes" role="group" aria-label="What to analyse">
    ${Object.values(F).map(t=>`
      <button class="mode" type="button" data-mode="${t.key}"
              aria-pressed="${t.key===e}">${c(t.tab)}</button>`).join("")}
  </div>`}function L(e,t,a,s,n){const i=n?s.replace("<input ",'<input aria-invalid="true" '):s;return`
  <div class="fld${n?" is-wrong":""}">
    <label class="t-label" for="${e}">${c(t)}</label>
    ${i}
    <p class="fld__hint t-micro" id="${e}-hint">${n?c(n):c(a)}</p>
  </div>`}function ve(e,t){return`
    ${L("url","YouTube address","One video. The address has to contain an eleven-character video id.",`<input id="url" name="video_url" type="url" inputmode="url" required
              autocomplete="off" spellcheck="false"
              aria-describedby="url-hint"
              placeholder="https://www.youtube.com/watch?v="
              value="${c(e.video_url||"")}">`,t.video_url)}
    <div class="fld__pair">
      ${L("brand","Brand","Names the saved report.",`<input id="brand" name="brand_name" required autocomplete="off" autocapitalize="words"
                aria-describedby="brand-hint" placeholder="Samsung"
                value="${c(e.brand_name||"")}">`,t.brand_name)}
      ${L("product","Product","Must not match a report already saved here.",`<input id="product" name="product_name" required autocomplete="off" autocapitalize="words"
                aria-describedby="product-hint" placeholder="Ultra 25"
                value="${c(e.product_name||"")}">`,t.product_name)}
    </div>`}function ge(e){const t=String(e||"0");return x.some(([a])=>a===t)?x:[...x,[t,`${t} days ago`]].sort(([a],[s])=>Number(a)-Number(s))}function K(e,t){const a=A.find(([s])=>s===e);return!!a&&Number(t)>=0&&Number(t)<=a[2]}function J(e,{speak:t=!1}={}){const a=e.querySelector('input[name="window"]:checked'),s=[...e.querySelectorAll('input[name="offset"]')];if(!a||!s.length)return;const[,n,i]=A.find(([l])=>l===a.value)||A[1],o=(x.find(([l])=>Number(l)===i)||["",`${i} days ago`])[1].toLowerCase(),r=`${n} can end at most ${o}`;for(const l of s)l.disabled=!K(a.value,l.value),l.closest(".win__one").title=l.disabled?`Too far back: ${r.toLowerCase()}`:"";const h=s.find(l=>l.checked);h&&h.disabled&&(h.checked=!1,s.find(l=>l.value==="0").checked=!0,t&&f(`Ending moved to today: ${r.toLowerCase()}.`));const p=e.querySelector("[data-ending-note]");p&&(p.textContent=`${r}, one window back. Ending there searches the period just before, with no days in common, for a clean before-and-after in the combined book.`)}function be(e,t,a){return`
    ${L("subject",e.label,e.hint,`<input id="subject" name="subject" required autocomplete="off" autocapitalize="words"
              aria-describedby="subject-hint"
              placeholder="${c(e.placeholder)}"
              value="${c(t.subject||"")}">`,a.subject)}
    <fieldset class="win">
      <legend class="t-label">Look back over</legend>
      <div class="win__row">
        ${A.map(([s,n],i)=>`
          <label class="win__one">
            <input type="radio" name="window" value="${s}"
                   ${(t.window||"month")===s?"checked":""}>
            <span>${c(n)}</span>
          </label>`).join("")}
      </div>
    </fieldset>
    <fieldset class="win">
      <legend class="t-label">Ending</legend>
      <div class="win__row">
        ${ge(t.offset).map(([s,n])=>`
          <label class="win__one">
            <input type="radio" name="offset" value="${s}"
                   ${String(t.offset||"0")===s?"checked":""}>
            <span>${c(n)}</span>
          </label>`).join("")}
      </div>
      <p class="t-micro u-faint" data-ending-note>Ending earlier searches a window of the same length that shares
        no days with a recent one, for a clean before-and-after in the combined book.</p>
    </fieldset>`}function _e(e="video",t={},a={},s=""){const n=F[e]||F.video,i=n.key!=="video";return y(`
    <section class="rn__form" aria-labelledby="fm-h">
      <div class="rn__brief">
        <p class="rn__eyebrow">The analysis studio</p>
        <h1 id="fm-h" class="t-l">${c(n.title)}</h1>
        <p class="t-lede">${c(n.lede)}</p>
        ${s?`<p class="notice t-small">${s}</p>`:""}
      </div>

      ${me(n.key)}

      <form class="rn__panel" data-form novalidate>
        <input type="hidden" name="mode" value="${n.key}">
        ${i?be(n,t,a):ve(t,a)}
        <div class="rn__go">
          <button class="btn" data-variant="solid" type="submit">
            ${i?`Discover ${m} videos`:"Begin analysis"}
          </button>
          <p class="t-micro u-faint">${i?"Searching costs one API call and starts nothing. You confirm the five before any of the machine's time is spent.":"Four to nine minutes. Needs Ollama running on this machine."}</p>
        </div>
      </form>

      <aside class="rn__what">
        <h2 class="t-label">Four independent lenses <span>Held-out accuracy</span></h2>
        <ul class="rn__chans">
          ${D.map(o=>{const r=I[o];return`
            <li data-channel="${o}" style="--ch:var(--ch-${o})">
              <i class="tp__mark" data-mark="${o}" aria-hidden="true"></i>
              <span class="rn__cn t-label">${c(r.label)}</span>
              <span class="t-read">${de(r.accuracy)}</span>
              <span class="t-micro u-faint">${c(r.sample)}</span>
            </li>`}).join("")}
        </ul>
        <p class="t-micro u-faint">
          Each percentage is what that channel scored on this project's own
          hand-labelled data, on speakers or videos it had never seen. Two of the
          four are at or near guessing, which is why a run reports where they
          disagree rather than averaging them into one number.
        </p>
      </aside>
    </section>`)}function Q(e,t){const a=e.verdict==="ok",s=Math.floor((e.duration_s||0)/60),n=String((e.duration_s||0)%60).padStart(2,"0");return`
  <li class="cand${a?"":" is-refused"}"><div class="cand__visual" aria-hidden="true"><img class="cand__thumb" src="/thumbnails/${c(e.video_id)}.jpg" alt="" loading="lazy" decoding="async"><span>Play / review</span><svg viewBox="0 0 80 80"><circle cx="40" cy="40" r="30"/><path d="M34 27L53 40L34 53Z"/></svg><span>${s}:${n}</span></div>
    <label class="cand__pick">
      <input type="checkbox" name="pick" value="${c(e.video_id)}"
             ${t?"checked":""}>
      <span class="sr-only">Include ${c(e.title)}</span>
    </label>
    <div class="cand__body">
      <h3 class="cand__title t-panel">${c(e.title)}</h3>
      <p class="cand__meta t-micro u-faint">
        ${c(e.channel)}
        <span class="cand__sep" aria-hidden="true"></span>
        ${s}m ${n}s
        <span class="cand__sep" aria-hidden="true"></span>
        ${v(e.view_count)} views
        <span class="cand__sep" aria-hidden="true"></span>
        ${v(e.comment_count)} comments
      </p>
    </div>
    <p class="cand__verdict t-label">${a?"Eligible":c(e.verdict)}</p>
  </li>`}const we=/subject not named/i;function G(e){const t=new Date(e||"");return Number.isNaN(t.getTime())?String(e||""):t.toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric"})}function ye(e,t){const a=t.candidates||[],s=new Set(t.suggested||[]),n=a.filter(r=>r.verdict==="ok"),i=a.filter(r=>r.verdict!=="ok"),o=i.filter(r=>we.test(r.verdict||""));return a.length?y(`
    <section class="cast" aria-labelledby="ca-h">
      <div class="cast__head">
        <p class="rn__eyebrow">Curate your perspective</p><h1 id="ca-h" class="t-l">Choose your five.</h1>
        <p class="t-lede">
          ${v(a.length)} videos came back for
          &ldquo;${c(t.subject||"")}&rdquo;, ${v(n.length)} of
          them eligible.${o.length?`
          ${v(o.length)} of the ${v(i.length)} refusals
          ${o.length===1?"is a judgement":"are judgements"} you can
          overrule: a video whose title does not name the subject may still be
          about it.`:""} Every refusal is shown with the rule that produced it
          rather than hidden, and all of them stay selectable.
        </p>
        ${n.length<m?`
          <p class="cast__short t-small">
            Only ${v(n.length)} passed every rule, so reaching
            ${m} means taking ${v(m-n.length)}
            from the refused list below. Each one carries its reason, and a run
            built on them is worth exactly what those reasons are worth.
          </p>`:""}
        <p class="t-micro u-faint">Searched as
          <code>${c(t.query_used||"")}</code>, published ${c(G(t.published_after))}
          to ${t.published_before?c(G(t.published_before)):"today"}</p>
      </div>

      <form data-pick>
        <div class="cast__bar">
          <p class="t-label" data-tally></p>
          <div class="cast__acts">
            <button class="btn" type="button" data-back>Change the search</button>
            <button class="btn" data-variant="solid" type="submit" data-start-sweep>
              Analyse the ${m} chosen
            </button>
          </div>
        </div>

        <ul class="cast__list">
          ${n.map(r=>Q(r,s.has(r.video_id))).join("")}
        </ul>

        ${i.length?`
          <div class="cast__refused">
            <h2 class="t-label">Refused, with the reason</h2>
            <p class="t-micro u-faint">
              These are still selectable. Nothing here is hidden from you, and
              the rule that refused each one is printed beside it.
            </p>
            <ul class="cast__list">
              ${i.map(r=>Q(r,!1)).join("")}
            </ul>
          </div>`:""}
      </form>
    </section>`):y(`
      <section class="state">
        <p class="t-label state__tag">Nothing found</p>
        <h2 class="t-l">The search came back empty.</h2>
        <p class="t-body">No videos matched
          &ldquo;${c(t.subject||"")}&rdquo; in that period. A longer
          window usually fixes it.</p>
        <button class="btn" type="button" data-back>Change the search</button>
      </section>`)}function P(e,t){if(t<0)return"waiting";for(let a=0;a<_.length;a+=1)if(_[a].records.includes(e))return a<t?"recorded":a===t?"recording":"waiting";return"waiting"}function X(e){return e<2?"waiting":e===2||e===4?"recording":"recorded"}function $e(e,t){const a=t.stage_index,s=_[a]||null,n=e==="sweep";return y(`
    <section class="wait" aria-labelledby="wa-h" data-wait>
      <div class="wait__top">
        <div><p class="rn__eyebrow">Analysis in motion</p><h1 id="wa-h" class="t-l">${n?"Five perspectives.":"Reading between<br>the signals."}</h1></div>
        <div class="wait__time"><span class="rn__eyebrow">Elapsed</span><p class="wait__clock t-readout" data-elapsed>0:00</p></div>
      </div>

      ${n?`
        <div class="wait__which">
          <p class="t-label" data-video-line>${t.video_index?`Video ${t.video_index} of ${t.video_total||m}`:"Preparing your five videos"}</p>
          <p class="t-small u-dim" data-video-title>${c(t.video_title||"")}</p>
          <ol class="wait__dots" data-dots aria-hidden="true"></ol>
        </div>`:""}

      <div class="wait__stage">
        <p class="t-label u-faint" data-stage-no>${s?`Stage ${a+1} of ${_.length}`:"Queued"}</p>
        <h2 class="t-panel" data-stage-name>${s?c(s.label):"Preparing the instrument"}</h2>
        <p class="t-small u-dim" data-stage-what>${s?c(s.what):"Waiting for the worker. Your session will appear here as soon as processing starts."}</p>
      </div>

      <!-- The instrument assembling itself. The lanes are EMPTY on purpose:
           nothing has been measured yet, and drawing a plausible trace to fill
           them would be inventing a measurement. -->
      <div class="rec" data-rec role="progressbar"
           aria-label="How far this run has got"
           aria-valuemin="0" aria-valuemax="${_.length}">
        ${D.map(i=>`
          <div class="rec__lane" data-channel="${i}"
               data-state="${P(i,a)}"
               style="--ch:var(--ch-${i})">
            <span class="rec__id t-label">
              <i class="tp__mark" data-mark="${i}" aria-hidden="true"></i>
              ${c(I[i].short)}
            </span>
            <span class="rec__track"><i class="rec__scan"></i></span>
            <span class="rec__state t-micro"></span>
          </div>`).join("")}
        <div class="rec__lane rec__lane--ctrl" data-controller
             data-state="${X(a)}">
          <span class="rec__id t-label">
            <i class="rec__ctrlmark" aria-hidden="true"></i>
            Controller
          </span>
          <span class="rec__track"><i class="rec__scan"></i></span>
          <span class="rec__state t-micro"></span>
        </div>
        <p class="rec__note t-micro u-faint">
          Live processing status. Measured readings appear in the finished report.
        </p>
      </div>

      <!-- The product's central claim, as a live reading. -->
      <div class="port" data-port>
        <span class="port__lamp" aria-hidden="true"></span>
        <div>
          <p class="t-label" data-port-state></p>
          <p class="t-micro u-faint" data-port-why></p>
        </div>
      </div>

      <div class="wait__acts">
        <button class="btn" type="button" data-cancel>Stop this run</button>
        <p class="t-micro u-faint">
          ${n?"Stopping is checked between stages, so it is not instant. Every report already finished is kept, and running the same sweep again resumes from there.":"Stopping ends the run at once. Nothing is written to the outputs directory unless the run finishes."}
        </p>
      </div>
    </section>`)}const N={done:{tag:"Finished",urgent:!1,say:({result:e,kind:t})=>{if(t==="sweep"){const s=e&&e.summary||{},n=s.authenticity||{};return`The sweep finished. ${s.video_count||0} videos. Mean authenticity ${g(n.mean)} out of 100, ranging from ${g(n.min)} to ${g(n.max)}. ${s.spread_verdict||""}. A link to the combined report follows.`}const a=(e&&e.flagged_segments||[]).length;return`The analysis finished. Authenticity ${g(e.authenticity_score)} out of 100. Brand health ${g(e.brand_health_score)} out of 100. ${e.segment_count??"An unknown number of"} segments, ${a} flagged as cross-channel conflicts. The bias caveat is on the report. A link to open it follows.`}},partial:{tag:"Partly finished",urgent:!1,say:({result:e})=>{const t=e&&e.summary||{},a=(e&&e.failed||[]).length;return`The sweep finished partly. ${t.video_count||0} of ${(t.video_count||0)+a} videos were analysed; ${a} could not be. Each failure is listed with its reason. The combined report covers the videos that did finish.`}},cancelled:{tag:"Stopped",urgent:!1,say:({kind:e})=>e==="sweep"?"The sweep was stopped. Every report it had already finished is kept, and running the same sweep again resumes from there rather than starting over.":"The run was stopped. Nothing was written to the outputs directory. Links to start again and to open the library follow."},error:{tag:"Failed",urgent:!0,say:({data:e})=>"The run did not finish. The backend reported: "+(e&&e.error||"no reason given")+". The usual causes are a private, region-locked or removed video, comments disabled on it, an exhausted YouTube quota, or Ollama not running."},lost:{tag:"No longer known",urgent:!0,say:()=>"That run is no longer known to the server. Jobs are held in memory, so restarting Flask forgets them. If the run had already finished, its report is in the library."}};function ke(e){return e&&e.report_file?`/library/${encodeURIComponent(e.report_file)}`:null}function Se(e,t){const a=N[e]||N.error,s=t.result||t.report||{},n=t.kind==="sweep";let i="";if(e==="done"&&!n){const o=ke(t),r=(s.flagged_segments||[]).length;i=`
      <dl class="fin__scores">
        <div><dt class="t-label u-faint">Authenticity</dt>
          <dd class="t-readout">${g(s.authenticity_score)}</dd></div>
        <div><dt class="t-label u-faint">Brand health</dt>
          <dd class="t-readout">${g(s.brand_health_score)}</dd></div>
        <div><dt class="t-label u-faint">Flagged</dt>
          <dd class="t-readout${r?" is-tear":""}">${v(r)}</dd></div>
      </dl>
      <p class="t-small u-dim">
        ${v(s.segment_count)} segments. Both scores measure how far four
        independent readings of the same moment disagreed. Neither is a finding
        about whether anyone was telling the truth.
      </p>
      <div class="fin__acts">
        ${o?`<a class="btn" data-variant="solid" href="${o}">Open the report</a>`:""}
        <a class="btn" href="/library">Open the library</a>
      </div>`}else if((e==="done"||e==="partial")&&n){const o=s.summary||{},r=o.authenticity||{},h=s.failed||[];i=`
      <dl class="fin__scores">
        <div><dt class="t-label u-faint">Mean authenticity</dt>
          <dd class="t-readout">${g(r.mean)}</dd></div>
        <div><dt class="t-label u-faint">Lowest</dt>
          <dd class="t-readout">${g(r.min)}</dd></div>
        <div><dt class="t-label u-faint">Highest</dt>
          <dd class="t-readout">${g(r.max)}</dd></div>
      </dl>
      ${o.spread_verdict?`<p class="t-small u-dim">${c(o.spread_verdict)}</p>`:""}
      ${h.length?`
        <div class="fin__failed">
          <h2 class="t-label">Could not be analysed</h2>
          <ul class="t-small">
            ${h.map(p=>`<li><b>${c(p.title||p.video_id||"A video")}</b>
              <span class="u-dim">${c(p.reason||p.error||"no reason recorded")}</span></li>`).join("")}
          </ul>
        </div>`:""}
      <div class="fin__acts">
        ${t.sweep_id?`<a class="btn" data-variant="solid" href="/brand/${encodeURIComponent(t.sweep_id)}">Open the combined report</a>`:""}
        <a class="btn" href="/library">Open the library</a>
      </div>`}else i=`
      <div class="fin__acts">
        <button class="btn" data-variant="solid" type="button" data-again>Start another run</button>
        <a class="btn" href="/library">Open the library</a>
      </div>`;return y(`
    <section class="fin" data-outcome="${e}" aria-labelledby="fi-h">
      <p class="t-label fin__tag${a.urgent?" is-tear":""}">${c(a.tag)}</p>
      <h1 id="fi-h" class="t-l">${c(e==="done"?n?"Five videos, combined.":"The run finished.":e==="partial"?"Some of it finished.":e==="cancelled"?"Stopped.":e==="lost"?"That run is no longer known.":"The run did not finish.")}</h1>
      ${e==="error"?`<p class="fin__why t-body">${c(t&&t.error||"No reason was given.")}</p>
           <p class="t-small u-dim">
             The usual causes are a private, region-locked or removed video, comments
             disabled on it, an exhausted YouTube quota, or Ollama not running on
             <code>localhost:11434</code>.
           </p>`:e==="lost"?`<p class="t-body">Jobs are held in memory, so restarting the server forgets
               them. If this run had already finished, its report is in the library.</p>`:e==="cancelled"?`<p class="t-body">${n?"Every report it had already finished is kept. Running the same sweep again resumes from there rather than starting over.":"Nothing was written to the outputs directory."}</p>`:""}
      ${i}
    </section>`)}let k=null,S=null,T=null,M=-2;function ee(){k&&(clearTimeout(k),k=null),S&&(clearInterval(S),S=null)}function Te(e,t,a){for(const u of d.querySelectorAll("[data-optic]"))u.dataset.state=P(u.dataset.optic,t.stage_index??-1);const s=d.querySelector(".optics");s&&(s.dataset.stage=String(t.stage_index??-1));const n=typeof t.stage_index=="number"?t.stage_index:-1,i=_[n]||null,o=t.total_stages||_.length,r=d.querySelector("[data-stage-no]"),h=d.querySelector("[data-stage-name]"),p=d.querySelector("[data-stage-what]");if(!r)return;r.textContent=n<0?"Queued":`Stage ${n+1} of ${o}`,h.textContent=i?i.label:"Waiting for the worker",p.textContent=i?i.what:"";const l=d.querySelector("[data-rec]");l&&(n<0?(l.removeAttribute("aria-valuenow"),l.setAttribute("aria-valuetext","Queued. No stage has started yet.")):(l.setAttribute("aria-valuenow",String(n)),l.setAttribute("aria-valuetext",`Stage ${n+1} of ${o}, ${i?i.spoken:"working"}. ${n} of ${o} stages complete.`)));const q={recorded:"recorded",recording:"recording",waiting:"not yet"};for(const u of d.querySelectorAll("[data-channel].rec__lane")){const w=P(u.dataset.channel,n);u.dataset.state=w,u.querySelector(".rec__state").textContent=q[w]}const C=d.querySelector("[data-controller]");if(C){const u=X(n);C.dataset.state=u,C.querySelector(".rec__state").textContent=u==="recorded"?"done":u==="recording"?n===4?"writing the report":"reading all four":"waiting for four"}const W=d.querySelector("[data-port]"),j=i?i.reaches:null;if(W&&(W.dataset.open=String(!!j),d.querySelector("[data-port-state]").textContent=j?"The aperture is open":"Sealed",d.querySelector("[data-port-why]").textContent=j||"Nothing is leaving this machine. The controller is a local model on localhost:11434."),e==="sweep"){const u=d.querySelector("[data-video-line]"),w=d.querySelector("[data-video-title]"),te=d.querySelector("[data-dots]");if(u){const E=t.video_index||0,O=t.video_total||m;u.textContent=t.phase==="combined"?`All ${O} videos read. Writing the combined report`:E?`Video ${E} of ${O}`:"Starting",w.textContent=t.video_title||"",te.innerHTML=Array.from({length:O},(Ne,U)=>`<li data-state="${U<E-1?"done":U===E-1?"now":"next"}"></li>`).join("")}}if(n!==M){M=n;const u=i?i.spoken:"waiting for the worker";f(`Stage ${Math.max(1,n+1)} of ${o}: ${u}.`),B(n<0?"Queued":`Stage ${n+1} of ${o}`)}const Y=d.querySelector("[data-elapsed]");if(Y&&!S){const u=()=>{const w=a||Date.now()/1e3;Y.textContent=pe(Math.max(0,Date.now()/1e3-w))};u(),S=setInterval(u,1e3)}}function H(){window.scrollY>0&&window.scrollTo({top:0,behavior:"instant"});const e=d.querySelector("h1");e&&(e.setAttribute("tabindex","-1"),e.focus({preventScroll:!0}))}function $(e,t){ee(),T=null;const a=N[e]||N.error;d.innerHTML=Se(e,t),H(),B(a.tag),f(a.say({result:t.result||t.report||{},data:t,kind:t.kind||"analysis"}),{urgent:a.urgent}),Ae()}function Ae(){const e=d.querySelector("[data-again]");e&&e.addEventListener("click",()=>{B(""),b()})}async function R(e,t,a){T={jobId:e,kind:t},d.innerHTML=$e(t,{stage_index:-1}),H(),qe(e,t);const s=t==="sweep"?re:ce;async function n(){if(!T||T.jobId!==e)return;let i;try{i=await s(e)}catch(r){if(r&&r.status===404){$("lost",{});return}k=setTimeout(n,V*2);return}const o=i.status;if(o==="running"){Te(t,i,a||i.started_at),k=setTimeout(n,V);return}$(o==="done"?"done":o==="partial"?"partial":o==="cancelled"?"cancelled":"error",i)}n()}function qe(e,t){const a=d.querySelector("[data-cancel]");a&&a.addEventListener("click",async()=>{a.disabled=!0,a.textContent="Stopping",f(t==="sweep"?"Stopping the run. This is checked between stages, so it is not instant.":"Stopping the run.");try{await(t==="sweep"?ie(e):oe(e))}catch{a.disabled=!1,a.textContent="Stop this run",f("The stop request did not reach the server. The run is still going.",{urgent:!0})}})}const je=/(?:v=|youtu\.be\/|\/shorts\/|\/embed\/)([A-Za-z0-9_-]{11})/;function Z(e){const t=new FormData(e),a={};for(const[s,n]of t.entries())a[s]=String(n).trim();return a}function b(e="video",t={},a={},s=""){ee(),T=null,M=-2,d.innerHTML=_e(e,t,a,s),Ee()}function Ee(){for(const t of d.querySelectorAll("[data-mode]"))t.addEventListener("click",()=>{const a=d.querySelector("[data-form]");b(t.dataset.mode,a?Z(a):{});const s=d.querySelector(`[data-mode="${t.dataset.mode}"]`);s&&s.focus()});const e=d.querySelector("[data-form]");if(e){J(e);for(const t of e.querySelectorAll('input[name="window"]'))t.addEventListener("change",()=>J(e,{speak:!0}));e.addEventListener("submit",async t=>{t.preventDefault();const a=Z(e),s=a.mode||"video",n=e.querySelector('button[type="submit"]'),i={};if(s==="video"?(a.video_url?je.test(a.video_url)||(i.video_url="That address has no eleven-character video id in it."):i.video_url="Paste the address of a YouTube video.",a.brand_name||(i.brand_name="Needed: it names the saved report."),a.product_name||(i.product_name="Needed: it names the saved report.")):a.subject||(i.subject=`Name the ${s} to look for.`),Object.keys(i).length){b(s,a,i);const o=d.querySelector(".is-wrong input");o&&o.focus(),f(Object.values(i).join(" "),{urgent:!0});return}n.disabled=!0,n.textContent=s==="video"?"Preparing analysis…":"Discovering videos…",e.setAttribute("aria-busy","true"),d.querySelector(".rn").classList.add("is-discovering");try{if(s==="video"){const o=await le({video_url:a.video_url,brand_name:a.brand_name,product_name:a.product_name});f("The analysis has started. It takes four to nine minutes."),R(o.job_id,"analysis",Date.now()/1e3)}else{const o=await ue({subject:a.subject,window:a.window||"month",offset_days:Number(a.offset||0)});d.innerHTML=ye(s,o),H(),xe(s,a,o),f(`${(o.candidates||[]).length} videos found, ${o.eligible||0} of them eligible. Choose ${m}.`)}}catch(o){const r=o&&o.message||"the request failed";b(s,a,{},c(r)),f(r,{urgent:!0})}})}}function xe(e,t,a){const s=d.querySelector("[data-pick]"),n=d.querySelector("[data-tally]"),i=d.querySelector("[data-start-sweep]"),o=d.querySelectorAll("[data-back]");for(const h of o)h.addEventListener("click",()=>b(e,t));if(!s)return;function r(){const h=s.querySelectorAll('input[name="pick"]:checked').length;n.textContent=`${h} chosen of ${m}`,n.classList.toggle("is-tear",h!==m),i.disabled=h!==m}s.addEventListener("change",r),r(),s.addEventListener("submit",async h=>{h.preventDefault();const p=[...s.querySelectorAll('input[name="pick"]:checked')].map(l=>l.value);i.disabled=!0,i.textContent="Starting";try{const l=await he({subject:t.subject,subject_kind:e,window:t.window||"month",offset_days:Number(t.offset||0),video_ids:p,candidates:a.candidates||[],query_used:a.query_used||"",published_after:a.published_after||"",published_before:a.published_before||null});if(l.already_finished){window.location.href=`/brand/${encodeURIComponent(l.sweep_id)}`;return}f(`The sweep has started on ${p.length} videos. This takes considerably longer than a single run.`),R(l.job_id,"sweep",Date.now()/1e3)}catch(l){const q=l&&l.message||"the sweep could not be started";b(e,t,{},c(q)),f(q,{urgent:!0})}})}async function Le(){ae(),se({here:"/run"});const e=document.querySelector("[data-footer]");e&&e.remove();try{const a=await ne();if(a&&a.active){const s=a.kind==="sweep"?"sweep":"analysis";R(a.job_id,s,a.started_at),f("This machine is already running an analysis. Showing its progress."),clearTimeout(window.__bpFallback);return}}catch{d.innerHTML=y(`
      <section class="state state--error">
        <p class="t-label state__tag">Backend unreachable</p>
        <h1 class="t-l">Nothing answered on this machine.</h1>
        <p class="t-body">
          The interface is served by the same Flask process that runs the
          pipeline, so if this page loaded and the API did not, the server is
          part-way up or has stopped. Start it with
          <code>python -m flask --app app run --port 5001</code> from
          <code>brandpulse_ai/</code>.
        </p>
        <a class="btn" href="/library">Try the library</a>
      </section>`),clearTimeout(window.__bpFallback);return}const t=new URLSearchParams(window.location.search);if(t.get("subject")){const a=t.get("kind")==="brand"?"brand":"product",s=A.some(([r])=>r===t.get("window"))?t.get("window"):"month",n=t.get("offset")||"0",i=/^\d{1,4}$/.test(n)?String(Number(n)):"0",o=K(s,i)?i:"0";b(a,{subject:t.get("subject"),window:s,offset:o},{},o===i?"":"That link asked for an ending further back than this window allows, so it starts at today. A window can end at most one window back.")}else b();clearTimeout(window.__bpFallback)}Le();
