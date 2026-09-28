import{m as je,a as Be,b as oe,p as He}from"./chrome-Bbzm0knH.js";import{_ as me}from"./preload-helper-wn6Ki-z9.js";/* empty css                  */import{p as Ue,d as b,q as Ve,v as De,x as We,y as Ge,z as ze,A as Ke,B as Qe,D as Ye,E as Je,F as Xe,e as pe,g as Ze,j as et,k as tt,G as at,w as st,o as nt,l as ot,H as rt,m as ue,i as ct,I as D}from"./codex-CieP9hhw.js";import{w as it,e as u,j as Ie,x as lt,c as h,m as A,p as F,a as E,h as qe,n as B,F as ce,C as K,A as Le,B as dt,D as W,k as ee,E as Ne,G as Fe,s as ht,H as Me,r as mt,I as pt}from"./contract-wMVeQDZg.js";import{t as ut,c as ft,m as _t,s as fe}from"./leaf-vrvMp2mH.js";import{m as gt,v as bt,p as re,a as vt,h as $t}from"./frames-Dx4w5fNa.js";const p=document.querySelector("[data-report]");function yt(){const t=decodeURIComponent(window.location.pathname),a=t.match(/^\/brand\/([^/]+)\/([^/]+)\/?$/);if(a)return{kind:"member",sweepId:a[1],videoId:a[2]};const e=t.match(/^\/library\/(.+?)\/?$/);return e?{kind:"report",filename:e[1]}:{kind:"none"}}function X(t,a,e,o=""){p.innerHTML=`
    <section class="state${t==="Unreachable"?" state--error":""}">
      <p class="t-label state__tag">${u(t)}</p>
      <h1 class="t-l">${u(a)}</h1>
      <p class="t-body">${e}</p>${o}
    </section>`,delete document.documentElement.dataset.carrying,clearTimeout(window.__bpFallback)}const wt=t=>t.reduce((a,e)=>(e.conflict_score??-1)>(a.conflict_score??-1)?e:a,t[0]),xt=[["Overview","ti-h"],["Key moments","mo-h"],["Four channels","rl-h"],["Audience","au-h"],["Evidence","le-h"]];function _e(t){const a=[["Length",A(t.duration)],["Segments",h(t.segments)],["Comments read",h(t.comments)]],e=t.worst?vt(t.worst):null,o=t.worst&&typeof t.worst.conflict_score=="number"&&t.worst.conflict_score>0;let s;t.plate?o?s=`The plate is ${A(e)}, the midpoint of the run&rsquo;s most contested
      segment (${A(t.worst.start_s)} to ${A(t.worst.end_s)}, conflict
      ${E(t.worst.conflict_score)}).${t.onShelf?" The same frame is printed on this volume&rsquo;s cover.":""}`:s=`The plate is ${A(e)}. No segment in this run scored any conflict,
      so it is the first segment&rsquo;s midpoint.`:s="No frame was derived for this video, so this page carries no plate.";const n=t.plate?`
      <p class="cx-kicker">${t.kicker}</p>
      <h1 id="ti-h" class="ti__title cx-display" data-len="${ue(t.brand)}">${u(t.brand)}</h1>
      ${t.product?`<p class="ti__sub">${u(t.product)}</p>`:""}
      <span class="ti__rule cx-rule" aria-hidden="true"></span>`:"";return`
  <section class="ti${t.plate?"":" ti--plain"}" aria-labelledby="ti-h">
    ${t.plate?`
      <figure class="ti__plate cx-bleed">
        <img src="${t.plate}" alt="A frame from this video at ${A(e)}." decoding="async">
      </figure>`:`
      <div class="ti__board cx-bleed">
        <p class="ti__bk">${t.kicker}</p>
        <h1 id="ti-h" class="ti__title cx-display" data-len="${ue(t.brand)}">${u(t.brand)}</h1>
        <span class="ti__brule" aria-hidden="true"></span>
        ${t.product?`<p class="ti__bsub">${u(t.product)}</p>`:""}
      </div>`}
    <div class="ti__block">${n}
      <dl class="ti__facts">
        ${a.map(([l,r])=>`<div><dt>${l}</dt><dd class="t-read">${r}</dd></div>`).join("")}
      </dl>
      ${ct(t.short)}
      ${t.plate?"":`
      <nav class="toc toc--chapters" aria-label="Contents">
        <p class="cx-h3">Contents</p>
        <ol class="toc__list">
          ${xt.map(([l,r],m)=>`
            <li><span class="toc__n t-read">${m+1}</span>
              <button class="toc__t" type="button" data-cx-xref="${r}">${l}</button>
              <span class="toc__pg t-read" data-cx-xref="${r}"><span data-cx-xref-page></span></span></li>`).join("")}
        </ol>
      </nav>`}
      ${t.plate?`<p class="ti__stand cx-note">If you are the person in this frame,
        <button class="cx-xref" type="button" data-cx-xref="standing">page
        <span data-cx-xref-page></span></button> is written to you.</p>`:""}
      <p class="ti__cap cx-note">${s}${t.videoId?` Source:
        <a href="${u(t.videoUrl)}" rel="noopener noreferrer" target="_blank">${t.videoTitle?`“${u(t.videoTitle)}”, on YouTube`:"the video, on YouTube"}<span class="sr-only"> (opens in a new tab)</span></a>.`:""}</p>
    </div>
  </section>`}function ge(t,a,e,o,s){const n=a.length,l=A(Math.max(...a.map(_=>_.end_s))),r=[];r.push(e?`${h(n)} segments across ${l}. In ${h(e)} of them
       (${F(e/n*100,0)}) the readings disagreed enough to be flagged
       (${E(W)} or more on a 0 to 1 scale); those count twice.`:`${h(n)} segments across ${l}; none disagreed enough to be flagged
       (${E(W)} on a 0 to 1 scale).`),s&&typeof s.conflict_score=="number"&&s.conflict_score>0&&r.push(`The biggest disagreement is at ${A(s.start_s)}, scored
      ${E(s.conflict_score)} by the local model.`);const m=o.facial;r.push(`A face was read in ${h(m.read)} of ${h(m.total)}
    segments${m.thin?", under half the video":""}.`);const f=t.comment_sentiment||{},i=f.distribution||{},c=qe(i);return f.label&&c?r.push(c.nearTie?`The audience, read once for the whole video, is close to a tie:
         ${h(c.top[1])} ${u(c.top[0].toLowerCase())} against
         ${h(c.second[1])} ${u(c.second[0].toLowerCase())}.`:`The audience, read once for the whole video, reads
         ${u(f.label.toLowerCase())}: ${h(i.POSITIVE||0)} positive,
         ${h(i.NEUTRAL||0)} neutral and ${h(i.NEGATIVE||0)} negative comments.`):r.push("No audience reading was recorded for this video."),r.join(" ")}function be(t,a,e,o,s,n=null,l=null){const r=a.length,m=$=>typeof $=="number"&&Number.isFinite($)?Math.min(100,Math.max(0,$)).toFixed(2):null,f=($,O,H)=>{const M=m(O);return`
    <div class="fi__score">
      <p class="fi__k">${$}<span class="fi__dag" aria-hidden="true">&dagger;</span></p>
      <p class="fi__v"><span class="t-read">${ht(O)}</span><span class="fi__of">of 100</span></p>
      <span class="fi__scale" aria-hidden="true">${M!=null?`<i style="--at:${M}%"></i>`:""}</span>
      <p class="fi__def">${H}</p>
    </div>`},i=o.facial,c=(t.all_comments||[]).length,_=t.bias_caveat?`<p class="fi__note cal__caveat"><span class="fi__dag" aria-hidden="true">&dagger;</span>
         ${u(t.bias_caveat)}${t.vocal_caveat?` The vocal channel carries a
         caveat of its own, printed with the channels on
         <button class="cx-xref" type="button" data-cx-xref="vocal-caveat">page
         <span data-cx-xref-page></span></button>.`:""}</p>`:`<p class="fi__note cal__caveat">This report carries no caveat text of its own.
         That is unusual and is stated rather than passed over: every report
         written by the current pipeline carries at least the facial bias
         disclosure.</p>`,S=`<p class="fi__not cx-note">
      Both scores measure how far four independent readings of the same
      moment disagreed with each other.
      Neither is a finding about whether anyone was telling the truth,
      and neither is comparable between videos.
    </p>`;return n?`
  <section class="fi rd" aria-label="The reading">
    <div class="rd__head"><p class="cx-kicker">The reading</p>
      ${ot(n.facts.confidence.level,"#channels")}</div>
    ${rt(n,l,ge(t,a,e,o,s))}
    <div class="fi__scores">
      ${f("Authenticity",t.authenticity_score,"How far the four readings of each moment agreed; flagged moments count twice.")}
      ${f("Brand health",t.brand_health_score,"60% audience comment sentiment and 40% Authenticity.")}
    </div>
    ${S}
    ${_}
  </section>`:`
  <section class="fi" aria-label="What the run found">
    <div class="fi__scores">
      ${f("Authenticity",t.authenticity_score,"100 minus the weighted mean conflict between channels; flagged segments count twice.")}
      ${f("Brand health",t.brand_health_score,"60% audience comment sentiment and 40% Authenticity.")}
    </div>

    <dl class="fi__counts">
      <div><dt>Segments</dt><dd class="t-read">${h(r)}</dd>
        <dd class="fi__sub">across ${A(Math.max(...a.map($=>$.end_s)))}</dd></div>
      <div><dt>Flagged</dt><dd class="t-read${e?" is-tear":""}">${h(e)}</dd>
        <dd class="fi__sub">${F(r?e/r*100:0,0)} of the run</dd></div>
      <div><dt>Faces read</dt><dd class="t-read">${h(i.read)}</dd>
        <dd class="fi__sub">of ${h(i.total)} segments</dd></div>
      <div><dt>Comments</dt><dd class="t-read">${h(c)}</dd>
        <dd class="fi__sub">whole video</dd></div>
    </dl>

    <p class="fi__summary cx-text">${ge(t,a,e,o,s)}</p>

    ${S}

    ${_}
  </section>`}function ve(){return`
  <section class="mo" data-act="moment" aria-labelledby="mo-h">
    <h2 id="mo-h" class="sr-only">The moment under the playhead</h2>
    <figure class="mo__plate cx-bleed">
      <div class="mo__frame" data-flip-id="report-frame">
        <img alt="" data-frame hidden>
        <div class="mo__none" data-noframe hidden><p>No frame was derived for this second.</p></div>
      </div>
    </figure>
    <p class="mo__cap"><span class="mo__when t-time" data-at></span>
      <span class="mo__capt" data-cap></span></p>
    <div class="mo__strip" data-transport></div>
    <nav class="mo__nav" aria-label="Moments">
      <div class="mo__step">
        <button class="cx-btn cx-btn--icon" type="button" data-mo-step="-1"
                aria-label="Previous moment">${D("prev")}</button>
        <span class="mo__navl">Moment</span>
        <button class="cx-btn cx-btn--icon" type="button" data-mo-step="1"
                aria-label="Next moment">${D("next")}</button>
      </div>
      <div class="mo__step" data-mo-flags>
        <button class="cx-btn cx-btn--icon" type="button" data-mo-flag="-1"
                aria-label="Previous flagged moment">${D("prev")}</button>
        <span class="mo__navl" data-mo-flagpos></span>
        <button class="cx-btn cx-btn--icon" type="button" data-mo-flag="1"
                aria-label="Next flagged moment">${D("next")}</button>
      </div>
      <a class="mo__all" href="#evidence" data-mo-all>Every moment</a>
    </nav>
  </section>`}function $e(){return`
  <section class="mr" data-act="moment-read" aria-label="What was said, and what each channel read">
    <header class="mr__head">
      <p class="mr__pos" data-pos></p>
      <p class="mr__flag" data-flagged hidden>Flagged</p>
    </header>
    <blockquote class="mr__said" data-said></blockquote>
    <button class="cx-btn mr__more" type="button" data-said-more hidden></button>
    <table class="rd">
      <caption class="sr-only">Each channel's reading of this segment</caption>
      <colgroup><col class="rd__c1"><col><col class="rd__c3"><col class="rd__c4"></colgroup>
      <thead>
        <tr>
          <th scope="col">Channel</th>
          <th scope="col">Read</th>
          <th scope="col"><span class="rd__axis" aria-hidden="true"><i>&minus;</i><i>0</i><i>+</i></span>
            <span class="sr-only">Valence, negative to positive</span></th>
          <th scope="col">Score</th>
        </tr>
      </thead>
      <tbody data-rows></tbody>
    </table>
    <p class="rd__verdict" data-verdict></p>
    <div class="why" data-why></div>
  </section>`}function kt(t,a,e){const o=B[a],s=mt(t,a,e),n=pt(t,a,e),l=a==="facial"?Ne(t):null,r=Fe(s);let m="";if(a==="audience")m="one reading, whole video";else if(a==="facial")m=l!=null?`pooled from ${h(l)} frame${l===1?"":"s"}`:"no face found";else if(a==="vocal"){const c=Me((t.model_outputs||{}).vocal_emotion);m=c&&c.arousal!=null?"read on arousal":""}s&&!r&&(m=`${s.toLowerCase()} has no valence, so it is not compared`);const f=n!=null?E(n):null,i=a==="vocal"?"arousal":a==="audience"?"mean confidence":"confidence";return`
  <tr data-channel="${a}" style="--ch:var(--ch-${a})"${s?"":" data-absent"}>
    <th scope="row">
      <span class="rd__ch"><i class="mo__mark" data-mark="${a}" aria-hidden="true"></i>${u(o.short)}</span>
      ${m?`<span class="rd__note">${u(m)}</span>`:""}
    </th>
    <td class="rd__read">${s?u(s.toLowerCase()):"<span class='is-absent'>no reading</span>"}</td>
    <td class="rd__scale">
      <span class="rd__dots" data-v="${r||"none"}" aria-hidden="true"><i></i><i></i><i></i></span>
      <span class="sr-only">${r?`valence ${r.toLowerCase()}`:"no valence"}</span>
    </td>
    <td class="rd__score">${f!=null?`<span class="t-read">${f}</span>
      <span class="rd__what">${i}</span>`:"<span class='is-absent'>none</span>"}</td>
  </tr>`}function St(t){const a=t.conflict_score,e=Le(t),s=(t.conflict_reasons||[]).filter(l=>typeof l=="string").filter(l=>l.startsWith("channels_in_conflict: ")).map(l=>l.slice(22)),n=typeof a=="number"&&Number.isFinite(a)?(Math.min(1,Math.max(0,a))*100).toFixed(2):null;return`
    <div class="why__row">
      <p class="why__k">Conflict</p>
      <p class="why__n t-read${t.flagged?" is-tear":""}">${E(a)}</p>
      <span class="why__scale" aria-hidden="true" style="--thr:${(W*100).toFixed(1)}%">
        <b class="why__thr"></b>${n!=null?`<i class="${t.flagged?"is-tear":""}" style="--at:${n}%"></i>`:""}
        <span class="why__lo">0</span><span class="why__hi">1</span>
      </span>
    </div>
    <p class="why__says cx-note">${t.flagged?`At or above the ${E(W)} threshold, so this segment is
         flagged and counted twice toward Authenticity.`:`Below the ${E(W)} threshold, so it is counted once.`}
      ${s.length?`The controller named ${s.map(l=>`<code>${u(l)}</code>`).join(", ")} as in conflict.`:"The controller named no channels."}</p>
    ${e?`
      <p class="why__damp cx-note">
        The controller scored this ${E(e.before)}. It was reduced to
        <b>${E(e.after)}</b> because the conflict rested on the
        <b>${u(e.channel||"weak")}</b> channel alone, which is down-weighted by its
        own measured accuracy (&times;${e.weight.toFixed(3)}). The value before the
        reduction is read from the orchestrator&rsquo;s audit trail, not worked back out.
      </p>`:""}`}function ye(t,a){const e=Ie(a,t.comment_sentiment),o=ce,s=K.filter(n=>B[n].perSegment&&e[n].thin);return`
  <section class="rl" data-act="coverage" aria-labelledby="rl-h">
    <h2 id="rl-h" class="cx-h">How the evidence was read</h2>
    <p class="cx-lede">
      How much of this video each channel could read, and how accurate each was
      when tested on this project&rsquo;s own hand-labelled data. A segment a
      channel could not read is a gap, never a neutral reading.
    </p>
    <table class="rl__t">
      <caption class="sr-only">Coverage in this video and measured accuracy, per channel</caption>
      <thead>
        <tr><th scope="col">Channel</th><th scope="col">Read in this video</th>
            <th scope="col">Accuracy when tested</th></tr>
      </thead>
      <tbody>
      ${K.map(n=>{const l=e[n],r=B[n],m=n==="facial";return`
        <tr data-channel="${n}" style="--ch:var(--ch-${n})"${l.thin&&r.perSegment?" data-thin":""}>
          <th scope="row">
            <span class="rl__name"><i class="mo__mark" data-mark="${n}" aria-hidden="true"></i>${u(r.label)}</span>
            <span class="rl__reads">${u(r.reads)}</span>
          </th>
          <td>
            ${r.perSegment?`
              <span class="rl__bar" aria-hidden="true"><i style="--to:${(l.share*100).toFixed(2)}%"></i></span>
              <span class="rl__v"><span class="t-read">${h(l.read)}</span> of ${h(l.total)} segments</span>`:`<span class="rl__v">${l.read?"One reading for the whole video":"<span class='is-absent'>no reading</span>"}</span>`}
          </td>
          <td>
            <span class="rl__acc${m?" rl__acc--ref":""}" aria-hidden="true">
              <i style="--at:${r.accuracy}%"></i>
              ${m?`<b data-kind="constant" style="--at:${o.constant.value}%"></b>
                          <b data-kind="ceiling" style="--at:${o.ceiling.value}%"></b>`:""}
            </span>
            <span class="rl__v"><span class="t-read">${F(r.accuracy)}</span>
              <span class="rl__sample">${u(r.sample)}</span></span>
          </td>
        </tr>`}).join("")}
      </tbody>
    </table>
    <p class="rl__legend cx-note">On the facial row,
      <i class="rl__tick" aria-hidden="true"></i> is a constant that always answers neutral
      (${F(o.constant.value)}), <i class="rl__tick rl__tick--ceil" aria-hidden="true"></i>
      the human ceiling (${F(o.ceiling.value)}).${s.length?`
      ${s.map(n=>u(B[n].label)).join(" and ")} read under half of this video.`:""}</p>
  </section>`}function we(t){const a=[t.bias_caveat,t.vocal_caveat].filter(Boolean);return`
  <section class="lm" data-act="weak" aria-labelledby="lm-h">
    <h2 id="lm-h" class="cx-h">What limits the reading</h2>
    ${a.length?`
      <ol class="lm__notes">
        ${a.map((e,o)=>{const s=e===t.bias_caveat;return`
          <li class="lm__note" id="${s?"bias-caveat":"vocal-caveat"}">
            <p class="lm__k"><span class="lm__n">${o+1}</span>${s?"Facial emotion":"Vocal prosody"}</p>
            <p class="cal__caveat">${u(e)}</p>
            ${s?`<p class="lm__plus cx-note">Measured here: ${F(B.facial.accuracy)}
              on held-out speakers, below a constant that always answers neutral
              (${F(ce.constant.value)}). None of nine models benched beat it, so the
              channel stays in, down-weighted to 0.342 when it is the only one dissenting.</p>`:""}
          </li>`}).join("")}
      </ol>`:`<p class="cal__caveat">This report carries no caveat text of its own. That is
           unusual and is stated rather than passed over: every report written by the
           current pipeline carries at least the facial bias disclosure.</p>`}
  </section>`}function xe(){return`
  <section class="lm" data-cannot-tell aria-labelledby="ct-h">
    <h2 id="ct-h" class="cx-h">What these numbers cannot tell you</h2>
    <ol class="lm__notes">
      ${[["Whether anyone was honest.","Authenticity measures how far four automatic readings of the same seconds disagreed. It is not a judgement of sincerity, and a low score is not evidence of a lie."],["Whether the product is any good.","Brand health mixes the audience's tone with that disagreement. It says nothing about the product's quality."],["How this video compares with another.","Both scores depend on the video's length, its speaker, and which local model is installed on this machine, so they are read within one video, not ranked across several."],["Anything outside English.","The transcript, the comments and every sentence written about them are read as English."]].map(([a,e],o)=>`
        <li class="lm__note">
          <p class="lm__k"><span class="lm__n">${o+1}</span>${u(a)}</p>
          <p class="cal__caveat">${u(e)}</p>
        </li>`).join("")}
    </ol>
  </section>`}function ke(){return`
  <section class="lm" id="standing" data-standing tabindex="-1" aria-labelledby="st-h">
    <h2 id="st-h" class="cx-h">If you are the person in this video</h2>
    <ol class="lm__notes">
      <li class="lm__note">
        <p class="lm__k"><span class="lm__n">1</span>None of these numbers is a finding about you.</p>
        <p class="cal__caveat">They measure how far four automated readings of the same
          seconds drifted apart. A low Authenticity score is a disagreement between
          machines, not evidence that anyone was insincere, and it should not be
          repeated as though it were.</p>
      </li>
      <li class="lm__note">
        <p class="lm__k"><span class="lm__n">2</span>The reading taken from your face is the weakest here.</p>
        <p class="cal__caveat">It scored ${F(B.facial.accuracy)} on speakers it had
          never seen, below a constant that always answers neutral
          (${F(ce.constant.value)}). Its usual mistake is to read a neutral
          face as a negative one.</p>
      </li>
      <li class="lm__note">
        <p class="lm__k"><span class="lm__n">3</span>There is no way to contest a reading in this build.</p>
        <p class="cal__caveat">It runs on one machine, with no server and no account.
          Everything behind the numbers stays on this machine and can be inspected: the
          frames that were sampled, what each channel returned, and the conflict score that
          followed. A deployed version would owe you three things this one does not have:
          a named person to contact, the right to see the frames a reading was drawn from,
          and a way to have a reading struck from a report.</p>
      </li>
    </ol>
  </section>`}const Tt=[["pitch","Pitch","Hz","vocal","mean fundamental frequency per segment, by autocorrelation"],["energy","Energy","","vocal","mean short-term energy, unitless"],["arousal","Arousal","","vocal","the one dimension the orchestrator reads, before thresholding"],["valence","Valence","","vocal","recorded, never read"],["dominance","Dominance","","vocal","recorded, never read"]];function Oe(t,a){const e=[];for(const o of t){const s=o.model_outputs||{};let n=null;if(a==="pitch")n=s.pitch_mean_hz;else if(a==="energy")n=s.energy_mean;else{const l=Me(s.vocal_emotion);n=l?l[a]:null}e.push(typeof n=="number"&&Number.isFinite(n)?n:null)}return e}function Se(t){const a=Tt.map(([e,o,s,n,l])=>{const r=Oe(t,e),m=r.filter(f=>f!=null);return{key:e,label:o,unit:s,channel:n,note:l,points:r,real:m}}).filter(e=>e.real.length);return`
  <section class="me" data-act="measures" aria-labelledby="me-h">
    <h2 id="me-h" class="cx-h">Measured, and deliberately not scored</h2>
    <p class="cx-lede">
      The pipeline extracts these for every segment and the scorer reads none of
      them. They are printed because a number that was computed and discarded is
      part of what the run did, and hiding it would make the system look tidier
      than it is. Each line runs the length of the video.
    </p>
    ${a.length?`
    <ul class="me__list">
      ${a.map(e=>{const o=Math.min(...e.real),s=Math.max(...e.real),n=e.real.reduce((l,r)=>l+r,0)/e.real.length;return`
        <li class="me__row">
          <p class="me__id"><b>${u(e.label)}</b><span>${u(e.note)}</span></p>
          <span class="me__spark" data-spark="${e.key}" aria-hidden="true"></span>
          <dl class="me__stats">
            <div><dt>low</dt><dd class="t-read">${o.toFixed(2)}${u(e.unit)}</dd></div>
            <div><dt>mean</dt><dd class="t-read">${n.toFixed(2)}${u(e.unit)}</dd></div>
            <div><dt>high</dt><dd class="t-read">${s.toFixed(2)}${u(e.unit)}</dd></div>
            <div><dt>read on</dt><dd class="t-read">${h(e.real.length)} of ${h(e.points.length)}</dd></div>
          </dl>
        </li>`}).join("")}
    </ul>`:'<p class="cx-note">This run recorded none of these measures.</p>'}
  </section>`}function Te(t,a){const e=a.length,o=a.filter(i=>i.flagged).length,s=a.filter(i=>i.conflict_score===0).length,n=a.map(Le).filter(Boolean),l=i=>n.filter(c=>c.channel===i),r=i=>[...new Set(i.map(c=>c.weight.toFixed(3)))],m=a.filter(i=>dt(i).channels.size>0).length,f=["facial","vocal"].map(i=>{const c=l(i);return c.length?`${B[i].short.toLowerCase()} &times;${r(c).join(", &times;")} on
         ${h(c.length)} segment${c.length===1?"":"s"}`:null}).filter(Boolean);return`
  <section class="mt" aria-labelledby="mt-h">
    <h2 id="mt-h" class="cx-h">How a disagreement becomes a score</h2>
    <p class="cx-text">
      For every segment, the four readings are sent together to a language model
      running on this machine, the controller, which answers with a conflict score
      between 0 and 1. The two scores on the overview are built from those
      answers and nothing else.
    </p>
    <dl class="mt__figs">
      <div><dt>At or above the ${E(W)} threshold, so flagged and counted twice</dt>
        <dd><span class="t-read">${h(o)}</span> of ${h(e)}</dd></div>
      <div><dt>Scored exactly zero</dt>
        <dd><span class="t-read">${h(s)}</span> of ${h(e)}</dd></div>
      <div><dt>Reduced because one weak channel was the only dissent</dt>
        <dd><span class="t-read">${h(n.length)}</span> of ${h(e)}</dd></div>
      <div><dt>The controller named which channels were in conflict</dt>
        <dd><span class="t-read">${h(m)}</span> of ${h(e)}</dd></div>
    </dl>
    <p class="cx-note">
      When the only dissent comes from the facial or the vocal channel, the
      controller&rsquo;s score is multiplied by that channel&rsquo;s measured accuracy,
      so a channel that is usually wrong cannot flag a segment on its own.
      ${f.length?`In this video: ${f.join("; ")}.`:"No segment in this video was reduced that way."}
    </p>
    <p class="cx-note">
      The controller can also name the channels it thought were in conflict.
      ${m===0?"In this video it named none.":`In this video it did so on ${h(m)} of ${h(e)} segments.`}
      The reduction above does not depend on it: it also has a deterministic
      trigger that reads the pipeline&rsquo;s own channel labels and needs no
      model compliance.
    </p>
  </section>`}const ne=["POSITIVE","NEUTRAL","NEGATIVE"];function Ae(t){const a=t.comment_sentiment||{},e=a.distribution||{},o=qe(e),s=(t.all_comments||[]).filter(r=>r&&r.text),n=Object.values(e).reduce((r,m)=>r+m,0),l=r=>n?(e[r]||0)/n*100:0;return`
  <section class="au" data-act="audience" aria-labelledby="au-h">
    <h2 id="au-h" class="cx-h">What the audience said</h2>
    <p class="cx-lede">
      One reading for the whole video. Comments are posted hours or days after
      it and cannot know which second they are about, so this channel has no
      time resolution and is drawn flat across the timeline.
    </p>
    ${n?`
    <figure class="au__fig">
      <div class="au__band" role="img" aria-label="${ne.map(r=>`${h(e[r]||0)} ${r.toLowerCase()}`).join(", ")}, of ${h(n)} comments">
        ${ne.map(r=>`<i data-k="${r}" style="--n:${e[r]||0}"></i>`).join("")}
      </div>
      <dl class="au__nums">
        ${ne.map(r=>`
          <div data-k="${r}"><dt><i class="cm__glyph" aria-hidden="true"></i>${r.toLowerCase()}</dt>
            <dd class="t-read">${h(e[r]||0)}</dd>
            <dd class="au__pct">${F(l(r),1)}</dd></div>`).join("")}
      </dl>
    </figure>`:'<p class="cx-note">No distribution of comment classes was recorded for this video.</p>'}
    <p class="au__verdict cx-text">${a.label?`Classified <b>${u(a.label.toLowerCase())}</b> overall${a.confidence!=null?`, with a mean confidence of ${E(a.confidence)}`:""}, across
        ${h(a.comment_count||s.length)} comments.`:"No aggregate audience reading was recorded."}</p>
    ${o&&o.nearTie?`
      <p class="au__tie cx-note">
        This is close. ${u(o.top[0].toLowerCase())} leads
        ${u(o.second[0].toLowerCase())} by ${F(o.margin*100,1)} of the
        comments, so reporting the leading label as a verdict would overstate it.
        Both counts are above.
      </p>`:""}
    <p class="cx-note">A sample of ${h(s.length)} comments, each classified on
      its own. No author is stored, logged or shown anywhere in this system.</p>
  </section>`}function Ee(){return`
  <div class="cm__head" data-act="audience-quotes">
    <h3 class="cx-h3">The comments, as classified</h3>
    <p class="cm__range" data-cm-range></p>
  </div>
  <ul class="cm__list" data-cx-flow data-comments></ul>
  <button class="cx-btn cm__showmore" type="button" data-more hidden>Show more comments</button>`}const At=420,Pe=340;function ie(t,a){const e=t.slice(0,a),o=e.lastIndexOf(" ");return(o>a*.6?e.slice(0,o):e).replace(/[\s,.;:]+$/,"")}function Et(t){const a=(t.all_comments||[]).map((s,n)=>({c:s,src:n})).filter(({c:s})=>s&&s.text),e=[];return{items:a.map(({c:s,src:n},l)=>{const r=typeof s.label=="string"?s.label:typeof s.sentiment=="string"?s.sentiment:"",m=Fe(r)||"",f=String(s.text),i=f.length>At;e.push(f);const c=document.createElement("li");return c.className="cm",c.dataset.i=String(l),c.dataset.src=String(n),m&&(c.dataset.k=m),c.innerHTML=`
      <blockquote class="cm__q" data-cm-text>${i?`${u(ie(f,Pe))}&hellip;`:u(s.text)}</blockquote>
      <p class="cm__k">${m?'<i class="cm__glyph" aria-hidden="true"></i>':""}
        <span>${r?u(r.toLowerCase()):"unclassified"}</span>${typeof s.confidence=="number"?`<span class="t-read">${E(s.confidence)}</span>`:""}${i?`<button class="cm__more" type="button" data-cm-more aria-expanded="false">Read all
          ${h(f.length)} characters</button>`:""}</p>`,c}),full:e}}const z=[{key:"all",label:"All",of:()=>!0},{key:"flagged",label:"Flagged",of:t=>!!t.flagged},{key:"facevwords",label:"Face against words",of:(t,a)=>a.facial==="NEGATIVE"&&a.transcript==="POSITIVE"},{key:"noface",label:"No face read",of:(t,a)=>!a.facial}],Z=[{key:"time",label:"In time order",of:(t,a)=>t.start_s-a.start_s},{key:"conflict",label:"Most conflict first",of:(t,a)=>(a.conflict_score??-1)-(t.conflict_score??-1)}];function Ce(t,a){const e=t.comment_sentiment,o=Object.fromEntries(z.map(s=>[s.key,a.filter(n=>s.of(n,ee(n,e))).length]));return`
  <section class="le" data-act="ledger" aria-labelledby="le-h">
    <div class="le__top">
      <div class="le__intro">
        <h2 id="le-h" class="cx-h">Every segment</h2>
        <p class="cx-lede">
          The whole record, folded out. Filter it, reorder it, and pick any row to
          make it the current moment. Arrow keys move between rows.
        </p>
      </div>
      <div class="le__acts">
        <button class="cx-btn" type="button" data-cx-tomoment>Open the selected moment</button>
        <button class="cx-btn" type="button" data-cx-foldback>${D("prev")} Fold back into the book</button>
      </div>
    </div>

    <div class="le__controls">
      <div class="le__group" role="group" aria-label="Filter the segments">
        ${z.map((s,n)=>`
          <button class="chip" type="button" data-view="${s.key}"
                  aria-pressed="${n===0}">${u(s.label)}
            <span class="chip__n t-read">${h(o[s.key])}</span></button>`).join("")}
      </div>
      <div class="le__group" role="group" aria-label="Order the segments">
        ${Z.map((s,n)=>`
          <button class="chip" type="button" data-sort="${s.key}"
                  aria-pressed="${n===0}">${u(s.label)}</button>`).join("")}
      </div>
    </div>

    <p class="le__empty cx-note" data-empty hidden></p>

    <table class="le__table">
      <caption class="sr-only">Every segment, with each channel's reading and its
        conflict score</caption>
      <thead>
        <tr>
          <th scope="col">At</th>
          <th scope="col">Readings</th>
          <th scope="col">What was said</th>
          <th scope="col">Conflict</th>
        </tr>
      </thead>
      <tbody data-ledger></tbody>
    </table>

    <p class="le__end">
      <button class="cx-btn" type="button" data-cx-foldback>${D("prev")} Fold back into the book</button>
    </p>
  </section>`}function Ct(t,a){const e=ee(a,t.comment_sentiment),o=a.conflict_score??0;return`
  <tr data-seg="${a.segment_id}"${a.flagged?" data-flag":""} tabindex="-1">
    <th scope="row" class="t-time">${A(a.start_s)}</th>
    <td>
      <span class="le__glyphs" aria-hidden="true">
        ${K.map(s=>`<i data-channel="${s}" data-v="${e[s]||"none"}"
             style="--ch:var(--ch-${s})"></i>`).join("")}
      </span>
      <span class="sr-only">${K.map(s=>`${B[s].short} ${e[s]?e[s].toLowerCase():"not measured"}`).join(", ")}.</span>
    </td>
    <td class="le__txt">${u(a.text||"")}</td>
    <td class="le__cs">
      <span class="le__bar" style="--to:${(o*100).toFixed(1)}%"></span>
      <span class="t-read">${E(a.conflict_score)}</span>
      ${a.flagged?'<span class="sr-only">Flagged.</span>':""}
    </td>
  </tr>`}const It=460,qt=380;function Lt(t,a,e,o){const s=t.comment_sentiment,n=p.querySelector("[data-frame]"),l=p.querySelector("[data-noframe]"),r=p.querySelector("[data-cap]"),m=p.querySelector("[data-at]"),f=p.querySelector("[data-pos]"),i=p.querySelector("[data-flagged]"),c=p.querySelector("[data-said]"),_=p.querySelector("[data-said-more]"),S=p.querySelector("[data-rows]"),$=p.querySelector("[data-verdict]"),O=p.querySelector("[data-why]"),H=p.querySelector("[data-mo-flagpos]"),M=a.filter(U=>U.flagged);let C="",j=!1;const q=()=>{const U=C.length>It;c.textContent=C?`“${U&&!j?`${ie(C,qt)}…`:C}”`:"",c.hidden=!C,c.dataset.size=C.length>300?"s":C.length>140?"m":"l",_.hidden=!U,_.textContent=j?"Show less of this segment":`Show all ${h(C.length)} characters of this segment`,_.setAttribute("aria-expanded",String(j))};return _.addEventListener("click",()=>{j=!j,q()}),function(v){if(!v)return;const Q=a.indexOf(v)+1;m.textContent=`${A(v.start_s)} to ${A(v.end_s)}`,f.textContent=`Segment ${h(Q)} of ${h(a.length)}, ${A(v.start_s)} to ${A(v.end_s)}`,i.hidden=!v.flagged,C=v.text||"",j=!1,q(),S.innerHTML=K.map(y=>kt(v,y,s)).join("");const te=ee(v,s),P=Object.values(te),G=new Set(P).size;$.textContent=P.length<2?"Fewer than two channels read this segment, so there is nothing to compare.":G===1?`All ${P.length} channels that read this segment agree.`:`${G} different readings of the same segment.`,$.classList.toggle("is-tear",!!v.flagged),O.innerHTML=St(v);const Y=re(o,e,v);Y?(n.src=Y,n.alt=`A frame this run analysed at ${A((v.start_s+v.end_s)/2)}.`,n.hidden=!1,l.hidden=!0):(n.hidden=!0,l.hidden=!1);const V=Ne(v);if(r.textContent=$t(o,e)?`The segment midpoint${V!=null?`, one of ${h(V)} frame${V===1?"":"s"} the facial channel pooled`:""}.`:"No imagery was derived for this video.",M.length){const y=M.indexOf(v);H.textContent=y>=0?`Flagged ${h(y+1)} of ${h(M.length)}`:`${h(M.length)} flagged`}}}function Nt(t,a){const e=t.filter(s=>s.flagged);for(const s of p.querySelectorAll("[data-mo-step]"))s.addEventListener("click",()=>a.step(Number(s.dataset.moStep)));const o=p.querySelector("[data-mo-flags]");if(!e.length){o.innerHTML='<span class="mo__navl">No segment in this run was flagged</span>';return}for(const s of p.querySelectorAll("[data-mo-flag]"))s.addEventListener("click",()=>{const n=Number(s.dataset.moFlag),l=a.t,r=n>0?e.find(m=>m.start_s>l+.02)||e[0]:[...e].reverse().find(m=>m.start_s<l-.02)||e[e.length-1];a.set(r.start_s+.01,{reason:"jump"})})}function Ft(t,a,e){const o=p.querySelector("[data-ledger]"),s=p.querySelector("[data-empty]");if(!o)return()=>{};let n=z[0],l=Z[0],r=[];function m(){const i=t.comment_sentiment;r=a.filter(_=>n.of(_,ee(_,i))).sort(l.of),o.innerHTML=r.map(_=>Ct(t,_)).join("");const c=r.length===0;s.hidden=!c,c&&(s.textContent=n.key==="facevwords"?"No segment in this run has the face reading negative while the words read positive. That is a finding about this video, not an empty table.":"No segment in this run matches that filter."),f(e.segment)}function f(i){const c=o.querySelectorAll("tr[data-seg]");for(const $ of c)$.removeAttribute("aria-current"),$.tabIndex=-1;const _=i?o.querySelector(`tr[data-seg="${i.segment_id}"]`):null;_&&_.setAttribute("aria-current","true");const S=_||c[0];S&&(S.tabIndex=0)}for(const i of p.querySelectorAll("[data-view]"))i.addEventListener("click",()=>{n=z.find(c=>c.key===i.dataset.view)||z[0];for(const c of p.querySelectorAll("[data-view]"))c.setAttribute("aria-pressed",String(c===i));m(),oe(`${n.label}. ${r.length} segment${r.length===1?"":"s"}.`)});for(const i of p.querySelectorAll("[data-sort]"))i.addEventListener("click",()=>{l=Z.find(c=>c.key===i.dataset.sort)||Z[0];for(const c of p.querySelectorAll("[data-sort]"))c.setAttribute("aria-pressed",String(c===i));m(),oe(l.label)});return o.addEventListener("click",i=>{const c=i.target.closest("tr[data-seg]");if(!c)return;const _=a.find(S=>String(S.segment_id)===c.dataset.seg);_&&e.set(_.start_s+.01,{reason:"jump"})}),o.addEventListener("keydown",i=>{const c=i.target.closest("tr[data-seg]");if(!c)return;const _={ArrowDown:1,ArrowUp:-1};if(i.key in _){const S=[...o.querySelectorAll("tr[data-seg]")],$=S[S.indexOf(c)+_[i.key]];$&&(c.tabIndex=-1,$.tabIndex=0,$.focus(),$.click()),i.preventDefault()}(i.key==="Enter"||i.key===" ")&&(c.click(),i.preventDefault())}),m(),f}function Mt(t){for(const a of p.querySelectorAll("[data-spark]")){const e=Oe(t,a.dataset.spark),o=e.filter(i=>i!=null);if(!o.length)continue;const s=Math.min(...o),l=Math.max(...o)-s||1,r=e.map((i,c)=>{if(i==null)return null;const _=c/Math.max(1,e.length-1)*100,S=100-(i-s)/l*100;return`${_.toFixed(2)},${S.toFixed(2)}`});let m="",f=!1;for(const i of r){if(i==null){f=!1;continue}m+=`${f?"L":"M"}${i} `,f=!0}a.innerHTML=`<svg viewBox="0 0 100 100" preserveAspectRatio="none"
      aria-hidden="true"><path d="${m.trim()}" fill="none"
      stroke="var(--ch-vocal)" stroke-width="1.4" vector-effect="non-scaling-stroke"/></svg>`}}function Ot(t){return t?`
  <nav class="member" aria-label="This video inside a combined report">
    <a class="member__back" href="/brand/${encodeURIComponent(t.sweepId)}">
      Back to the combined report</a>
    <p class="member__which">Video ${t.index} of ${t.total}${t.subject?` on ${u(t.subject)}`:""}</p>
    <div class="member__kin">
      ${t.prev?`<a href="${t.prev}">Previous video</a>`:""}
      ${t.next?`<a href="${t.next}">Next video</a>`:""}
    </div>
  </nav>`:""}async function Pt(){je(),Be({here:"/library"});const t=ut(),a=yt();if(a.kind==="none"){X("No report named","This address does not name a report.","A report is opened from the library, which lists everything saved on this machine.",'<a class="btn" href="/library">Open the library</a>');return}let e=null,o=null;try{if(a.kind==="member"){const{getSweep:d,getSweepMember:g}=await me(async()=>{const{getSweep:k,getSweepMember:w}=await import("./contract-wMVeQDZg.js").then(x=>x.S);return{getSweep:k,getSweepMember:w}},[]);e=await g(a.sweepId,a.videoId);try{const k=await d(a.sweepId),w=k.members||[],x=w.findIndex(I=>I.video_id===a.videoId);if(x>=0){const I=se=>se?`/brand/${encodeURIComponent(a.sweepId)}/${encodeURIComponent(se.video_id)}`:null;o={sweepId:a.sweepId,index:x+1,total:w.length,subject:k.subject||k.query||"",title:w[x].title||"",channel:w[x].channel||"",prev:I(w[x-1]),next:I(w[x+1])}}}catch{}e.__filename=e.brand_name?`${e.brand_name} (${e.product_name||""}).json`:""}else e=await it(a.filename),e.__filename=a.filename}catch(d){d&&d.status===404?X("Not found","There is no report saved under that name.","It may have been renamed or removed from the outputs directory since the link was made.",'<a class="btn" href="/library">Open the library</a>'):X("Unreachable","The report could not be read.",`The backend answered: ${u(d&&d.message||"no reason given")}. Reports are plain JSON in this machine's own <code>outputs/</code> directory, so this is a local read rather than a network problem.`,'<a class="btn" href="/library">Open the library</a>');return}const s=(e.all_segments||[]).filter(d=>typeof d.start_s=="number"&&typeof d.end_s=="number");if(!s.length){X("Empty run","This report has no segments.","It was written without any, which means transcription produced nothing to align the other three channels to. There is nothing to draw and nothing to score.",'<a class="btn" href="/library">Open the library</a>');return}let n=null;try{const{getReportAnalysis:d,getMemberAnalysis:g}=await me(async()=>{const{getReportAnalysis:k,getMemberAnalysis:w}=await import("./contract-wMVeQDZg.js").then(x=>x.S);return{getReportAnalysis:k,getMemberAnalysis:w}},[]);n=a.kind==="member"?await g(a.sweepId,a.videoId):await d(a.filename),(!n||!n.facts)&&(n=null)}catch{n=null}const l=a.kind==="member"?`python write_analysis.py --sweep ${a.sweepId} --member ${a.videoId}`:`python write_analysis.py --report "${a.filename}"`,r=(e.flagged_segments||[]).length||s.filter(d=>d.flagged).length,m=await gt(),f=bt(e),i=Ie(s,e.comment_sentiment),c=wt(s),_=Math.max(...s.map(d=>d.end_s));t&&(p.dataset.opening="yes");const{brand:S,product:$}=lt(e.__filename||""),O={brand:o&&o.title?o.title:S||e.brand_name||"Untitled",product:o&&o.title?o.channel||"":$,kicker:o?`Video ${o.index} of ${o.total}${o.subject?` in ${u(o.subject)}`:""}`:"One video, read four ways",plate:re(m,f,c),worst:c,duration:_,segments:s.length,comments:(e.all_comments||[]).length,videoId:f,videoUrl:f?`https://www.youtube.com/watch?v=${f}`:"",videoTitle:String(o&&o.title||n&&n.video_meta&&n.video_meta.fetched&&n.video_meta.title||e.video_title||"").trim(),onShelf:!o,short:n?Ue(n):""},H=[O.brand,o?"":O.product].filter(Boolean).join(", "),M=()=>`
    <p class="cm__range cm__range--cont" data-cm-range></p>
    <ul class="cm__list" data-cx-flow></ul>`,C=new Map(s.map(d=>[d.segment_id,d])),j=new Map((n&&n.reading&&n.reading.topics||[]).map(d=>[d.id,d])),q={segment:d=>C.get(d)||null,comment:d=>(e.all_comments||[])[d]||null,topic:d=>j.get(d)||null},U=d=>{const g=C.get(d.seg);return g?re(m,f,g):null},v=()=>'<ul class="cl__list" data-cx-flow></ul>',Q=!!(n&&n.reading&&n.reading.claims.length),te=n?[{id:"overview",label:"Overview",spreads:[b({key:"overview",plain:["verso","recto"],verso:_e(O),recto:be(e,s,r,i,c,n,q)}),b({key:"overview-2",verso:De(n,q,l),recto:Ve(n,q)})]},{id:"said",label:"What they said",spreads:[b({key:"said-tone",wide:!0,verso:We(n,e,q)}),b({key:"said",verso:ze(n,l),recto:Ge(n,l)}),...Q?[b({key:"said-claims",verso:v(),recto:v()})]:[]]},{id:"audience",label:"Audience",spreads:[b({key:"audience-talk",verso:Qe(n,q,l),recto:Ke(n,q,l)}),b({key:"audience",verso:Ae(e),recto:Ee()})]},{id:"moments",label:"Key moments",spreads:[b({key:"moments-odd",wide:!0,verso:Ye(n,e,q,U)}),b({key:"moments",plain:["verso"],verso:ve(),recto:$e()})]},{id:"channels",label:"Trust",spreads:[b({key:"trust",verso:Xe(n),recto:Je(n,q)}),b({key:"channels",verso:ye(e,s),recto:we(e)}),b({key:"channels-2",verso:Se(s),recto:Te(e,s)}),b({key:"standing",verso:xe(),recto:ke()})]},{id:"evidence",label:"Evidence",spreads:[b({key:"evidence",wide:!0,verso:Ce(e,s)})]}].map(d=>({...d,html:pe(d)})):[{id:"overview",label:"Overview",spreads:[b({key:"overview",plain:["verso","recto"],verso:_e(O),recto:be(e,s,r,i,c)})]},{id:"moments",label:"Key moments",spreads:[b({key:"moments",plain:["verso"],verso:ve(),recto:$e()})]},{id:"channels",label:"Four channels",spreads:[b({key:"channels",verso:ye(e,s),recto:we(e)}),b({key:"channels-2",verso:Se(s),recto:Te(e,s)}),b({key:"standing",verso:xe(),recto:ke()})]},{id:"audience",label:"Audience",spreads:[b({key:"audience",verso:Ae(e),recto:Ee()})]},{id:"evidence",label:"Evidence",spreads:[b({key:"evidence",wide:!0,verso:Ce(e,s)})]}].map(d=>({...d,html:pe(d)}));p.dataset.codex="yes",p.innerHTML=`
    ${Ot(o)}
    ${Ze({title:u(H||"this report"),chapters:te,backHref:o?`/brand/${encodeURIComponent(o.sweepId)}`:"/library",backLabel:o?"Back to the combined report":"Close the book"})}`;const P=ft(_,s),G=Lt(e,s,f,m),Y=Ft(e,s,P);_t(p.querySelector("[data-transport]"),{report:e,segments:s,clock:P,onSegment:d=>{G(d),Y(d)}}),P.set(s[0].start_s+.01,{reason:"boot"}),G(s[0]),Nt(s,P),Mt(s);let V="overview";const y=et(p,{title:H,onSpread:d=>{d.hasAttribute("data-wide")||(V=d.dataset.cxKey),tt(d)}});y&&Q&&y.flow({chapter:"said",items:at(n,q),cont:d=>b({key:`said-claims-${d}`,cont:!0,verso:v(),recto:v()})});const{items:R,full:Re}=Et(e),ae=p.querySelector("[data-more]");let J=12;const le=()=>{R.forEach((d,g)=>{d.hidden=g>=J}),ae.hidden=J>=R.length};y&&y.flow({chapter:"audience",items:R,cont:d=>b({key:`audience-${d}`,cont:!0,verso:M(),recto:M()}),prepare:()=>{for(const d of R)d.hidden=!1;ae.hidden=!0},after:d=>{if(!y.isWide()){le();const g=p.querySelector("[data-cm-range]");g&&(g.textContent=`${h(R.length)} comments`);return}for(const g of d){const k=g.querySelectorAll("li[data-i]"),w=g.parentElement.querySelector("[data-cm-range]");if(!w)continue;if(!k.length){w.textContent=`End of the comments, all ${h(R.length)} shown`;continue}const x=Number(k[0].dataset.i)+1,I=Number(k[k.length-1].dataset.i)+1;w.textContent=`Comments ${h(x)} to ${h(I)} of ${h(R.length)}`}}}),ae.addEventListener("click",()=>{J+=24,le(),oe(`Showing ${Math.min(J,R.length)} of ${R.length} comments.`)}),p.addEventListener("click",d=>{const g=d.target.closest("[data-cm-more]");if(!g)return;const k=g.closest("li[data-i]"),w=k.querySelector("[data-cm-text]"),x=Re[Number(k.dataset.i)],I=g.getAttribute("aria-expanded")!=="true";w.textContent=I?x:`${ie(x,Pe)}…`,g.setAttribute("aria-expanded",String(I)),g.textContent=I?"Show less":`Read all ${h(x.length)} characters`});const de=o?`sweep:${o.sweepId}`:`run:${e.__filename||a.filename||""}`;if(st(p,{link:p.querySelector("[data-cx-close]"),cover:t&&t.cover,before:()=>fe(de,"close")}),window.addEventListener("pagehide",()=>fe(de,"leave")),y){const d=()=>{const T=p.querySelector('[data-cx-key="moments"]');T?y.reveal(T):y.goChapter("moments")};for(const T of p.querySelectorAll("[data-cx-tomoment]"))T.addEventListener("click",d);const g=T=>{const L=T[0],he=Number(T.slice(1));if(L==="S"){const N=C.get(he);if(!N)return;P.set(N.start_s+.01,{reason:"evidence"}),d()}else if(L==="C"){const N=p.querySelector(`.cm[data-src="${he}"]`);if(!N)return;N.hidden=!1,y.reveal(N),N.setAttribute("tabindex","-1"),requestAnimationFrame(()=>N.focus({preventScroll:!0}))}else if(L==="T"){const N=p.querySelector('[data-cx-key="said"]');N&&y.reveal(N)}};p.addEventListener("click",T=>{const L=T.target.closest("[data-ev]");L&&g(L.dataset.ev)});const k=new URLSearchParams(window.location.search),w=k.get("at"),x=k.get("c"),I=/^\d{1,5}$/.test(w||"")?`S${Number(w)}`:/^\d{1,5}$/.test(x||"")?`C${Number(x)}`:null;I&&requestAnimationFrame(()=>g(I));for(const T of p.querySelectorAll("[data-cx-goto-trust]"))T.addEventListener("click",L=>{L.preventDefault(),y.goChapter("channels")});for(const T of p.querySelectorAll("[data-cx-foldback]"))T.addEventListener("click",()=>{const L=p.querySelector(`[data-cx-key="${CSS.escape(V)}"]`);L?y.reveal(L):y.goChapter("moments")});p.querySelector("[data-mo-all]").addEventListener("click",T=>{T.preventDefault(),y.goChapter("evidence")})}He(p.querySelector('[data-flip-id="report-frame"]')),delete document.documentElement.dataset.carrying,requestAnimationFrame(()=>nt(p,t)),document.title=`${H||"Report"} — BrandPulse`,clearTimeout(window.__bpFallback)}Pt();
