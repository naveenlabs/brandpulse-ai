import{e as m,m as G,c as ne,a as at,p as Pe}from"./contract-wMVeQDZg.js";import{r as le,g as me,e as st,f as He}from"./chrome-Bbzm0knH.js";import{d as ot,o as ct}from"./leaf-vrvMp2mH.js";let rt=0;const Ce=e=>`${e}${rt+=1}`,ge=(e,n,s)=>Math.min(s,Math.max(n,e)),ae=e=>typeof e=="number"&&Number.isFinite(e);function se(e){if(!ae(e))return"not readable";const n=Math.abs(e).toFixed(2);return e>.004?`+${n}`:e<-.004?`−${n}`:"0.00"}const it={POSITIVE:"pos",NEUTRAL:"neu",NEGATIVE:"neg"};function lt(e,n){return`<pattern id="${e}" width="5" height="5" patternUnits="userSpaceOnUse"
    patternTransform="rotate(45)"><rect width="5" height="5" class="ch-bg"/>
    <line x1="0" y1="0" x2="0" y2="5" class="${n}" stroke-width="2.2"/></pattern>`}function dt({reviewer:e,audience:n,agreement:s}){const i=v=>86+(ge(v,-1,1)+1)/2*348,d=v=>v&&ae(v.lean),h=(v,k)=>d(v)&&ae(v.se)?`<line class="tug__ci" x1="${i(v.lean-1.96*v.se).toFixed(1)}" y1="${k}"
        x2="${i(v.lean+1.96*v.se).toFixed(1)}" y2="${k}" data-grow-c/>`:"",u=(v,k,P)=>d(v)?`<text class="tug__lab" x="${ge(i(v.lean),120,400).toFixed(1)}" y="${k}" text-anchor="middle">${P} ${se(v.lean)}</text>`:`<text class="tug__lab" x="260" y="${k}" text-anchor="middle">${P}: not readable</text>`,g=s&&(s.call==="reviewer_warmer"||s.call==="audience_warmer"),S=d(e)&&d(n)?`<line class="tug__gap${g?" is-clear":""}" x1="${i(e.lean).toFixed(1)}" y1="30"
        x2="${i(n.lean).toFixed(1)}" y2="74"/>`:"",A=[d(e)?`The reviewer's words lean ${se(e.lean)}`:"The reviewer's words could not be read",d(n)?`the comments lean ${se(n.lean)}`:"the comments could not be read"].join("; ");return`<svg class="tug" viewBox="0 0 520 104" role="img"
      aria-label="${m(`${A}, on a scale from minus one, all negative, to plus one, all positive.`)}">
    <line class="tug__axis" x1="86" y1="52" x2="434" y2="52"/>
    <line class="tug__tick" x1="86" y1="47" x2="86" y2="57"/>
    <line class="tug__tick tug__tick--zero" x1="${520/2}" y1="43" x2="${520/2}" y2="61"/>
    <line class="tug__tick" x1="434" y1="47" x2="434" y2="57"/>
    <text class="tug__end" x="76" y="56" text-anchor="end">negative</text>
    <text class="tug__end" x="444" y="56" text-anchor="start">positive</text>
    ${S}
    ${h(e,30)}${h(n,74)}
    ${d(e)?`<circle class="tug__r" cx="${i(e.lean).toFixed(1)}" cy="30" r="6.5" data-pop/>`:""}
    ${d(n)?`<rect class="tug__a" x="${(i(n.lean)-6).toFixed(1)}" y="68" width="12" height="12" data-pop/>`:""}
    ${u(e,14,"Reviewer")}${u(n,99,"Audience")}
  </svg>`}function ht({points:e=[],turns:n=[],flagged:s=[],duration:c=0,labels:l={},compact:a=!1}){const o=a?480:960,i=a?132:300,d=a?8:64,h=o-(a?8:20),u=a?10:58,g=i-(a?22:44),S=(u+g)/2,A=(g-u)/2,v=c>0?c:Math.max(1,...e.map(_=>_.end||0)),k=_=>d+ge(_,0,v)/v*(h-d),P=_=>S-ge(_,-1,1)*A,Y=[];let j=[];for(const _ of e){if(!ae(_.smooth)){j.length&&Y.push(j),j=[];continue}j.push(_)}j.length&&Y.push(j);const J=Y.map(_=>_.length===1?`M${k(_[0].start).toFixed(1)},${P(_[0].smooth).toFixed(1)}H${k(_[0].end).toFixed(1)}`:_.map((M,V)=>`${V?"L":"M"}${k(M.t).toFixed(1)},${P(M.smooth).toFixed(1)}`).join("")).join(""),de=Y.map(_=>{const M=_.length===1?[{t:_[0].start,smooth:_[0].smooth},{t:_[0].end,smooth:_[0].smooth}]:_;return`${M.map((K,H)=>`${H?"L":"M"}${k(K.t).toFixed(1)},${P(K.smooth).toFixed(1)}`).join("")}L${k(M[M.length-1].t).toFixed(1)},${S}L${k(M[0].t).toFixed(1)},${S}Z`}).join(""),W=Ce("ta-a"),oe=Ce("ta-b"),$e=Ce("ta-h"),xe=a?[]:[0,.25,.5,.75,1].map(_=>{const M=d+_*(h-d),V=_===0?"start":_===1?"end":"middle";return`<line class="ta__grid" x1="${M.toFixed(1)}" y1="${u}" x2="${M.toFixed(1)}" y2="${g}"/>
      <text class="ta__time" x="${M.toFixed(1)}" y="${g+30}" text-anchor="${V}">${G(_*v)}</text>`}).join(""),ve=s.map(_=>`<rect class="ta__flag" x="${k(_.start_s).toFixed(1)}" y="${g+6}"
      width="${Math.max(3,k(_.end_s)-k(_.start_s)).toFixed(1)}" height="7" data-pop>
      <title>${m(`Flagged at ${G(_.start_s)}`)}</title></rect>`).join(""),Te=a?"":(()=>{const V=[],K=[-1/0,-1/0],H=n.map((B,L)=>({turn:B,i:L})).sort((B,L)=>B.turn.t-L.turn.t);for(const{turn:B,i:L}of H){const re=`${L+1} ${l[B.seg]||(B.kind==="peak"?"Peak":"Dip")}`,ee=re.length*7.2,he=k(B.t),Q=ge(he,d+ee/2,h-ee/2);let Z=K.findIndex(D=>Q-ee/2>=D+18);Z<0&&(Z=K[0]<=K[1]?0:1),K[Z]=Q+ee/2,V.push({turn:B,i:L,text:re,cx:Q,row:Z,px:he})}return V.map(({turn:B,i:L,text:re,cx:ee,row:he,px:Q})=>{const Z=he===0?14:34,D=P(B.smooth);return`<g class="ta__pin" data-pop>
        <line class="ta__stem" x1="${Q.toFixed(1)}" y1="${Z+6}" x2="${Q.toFixed(1)}" y2="${(D-5).toFixed(1)}"/>
        <circle class="ta__dot" cx="${Q.toFixed(1)}" cy="${D.toFixed(1)}" r="4.5"/>
        <text class="ta__lab" x="${ee.toFixed(1)}" y="${Z}" text-anchor="middle"><tspan class="ta__n">${L+1}</tspan>${m(re.slice(String(L+1).length))}</text>
      </g>`}).join("")})(),ce=`The reviewer's tone across ${G(v)}, smoothed over a minute. `+(n.length?`${n.length} turning point${n.length>1?"s":""} are marked. `:"")+(s.length?`${s.length} flagged moment${s.length>1?"s":""} are ticked on the time axis.`:"");return`<svg class="ta${a?" ta--compact":""}" viewBox="0 0 ${o} ${i}" role="img"
      aria-label="${m(ce)}">
    <defs>
      <clipPath id="${W}"><rect x="0" y="0" width="${o}" height="${S}"/></clipPath>
      <clipPath id="${oe}"><rect x="0" y="${S}" width="${o}" height="${i-S}"/></clipPath>
      ${lt($e,"ta__hatch")}
    </defs>
    ${xe}
    ${a?"":`<text class="ta__axis" x="${d-10}" y="${u+4}" text-anchor="end">positive</text>
      <text class="ta__axis" x="${d-10}" y="${g+4}" text-anchor="end">negative</text>`}
    <line class="ta__zero" x1="${d}" y1="${S}" x2="${h}" y2="${S}"/>
    <path class="ta__pos" d="${de}" clip-path="url(#${W})" data-fade/>
    <path class="ta__neg" d="${de}" clip-path="url(#${oe})" fill="url(#${$e})" data-fade/>
    <path class="ta__line" d="${J}" data-draw/>
    ${ve}${Te}
  </svg>`}function pt(e){const n=e.filter(l=>l.reviewer&&l.reviewer.claims);if(!n.length)return"";const s=l=>Object.values(l.reviewer.seconds).reduce((a,o)=>a+o,0),c=Math.max(...n.map(s),1);return`<ol class="tb" role="list">${n.map(l=>{const a=l.reviewer.seconds,o=s(l),i=d=>a[d]>0?`<i class="tb__seg tb__seg--${it[d]}" style="width:${(a[d]/o*100).toFixed(2)}%"></i>`:"";return`<li class="tb__row">
      <span class="tb__name">${m(l.name)}</span>
      <span class="tb__track"><span class="tb__bar" style="width:${(o/c*100).toFixed(2)}%" data-grow
        role="img" aria-label="${m(`${l.name}: ${G(o)} of talk, ${G(a.POSITIVE)} read positive, ${G(a.NEUTRAL)} neutral, ${G(a.NEGATIVE)} negative`)}">
        ${i("POSITIVE")}${i("NEUTRAL")}${i("NEGATIVE")}</span></span>
      <span class="tb__n t-read">${G(o)}</span>
    </li>`}).join("")}</ol>`}function ut(e){const n=e.filter(c=>c.audience&&c.audience.comments);if(!n.length)return"";const s=Math.max(1,...n.flatMap(c=>[c.audience.counts.POSITIVE,c.audience.counts.NEGATIVE]));return`<ol class="th" role="list">${n.map(c=>{const l=c.audience.counts;return`<li class="th__row">
      <span class="th__name">${m(c.name)}</span>
      <span class="th__neg"><i style="width:${(l.NEGATIVE/s*100).toFixed(2)}%" data-grow-left></i>
        <b class="t-read">${l.NEGATIVE||""}</b></span>
      <span class="th__pos"><i style="width:${(l.POSITIVE/s*100).toFixed(2)}%" data-grow></i>
        <b class="t-read">${l.POSITIVE||""}</b></span>
      <span class="th__neu">${l.NEUTRAL?`${l.NEUTRAL} neutral`:""}</span>
      <span class="sr-only">${m(`${c.name}: ${l.POSITIVE} positive, ${l.NEUTRAL} neutral, ${l.NEGATIVE} negative comments`)}</span>
    </li>`}).join("")}</ol>`}function ft(e){const n=e.filter(o=>o.reviewer&&ae(o.reviewer.lean)||o.audience&&ae(o.audience.lean));if(!n.length)return"";const s=240,c=10,l=230,a=o=>c+(ge(o,-1,1)+1)/2*(l-c);return`<ol class="db" role="list">${n.map(o=>{const i=o.reviewer&&ae(o.reviewer.lean)?o.reviewer.lean:null,d=o.audience&&ae(o.audience.lean)?o.audience.lean:null,h=o.agreement&&o.agreement.call,u=i==null?"no claims from the reviewer":d==null?"no comments on it":h==="reviewer_warmer"?"reviewer warmer":h==="audience_warmer"?"audience warmer":"no clear difference";return`<li class="db__row">
      <span class="db__name">${m(o.name)}</span>
      <svg class="db__svg" viewBox="0 0 ${s} 22" aria-hidden="true">
        <line class="db__axis" x1="${c}" y1="11" x2="${l}" y2="11"/>
        <line class="db__zero" x1="${(c+l)/2}" y1="4" x2="${(c+l)/2}" y2="18"/>
        ${i!=null&&d!=null?`<line class="db__gap" x1="${a(i).toFixed(1)}" y1="11" x2="${a(d).toFixed(1)}" y2="11"/>`:""}
        ${i!=null?`<circle class="db__r" cx="${a(i).toFixed(1)}" cy="11" r="5" data-pop/>`:""}
        ${d!=null?`<rect class="db__a" x="${(a(d)-4.5).toFixed(1)}" y="6.5" width="9" height="9" data-pop/>`:""}
      </svg>
      <span class="db__note">${u}</span>
      <span class="sr-only">${m(`${o.name}: reviewer ${i==null?"no claims":se(i)}, audience ${d==null?"no comments":se(d)}, ${u}.`)}</span>
    </li>`}).join("")}</ol>`}function qt(e){if(!e||le()||e.dataset.drawn==="yes")return;e.dataset.drawn="yes";const n="power2.out";for(const i of e.querySelectorAll("[data-draw]")){if(typeof i.getTotalLength!="function")continue;const d=i.getTotalLength();d&&me.fromTo(i,{strokeDasharray:d,strokeDashoffset:d},{strokeDashoffset:0,duration:1.1,ease:n,clearProps:"strokeDasharray,strokeDashoffset"})}const s=e.querySelectorAll("[data-grow]");s.length&&me.from(s,{scaleX:0,transformOrigin:"0% 50%",duration:.7,ease:n,stagger:.035,clearProps:"transform"});const c=e.querySelectorAll("[data-grow-left]");c.length&&me.from(c,{scaleX:0,transformOrigin:"100% 50%",duration:.7,ease:n,stagger:.035,clearProps:"transform"});const l=e.querySelectorAll("[data-grow-c]");l.length&&me.from(l,{scaleX:0,transformOrigin:"50% 50%",duration:.6,ease:n,delay:.25,clearProps:"transform"});const a=e.querySelectorAll("[data-pop]");a.length&&me.from(a,{scale:0,transformOrigin:"50% 50%",duration:.45,ease:"back.out(1.6)",stagger:a.length>20?{amount:.6}:.03,delay:.2,clearProps:"transform"});const o=e.querySelectorAll("[data-fade]");o.length&&me.from(o,{opacity:0,duration:.9,ease:n,delay:.3,clearProps:"opacity"})}function Ae(e,n){const s=String(e||"").split(/\s+/).filter(Boolean);return s.length>n?`${s.slice(0,n).join(" ")}…`:s.join(" ")}const mt=[["transcript","words"],["facial","face"],["vocal","voice"],["comment","comments"]];function gt(e){const n=e||{},s=i=>i.length<=1?i.join(""):`${i.slice(0,-1).join(", ")} and ${i[i.length-1]}`,c=new Map,l=[];for(const[i,d]of mt){if(!n[i]){l.push(d);continue}const h=String(n[i]).toLowerCase();c.has(h)||c.set(h,[]),c.get(h).push(d)}const a=[...c.entries()].map(([i,d],h)=>h===0?`the ${s(d)} read ${i}`:`the ${s(d)} ${i}`);let o="";if(a.length===1){const[[i,d]]=[...c.entries()];o=d.length===1?`Only the ${d[0]} could be read: ${i}.`:`The ${s(d)} all read ${i}.`}else a.length===2?o=`${a[0]}, and ${a[1]}.`:a.length>2&&(o=`${a.slice(0,-1).join(", ")} and ${a[a.length-1]}.`);return o=o.charAt(0).toUpperCase()+o.slice(1),a.length?l.length?`${o} The ${s(l)} could not be read.`:o:"No channel could be read at this moment."}const De={well_covered:"Plenty of evidence behind this reading.",partly_covered:"Some of the evidence behind this reading is thin.",thinly_covered:"The evidence behind this reading is thin.",unknown:"How much evidence is behind this reading is unknown."},We={present:"The creator declared a paid promotion.",absent:"No paid promotion was declared.",not_checked:"Whether a paid promotion was declared could not be checked."};function Tt(e){const n=e&&e.facts;if(!n)return"";const s=n.confidence&&n.confidence.level,c=Number(n.flagged)||0,l=c?`${ne(c)} of ${ne(n.segments)} segments ${c===1?"was":"were"} flagged for strong disagreement.`:"No segment was flagged for strong disagreement.",a=(n.signs&&n.signs.signs||[]).find(i=>i.id==="S1"),o=We[a&&a.state]||We.not_checked;return`${De[s]||De.unknown} ${l} ${o} It cannot say whether the reviewer is honest.`}function Et(e){return e?`<div class="ti__short" role="note"><p class="ti__shk">In short</p>
    <p class="ti__shp">${m(e)}</p></div>`:""}const qe={well_covered:{word:"Well covered",dots:3},partly_covered:{word:"Partly covered",dots:2},thinly_covered:{word:"Thinly covered",dots:1},unknown:{word:"Coverage unknown",dots:0}};function z(e,n){const s=(e||[]).map(c=>{const l=c[0],a=Number(c.slice(1));return l==="S"&&n.segment(a)?`<button class="ev" type="button" data-ev="${c}"
        aria-label="${G(n.segment(a).start_s)}, open this moment">${G(n.segment(a).start_s)}</button>`:l==="C"&&n.comment(a)?`<button class="ev ev--c" type="button" data-ev="${c}"
        aria-label="comment ${a+1}, read it">comment ${a+1}</button>`:l==="T"&&n.topic(c)?`<button class="ev ev--t" type="button" data-ev="${c}">${m(n.topic(c).name)}</button>`:""}).filter(Boolean);return s.length?`<span class="evs">${s.join("")}</span>`:""}function Ge(e){return e&&e.source==="template"?`<span class="src src--code" title="The fact checks set the model's sentence aside, so this one was built from the figures by code.">from the figures</span>`:e&&e.source==="code"?'<span class="src src--code" title="Written by code from the figures, by design: these are counts, and code states counts exactly.">from the figures</span>':""}function be(e,n){return`<div class="ny" role="note">
    <p class="ny__h">${m(e)}</p>
    <p class="ny__p">Written by the local model at the end of a run. It has not been run
      for this report yet; everything on this page that is a figure is already here.</p>
    ${n?`<p class="ny__cmd"><code>${m(n)}</code></p>`:""}
  </div>`}function Pt(e,n){const s=qe[e]||qe.unknown;return`<a class="lvl" href="${n}" data-lvl="${m(e||"unknown")}" data-cx-goto-trust>
    <span class="lvl__dots" aria-hidden="true">${[1,2,3].map(c=>`<i${c<=s.dots?" data-on":""}></i>`).join("")}</span>
    <span>${s.word}</span></a>`}function Ct(e,n,s){const c=e&&e.written&&e.written.verdict;return c&&c.source==="model"?`<p class="vd">${m(c.text)}</p>${z(c.evidence,n)}`:`<p class="vd vd--code">${s}</p>
    <p class="vd__src">${e&&e.written?"Written by code from the figures: the fact checks set the local model's own summary aside.":"Summarised from the figures. The written report has not been run for this video."}</p>`}function Ft(e,n,s){const c=e&&e.written,l=c&&c.takeaways||[],a=c&&(e.verifier&&e.verifier.by_field&&e.verifier.by_field.takeaway||{}).dropped||0;return`<section class="tk" aria-labelledby="tk-h">
    <h2 id="tk-h" class="cx-h">What to take from it</h2>
    ${c?l.length?`
    <ol class="tk__list">${l.map((o,i)=>`
      <li class="tk__item"><span class="tk__n" aria-hidden="true">${i+1}</span>
        <div><p class="tk__text">${m(o.text)}</p>${z(o.evidence,n)}</div></li>`).join("")}
    </ol>`:`<p class="cx-note">None of the model's takeaways passed the checks, so none is printed.</p>`:be("Three takeaways for the brand",s)}
    ${c&&a?`<p class="cx-note tk__dropped">${a} further ${a===1?"takeaway was":"takeaways were"} written and
      dropped because ${a===1?"it":"they"} did not hold up against the run.</p>`:""}
    <p class="cx-note">Written by the local model from the figures in this book; every sentence
      cites where it comes from, and was checked against the run before it was kept.</p>
  </section>`}function Lt(e,n){const s=e.facts,c=e.written,l=s.agreement.call,a={reviewer_warmer:"The reviewer is warmer than the audience",audience_warmer:"The audience is warmer than the reviewer",no_clear_difference:"No clear difference between reviewer and audience",unknown:"Reviewer and audience cannot be compared"}[l]||"Reviewer and audience",o=(i,d)=>i?`
    <div class="ag__part"><p class="ag__k">${d}</p>
      <p class="ag__words">${m(i.text)} ${Ge(i)}</p>${z(i.evidence,n)}</div>`:"";return`<section class="ag" aria-labelledby="ag-h">
    <h2 id="ag-h" class="cx-h">${a}</h2>
    <figure class="ag__fig">${dt(s)}
      <figcaption class="cx-note">Each mark is a lean from all negative (&minus;1) to all positive
        (+1), with its 95% interval. The reviewer is read from the words (transcript model, tested
        at ${s.confidence.accuracy.transcript??"an unrecorded"}%), the audience from the comments
        (comment model, ${s.confidence.accuracy.comment??"unrecorded"}%). One side is called warmer only
        when the interval of the gap between them excludes zero.</figcaption></figure>
    ${c?`${o(c.agreement_words,"Do they agree?")}${o(c.brand_health_words,"Brand health, in words")}`:`<p class="ag__words">${m($t(s))}</p>
        <div class="ag__part"><p class="ag__k">Brand health, in figures</p>
          <p class="ag__words">Of ${ne(s.audience.n)} comments, ${ne(s.audience.counts.POSITIVE)} read
            positive, ${ne(s.audience.counts.NEUTRAL)} neutral and ${ne(s.audience.counts.NEGATIVE)}
            negative. The written report puts this into words once it has been run.</p></div>`}
  </section>`}function $t(e){return{reviewer_warmer:"The reviewer is measurably warmer than the audience.",audience_warmer:"The audience is measurably warmer than the reviewer.",no_clear_difference:"There is no clear difference between the reviewer and the audience."}[e.agreement.call]||"The two cannot be compared on this report."}function Mt(e,n,s){const c=e.facts,l={};for(const i of e.written&&e.written.turn_labels||[])l[i.seg]=i.label;const a=(n.all_segments||[]).filter(i=>i.flagged),o=c.tone.turns;return`<section class="tn" aria-labelledby="tn-h">
    <div class="tn__head">
      <h2 id="tn-h" class="cx-h">How the tone moved</h2>
      <p class="cx-lede">How positive the reviewer's words read, moment by moment, smoothed over a
        minute: solid above the line, hatched below it. ${a.length?`The pink ticks are the ${a.length===1?"moment":`${a.length} moments`} the controller flagged.`:""}</p>
    </div>
    <figure class="tn__fig">${ht({points:c.tone.points,turns:o,flagged:a,duration:c.duration_s,labels:l})}</figure>
    ${o.length?`<ol class="tn__turns">${o.map((i,d)=>`
      <li><span class="tn__n">${d+1}</span>
        <span class="tn__what">${l[i.seg]?m(l[i.seg]):i.kind==="peak"?"Peak":"Dip"}</span>
        ${z([`S${i.seg}`],s)}</li>`).join("")}</ol>`:`<p class="cx-note">The tone never turned by enough to mark: no peak or dip stood more than
        ${.2.toFixed(1)} above its surroundings.</p>`}
  </section>`}function Rt(e,n){const s=e.reading&&e.reading.topics||[];return`<section class="tt" aria-labelledby="tt-h">
    <h2 id="tt-h" class="cx-h">Where the time went</h2>
    ${e.reading?`
    <p class="cx-lede">The reviewer's claims, grouped into topics, and the time spent on each.
      Each bar is split by how the transcript model read those seconds.</p>
    ${pt(s)||'<p class="cx-note">The local model found no claims about the product to group.</p>'}
    <p class="tt__key" aria-hidden="true"><i class="k k--pos"></i>positive <i class="k k--neu"></i>neutral
      <i class="k k--neg"></i>negative</p>`:be("The topics the video covered",n)}
  </section>`}function It(e,n){const s=e.reading&&e.reading.topics||[];return`<section class="tv" aria-labelledby="tv-h">
    <h2 id="tv-h" class="cx-h">Reviewer and audience, topic by topic</h2>
    ${e.reading?`
    <p class="cx-lede">For each topic, how the reviewer's words about it read
      <i class="k k--r" aria-hidden="true"></i> against how the comments about it read
      <i class="k k--a" aria-hidden="true"></i>, on one scale from all negative to all positive.</p>
    ${ft(s)||'<p class="cx-note">No topic had readings from either side.</p>'}
    <p class="cx-note"><b>&ldquo;No clear difference&rdquo; does not mean the two sides agree.</b>
      It means there were too few comments on that topic to be sure they differ, even where the
      two marks look far apart. Topics and which comments belong to them are the local model's
      grouping; how each side reads is the two benched classifiers'.</p>`:be("The reviewer and the audience on each topic",n)}
  </section>`}function Nt(e,n){const s=e.reading&&e.reading.claims||[],c=a=>(n.topic(a)||{}).name||"",l=(a,o,i)=>{const d=s.filter(u=>a.includes(u.stance));if(!d.length)return[];const h=document.createElement("li");return h.className="cl__head",h.innerHTML=`<h3 class="cx-h3">${o}</h3><p class="cx-note">${i}</p>`,[h,...d.map(u=>{const g=document.createElement("li");return g.className="cl",g.dataset.stance=u.stance,g.innerHTML=`
        <p class="cl__meta">${c(u.topic)?`<span class="cl__topic">${m(c(u.topic))}</span>`:""}
          ${z([`S${u.seg}`],n)}</p>
        <p class="cl__claim">${m(u.claim)}</p>
        <blockquote class="cl__quote">&ldquo;${m(u.quote)}&rdquo;</blockquote>`,g})]};return[...l(["praise"],"What the reviewer liked","In their own words, in the order they said them."),...l(["criticism"],"What they did not like","The same, for the criticisms."),...l(["mixed","neutral"],"Mixed or neutral","Claims that were neither clearly for nor against.")]}function Bt(e,n,s){const c=(e.reading&&e.reading.topics||[]).filter(a=>a.audience.comments),l=e.written;return`<section class="tl" aria-labelledby="tl-h">
    <h2 id="tl-h" class="cx-h">How people talk about it</h2>
    ${l&&l.audience_words?`<p class="tl__words">${m(l.audience_words.text)} ${Ge(l.audience_words)}</p>
      ${z(l.audience_words.evidence,n)}`:""}
    ${e.reading?`
    ${ut(c)||'<p class="cx-note">No comment was about anything the model could name.</p>'}
    <p class="tt__key" aria-hidden="true"><span class="th__keyl">complaints</span><span class="th__keyr">praise</span></p>
    <p class="cx-note">Which comments belong to which topic is the local model's reading; whether each
      is positive or negative is the benched comment model's (tested at
      ${e.facts.confidence.accuracy.comment??"an unrecorded"}% on unseen videos).</p>`:be("What the comments talk about",s)}
  </section>`}function Ot(e,n,s){const c=(e.reading&&e.reading.questions||[]).slice(0,3),l=new Set(c.map(o=>o.i)),a=[];for(const o of e.reading&&e.reading.topics||[]){const i=o.audience.examples.find(d=>!l.has(d.i));if(!(!i||o.name.toLowerCase()==="other")&&(l.add(i.i),a.push({topic:o.name,ex:i}),a.length===2))break}return`<section class="ak" aria-labelledby="ak-h">
    <h2 id="ak-h" class="cx-h">What they ask, and in their words</h2>
    ${e.reading?`
    ${c.length?`<ul class="ak__qs">${c.map(o=>`
      <li><p class="ak__q">&ldquo;${m(Ae(o.quote,26))}&rdquo;</p>${z([`C${o.i}`],n)}</li>`).join("")}</ul>`:'<p class="cx-note">Nobody asked a question in the comments that were read.</p>'}
    <div class="ak__voices">${a.map(o=>`
      <figure class="ak__voice"><figcaption class="cl__topic">${m(o.topic)}</figcaption>
        <blockquote>&ldquo;${m(Ae(o.ex.quote,30))}&rdquo;</blockquote>
        ${z([`C${o.ex.i}`],n)}</figure>`).join("")}</div>
    <p class="cx-note">Usernames and links are removed before any comment is quoted.</p>`:be("The questions and voices of the audience",s)}
  </section>`}const xt=`<span class="src src--code" title="Built by code from the four readings above; the local model's own note was set aside by the fact checks or has not been written.">from the readings</span>`;function jt(e,n,s,c,l){const a=e.facts.moments,o={};for(const h of e.written&&e.written.moment_notes||[])o[h.seg]=h.text;const i={transcript:"words",facial:"face",vocal:"voice",comment:"comments"},d=h=>{const u=c(h),g=["transcript","facial","vocal","comment"].map(A=>{const v=h.valences[A];return`<li data-v="${v?m(v.toLowerCase()):"none"}"><span class="om__ch">${i[A]}</span>
        <span class="om__v">${v?m(v.toLowerCase()):"no reading"}</span></li>`}).join(""),S=h.text.split(/\s+/).slice(0,32).join(" ");return`<article class="om" aria-label="${m(`The moment at ${h.time}`)}">
      <div class="om__frame">${u?`<img src="${u}" alt="" loading="lazy" decoding="async">`:'<span class="om__none">No frame for this second</span>'}</div>
      <p class="om__when"><span class="t-time">${m(h.time)}</span>
        <span class="om__c${h.flagged?" is-flagged":""}">conflict ${at(h.conflict)}${h.flagged?", flagged":""}${h.damped?", down-weighted":""}</span></p>
      <blockquote class="om__said">&ldquo;${m(S)}${S.length<h.text.length?"…":""}&rdquo;</blockquote>
      <ul class="om__reads">${g}</ul>
      ${o[h.seg]?`<p class="om__note">${m(o[h.seg])}</p>`:`<p class="om__note">${m(gt(h.valences))} ${xt}</p>`}
      <button class="cx-btn" type="button" data-ev="S${h.seg}">Open this moment</button>
    </article>`};return`<section class="omx" aria-labelledby="om-h">
    <div class="omx__head">
      <h2 id="om-h" class="cx-h">The moments that do not add up</h2>
      <p class="cx-lede">The ${a.length===1?"moment":`${a.length} moments`} where the four readings disagreed most,
        highest first: what was said, what each channel read, and why they do not match.</p>
    </div>
    ${a.length?`<div class="omx__grid">${a.map(d).join("")}</div>`:`<p class="cx-text">No moment of this video scored any conflict: all four readings agreed
        wherever they could be read.</p>`}
  </section>`}function Ht(e){const n=e.facts.confidence,s=qe[n.level]||qe.unknown,c=a=>a.unit==="comments"?ne(a.value):a.value==null?"no conflict":Pe(a.value*100,0),l=a=>a.target==null?"no floor recorded":a.id==="comments"?`at least ${ne(a.target)}`:a.id==="transcript"?`at least ${Pe(a.target*100,0)} of segments`:`no more than ${Pe(a.target*100,0)}`;return`<section class="tr" aria-labelledby="tr-h">
    <h2 id="tr-h" class="cx-h">How far to trust this reading</h2>
    <div class="tr__level" data-lvl="${m(n.level)}">
      <span class="lvl__dots lvl__dots--big" aria-hidden="true">${[1,2,3].map(a=>`<i${a<=s.dots?" data-on":""}></i>`).join("")}</span>
      <p class="tr__word">${s.word}</p>
    </div>
    <p class="cx-text">${m(n.means_not)}</p>
    <table class="tr__checks">
      <thead><tr><th scope="col">Check</th><th scope="col">This video</th><th scope="col">Needs</th><th scope="col"><span class="sr-only">Result</span></th></tr></thead>
      <tbody>${n.checks.map(a=>`
        <tr data-pass="${a.passed===!0?"yes":a.passed===!1?"no":"unknown"}">
          <th scope="row">${m(a.label)}</th><td class="t-read">${c(a)}</td><td>${l(a)}</td>
          <td class="tr__res">${a.passed===!0?"met":a.passed===!1?"not met":"unknown"}</td></tr>`).join("")}
      </tbody></table>
    <div class="tr__ceiling"><p class="ag__k">What no report here can promise</p>
      <p class="cx-note">${m(n.ceiling.text)}</p></div>
  </section>`}const _t={present:"Present",absent:"Absent",not_checked:"Not checked"};function Dt(e,n){const s=e.facts.signs,c=e.video_meta||{},l=o=>{const i=o.evidence||{};if(o.id==="S1"){const d=[];i.label===!0&&d.push("The creator ticked YouTube's &ldquo;includes paid promotion&rdquo; box."),i.label===!1&&d.push("YouTube's paid-promotion box is not ticked; creators set it themselves and it is off by default.");for(const h of(i.description||[]).slice(0,2))d.push(`Description: &ldquo;${m(Ae(h.context,14))}&rdquo;`);return d.join(" ")}if(o.id==="S2")return(i.speech||[]).slice(0,3).map(d=>`&ldquo;${m(d.match)}&rdquo; ${z([`S${d.seg}`],n)}`).join(" ")+((i.speech||[]).length>3?` and ${i.speech.length-3} more`:"");if(o.id==="S3")return(i.description||[]).slice(0,2).map(d=>`&ldquo;${m(Ae(d.context,14))}&rdquo;`).join(" ");if(o.id==="S4"){const d=i.agreement||{};return d.gap==null?"":`Gap ${se(d.gap)}, 95% interval ${se(d.low)} to ${se(d.high)}.`}if(o.id==="S5"){const d=[...new Set([...i.positive_flagged||[],...i.controller_flag||[]])];return d.length?z(d.map(h=>`S${h}`),n):""}return""},a=c.fetched===!1&&c.error?`<p class="cx-note">Signs 1 and 3 need the video's own details from YouTube, which were not
        available for this report (${m(c.error)}).</p>`:c.fetched?"":`<p class="cx-note">Signs 1 and 3 need the video's own details from YouTube, which are
          fetched when the written report is run.</p>`;return`<section class="sg" aria-labelledby="sg-h">
    <h2 id="sg-h" class="cx-h">Could this be paid?</h2>
    <p class="sg__sum"><span class="t-read">${s.present}</span> of ${s.checked} checked
      ${s.checked===1?"sign is":"signs are"} present</p>
    <ol class="sg__list">${s.signs.map(o=>`
      <li class="sg__row" data-state="${o.state}">
        <span class="sg__mark" aria-hidden="true"></span>
        <div class="sg__body">
          <p class="sg__name">${m(o.name)} <span class="sg__kind">${o.kind==="fact"?"fact":"inference"}</span></p>
          <p class="sg__state">${_t[o.state]}</p>
          ${o.state==="present"?`<p class="sg__ev">${l(o)}</p>`:o.id==="S1"&&o.state==="absent"?`<p class="sg__ev">${l(o)}</p>`:""}
        </div></li>`).join("")}
    </ol>
    <p class="sg__disc">${m(s.disclaimer)}</p>
    ${a}
  </section>`}const Ve=720,ke=8,wt=.38,Ke=.38,yt=260,ze="(min-width: 1100px)",ye=()=>document.documentElement.dataset.read==="page",we=()=>!ye()&&window.matchMedia(ze).matches,X=(e,n)=>{const s=document.createElement(e);return n&&(s.className=n),s},Fe=e=>`<svg class="cx-arrow" viewBox="0 0 16 11" width="15" height="11"
  aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4"
  style="transform:rotate(${e==="prev"?180:0}deg)"><path d="M0 5.5H14.6M10.3 1.2 14.9 5.5 10.3 9.8"/></svg>`;function Wt({key:e,verso:n="",recto:s="",wide:c=!1,plain:l=[],cont:a=!1}){const o=(d,h)=>`
    <div class="cx__page cx__page--${d}${l.includes(d)?" is-plain":""}" data-cx-page>
      <p class="cx__run" data-cx-run aria-hidden="true"></p>
      <div class="cx__body">${h}</div>
      <p class="cx__folio" data-cx-folio aria-hidden="true"></p>
    </div>`,i=`data-cx-spread data-cx-key="${e}" tabindex="-1"${a?" data-cx-cont":""}`;return c?`<div class="cx__spread" ${i} data-wide>
      <div class="cx__pages">${o("fold",n)}</div></div>`:`<div class="cx__spread" ${i}>
    <div class="cx__pages">${o("verso",n)}${o("recto",s)}</div></div>`}function Vt(e){const n=String(e||"").length;return n>30?"l":n>14?"m":"s"}function Kt({id:e,label:n,spreads:s}){return`<section class="cx__chapter" data-cx-chapter="${e}" data-cx-label="${n}"
    aria-label="${n}">${s.join("")}</section>`}function Ut({title:e,chapters:n,backHref:s,backLabel:c}){const l=n.map((a,o)=>`
    <li><a class="cx__ch" href="#${a.id}" data-cx-goto="${a.id}">
      <span class="cx__chn">${o+1}</span><span class="cx__chl">${a.label}</span></a></li>`).join("");return`<div class="cx" data-cx>
    <div class="cx__bar">
      <a class="cx__close" href="${s}" data-cx-close>${Fe("prev")}<span>${c}</span></a>
      <nav class="cx__toc" aria-label="Chapters of ${e}"><ol>${l}</ol></nav>
      ${ye()?`<a class="cx__mode" href="${location.pathname}">Read as a book</a>`:`<a class="cx__mode" href="${location.pathname}?read=page">Read as one page</a>`}
      <p class="cx__where" data-cx-where aria-live="polite"></p>
    </div>
    <div class="cx__stage">
      <button class="cx__turnbtn cx__turnbtn--prev" type="button" data-cx-prev>
        ${Fe("prev")}<span>Previous</span></button>
      <div class="cx__book" data-cx-book>${n.map(a=>a.html).join("")}</div>
      <button class="cx__turnbtn cx__turnbtn--next" type="button" data-cx-next>
        ${Fe("next")}<span>Next</span></button>
    </div>
  </div>`}function Xt(e,n={}){const s=e.querySelector("[data-cx-book]");if(!s)return null;const c=e.querySelector(".cx__bar"),l=e.querySelector("[data-cx-prev]"),a=e.querySelector("[data-cx-next]"),o=e.querySelector("[data-cx-where]"),i=[...e.querySelectorAll("[data-cx-goto]")],d=n.title||"";let h=[],u=0,g=we(),S=0,A=null,v=0;const k=[];let P=decodeURIComponent(location.hash.replace(/^#/,""))||null;const Y=e.querySelector("[data-cx]"),j=document.querySelector("[data-footer]");function J(){if(!Y)return;if(!g){Y.style.removeProperty("--cx-h");return}const t=getComputedStyle(s),r=parseFloat(t.paddingTop)||0,p=parseFloat(t.paddingBottom)||0,f=s.getBoundingClientRect(),x=f.top+window.scrollY+r,q=e.getBoundingClientRect().bottom-f.bottom,T=j?j.getBoundingClientRect().height:0,w=parseFloat(getComputedStyle(document.documentElement).fontSize)||16,y=window.innerHeight-x-p-q-T;Y.style.setProperty("--cx-h",`${Math.floor(Math.min(58*w,Math.max(30*w,y)))}px`)}J();const de=()=>[...s.querySelectorAll("[data-cx-chapter]")],W=t=>t.closest("[data-cx-chapter]"),oe=t=>t.hasAttribute("data-wide"),$e=t=>[...t.querySelectorAll(":scope > .cx__pages > [data-cx-page]")];function xe(t,r,p){const f=$e(t);if(oe(t)){const x=t.querySelector(".cx__pages").getBoundingClientRect().width||2*p;return{page:f[0],width:x,shift:r==="l"?0:p-x}}return{page:r==="l"?f[0]:f[1],width:p,shift:0}}function ve(){h=[...s.querySelectorAll("[data-cx-spread]")];let t=0;for(const r of h){const p=W(r).dataset.cxLabel,f=$e(r);if(oe(r)){t+=2,r.dataset.cxPages=`${t-1} and ${t}`,f[0].dataset.cxFolio=String(t-1),f[0].querySelector("[data-cx-run]").textContent=`${d}, ${p}`,f[0].querySelector("[data-cx-folio]").textContent=`${t-1} and ${t}, folded out`;continue}f.forEach((x,q)=>{t+=1,x.dataset.cxFolio=String(t),x.querySelector("[data-cx-run]").textContent=q===0?d:p,x.querySelector("[data-cx-folio]").textContent=String(t)}),r.dataset.cxPages=`${t-1} and ${t}`}S=t;for(const r of e.querySelectorAll("[data-cx-xref]")){const p=s.querySelector(`#${CSS.escape(r.dataset.cxXref)}`),f=p&&p.closest("[data-cx-page]"),x=r.querySelector("[data-cx-xref-page]");x&&(x.textContent=f&&f.dataset.cxFolio?f.dataset.cxFolio:"")}}function Te(){const t=h[u],r=W(t),p=[...r.querySelectorAll("[data-cx-spread]")],f=r.dataset.cxLabel;if(!g){const q=p[0].dataset.cxPages.split(" and ")[0],T=p[p.length-1].dataset.cxPages.split(" and ")[1];return`${f}, pages ${q} to ${T} of ${S}`}const x=p.length>1?`, spread ${p.indexOf(t)+1} of ${p.length}`:"";return oe(t)?`${f}${x}, pages ${t.dataset.cxPages} of ${S}, folded out`:`${f}${x}, pages ${t.dataset.cxPages} of ${S}`}function ce(){const t=h[u],r=W(t),p=ye();for(const $ of de())$.hidden=!p&&$!==r;for(const $ of h)$.hidden=!p&&(g?$!==t:W($)!==r);const f=r.dataset.cxChapter;for(const $ of i)$.dataset.cxGoto===f?$.setAttribute("aria-current","true"):$.removeAttribute("aria-current");const x=de(),q=x.indexOf(r),T=g?u===0:q===0,w=g?u===h.length-1:q===x.length-1,y=$=>g?M($):x[$]&&x[$].dataset.cxLabel;l.disabled=T,a.disabled=w,l.setAttribute("aria-label",T?"Previous, this is the start of the book":`Previous, ${y(g?u-1:q-1)}`),a.setAttribute("aria-label",w?"Next, this is the end of the book":`Next, ${y(g?u+1:q+1)}`),o.textContent=p?`${x.length} chapters, ${S} pages, on one page`:Te(),e.dataset.cxMode=oe(t)?"fold":"spread";const C=t.dataset.cxKey;if(p){_(),n.onSpread&&n.onSpread(t,r);return}const F=P?`${location.pathname}${location.search}#${P}`:u===0?`${location.pathname}${location.search}`:`${location.pathname}${location.search}#${C}`;try{history.replaceState(history.state,"",F)}catch{}_(),n.onSpread&&n.onSpread(t,r)}function _(){for(const t of s.querySelectorAll("[data-cx-spread]:not([hidden]) .cx__body")){const r=t.closest("[data-cx-page]");t.scrollHeight-t.clientHeight>2?(t.tabIndex=0,t.setAttribute("role","region"),t.setAttribute("aria-label",`Page ${r?r.dataset.cxFolio:""}, which scrolls`)):t.hasAttribute("tabindex")&&(t.removeAttribute("tabindex"),t.removeAttribute("role"),t.removeAttribute("aria-label"))}}const M=t=>{const r=h[t];return r?`${W(r).dataset.cxLabel}, pages ${r.dataset.cxPages}`:""};function V(){const t=document.activeElement;(!t||t===document.body||t.closest("[hidden]")||t instanceof HTMLButtonElement&&t.disabled)&&t!==document.body&&h[u].focus({preventScroll:!0})}function K(){const t=document.querySelector(".masthead"),r=t?t.getBoundingClientRect().bottom:0,p=c.getBoundingClientRect().top;(p<r-1||p>window.innerHeight*.5)&&window.scrollTo({top:window.scrollY+p-r,behavior:"instant"})}function H(t,{animate:r=!0}={}){P=null;const p=Math.max(0,Math.min(h.length-1,t));if(A&&A.finish(),p===u)return;const f=performance.now(),x=f-v<yt;v=f;const q=u,T=h[q],w=h[p];if(r&&!x&&g&&!le()&&!T.hidden){A=ee(q,p);return}u=p,ce(),K(),r&&!x&&B(w),V()}function B(t){typeof t.animate=="function"&&t.animate([{opacity:le()?.55:0},{opacity:1}],{duration:le()?140:220,easing:"ease-out"})}function L(t){if(g){H(u+t);return}const r=de(),p=r[r.indexOf(W(h[u]))+t];p&&H(h.indexOf(p.querySelector("[data-cx-spread]")))}function re(t){const r=s.querySelector(`[data-cx-chapter="${CSS.escape(t)}"]`);if(r){if(ye()){const p=r.querySelector("h1, h2");r.scrollIntoView({block:"start"}),p&&(p.setAttribute("tabindex","-1"),p.focus({preventScroll:!0}));return}H(h.indexOf(r.querySelector("[data-cx-spread]")))}}function ee(t,r){const p=r>t?"next":"prev",f=h[t],x=h[r];K();const T=f.querySelector(".cx__pages").getBoundingClientRect(),w=s.getBoundingClientRect(),y=T.width/2,C=p==="next"?"l":"r",F=p==="next"?"r":"l";let $=T.height;const E=X("div","cx__turn");E.setAttribute("aria-hidden","true"),E.style.left=`${T.left-w.left}px`,E.style.top=`${T.top-w.top}px`,E.style.width=`${T.width}px`;const R=bt(xe(f,C,y),y);R.classList.add("cx__still"),R.style.left=p==="next"?"0px":`${y}px`;const O=X("div","cx__cast cx__cast--under"),I=X("div","cx__cast cx__cast--over");O.dataset.side=p==="next"?"r":"l",I.dataset.side=p==="next"?"l":"r";const b=he(p,y,xe(f,F,y));b.root.style.left=p==="next"?`${y}px`:"0px",E.append(R,I,O,b.root);const N=pe=>{E.style.height=`${pe}px`;for(const ie of[R,b.root])ie.style.height=`${pe}px`;for(const ie of E.querySelectorAll(".cx__proxy"))ie.style.minHeight=`${pe}px`,ie.style.height=`${pe}px`};N($),s.appendChild(E),u=r,ce();const U=x.querySelector(".cx__pages").getBoundingClientRect();$=Math.max($,U.height),N($),Ue(E);const Ee=c.getBoundingClientRect().bottom,Ze=j?Math.min(window.innerHeight,j.getBoundingClientRect().top):window.innerHeight,Ie=Math.min(U.top-Ee,Ze-(U.top+$)),Je=Math.max(10,(Number.isFinite(Ie)?Ie:24)-6),et=Math.max(1800,y+$*y/(2*Je));E.style.perspective=`${et.toFixed(0)}px`,E.style.perspectiveOrigin=`${y}px ${$/2}px`;let _e=0,Ne=!1;const Se=()=>{Ne||(Ne=!0,cancelAnimationFrame(_e),clearTimeout(tt),E.remove(),A=null,V())},tt=setTimeout(Se,Ve+900);return _e=requestAnimationFrame(()=>{_e=requestAnimationFrame(()=>{b.fillBack(xe(x,C,y),$);const pe=performance.now(),ie=nt=>{const ue=Math.min(1,(nt-pe)/Ve);if(le()){Se();return}const Be=ue*ue*ue*(ue*(6*ue-15)+10);b.pose(Be);const fe=Math.PI*Be,Oe=y*Math.abs(Math.cos(fe)),je=Math.sin(fe);O.style.setProperty("--w",`${(fe<Math.PI/2?Oe*1.15:0).toFixed(1)}px`),O.style.setProperty("--o",(fe<Math.PI/2?je*.55:0).toFixed(3)),I.style.setProperty("--w",`${(fe>Math.PI/2?Oe*1.15:0).toFixed(1)}px`),I.style.setProperty("--o",(fe>Math.PI/2?je*.5:0).toFixed(3)),ue<1?_e=requestAnimationFrame(ie):Se()};_e=requestAnimationFrame(ie)})}),{finish:Se}}function he(t,r,p){const f=X("div","cx__leaf");f.dataset.dir=t,f.style.width=`${r}px`;const x=r/ke,q=[];let T=f;for(let w=0;w<ke;w+=1){const y=X("div","cx__strip");y.style.width=`${x}px`;const C=X("div","cx__face cx__face--front"),F=X("div","cx__face cx__face--back"),$=Le(p.page,p.width);$.style.left=`${p.shift-(t==="next"?w*x:r-(w+1)*x)}px`,C.append($,X("div","cx__sh")),F.append(X("div","cx__sh")),y.append(C,F),w===ke-1&&y.classList.add("is-edge"),T.appendChild(y),T=y,q.push({s:y,back:F})}return{root:f,fillBack(w,y){q.forEach(({back:C},F)=>{const $=Le(w.page,w.width);$.style.minHeight=`${y}px`,$.style.height=`${y}px`,$.style.left=`${w.shift-(t==="next"?r-(F+1)*x:F*x)}px`,C.insertBefore($,C.firstChild)}),Ue(f)},pose(w){const y=t==="next"?-1:1,C=Math.PI*w,F=wt*Math.sin(Math.PI*w),$=C+F,E=2*F/ke;f.style.transform=`rotateY(${(y*$*180/Math.PI).toFixed(2)}deg)`,q.forEach(({s:R},O)=>{O>0&&(R.style.transform=`rotateY(${(-y*E*180/Math.PI).toFixed(3)}deg)`);const I=Math.abs(Math.cos($-O*E)),b=Math.abs(Math.cos($-(O+1)*E));R.style.setProperty("--a1",((1-I)*Ke).toFixed(3)),R.style.setProperty("--a2",((1-b)*Ke).toFixed(3)),R.style.setProperty("--gl",(Math.sin(C)*I*I*.09).toFixed(3))})}}}function Q(t){const r=s.querySelector(`[data-cx-chapter="${CSS.escape(t.chapter)}"]`);if(!r)return;for(const b of r.querySelectorAll("[data-cx-cont]"))b.remove();const p=r.querySelector("[data-cx-flow]");if(!p)return;t.prepare&&t.prepare();for(const b of r.querySelectorAll("[data-cx-flow]"))b.replaceChildren();if(!g){p.append(...t.items),t.after&&t.after([p]);return}const f=r.hidden,x=[...r.querySelectorAll("[data-cx-spread]")].filter(b=>b.hidden);r.hidden=!1;for(const b of x)b.hidden=!1;r.classList.add("cx--measure");const q=8,T=b=>{const N=b.closest("[data-cx-page]"),U=N.querySelector("[data-cx-folio]"),Ee=parseFloat(getComputedStyle(N).rowGap)||0;return U.getBoundingClientRect().top-Ee-b.getBoundingClientRect().top-q},w=[...r.querySelectorAll("[data-cx-flow]")],y=w.map(T);p.append(...t.items);const C=parseFloat(getComputedStyle(p).rowGap)||0,F=t.items.map(b=>b.getBoundingClientRect().height);p.replaceChildren();let $=1;const E=()=>{$+=1,[...r.querySelectorAll("[data-cx-spread]")].pop().insertAdjacentHTML("afterend",t.cont($));const N=[...r.querySelectorAll("[data-cx-spread]")].pop();for(const U of N.querySelectorAll("[data-cx-flow]"))w.push(U),y.push(T(U))};let R=0,O=0,I=0;t.items.forEach((b,N)=>{const U=(I?C:0)+F[N];I&&O+U>y[R]+.5&&(R+=1,w[R]||E(),O=0,I=0),w[R].appendChild(b),O+=(I?C:0)+F[N],I+=1});for(let b=0;b<w.length;b+=1){const N=w[b];for(;N.childElementCount>1&&N.getBoundingClientRect().height>y[b]+.5;)w[b+1]||E(),w[b+1].insertBefore(N.lastElementChild,w[b+1].firstChild)}r.classList.remove("cx--measure"),r.hidden=f,t.after&&t.after(w)}function Z(t){k.push(t),D()}function D(){const t=h[u],r=t?W(t):null,p=t&&r?[...r.querySelectorAll("[data-cx-spread]")].indexOf(t):0;A&&A.finish();for(const f of k)Q(f);if(ve(),t&&t.isConnected)u=h.indexOf(t);else if(r){const f=[...r.querySelectorAll("[data-cx-spread]")];u=h.indexOf(f[Math.min(p,f.length-1)])}if(P){const f=h.findIndex(x=>x.dataset.cxKey===P);f>=0&&(u=f,P=null)}u<0&&(u=0),ce()}l.addEventListener("click",()=>L(-1)),a.addEventListener("click",()=>L(1));for(const t of i)t.addEventListener("click",r=>{r.metaKey||r.ctrlKey||r.shiftKey||r.button!==0||(r.preventDefault(),re(t.dataset.cxGoto))});e.addEventListener("click",t=>{const r=t.target.closest("[data-cx-xref]");if(!r)return;const p=s.querySelector(`#${CSS.escape(r.dataset.cxXref)}`),f=p&&p.closest("[data-cx-spread]");f&&(t.preventDefault(),H(h.indexOf(f)),p.setAttribute("tabindex","-1"),requestAnimationFrame(()=>p.focus({preventScroll:!0})))});const Qe=t=>{if(!t||!t.closest)return!1;const r=t.tagName;return r==="INPUT"||r==="TEXTAREA"||r==="SELECT"||t.isContentEditable||t.closest("[data-transport], [role=slider], [data-ledger], [role=grid], [role=tablist]")!==null};window.addEventListener("keydown",t=>{t.defaultPrevented||t.altKey||t.ctrlKey||t.metaKey||t.shiftKey||Qe(t.target)||ye()||(t.key==="ArrowRight"?(t.preventDefault(),L(1)):t.key==="ArrowLeft"&&(t.preventDefault(),L(-1)))}),window.addEventListener("hashchange",()=>{const t=decodeURIComponent(location.hash.replace(/^#/,"")),r=h.findIndex(p=>p.dataset.cxKey===t);r>=0&&H(r)}),window.matchMedia(ze).addEventListener("change",()=>{g=we(),J(),D()});let te=null;window.addEventListener("beforeprint",()=>{const t=document.documentElement;te={read:t.dataset.read||null,theme:st()},t.dataset.read="page",te.theme!=="field"&&He("field",{persist:!1}),g=we(),J(),ce()}),window.addEventListener("afterprint",()=>{if(!te)return;const t=document.documentElement;te.read?t.dataset.read=te.read:delete t.dataset.read,te.theme!=="field"&&He(te.theme,{persist:!1}),te=null,g=we(),J(),D()});let Me=`${window.innerWidth}x${window.innerHeight}`,Re=0;if(window.addEventListener("resize",()=>{A&&A.finish(),J(),clearTimeout(Re),Re=setTimeout(()=>{const t=`${window.innerWidth}x${window.innerHeight}`;t!==Me&&(Me=t,g&&k.length&&D())},220)}),document.fonts&&document.fonts.ready&&document.fonts.ready.then(()=>{J(),k.length&&D(),P=null}),ve(),P){const t=h.findIndex(r=>r.dataset.cxKey===P);t>=0&&(u=t,P=null)}return ce(),{go:H,step:L,goChapter:re,flow:Z,relayout:D,at:()=>u,current:()=>h[u],isWide:()=>g,reveal(t){const r=t&&t.closest("[data-cx-spread]");r&&H(h.indexOf(r))}}}function Ue(e){for(const n of e.querySelectorAll("[data-cx-scroll]")){const s=n.querySelector(".cx__body");s&&(s.scrollTop=Number(n.dataset.cxScroll)||0)}}function Le(e,n){const s=e.cloneNode(!0);s.classList.add("cx__proxy"),s.setAttribute("aria-hidden","true"),s.inert=!0,s.removeAttribute("data-cx-page");for(const o of s.querySelectorAll("[id]"))o.removeAttribute("id");s.style.width=`${n}px`;const c=e.querySelector(".cx__body");c&&c.scrollTop&&(s.dataset.cxScroll=String(c.scrollTop));const l=e.querySelectorAll("canvas"),a=s.querySelectorAll("canvas");return l.forEach((o,i)=>{const d=a[i];if(!(!d||!o.width||!o.height)){d.width=o.width,d.height=o.height;try{d.getContext("2d").drawImage(o,0,0)}catch{}}}),s}function bt({page:e,width:n,shift:s},c){const l=Le(e,n);if(!s&&n===c)return l;const a=X("div","cx__window");return a.style.width=`${c}px`,l.style.left=`${s}px`,a.appendChild(l),a}const Xe=.887/1.33;function Ye(e){const n=e.querySelector("[data-cx-spread]:not([hidden]) .cx__pages");if(!n)return null;const s=n.getBoundingClientRect(),c=document.querySelector(".masthead"),l=(c?c.getBoundingClientRect().bottom:0)+6,a=window.innerHeight-6,o=we(),i=o?s.left+s.width/2:s.left,d=o?s.width/2:s.width,h=Math.max(s.top,l),u=Math.max(160,Math.min(s.bottom,a)-h);let g=u*.9,S=g*Xe;S>d&&(S=d,g=S/Xe);const A={x:i,y:h+(u-g)/2,w:S,h:g},v=Math.max(12,Math.min(A.y-l,a-(A.y+g))),k=Math.max(1750,S+g*S/(2*v));return{to:A,P:k,origin:{x:i,y:A.y+g/2}}}function Gt(e,n){const s=n?Ye(e):null,c=()=>{const a=e.hasAttribute("data-opening");delete e.dataset.opening;const o=e.querySelector("[data-cx]");a&&o&&!le()&&o.animate([{opacity:0},{opacity:1}],{duration:460,easing:"cubic-bezier(.2,.7,.2,1)"})};if(!s)return c(),!1;const l=ct(document.body,{cover:n.cover,from:n.rect,to:s.to,perspective:s.P,origin:s.origin,onReveal:c});return l||c(),l}function zt(e,{link:n,cover:s,before:c}){if(!n)return;let l=!1;n.addEventListener("click",a=>{if(l){a.preventDefault();return}if(c&&c(),!s||le()||a.defaultPrevented||a.button!==0||a.metaKey||a.ctrlKey||a.shiftKey||a.altKey)return;const o=Ye(e);if(!o)return;a.preventDefault();const i=n.href;let d=!1;const h=()=>{d||(d=!0,window.location.assign(i))};setTimeout(h,1900),l=!0,ot(document.body,{cover:s,to:o.to,perspective:o.P,origin:o.origin,onDone:h,onCover:()=>{e.dataset.closing="yes"}})||h()})}export{Ot as A,Bt as B,xt as C,jt as D,Dt as E,Ht as F,Nt as G,Ct as H,Fe as I,Ae as a,Ge as b,ge as c,Wt as d,Kt as e,ae as f,Ut as g,lt as h,Et as i,Xt as j,qt as k,Pt as l,Vt as m,be as n,Gt as o,Tt as p,Lt as q,gt as r,se as s,ut as t,Ce as u,Ft as v,zt as w,Mt as x,It as y,Rt as z};
