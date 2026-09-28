import{m as Be,a as Ie,s as Oe,b as qe,r as He,F as ce}from"./chrome-Bbzm0knH.js";/* empty css                  */import{f as M,s as A,h as Te,c as O,u as Y,l as Ve,n as je,a as P,t as De,i as Ue,b as Ae,C as ze,r as Ge,d as q,e as re,g as Ye,w as Qe,j as Xe,o as Ze,k as de,m as Ke}from"./codex-CieP9hhw.js";import{e as d,s as j,c as u,m as ne,a as Je,g as le,l as et,b as tt,d as st,f as at,h as nt,p as D,i as ot,C as ee,j as it,k as ct,n as se,o as rt}from"./contract-wMVeQDZg.js";import{t as dt,s as he,c as lt,m as ht}from"./leaf-vrvMp2mH.js";import{m as pe,p as Ee,v as pt}from"./frames-Dx4w5fNa.js";const S=e=>String(e).padStart(2,"0"),Ne={positive:"leans positive",balanced:"balanced",negative:"leans negative",unknown:"not readable"},I=e=>e&&M(e.se)?1.96*e.se:0;function Me(e){const s=Math.max(0,...e.filter(a=>a&&M(a.lean)).map(a=>Math.abs(a.lean)+I(a)));return Math.min(1,Math.max(.5,Math.ceil((s+.02)*4)/4))}function ut(e){if(!e||e.label==="too_few")return"Too few videos to call";const s={positive:"lean positive",balanced:"are balanced",negative:"lean negative"}[e.call];return e.label==="all"?`All ${e.of} ${s}`:e.label==="all_but_one"?`${e.count} of ${e.of} ${s}`:e.call?`Split: ${e.count} of ${e.of} ${s}`:`Split: no reading is shared by more than ${e.count}`}function mt(e,s){const a=e.filter(n=>n.analysed),t=(n,i,o)=>`
    <div class="rb__row" data-who="${i}">
      <p class="rb__who"><i class="k ${i==="reviewer"?"k--r":"k--a"}" aria-hidden="true"></i>${n}
        <span class="rb__sum">${ut(o)}</span></p>
      <ol class="rb__tiles" style="--cols:${Math.max(a.length,1)}">${a.map(c=>`
        <li class="rb__tile" data-call="${d(c[i].call)}" data-vid="${c.n}" data-pop>
          <b class="t-read">${S(c.n)}</b><span class="sr-only">Video ${c.n}:</span>
          <span class="rb__w">${Ne[c[i].call]||""}</span></li>`).join("")}</ol>
    </div>`;return`<figure class="rb">${t("Reviewers' words","reviewer",s.reviewer_consensus)}
    ${t("Audiences","audience",s.audience_consensus)}</figure>`}function Q(e,s){if(!e||!M(e.lean))return'<span class="lmn lmn--none">not readable</span>';const a=120,t=5,n=115,i=9,o=l=>t+(O(l,-1,1)+1)/2*(n-t),c=I(e)?`<line class="lmn__ci" x1="${o(e.lean-I(e)).toFixed(1)}" y1="${i}" x2="${o(e.lean+I(e)).toFixed(1)}" y2="${i}" data-grow-c/>`:"",r=s==="reviewer"?`<circle class="lmn__r" cx="${o(e.lean).toFixed(1)}" cy="${i}" r="4.6" data-pop/>`:`<rect class="lmn__a" x="${(o(e.lean)-4.2).toFixed(1)}" y="${i-4.2}" width="8.4" height="8.4" data-pop/>`;return`<span class="lmn"><svg class="lmn__svg" viewBox="0 0 ${a} 18" aria-hidden="true">
      <line class="lmn__axis" x1="${t}" y1="${i}" x2="${n}" y2="${i}"/>
      <line class="lmn__zero" x1="${(t+n)/2}" y1="${i-5}" x2="${(t+n)/2}" y2="${i+5}"/>${c}${r}</svg>
    <span class="lmn__v t-read">${A(e.lean)}</span></span>`}function _t(e){const s=e.filter(m=>m.analysed&&M(m.reviewer.lean)&&M(m.audience.lean));if(!s.length)return"";const a=470,t=452,n=64,i=452,o=16,c=404,r=Me(s.flatMap(m=>[m.reviewer,m.audience])),l=m=>n+(O(m,-r,r)+r)/(2*r)*(i-n),h=m=>c-(O(m,-r,r)+r)/(2*r)*(c-o),p=[];for(let m=-r;m<=r+1e-9;m+=.25)p.push(Math.round(m*100)/100);const $=p.map(m=>`
    <line class="qd__grid${m===0?" qd__grid--zero":""}" x1="${l(m)}" y1="${o}" x2="${l(m)}" y2="${c}"/>
    <line class="qd__grid${m===0?" qd__grid--zero":""}" x1="${n}" y1="${h(m)}" x2="${i}" y2="${h(m)}"/>
    <text class="qd__tick" x="${l(m)}" y="${c+18}" text-anchor="middle">${A(m)}</text>
    <text class="qd__tick" x="${n-8}" y="${h(m)+4}" text-anchor="end">${A(m)}</text>`).join(""),v=12.5,_=[],b=[],E=[];for(const m of[...s].sort((T,x)=>T.n-x.n)){const T=l(m.reviewer.lean),x=h(m.audience.lean);let L=T;const W=x;for(;_.some(N=>Math.hypot(N[0]-L,N[1]-W)<2*v+1);)L+=2*v+2;_.push([L,W]);const H=m.agreement.call==="reviewer_warmer"||m.agreement.call==="audience_warmer",f=I(m.reviewer),g=I(m.audience);b.push(`<g class="qd__pt${H?" is-clear":""}" data-vid="${m.n}">
      ${f?`<line class="qd__ci" x1="${l(m.reviewer.lean-f).toFixed(1)}" y1="${x.toFixed(1)}" x2="${l(m.reviewer.lean+f).toFixed(1)}" y2="${x.toFixed(1)}" data-grow-c/>`:""}
      ${g?`<line class="qd__ci" x1="${T.toFixed(1)}" y1="${h(m.audience.lean-g).toFixed(1)}" x2="${T.toFixed(1)}" y2="${h(m.audience.lean+g).toFixed(1)}"/>`:""}
      ${L!==T?`<line class="qd__lead" x1="${T.toFixed(1)}" y1="${x.toFixed(1)}" x2="${L.toFixed(1)}" y2="${W.toFixed(1)}"/>
        <circle class="qd__true" cx="${T.toFixed(1)}" cy="${x.toFixed(1)}" r="2.4"/>`:""}
    </g>`),E.push(`<g class="qd__pt${H?" is-clear":""}" data-vid="${m.n}">
      <g data-pop><circle class="qd__disc" cx="${L.toFixed(1)}" cy="${W.toFixed(1)}" r="${v}"/>
      <text class="qd__n" x="${L.toFixed(1)}" y="${(W+4).toFixed(1)}" text-anchor="middle">${S(m.n)}</text></g>
    </g>`)}const k=b.join("")+E.join(""),F=`
    <polygon class="qd__half qd__half--a" points="${l(-r)},${h(-r)} ${l(-r)},${h(r)} ${l(r)},${h(r)}"/>
    <polygon class="qd__half qd__half--r" points="${l(-r)},${h(-r)} ${l(r)},${h(-r)} ${l(r)},${h(r)}"/>`,y=s.map(m=>`video ${m.n}: reviewer ${A(m.reviewer.lean)}, audience ${A(m.audience.lean)}`).join("; ");return`<svg class="qd" viewBox="0 0 ${a} ${t}" role="img"
      aria-label="${d(`Each video's reviewer lean across and audience lean up, from ${A(-r)} to ${A(r)}. ${y}.`)}">
    ${F}
    ${$}
    <line class="qd__diag" x1="${l(-r)}" y1="${h(-r)}" x2="${l(r)}" y2="${h(r)}" data-draw/>
    <text class="qd__cap qd__cap--a" x="${l(-r)+10}" y="${o+18}">Audience warmer</text>
    <text class="qd__cap qd__cap--r" x="${i-10}" y="${c-10}" text-anchor="end">Reviewer warmer</text>
    <text class="qd__axis" x="${(n+i)/2}" y="${t-6}" text-anchor="middle">The reviewer's words, lean</text>
    <text class="qd__axis" x="14" y="${(o+c)/2}" text-anchor="middle" transform="rotate(-90 14 ${(o+c)/2})">The audience, lean</text>
    ${k}
  </svg>`}function ue(e,s,a){const t=e.filter(_=>_.analysed&&M(_[s].lean));if(!t.length)return"";const n=560,i=76,o=16,c=544,r=46,l=_=>o+(O(_,-1,1)+1)/2*(c-o),h=a&&a.dimension===s?a:null,p=[],$=[...t].sort((_,b)=>_[s].lean-b[s].lean).map(_=>{const b=l(_[s].lean);let E=0;for(;p.some(([m,T])=>T===E&&Math.abs(m-b)<17);)E+=1;p.push([b,E]);const k=h&&h.n===_.n,F=r-E*17,y=s==="reviewer"?`<circle class="os__m${k?" is-odd":""}" cx="${b.toFixed(1)}" cy="${F}" r="${k?10:8}"/>`:`<rect class="os__m${k?" is-odd":""}" x="${(b-(k?10:8)).toFixed(1)}" y="${F-(k?10:8)}" width="${k?20:16}" height="${k?20:16}"/>`;return`<g data-vid="${_.n}" data-pop>${k&&M(_[s].se)?`<line class="os__ci" x1="${l(_[s].lean-I(_[s])).toFixed(1)}" y1="${F}" x2="${l(_[s].lean+I(_[s])).toFixed(1)}" y2="${F}"/>`:""}
      ${y}<text class="os__n${k?" is-odd":""}" x="${b.toFixed(1)}" y="${F+3.5}" text-anchor="middle">${S(_.n)}</text></g>`}).join(""),v=h?`<line class="os__med" x1="${l(h.others_median)}" y1="${r-30}" x2="${l(h.others_median)}" y2="${r+14}"/>
    <text class="os__lab" x="${l(h.others_median)}" y="${r+28}" text-anchor="middle">others' median ${A(h.others_median)}</text>`:"";return`<svg class="os${h?" is-focus":""}" viewBox="0 0 ${n} ${i+8}" aria-hidden="true">
    <line class="os__axis" x1="${o}" y1="${r}" x2="${c}" y2="${r}"/>
    <line class="os__zero" x1="${l(0)}" y1="${r-6}" x2="${l(0)}" y2="${r+6}"/>
    <text class="os__end" x="${o}" y="${i+4}">−1</text><text class="os__end" x="${c}" y="${i+4}" text-anchor="end">+1</text>
    ${v}${$}</svg>`}function $t(e,s=1){const r=x=>O(x,0,100)/100*1e3,l=x=>35-O(x,-s,s)/s*29,h=e.tone&&e.tone.points||[],p=[];let $=[];for(const x of h){if(!M(x.v)||!M(x.p)){$.length&&p.push($),$=[];continue}$.push(x)}if($.length&&p.push($),!p.length)return'<p class="tm__none">The words of this video could not be read.</p>';const v=p.map(x=>x.map((L,W)=>`${W?"L":"M"}${r(L.p).toFixed(1)},${l(L.v).toFixed(1)}`).join("")).join(""),_=p.map(x=>`${x.map((W,H)=>`${H?"L":"M"}${r(W.p).toFixed(1)},${l(W.v).toFixed(1)}`).join("")}L${r(x[x.length-1].p).toFixed(1)},35L${r(x[0].p).toFixed(1)},35Z`).join(""),b=Y("tm-a"),E=Y("tm-b"),k=Y("tm-h"),F=e.tone.duration_s||0,y=e.moment,m=y&&F?`<rect class="tm__mom${y.flagged?" is-flagged":""}" x="${r(100*y.start/F).toFixed(1)}" y="60" width="4" height="8" data-pop>
      <title>${d(`Most contested moment, ${y.time}${y.flagged?", flagged":""}`)}</title></rect>`:"",T=(e.tone&&e.tone.turns||[]).filter(x=>M(x.p)&&M(x.v)).map(x=>`<circle class="tm__turn" cx="${r(x.p).toFixed(1)}" cy="${l(x.v).toFixed(1)}" r="3.5" data-pop/>`).join("");return`<svg class="tm" viewBox="0 0 1000 70" preserveAspectRatio="none" aria-hidden="true">
    <defs><clipPath id="${b}"><rect x="0" y="0" width="1000" height="35"/></clipPath>
      <clipPath id="${E}"><rect x="0" y="35" width="1000" height="35"/></clipPath>
      ${Te(k,"ta__hatch")}</defs>
    <line class="ta__zero" x1="0" y1="35" x2="1000" y2="35" vector-effect="non-scaling-stroke"/>
    <path class="ta__pos" d="${_}" clip-path="url(#${b})" data-fade/>
    <path class="ta__neg" d="${_}" clip-path="url(#${E})" fill="url(#${k})" data-fade/>
    <path class="ta__line" d="${v}" vector-effect="non-scaling-stroke" data-draw/>
    ${T}${m}
  </svg>`}function vt(e){const s=e.flatMap(t=>(t.tone&&t.tone.points||[]).map(n=>n.v)).filter(M),a=s.length?Math.max(...s.map(Math.abs)):1;return Math.min(1,Math.max(.25,Math.ceil(a*4)/4))}const ft={present:"Present",absent:"Absent",not_checked:"Not checked"};function wt(e,s){const a=s.filter(t=>t.analysed);return`<table class="sgx">
    <caption class="sr-only">Each sign of a commercial interest, for each video</caption>
    <thead><tr><th scope="col"><span class="sr-only">Sign</span></th>
      ${a.map(t=>`<th scope="col" class="sgx__vid" data-vid="${t.n}"><span class="t-read">${S(t.n)}</span></th>`).join("")}
      <th scope="col" class="sgx__tot">Present in</th></tr></thead>
    <tbody>${e.signs.map(t=>`
      <tr><th scope="row" class="sgx__name">${d(t.name||t.id)}
          <span class="sg__kind">${t.kind==="fact"?"fact":"inference"}</span></th>
        ${a.map(n=>{const i=t.states[n.n]||"not_checked";return`<td data-vid="${n.n}"><button class="sgx__dot" type="button" data-state="${i}"
            data-sign="${d(t.id)}" data-n="${n.n}" data-pop
            aria-label="${d(`${t.name}, video ${n.n}: ${ft[i]}`)}"></button></td>`}).join("")}
        <td class="sgx__tot t-read">${a.length-t.not_checked?`${t.present} of ${a.length-t.not_checked}${t.not_checked?`<span class="sgx__nc">${t.not_checked} not checked</span>`:""}`:'<span class="sgx__nc">not checked</span>'}</td></tr>`).join("")}
    </tbody></table>`}const gt={praise:"praised",criticism:"criticised",mixed:"mixed",neutral:"neutral",silent:"not discussed"},bt={positive:"comments lean positive",negative:"comments lean negative",balanced:"comments balanced",unknown:"too few comments"};function yt(e,s){if(e.status==="not_written")return'<svg class="mx__g" viewBox="0 0 40 40" aria-hidden="true"><line class="mx__nw" x1="12" y1="20" x2="28" y2="20"/></svg>';const a=e.audience||{},t=a.comments?`<circle class="mx__ring" data-aud="${d(a.call)}" cx="20" cy="20" r="16"/>`:"",n=e.stance,i=n==="silent"?'<circle class="mx__dot" cx="20" cy="20" r="2.6"/>':n==="criticism"?`<circle class="mx__disc" data-stance="criticism" cx="20" cy="20" r="10" fill="url(#${s.hatch})"/>`:n==="mixed"?`<circle class="mx__disc" data-stance="mixed-o" cx="20" cy="20" r="10"/>
        <path class="mx__disc" data-stance="mixed" d="M20,10 A10,10 0 0 0 20,30 Z"/>`:n==="neutral"?`<circle class="mx__disc" data-stance="neutral" cx="20" cy="20" r="10"/>
        <line class="mx__neu" x1="14.5" y1="20" x2="25.5" y2="20"/>`:`<circle class="mx__disc" data-stance="${d(n)}" cx="20" cy="20" r="10"/>`;return`<svg class="mx__g" viewBox="0 0 40 40" aria-hidden="true">${t}${i}</svg>`}function Le(e){return`<span class="cb" aria-hidden="true">${e.map(s=>`<i class="cb__s" data-stance="${s.status==="not_written"?"not_written":s.stance}" data-vid="${s.n}"></i>`).join("")}</span>`}function K(e){const s=e.reviewer;return s.label==="agreed"?`${s.side==="praise"?"Praised":"Criticised"} in ${Math.max(s.praise_in,s.criticism_in)} of ${s.talked}`:s.label==="mostly"?`${s.side==="praise"?"Praised":"Criticised"} in ${Math.max(s.praise_in,s.criticism_in)} of ${s.talked}, one dissent`:s.label==="split"?`Split: praised in ${s.praise_in}, criticised in ${s.criticism_in}`:s.label==="neutral"?`Discussed in ${s.talked}, no side taken`:s.talked?`Discussed in ${s.talked}, too few sides to call`:"Not discussed"}function xt(e,s,a){const t=s.filter(p=>p.analysed),n={hatch:Y("mx-h")},i=new Map;for(const p of a||[])for(const $ of p.videos)i.set($,p.product);const o=a&&a.length?[...t].sort((p,$)=>{const v=a.findIndex(b=>b.videos.includes(p.n)),_=a.findIndex(b=>b.videos.includes($.n));return(v<0?99:v)-(_<0?99:_)||p.n-$.n}):t,c=a&&a.length?`<tr class="mx__groups"><td></td>${(()=>{const p=[];for(let $=0;$<o.length;){const v=i.get(o[$].n)||"";let _=1;for(;$+_<o.length&&(i.get(o[$+_].n)||"")===v;)_+=1;p.push(`<th scope="colgroup" colspan="${_}" class="mx__prod">${v?d(v):"No single product"}</th>`),$+=_}return p.join("")})()}<td></td></tr>`:"",r=(p,$)=>p.cells.find(v=>v.n===$)||{n:$,stance:"silent",audience:{}};let l=!0;const h=e.map(p=>`
    <tr class="mx__row" data-theme="${d(p.id)}" id="theme-${d(p.id)}">
      <th scope="row" class="mx__name"><span class="mx__tn">${d(p.name)}</span>
        ${p.aspects&&p.aspects.length?`<span class="mx__asp">${d(p.aspects.slice(0,4).join(", "))}</span>`:""}</th>
      ${o.map($=>{const v=r(p,$.n),_=v.status==="not_written"?`${p.name}, video ${$.n}: not written yet`:`${p.name}, video ${$.n}: ${gt[v.stance]}; ${v.audience&&v.audience.comments?`${v.audience.comments} comments, ${bt[v.audience.call]||""}`:"no comments on it"}`,b=l?"0":"-1";return l=!1,`<td data-vid="${$.n}"><button class="mx__cell" type="button" tabindex="${b}"
          data-cell="${d(p.id)}:${$.n}" data-vid="${$.n}" data-pop aria-label="${d(_)}">${yt(v,n)}</button></td>`}).join("")}
      <td class="mx__sum">${Le(o.map($=>r(p,$.n)))}
        <span class="mx__words" data-label="${d(p.reviewer.label)}">${K(p)}</span></td>
    </tr>`).join("");return`<table class="mx" role="grid" aria-label="Themes by video: the reviewer's stance and the audience's lean">
    <thead>${c}<tr><td class="mx__corner">
      <svg width="0" height="0" class="mx__defs" aria-hidden="true" focusable="false"><defs>${Te(n.hatch,"mx__hatch")}</defs></svg></td>
      ${o.map(p=>`<th scope="col" class="mx__vid" data-vid="${p.n}"><span class="t-read">${S(p.n)}</span>
        <span class="mx__vt">${d(String(p.title||"").split(/\s+/).slice(0,4).join(" "))}</span></th>`).join("")}
      <th scope="col" class="mx__sumh">Across the videos</th></tr></thead>
    <tbody>${h}</tbody></table>`}function kt(e){const s=Math.max(0,Math.floor((Math.min(...e)-5)/10)*10),a=Math.min(100,Math.ceil((Math.max(...e)+5)/10)*10);return a-s<20?[Math.max(0,s-10),Math.min(100,a+10)]:[s,a]}const me={reviewer:"The reviewers' words",audience:"The audiences",authenticity:"Authenticity",brand_health:"Brand health"};function St(e,s){const a=[...e.a,...e.b].map(y=>y.v).filter(M);if(!a.length)return"";const t=300,n=196,i=30,o=176,c=84,r=238;let l,h;if(e.kind==="lean"){const y=Me(a.map(m=>({lean:m,se:null})));l=-y,h=y}else[l,h]=kt(a);const p=y=>o-(O(y,l,h)-l)/(h-l||1)*(o-i),$=e.kind==="lean"?A:y=>String(Math.round(y)),v=(y,m)=>y.map((T,x)=>{const L=(x%3-1)*7;return`<circle class="sl__pt" cx="${m+L}" cy="${p(T.v).toFixed(1)}" r="4" data-vid="${T.n}" data-pop>
      <title>${d(`Video ${T.n}: ${e.kind==="lean"?A(T.v):j(T.v)}`)}</title></circle>`}).join(""),_=e.a.filter(y=>y.video_id&&e.b.some(m=>m.video_id===y.video_id)).map(y=>{const m=e.b.find(T=>T.video_id===y.video_id);return`<line class="sl__twice" x1="${c}" y1="${p(y.v).toFixed(1)}" x2="${r}" y2="${p(m.v).toFixed(1)}"/>`}).join(""),b=e.a_range.median,E=e.b_range.median,k=M(b)&&M(E)?`
    <line class="sl__band" x1="${c}" y1="${p(e.a_range.min)}" x2="${c}" y2="${p(e.a_range.max)}"/>
    <line class="sl__band" x1="${r}" y1="${p(e.b_range.min)}" x2="${r}" y2="${p(e.b_range.max)}"/>
    <line class="sl__med" x1="${c}" y1="${p(b).toFixed(1)}" x2="${r}" y2="${p(E).toFixed(1)}" data-draw/>
    <text class="sl__v" x="${c-14}" y="${(p(b)+4).toFixed(1)}" text-anchor="end">${$(b)}</text>
    <text class="sl__v" x="${r+14}" y="${(p(E)+4).toFixed(1)}">${$(E)}</text>`:"",F={moved:"moved: the two ranges do not overlap",within_spread:"within the spread",too_few:"too few videos to call"}[e.call]||"";return`<figure class="sl" data-call="${d(e.call)}">
    <figcaption class="sl__cap"><b>${me[e.key]||d(e.key)}</b><span class="sl__call">${F}</span></figcaption>
    <svg class="sl__svg" viewBox="0 0 ${t} ${n}" role="img" aria-label="${d(`${me[e.key]}: median ${M(b)?$(b):"none"} in ${s[0]} and ${M(E)?$(E):"none"} in ${s[1]}; ${F}.`)}">
      <text class="sl__col" x="${c}" y="14" text-anchor="middle">${d(s[0])}</text>
      <text class="sl__col" x="${r}" y="14" text-anchor="middle">${d(s[1])}</text>
      <line class="sl__axis" x1="${c}" y1="${i-6}" x2="${c}" y2="${o+6}"/>
      <line class="sl__axis" x1="${r}" y1="${i-6}" x2="${r}" y2="${o+6}"/>
      <text class="sl__tick" x="${c-30}" y="${i+4}" text-anchor="end">${$(h)}</text>
      <text class="sl__tick" x="${c-30}" y="${o+4}" text-anchor="end">${$(l)}</text>
      ${_}${k}${v(e.a,c)}${v(e.b,r)}
    </svg></figure>`}function z(e,s,a){if(!M(e)||!M(s))return'<span class="tw__none">not readable</span>';const t=200,n=6,i=194,o=10,[c,r]=a==="lean"?[-1,1]:[0,100],l=p=>n+(O(p,c,r)-c)/(r-c)*(i-n),h=a==="lean"?A:j;return`<span class="tw"><svg class="tw__svg" viewBox="0 0 ${t} 20" aria-hidden="true">
      <line class="tw__axis" x1="${n}" y1="${o}" x2="${i}" y2="${o}"/>
      <line class="tw__gap" x1="${l(e).toFixed(1)}" y1="${o}" x2="${l(s).toFixed(1)}" y2="${o}" data-grow/>
      <circle class="tw__a" cx="${l(e).toFixed(1)}" cy="${o}" r="4.5"/>
      <circle class="tw__b" cx="${l(s).toFixed(1)}" cy="${o}" r="4.5" data-pop/></svg>
    <span class="tw__v t-read">${h(e)} <span class="tw__then">then</span> ${h(s)}</span></span>`}const V={well_covered:{word:"Well covered",dots:3},partly_covered:{word:"Partly covered",dots:2},thinly_covered:{word:"Thinly covered",dots:1},unknown:{word:"Coverage unknown",dots:0}};function qt(e,s){const a=s.facts,t=a.videos||[],n=new Map(t.map(l=>[l.n,l])),i=s.reading&&s.reading.themes||[],o=new Map(i.map(l=>[l.id,l])),c=new Map;for(const l of i)for(const h of l.cells)h.quote&&c.set(`${h.n}:${h.quote.seg}`,h.quote.time);const r=e.sweep_id;return{record:e,a:s,facts:a,rows:t,byN:n,themes:i,byTheme:o,times:c,written:s.written||null,reading:s.reading||null,command:`python write_analysis.py --sweep ${r}`,href:(l,h="")=>{const p=n.get(l);return p&&p.analysed?`/brand/${encodeURIComponent(r)}/${encodeURIComponent(p.video_id)}${h}`:null}}}function X(e,s){const a=(e||[]).map(t=>{const n=String(t).match(/^(?:V(\d{1,2})(?::([SC])(\d{1,5}))?|H(\d{1,2}))$/);if(!n)return"";const[,i,o,c,r]=n;if(r!==void 0){const p=s.byTheme.get(`H${r}`);return p?`<button class="ev ev--t" type="button" data-evh="H${r}">${d(p.name)}</button>`:""}const l=Number(i);if(!s.byN.has(l))return"";if(!o)return`<button class="ev" type="button" data-evv="${l}" aria-label="Video ${l} in the table">${S(l)}</button>`;const h=s.href(l,o==="S"?`?at=${c}`:`?c=${c}`);if(!h)return"";if(o==="S"){const p=s.times.get(`${l}:${c}`);return`<a class="ev" href="${h}" aria-label="Open video ${l}${p?` at ${p}`:""}">${S(l)}${p?` at ${d(p)}`:", moment"}</a>`}return`<a class="ev ev--c" href="${h}" aria-label="Read comment ${Number(c)+1} on video ${l}">${S(l)}, comment ${Number(c)+1}</a>`}).filter(Boolean);return a.length?`<span class="evs">${a.join("")}</span>`:""}function U(e,s,a="cx-text"){return!e||!e.text?"":`<p class="${a}">${d(e.text)} ${Ae(e)}</p>${X(e.evidence,s)}`}function oe(e){const s=e.filter(Boolean);return s.length<=1?s.join(""):`${s.slice(0,-1).join(", ")} and ${s[s.length-1]}`}function Tt(e){const s=e.set,a=(n,i)=>{const o=[["positive","lean positive"],["balanced","are balanced"],["negative","lean negative"],["unknown","could not be read"]].filter(([c])=>n[c]).map(([c,r])=>`${r} in ${n[c]}`);return o.length?`${i} ${oe(o)}`:""},t=[a(s.reviewer_calls,"the reviewers' words"),a(s.audience_calls,"the audiences")].filter(Boolean);return`Across ${s.analysed} video${s.analysed===1?"":"s"}, ${t.join("; ")}.`}function Ce(e){const s=e.set.agreement_calls,a=[];return s.reviewer_warmer&&a.push(`the reviewer is measurably warmer than the audience in ${s.reviewer_warmer}`),s.audience_warmer&&a.push(`the audience is measurably warmer than the reviewer in ${s.audience_warmer}`),s.no_clear_difference&&a.push(`there is no clear difference in ${s.no_clear_difference}`),s.unknown&&a.push(`the two cannot be compared in ${s.unknown}`),a.length?`Of ${e.set.analysed} videos, ${oe(a)}.`:"No video could be compared."}const _e={well_covered:"Plenty of evidence behind this set.",partly_covered:"Some of the evidence behind this set is thin.",thinly_covered:"The evidence behind this set is thin.",unknown:"How much evidence is behind this set is unknown."};function jt(e){const s=e&&e.facts;if(!s)return"";const a=s.set.analysed,t=(s.signs&&s.signs.signs||[]).find(r=>r.id==="S1"),n=Object.values(t&&t.states||{}),i=(t&&t.present_in||[]).slice().sort((r,l)=>r-l),o=n.filter(r=>r==="not_checked").length;let c;if(!t)c="Whether any video declared a paid promotion could not be checked.";else if(i.length){const r=`${i.length===1?"Video":"Videos"} ${oe(i.map(S))}`,l=a-i.length-o;c=`${r} declared a paid promotion${l>0?`; the other ${u(l)} did not`:""}${o?`; for ${u(o)} it could not be checked`:""}.`}else c=o===a?"Whether any video declared a paid promotion could not be checked.":`None of the ${u(a-o)} videos checked declared a paid promotion.`;return Ue(`${_e[s.coverage&&s.coverage.level]||_e.unknown} ${c} It cannot say whether any reviewer is honest.`)}function At(e){if(!e.a.stale)return"";const s=new Map(e.rows.map(t=>[t.video_id,t.n])),a=(e.a.stale_members||[]).map(t=>s.get(t)).filter(Boolean).sort((t,n)=>t-n);return`<p class="rdx__stale" role="note">Written before ${a.length?`the own report of video ${a.map(S).join(", ")} changed`:"this sweep changed"}. Every figure
    is current; the themes and the words are from when it was written.
    <code>${d(e.command)} --combined-only</code></p>`}function Et(e){const s=e.facts,a=e.written,t=a&&a.verdict,n=t&&t.source==="model"?`<p class="vd">${d(t.text)}</p>${X(t.evidence,e)}`:t&&t.source==="code"?`<p class="vd">${d(t.text)}</p>${X(t.evidence,e)}
         <p class="vd__src">Summarised from the figures by code; the advice further on is the local model's.</p>`:`<p class="vd vd--code">${d(t?t.text:Tt(s))}</p>
         <p class="vd__src">${a?"Written by code from the figures: the fact checks set the local model's own summary aside.":"Summarised from the figures. The combined written report has not been run for this set."}</p>`;return`<section class="rd rdx" aria-labelledby="rdx-h">
    <div class="rd__head"><p class="cx-kicker" id="rdx-h">The reading across ${u(s.set.analysed)} video${s.set.analysed===1?"":"s"}</p>
      ${Ve(s.coverage.level,"#trust")}</div>
    ${At(e)}
    ${n}
    ${mt(s.videos,s.set)}
    <div class="rdx__agree"><p class="ag__k">Do reviewers and audiences agree?</p>
      <p class="rdx__words">${d(a&&a.agreement_words&&a.agreement_words.text||Ce(s))}</p></div>
    <p class="cx-note">Each tile is one video, numbered as in the contents. A reviewer is read from the words
      (the transcript model), an audience from its comments (the comment model); a lean is called only when its
      95% interval leaves zero. ${d(s.rules.consensus)}</p>
  </section>`}function Nt(e){const s=e.written,a=s&&s.takeaways||[],t=s&&(((e.a.verifier||{}).by_field||{}).takeaway||{}).dropped||0;return`<section class="tk" aria-labelledby="tkx-h">
    <h2 id="tkx-h" class="cx-h">What to take from the set</h2>
    ${s?a.length?`
    <ol class="tk__list">${a.map((n,i)=>{const o=e.byTheme.get((n.evidence||[]).find(c=>c.startsWith("H")));return`
      <li class="tk__item"><span class="tk__n" aria-hidden="true">${i+1}</span>
        <div><p class="tk__text">${d(n.text)}</p>
          ${o?`<p class="tk__basis">${d(o.name)}: ${K(o).toLowerCase()}</p>`:""}
          ${X(n.evidence,e)}</div></li>`}).join("")}
    </ol>`:`<p class="cx-note">None of the model's takeaways passed the checks, so none is printed.</p>`:je("Three takeaways across the videos",e.command)}
    ${s&&t?`<p class="cx-note tk__dropped">${t} further ${t===1?"takeaway was":"takeaways were"}
      written and dropped because ${t===1?"it":"they"} did not hold up against the set.</p>`:""}
    <p class="cx-note">The advice is the local model's, checked against every video's own report before it was
      kept; the figures under each are code's, read off the matrix.</p>
  </section>`}function Mt(e){const s=e.rows.filter(t=>t.analysed&&t.near_tie&&t.near_tie.near_tie);return s.length?`<div class="nt" data-vid-list>
    <p class="nt__p"><b>Near-ties.</b> ${s.map(t=>{const n=t.near_tie;return`<span class="t-read">${S(t.n)}</span> ${u(n.top[1])} against ${u(n.second[1])}${Number.isFinite(n.swing)?`, ${j(n.swing)} points at stake`:""}`}).join("; ")}. The comment label is a majority vote, and Brand health gives
      it 60% of its weight, so a handful of comments can swing it: one video read twice on this machine, days apart,
      went from 79.29 to 15.96 (23 Sep 2026). The leans above have no such cliff.</p>
  </div>`:""}function Lt(e){const s=e.signs||{signs:[]};return`<span class="vt__signs"><span class="vt__sd" aria-hidden="true">${s.signs.map(a=>`<i data-state="${d(a.state)}"></i>`).join("")}</span>
    <span class="t-read">${s.present} of ${s.checked}</span></span>`}const Ct={reviewer_warmer:"Reviewer",audience_warmer:"Audience",no_clear_difference:"Neither clearly",unknown:"Cannot tell"};function Ft(e){const s=e.rows,a={well_covered:3,partly_covered:2,thinly_covered:1,unknown:0},t=o=>Number.isFinite(o)?o:"",n=o=>{if(!o.analysed)return`<tr class="vt__row is-failed" data-vid="${o.n}" data-sort-n="${o.n}">
        <td class="vt__n t-read">${S(o.n)}</td>
        <td class="vt__video"><span class="vt__title">${d(o.title||o.video_id)}</span></td>
        <td colspan="8" class="vt__failed">Not analysed. ${d(o.reason||"No reason was recorded.")}</td></tr>`;const c=o.near_tie&&o.near_tie.near_tie,r=V[o.coverage]||V.unknown;return`<tr class="vt__row" data-vid="${o.n}" data-sort-n="${o.n}"
        data-sort-reviewer="${t(o.reviewer.lean)}" data-sort-audience="${t(o.audience.lean)}"
        data-sort-gap="${t(o.agreement.gap)}" data-sort-coverage="${a[o.coverage]??0}"
        data-sort-signs="${o.signs.present}" data-sort-authenticity="${t(o.scores.authenticity)}"
        data-sort-brand_health="${t(o.scores.brand_health)}">
      <td class="vt__n t-read">${S(o.n)}</td>
      <td class="vt__video"><a class="vt__title" href="${e.href(o.n)}">${d(P(o.title||o.video_id,7))}</a>
        <span class="vt__ch">${[o.channel?d(o.channel):"",o.duration_s?ne(o.duration_s):""].filter(Boolean).join(", ")}</span></td>
      <td class="vt__vd">${o.verdict?`${d(P(o.verdict.text,12))}${o.verdict.source==="template"?` ${Ae(o.verdict)}`:""}`:'<span class="vt__none">Not written yet</span>'}</td>
      <td>${Q(o.reviewer,"reviewer")}</td>
      <td>${Q(o.audience,"audience")}</td>
      <td class="vt__ag" data-call="${d(o.agreement.call)}">${Ct[o.agreement.call]||""}</td>
      <td><span class="lvl__dots" aria-hidden="true" title="${r.word}">${[1,2,3].map(l=>`<i${l<=r.dots?" data-on":""}></i>`).join("")}</span>
        <span class="sr-only">${r.word}</span></td>
      <td>${Lt(o)}</td>
      <td class="t-read vt__sc">${j(o.scores.authenticity)}</td>
      <td class="t-read vt__sc">${j(o.scores.brand_health)}${c?'<span class="vt__nt" aria-hidden="true">&asymp;</span><span class="sr-only">, resting on a near-tie of comments</span>':""}</td></tr>`},i=(o,c)=>`<th scope="col"${o==="n"?' aria-sort="ascending"':""}>
    <button class="vt__sort" type="button" data-sort="${o}">${c}</button></th>`;return`<section class="vt" aria-labelledby="vt-h">
    <div class="vt__head">
      <h2 id="vt-h" class="cx-h">The videos, side by side</h2>
      <p class="cx-lede">Every video on the same measures: a heading sorts by it, a title opens that video's own book.</p>
    </div>
    <div class="vt__wrap"><table class="vt__t">
      <caption class="sr-only">The videos in this set, compared</caption>
      <thead><tr>${i("n","No.")}<th scope="col">Video</th><th scope="col">Verdict</th>
        ${i("reviewer",`<i class="k k--r" aria-hidden="true"></i>Reviewer's words`)}
        ${i("audience",'<i class="k k--a" aria-hidden="true"></i>Audience')}
        ${i("gap","Warmer")}${i("coverage","Covered")}${i("signs","Signs")}
        ${i("authenticity","Authenticity&dagger;")}${i("brand_health","Brand health&dagger;")}</tr></thead>
      <tbody data-vt-body>${s.map(n).join("")}</tbody>
    </table></div>
    <p class="cx-note vt__key">Leans run from &minus;1 (all negative) to +1 (all positive), with 95% intervals.
      Warmer: the side measurably warmer. Signs: present of the five checked on the Trust pages.
      <span class="vt__nt">&asymp;</span> a near-tie of comments. Brand health gives a video's comments one
      majority label; where that label is negative, however narrowly, the comments add nothing and Brand health
      is 0.4&nbsp;&times;&nbsp;Authenticity, so compare videos on the leans.</p>
    ${e.record.bias_caveat?`<p class="cav vt__fn"><span aria-hidden="true">&dagger;</span> ${d(e.record.bias_caveat)}</p>`:""}
  </section>`}function Pt(e){const s=e.facts;return`<section class="qdx" aria-labelledby="qdx-h">
    <h2 id="qdx-h" class="cx-h">Reviewers against their audiences</h2>
    <p class="cx-lede">Each video once: how its reviewer's words lean, across, and how its comments lean, up.
      On the diagonal the two lean alike; above it the audience is warmer, below it the reviewer.</p>
    <figure class="qdx__fig">${_t(e.rows)}</figure>
    <p class="qdx__key" aria-hidden="true"><span><i class="qdx__k is-clear"></i>one side measurably warmer</span>
      <span><i class="qdx__k"></i>no clear difference</span><span><i class="qdx__kci"></i>95% intervals</span></p>
    <p class="rdx__words">${d(e.written&&e.written.agreement_words&&e.written.agreement_words.text||Ce(s))}</p>
  </section>`}function Rt(e,s){const a=e.facts,t=a.odd_one_out,n=e.written,i=e.themes.filter(c=>c.odd).map(c=>{const r=e.byN.get(c.odd.n);return`<li data-vid="${c.odd.n}"><span class="t-read">${S(c.odd.n)}</span> The only video to
      ${c.odd.stance==="criticism"?"criticise":"praise"} <b>${d(c.name)}</b>, which the others
      ${c.odd.stance==="criticism"?"praise":"criticise"}.${r?` <span class="od__t">${d(P(r.title,8))}</span>`:""}</li>`});let o;if(t){const c=e.byN.get(t.n)||{},r=s(c),l=t.dimension==="reviewer"?"reviewer's words":"audience";o=`<article class="od__card" data-vid="${t.n}">
      <div class="od__frame">${r?`<img src="${r}" alt="" loading="lazy" decoding="async">`:""}<span class="mem__n t-read">${S(t.n)}</span></div>
      <div class="od__body"><p class="od__title"><a href="${e.href(t.n)}">${d(c.title||"")}</a></p>
        <p class="od__fact">Its ${l} ${t.lean>t.others_median?"lean warmer":"lean cooler"} than the rest:
          <span class="t-read">${A(t.lean)}</span>, where the others' median is <span class="t-read">${A(t.others_median)}</span>.</p>
        ${n&&n.odd_words?U(n.odd_words,e,"od__words"):""}</div>
    </article>`}else o=`<p class="cx-text">No video stands apart, by this rule. Every video's leans sit within a quarter of
      the scale of the others', or too close for their intervals to tell apart.</p>`;return`<section class="od" aria-labelledby="od-h">
    <h2 id="od-h" class="cx-h">The odd one out</h2>
    ${o}
    <figure class="od__strips">
      <figcaption class="od__cap"><i class="k k--r" aria-hidden="true"></i>The reviewers' words</figcaption>${ue(e.rows,"reviewer",t)}
      <figcaption class="od__cap"><i class="k k--a" aria-hidden="true"></i>The audiences</figcaption>${ue(e.rows,"audience",t)}
    </figure>
    ${i.length?`<div class="od__themes"><p class="ag__k">Alone on a theme</p><ul class="od__list">${i.join("")}</ul></div>`:""}
    <p class="cx-note">${d(a.rules.odd)}</p>
  </section>`}function Wt(e){const s=e.rows.filter(t=>t.analysed),a=vt(s);return`<section class="tmx" aria-labelledby="tmx-h">
    <div class="tmx__head">
      <h2 id="tmx-h" class="cx-h">How each review moved</h2>
      <p class="cx-lede">Each reviewer's tone from first second to last, on one scale of the video's length and one
        scale of tone (${A(-a)} to ${A(a)}): solid above the line, hatched below, a dot at each turn,
        a tick at the most contested moment, pink when it was flagged.</p>
    </div>
    <ol class="tmx__list">${s.map(t=>`
      <li class="tmx__row" data-vid="${t.n}">
        <p class="tmx__who"><span class="t-read tmx__n">${S(t.n)}</span>
          <a class="tmx__t" href="${e.href(t.n)}">${d(P(t.title,9))}</a>
          <span class="tmx__len t-read">${ne(t.tone.duration_s)}</span></p>
        ${$t(t,a)}
        <span class="sr-only">${d(`Video ${t.n}: reviewer ${Ne[t.reviewer.call]}, ${t.tone.turns.length} turning points.`)}</span>
      </li>`).join("")}</ol>
    <p class="tmx__axis" aria-hidden="true"><span>start</span><span>half way</span><span>end</span></p>
  </section>`}const Bt={transcript:"words",facial:"face",vocal:"voice",comment:"comments"};function It(e,s){const a=e.rows.filter(n=>n.analysed),t=n=>{const i=n.moment;if(!i)return`<article class="omc" data-vid="${n.n}"><p class="omc__who"><span class="t-read">${S(n.n)}</span></p>
        <p class="cx-note">No moment of this video scored any conflict.</p></article>`;const o=s(n);return`<article class="omc" data-vid="${n.n}" aria-label="${d(`Video ${n.n}, the moment at ${i.time}`)}">
      <div class="om__frame">${o?`<img src="${o}" alt="" loading="lazy" decoding="async">`:'<span class="om__none">No frame for this second</span>'}
        <span class="mem__n t-read">${S(n.n)}</span></div>
      <p class="om__when"><span class="t-time">${d(i.time)}</span>
        <span class="om__c${i.flagged?" is-flagged":""}">conflict ${Je(i.conflict)}${i.flagged?", flagged":""}</span></p>
      <blockquote class="om__said">&ldquo;${d(P(i.text,16))}&rdquo;</blockquote>
      <ul class="om__reads">${["transcript","facial","vocal","comment"].map(c=>{const r=i.valences[c];return`<li data-v="${r?d(r.toLowerCase()):"none"}"><span class="om__ch">${Bt[c]}</span>
          <span class="om__v">${r?d(r.toLowerCase()):"no reading"}</span></li>`}).join("")}</ul>
      ${i.note?`<p class="om__note">${d(P(i.note,22))}</p>`:`<p class="om__note">${d(Ge(i.valences))} ${ze}</p>`}
      <a class="cx-btn" href="${e.href(n.n,`?at=${i.seg}`)}">Open this moment</a>
    </article>`};return`<section class="omx" aria-labelledby="omy-h">
    <div class="omx__head">
      <h2 id="omy-h" class="cx-h">One moment per video that does not add up</h2>
      <p class="cx-lede">The second of each video where its four readings disagreed most: what was said, what each
        channel read, and a note on it: the video's own report's where it passed the checks, otherwise the readings in words.</p>
    </div>
    <div class="omy__grid">${a.map(t).join("")}</div>
  </section>`}function ie(e){const s=e.facts.set.written;return je("The themes the videos share",e.command)+`<p class="cx-note">Themes are built from each video's own written report, grouped across the set by the
      local model. ${u(s.complete+s.partial)} of ${u(e.facts.set.analysed)} videos have one so far.</p>`}function Ot(e,s){if(!e.reading||!e.themes.length)return`<section class="mxp" aria-labelledby="mxp-h">
      <h2 id="mxp-h" class="cx-h">What they agree on, theme by theme</h2>${ie(e)}</section>`;const a=(e.reading.unplaced||[]).length,t=e.facts.set.analysed-(e.reading.members_written||[]).length;return`<section class="mxp" aria-labelledby="mxp-h">
    <div class="mxp__head">
      <h2 id="mxp-h" class="cx-h">What they agree on, theme by theme</h2>
      <p class="cx-lede">Themes down, videos across. The disc is the reviewer, the ring around it the audience on that
        theme. Point at a cell, or move with the arrow keys, to read what was said.</p>
    </div>
    <div class="mxp__body">
      <div class="mxp__grid">${xt(e.themes,e.rows,s)}</div>
      <aside class="mxd">
        <p class="mxp__key" aria-hidden="true">
          <span><i class="mk mk--praise"></i>praised</span><span><i class="mk mk--criticism"></i>criticised</span>
          <span><i class="mk mk--mixed"></i>mixed</span><span><i class="mk mk--neutral"></i>neutral</span>
          <span><i class="mk mk--silent"></i>not discussed</span>
          <span><i class="mr mr--positive"></i>comments positive</span><span><i class="mr mr--negative"></i>negative</span>
          <span><i class="mr mr--balanced"></i>balanced</span></p>
        <div class="mxd__detail" data-mx-detail aria-live="polite">
          <p class="mxd__hint">Point at a cell to read what the reviewer said about that theme, and what the
            comments said.</p>
        </div>
        <p class="cx-note">${d(e.facts.rules.theme)}${a?` ${u(a)} topic${a===1?"":"s"} raised by one video only ${a===1?"is":"are"} in no theme.`:""}${t>0?` ${u(t)} video${t===1?" has":"s have"} no written report of ${t===1?"its":"their"} own yet, and ${t===1?"its column is":"their columns are"} marked with a dash.`:""}</p>
      </aside>
    </div>
  </section>`}function Ht(e,s,a){const t=e.byTheme.get(s),n=e.byN.get(a);if(!t||!n)return"";const i=t.cells.find(h=>h.n===a),o=`<p class="mxd__who"><span class="t-read">${S(a)}</span> ${d(P(n.title,10))}</p>
    <p class="mxd__theme">${d(t.name)}</p>`;if(!i||i.status==="not_written")return`${o}<p class="cx-note">This video has no written report of its own yet.</p>`;const c={praise:"praised it",criticism:"criticised it",mixed:"was mixed about it",neutral:"mentioned it without taking a side",silent:"did not discuss it"}[i.stance],r=i.quote,l=i.audience;return`${o}
    <p class="mxd__k"><i class="k k--r" aria-hidden="true"></i>The reviewer ${c}</p>
    ${r?`<blockquote class="mxd__q">&ldquo;${d(P(r.quote,30))}&rdquo;</blockquote>
      <a class="ev" href="${e.href(a,`?at=${r.seg}`)}">Open ${d(r.time)}</a>`:""}
    <p class="mxd__k"><i class="k k--a" aria-hidden="true"></i>${l.comments?`${u(l.comments)} comment${l.comments===1?"":"s"}: ${u(l.counts.POSITIVE)} positive,
         ${u(l.counts.NEUTRAL)} neutral, ${u(l.counts.NEGATIVE)} negative`:"No comments on it"}</p>
    ${l.example?`<blockquote class="mxd__q mxd__q--c">&ldquo;${d(P(l.example.quote,26))}&rdquo;</blockquote>
      <a class="ev ev--c" href="${e.href(a,`?c=${l.example.i}`)}">Comment ${l.example.i+1}</a>`:""}
    ${i.pushback?'<p class="mxd__push">The reviewer and the comments pull opposite ways here.</p>':""}`}function ae(e,s,a){const t=s.cells.find(n=>n.stance===a&&n.quote);return t?`<blockquote class="ag__q" data-vid="${t.n}">&ldquo;${d(P(t.quote.quote,22))}&rdquo;
    <a class="ev" href="${e.href(t.n,`?at=${t.quote.seg}`)}">${S(t.n)} at ${d(t.quote.time)}</a></blockquote>`:""}function Vt(e){const s=e.written;if(!e.reading||!e.themes.length)return`<section class="agx" aria-labelledby="agx-h"><h2 id="agx-h" class="cx-h">Praised and criticised across the set</h2>
      ${ie(e)}</section>`;const a=n=>e.themes.filter(i=>["agreed","mostly"].includes(i.reviewer.label)&&i.reviewer.side===n),t=(n,i,o)=>n.length?`<ol class="agx__list">${n.map(c=>`
    <li class="agx__item"><p class="agx__name"><button class="ev ev--t" type="button" data-evh="${d(c.id)}">${d(c.name)}</button>
      <span class="agx__count">${K(c)}</span></p>
      ${Le(c.cells)}${ae(e,c,i)}</li>`).join("")}</ol>`:`<p class="cx-note">${o}</p>`;return`<section class="agx" aria-labelledby="agx-h">
    <h2 id="agx-h" class="cx-h">Praised and criticised across the set</h2>
    ${s&&s.consensus_words?U(s.consensus_words,e,"agx__words"):""}
    <div class="agx__cols">
      <div><p class="ag__k"><i class="mk mk--praise" aria-hidden="true"></i>Praised</p>
        ${t(a("praise"),"praise","No theme was praised by two or more reviewers without a dissent.")}</div>
      <div><p class="ag__k"><i class="mk mk--criticism" aria-hidden="true"></i>Criticised</p>
        ${t(a("criticism"),"criticism","No theme was criticised by two or more reviewers without a dissent.")}</div>
    </div>
  </section>`}function Dt(e){const s=e.written;if(!e.reading||!e.themes.length)return`<section class="spx" aria-labelledby="spx-h"><h2 id="spx-h" class="cx-h">Where they split</h2>
      <p class="cx-note">The themes come with the combined written report.</p></section>`;const a=e.themes.filter(n=>n.reviewer.label==="split"),t=e.themes.filter(n=>n.pushback.length);return`<section class="spx" aria-labelledby="spx-h">
    <h2 id="spx-h" class="cx-h">Where they split</h2>
    ${s&&s.split_words?U(s.split_words,e,"agx__words"):""}
    ${a.length?`<ol class="spx__list">${a.slice(0,3).map(n=>`
      <li class="spx__item"><p class="agx__name"><button class="ev ev--t" type="button" data-evh="${d(n.id)}">${d(n.name)}</button>
        <span class="agx__count">${K(n)}</span></p>
        <div class="spx__voices"><div><p class="spx__k">For</p>${ae(e,n,"praise")}</div>
          <div><p class="spx__k">Against</p>${ae(e,n,"criticism")}</div></div></li>`).join("")}</ol>`:`<p class="cx-note">No theme split the reviewers: wherever two or more took a side, they took the same one,
        or only one dissented.</p>`}
    ${t.length?`<div class="spx__push"><p class="ag__k">Where audiences push back</p><ul class="od__list">${t.map(n=>n.pushback.map(i=>{const o=n.cells.find(c=>c.n===i);return`<li data-vid="${i}"><span class="t-read">${S(i)}</span> The reviewer ${o.stance==="praise"?"praises":"criticises"}
          <b>${d(n.name)}</b>; its ${u(o.audience.comments)} comments on it lean ${o.audience.call}.</li>`}).join("")).join("")}</ul></div>`:""}
  </section>`}function Ut(e){return`<section class="lu" aria-labelledby="lu-h">
    <h2 id="lu-h" class="cx-h">The products these videos cover</h2>
    <p class="cx-lede">Each product as its videos' titles name it, with how each of its reviewers and audiences
      lean.</p>
    <ol class="lu__list">${(e.reading&&e.reading.product_groups||[]).map(a=>`
      <li class="lu__item"><p class="lu__name">${d(a.product)}</p>
        <p class="lu__vids">${a.videos.map(t=>`<span data-vid="${t}" class="t-read">${S(t)}</span>`).join(" ")}</p>
        <ul class="lu__rows">${a.videos.map(t=>{const n=e.byN.get(t);return n&&n.analysed?`<li data-vid="${t}"><span class="t-read">${S(t)}</span>
            ${Q(n.reviewer,"reviewer")}${Q(n.audience,"audience")}</li>`:""}).join("")}</ul></li>`).join("")}</ol>
  </section>`}function zt(e){const s=e.written,a=e.reading&&e.reading.product_groups||[],t=(n,i)=>e.themes.filter(o=>o.cells.some(c=>c.n===n&&c.stance===i)).map(o=>o.name);return`<section class="lu" aria-labelledby="lu2-h">
    <h2 id="lu2-h" class="cx-h">What they say about each</h2>
    ${s&&s.lineup_words?U(s.lineup_words,e,"agx__words"):""}
    <table class="lu__t"><caption class="sr-only">Themes praised and criticised, by product</caption>
      <thead><tr><th scope="col">Product</th><th scope="col">Praised</th><th scope="col">Criticised</th></tr></thead>
      <tbody>${a.map(n=>{const i=[...new Set(n.videos.flatMap(c=>t(c,"praise")))],o=[...new Set(n.videos.flatMap(c=>t(c,"criticism")))];return`<tr><th scope="row">${d(n.product)}</th><td>${i.length?d(i.join(", ")):"none"}</td>
          <td>${o.length?d(o.join(", ")):"none"}</td></tr>`}).join("")}</tbody></table>
    <p class="cx-note">Product names are copied from each video's title by the local model and checked against
      it; videos naming the same product are grouped.</p>
  </section>`}function Gt(e){const s=e.facts,a=e.written,t=s.audience.counts,n=e.themes.map(o=>{const c={POSITIVE:0,NEUTRAL:0,NEGATIVE:0};for(const r of o.cells)for(const l of Object.keys(c))c[l]+=((r.audience||{}).counts||{})[l]||0;return{name:o.name,audience:{comments:o.audience.comments,counts:c}}}).filter(o=>o.audience.comments),i=s.about_reviewers||[];return`<section class="tl" aria-labelledby="tlx-h">
    <h2 id="tlx-h" class="cx-h">How people talk about it</h2>
    ${a&&a.brand_health_words?U(a.brand_health_words,e,"tl__words"):`<p class="tl__words">Across ${u(s.audience.comments)} comments on ${u(s.set.analysed)} videos,
        ${u(t.POSITIVE)} read positive, ${u(t.NEUTRAL)} neutral and ${u(t.NEGATIVE)} negative.</p>`}
    ${n.length?`${De(n)}
      <p class="tt__key" aria-hidden="true"><span class="th__keyl">complaints</span><span class="th__keyr">praise</span></p>
      <p class="cx-note">Every audience's comments on each theme, counted together. Which comments belong to which
        theme is the local model's reading; whether each is positive or negative is the benched comment model's.</p>`:e.reading?"":ie(e)}
    ${i.length?`<div class="abx"><p class="ag__k">About the reviewers themselves</p>
      <ul class="od__list">${i.slice(0,3).map(o=>`<li data-vid="${o.n}"><span class="t-read">${S(o.n)}</span>
        ${u(o.comments)} comments${o.example?`, such as &ldquo;${d(P(o.example.quote,10))}&rdquo;`:""}</li>`).join("")}</ul></div>`:""}
  </section>`}const G=["POSITIVE","NEUTRAL","NEGATIVE"];function Yt(e){const s=e.rows.filter(c=>c.analysed),a=240,t=6,n=234,i=10,o=c=>t+(Math.max(-1,Math.min(1,c))+1)/2*(n-t);return`<section class="ea" aria-labelledby="eax-h">
    <h2 id="eax-h" class="cx-h">Each audience on its own</h2>
    <p class="cx-lede">The pooled figure can hide an audience that said the opposite of the rest, so each is drawn
      on one scale: its lean with a 95% interval, and its comments by label.</p>
    <ul class="eax">${s.map(c=>{const r=c.comments.distribution||{},l=G.reduce((_,b)=>_+(r[b]||0),0),h=c.audience,p=Number.isFinite(h.lean),$=p&&Number.isFinite(h.se)?1.96*h.se:0,v=c.near_tie&&c.near_tie.near_tie;return`<li class="eax__row" data-vid="${c.n}">
        <span class="eax__n t-read">${S(c.n)}</span>
        <div class="eax__lean"><svg class="lr__svg" viewBox="0 0 ${a} 20" aria-hidden="true">
            <line class="lr__axis" x1="${t}" y1="${i}" x2="${n}" y2="${i}"/>
            <line class="lr__zero" x1="${o(0)}" y1="${i-6}" x2="${o(0)}" y2="${i+6}"/>
            ${$?`<line class="lr__ci" x1="${o(h.lean-$).toFixed(1)}" y1="${i}" x2="${o(h.lean+$).toFixed(1)}" y2="${i}" data-grow-c/>`:""}
            ${p?`<rect class="lr__a" x="${(o(h.lean)-4.5).toFixed(1)}" y="${i-4.5}" width="9" height="9" data-pop/>`:""}
          </svg><span class="t-read eax__v">${p?A(h.lean):"not readable"}</span></div>
        <div class="eax__band">${l?`<div class="au__band" role="img" aria-label="${d(`Video ${c.n}: ${G.map(_=>`${r[_]||0} ${_.toLowerCase()}`).join(", ")}`)}">
            ${G.map(_=>`<i data-k="${_}" style="--n:${r[_]||0}"></i>`).join("")}</div>
          <p class="each__v">${G.map(_=>`${u(r[_]||0)} ${_.toLowerCase()}`).join(", ")}${v?", a near-tie":""}</p>`:'<p class="each__v is-absent">No comment distribution was recorded.</p>'}</div>
      </li>`}).join("")}</ul>
    ${Mt(e)}
  </section>`}function Qt(e,s){const a=[],t=new Set;for(const n of e)t.has(n.n)||(t.add(n.n),a.push(n));return[...a,...e.filter(n=>!a.includes(n))].slice(0,s)}function Xt(e){const s=e.facts.questions||[];return`<section class="ak" aria-labelledby="akx-h">
    <h2 id="akx-h" class="cx-h">What the audiences ask</h2>
    <p class="cx-lede">The questions each audience asked most, the most-liked first: what people still want to
      know after watching.</p>
    ${s.length?`<ul class="ak__qs akx__qs">${Qt(s,6).map(a=>`
      <li data-vid="${a.n}"><p class="ak__q"><span class="t-read akx__n">${S(a.n)}</span>&ldquo;${d(P(a.quote,18))}&rdquo;
        <a class="ev ev--c" href="${e.href(a.n,`?c=${a.i}`)}">comment ${a.i+1}</a></p></li>`).join("")}</ul>`:'<p class="cx-note">Nobody asked a question in the comments that were read.</p>'}
    <p class="cx-note">Usernames and links are removed before any comment is quoted.</p>
  </section>`}function Zt(e){const s=e.facts.coverage,a=V[s.level]||V.unknown,t=n=>n.id==="none_thin"?"none":`at least ${u(n.target)}`;return`<section class="tr" aria-labelledby="trx-h">
    <h2 id="trx-h" class="cx-h">How far to trust this set</h2>
    <div class="tr__level" data-lvl="${d(s.level)}">
      <span class="lvl__dots lvl__dots--big" aria-hidden="true">${[1,2,3].map(n=>`<i${n<=a.dots?" data-on":""}></i>`).join("")}</span>
      <p class="tr__word">${a.word}</p>
    </div>
    <p class="cx-text">${d(s.means_not)}</p>
    <table class="tr__checks">
      <thead><tr><th scope="col">Check</th><th scope="col">This set</th><th scope="col">Needs</th><th scope="col"><span class="sr-only">Result</span></th></tr></thead>
      <tbody>${s.checks.map(n=>`
        <tr data-pass="${n.passed===!0?"yes":n.passed===!1?"no":"unknown"}">
          <th scope="row">${d(n.label)}</th><td class="t-read">${u(n.value)}</td><td>${t(n)}</td>
          <td class="tr__res">${n.passed===!0?"met":n.passed===!1?"not met":"unknown"}</td></tr>`).join("")}
      </tbody></table>
    <ul class="trx__vids">${s.videos.map(n=>{const i=V[n.level]||V.unknown;return`<li data-vid="${n.n}"><span class="t-read">${S(n.n)}</span>
        <span class="lvl__dots" aria-hidden="true">${[1,2,3].map(o=>`<i${o<=i.dots?" data-on":""}></i>`).join("")}</span>
        <span>${i.word}${n.failed.length?`: ${d(n.failed.join("; ").toLowerCase())}`:""}</span></li>`}).join("")}</ul>
    <div class="tr__ceiling"><p class="ag__k">What no report here can promise</p>
      <p class="cx-note">${d(s.ceiling.text)}</p></div>
  </section>`}function Kt(e){const s=e.facts.signs,a=s.signs.filter(t=>t.not_checked).length;return`<section class="sg" aria-labelledby="sgx-h">
    <h2 id="sgx-h" class="cx-h">Could any of this be paid?</h2>
    <p class="cx-lede">Five signs of a commercial interest, checked on every video. A filled dot is present, an
      open one absent, a dashed one not checked. Point at a filled dot for what was found.</p>
    ${wt(s,e.rows)}
    <p class="sgx__ev" data-sg-detail aria-live="polite"></p>
    <p class="sg__disc">${d(s.disclaimer)}</p>
    ${a?`<p class="cx-note">Signs 1 and 3 need each video's own details from YouTube, which are fetched
      when its written report is run; until then they are not checked.</p>`:""}
  </section>`}function Jt(e,s,a){const t=e.byN.get(a),n=t&&t.signs&&t.signs.signs.find(c=>c.id===s);if(!n)return"";const i=n.evidence||{},o=`Video ${S(a)}, ${n.name.toLowerCase()}: ${n.state.replace("_"," ")}.`;if(n.state!=="present")return o;if(s==="S1")return`${o} ${i.label===!0?"The creator ticked YouTube's paid-promotion box.":""}
      ${(i.description||[]).slice(0,1).map(c=>`Description: &ldquo;${d(P(c.context,14))}&rdquo;`).join("")}`;if(s==="S2")return`${o} ${(i.speech||[]).map(c=>`&ldquo;${d(c.match)}&rdquo; at ${d(c.time)}`).join("; ")}`;if(s==="S3")return`${o} ${(i.description||[]).map(c=>`&ldquo;${d(P(c.context,12))}&rdquo;`).join("; ")}`;if(s==="S4"){const c=i.agreement||{};return`${o} Gap ${A(c.gap)}, 95% interval ${A(c.low)} to ${A(c.high)}.`}if(s==="S5"){const c=new Set([...i.positive_flagged||[],...i.controller_flag||[]]).size;return`${o} ${c} flagged moment${c===1?"":"s"} where the words read positive.`}return o}const es=["reviewer","audience","authenticity","brand_health"];function ts(e,s){const a=e.overlap||{},t=e.shared||{n:0},n=(i,o,c)=>`<li class="pc__row" data-ok="${i?"yes":"no"}">
    <span class="pc__mark" aria-hidden="true"></span><div><p class="pc__t">${o}</p><p class="cx-note">${c}</p></div></li>`;return`<div class="pc">
    <h3 class="cx-h3">Can these two be compared?</h3>
    <ol class="pc__list">
      ${n(!0,"The same subject, scored by the same controller",`Both were scored by <code>${d(e.a.controller||"an unrecorded model")}</code>.`)}
      ${n(a.known?a.disjoint:!1,a.known&&a.disjoint?"The periods do not overlap":"The periods overlap",a.known?a.disjoint?`${d(s[0])} and ${d(s[1])} share no days.`:`${a.nested?"One period sits inside the other":"The periods share days"}: about ${u(Math.round(a.overlap_days))} days
            in common. A difference here is partly the same stretch of time counted twice.`:"The dates of one of them were not recorded.")}
      ${n(t.n===0,t.n?`${u(t.n)} ${t.n===1?"video is":"videos are"} in both`:"No video is in both",t.n?`Read twice, days apart. They are the measure of how much this system moves when nothing about the
          video has changed, and they are drawn on the next spread.`:"Every video in one period is different from every video in the other.")}
    </ol>
  </div>`}function ss(e,s){const a=es.map(t=>e.measures.find(n=>n.key===t)).filter(Boolean);return`<section class="slx" aria-labelledby="slx-h">
    <h2 id="slx-h" class="cx-h">What moved between them</h2>
    <p class="cx-lede">Every video's value in each period, the medians joined, a hairline for a video read in both.
      ${d(e.rule)}</p>
    <div class="slx__grid">${a.map(t=>St(t,s)).join("")}</div>
  </section>`}function as(e,s){const a=e.shared;if(!a||!a.n)return`<section class="twx" aria-labelledby="twx-h"><h2 id="twx-h" class="cx-h">The same video, read twice</h2>
      <p class="cx-text">No video is in both periods, so nothing here was read twice.</p></section>`;const t=a.max_delta;return`<section class="twx" aria-labelledby="twx-h">
    <h2 id="twx-h" class="cx-h">The same video, read twice</h2>
    <p class="cx-lede">${u(a.n)} ${a.n===1?"video is":"videos are"} in both periods, analysed again days
      apart. The leans kept their calls in ${u(a.calls_unchanged)} of ${u(a.n)}; the largest moves were
      <b>${t.reviewer==null?"none":A(t.reviewer).replace("+","")}</b> in a reviewer's lean,
      <b>${t.audience==null?"none":A(t.audience).replace("+","")}</b> in an audience's,
      and <b>${j(t.brand_health)}</b> points of Brand health.</p>
    <ol class="twx__list">${a.videos.map(n=>`
      <li class="twx__item">
        <p class="twx__t">${d(P(n.title,10))}${n.label_changed?' <span class="twx__flip">comment label changed</span>':""}</p>
        <dl class="twx__grid">
          <div><dt><i class="k k--r" aria-hidden="true"></i>Reviewer</dt><dd>${z(n.a.reviewer,n.b.reviewer,"lean")}</dd></div>
          <div><dt><i class="k k--a" aria-hidden="true"></i>Audience</dt><dd>${z(n.a.audience,n.b.audience,"lean")}</dd></div>
          <div><dt>Authenticity</dt><dd>${z(n.a.authenticity,n.b.authenticity,"score")}</dd></div>
          <div><dt>Brand health</dt><dd>${z(n.a.brand_health,n.b.brand_health,"score")}</dd></div>
        </dl>
        ${n.label_changed?`<p class="twx__why">Comments read ${d(String(n.a.label).toLowerCase())}, then
          ${d(String(n.b.label).toLowerCase())}${n.a.near_tie||n.b.near_tie?", on a near-tie":""}.</p>`:""}
      </li>`).join("")}</ol>
    <p class="cx-note">Open mark: the reading in ${d(s[0])}; filled: in ${d(s[1])}. A change between
      periods smaller than these is not a change in the videos.</p>
  </section>`}function ns(e,s,a){const t=e.themes;if(!t)return`<section class="thx" aria-labelledby="thx-h"><h2 id="thx-h" class="cx-h">What changed by theme</h2>
      <div class="ny" role="note"><p class="ny__h">Themes in both periods</p>
        <p class="ny__p">Needs the combined written report of both periods, which the local model writes after
          each video's own. Every figure on the facing page is already here.</p>
        ${a.map(i=>`<p class="ny__cmd"><code>${d(i)}</code></p>`).join("")}</div></section>`;const n=i=>`<span class="thx__v t-read">${u(i.praise_in)} praised, ${u(i.criticism_in)} criticised of ${u(i.talked)}</span>`;return`<section class="thx" aria-labelledby="thx-h">
    <h2 id="thx-h" class="cx-h">What changed by theme</h2>
    <p class="cx-lede">Themes matched by name, or by the aspects they cover.</p>
    <table class="thx__t"><caption class="sr-only">Each theme in both periods</caption>
      <thead><tr><th scope="col">Theme</th><th scope="col">${d(s[0])}</th><th scope="col">${d(s[1])}</th></tr></thead>
      <tbody>${t.matched.map(i=>`<tr><th scope="row">${d(i.a.name)}</th><td>${n(i.a)}</td><td>${n(i.b)}</td></tr>`).join("")}
      ${t.only_a.map(i=>`<tr><th scope="row">${d(i.name)}</th><td>${n(i)}</td><td class="thx__none">not discussed</td></tr>`).join("")}
      ${t.only_b.map(i=>`<tr><th scope="row">${d(i.name)}</th><td class="thx__none">not discussed</td><td>${n(i)}</td></tr>`).join("")}
      </tbody></table>
  </section>`}function os(e,s){if(!s)return"";const a=new URLSearchParams({subject:e.subject||"",kind:e.subject_kind||"",window:e.window||"month"}),t=Number(e.offset_days||0),[n,i]=t===0?[s,"the period just before this one"]:[0,"the same length, ending today"],o=Math.max(0,s-Math.abs(t-n)),c=new URLSearchParams(a);return c.set("offset",String(n)),`<div class="pe">
    <p class="ag__k">A cleaner comparison</p>
    <p class="cx-note">The same search over an equal window ${t===0?"ending one window earlier":"ending today"}
      ${o?`shares ${o} of its ${s} days with this one`:"shares no days with this one"}. It is a
      new search (100 quota units), sent only when you start it.</p>
    <p class="pe__links"><a class="cx-btn" href="/run?${d(c.toString())}">Search ${i}</a></p>
  </div>`}const w=document.querySelector("[data-sweep]"),is={week:"the last week",month:"the last month",half:"the last six months",year:"the last year"},cs={brand:"A brand",product:"A product"};function rs(){const e=decodeURIComponent(window.location.pathname).match(/^\/brand\/([^/]+)\/?$/);return e?e[1]:null}function te(e,s,a,t=""){w.innerHTML=`
    <section class="state${e==="Unreachable"?" state--error":""}">
      <p class="t-label state__tag">${d(e)}</p>
      <h1 class="t-l">${d(s)}</h1>
      <p class="t-body">${a}</p>${t}
    </section>`,delete document.documentElement.dataset.carrying,clearTimeout(window.__bpFallback)}function $e(e,s=null){const a=e.summary||{},t=e.members||[],n=e.failed||[],i=at(Number(e.finished_at));return`
  <section class="ti ti--sweep" aria-labelledby="ti-h">
    <div class="ti__board cx-bleed">
      <p class="ti__bk">${cs[e.subject_kind]||"A subject"}, ${u(a.video_count)} video${a.video_count===1?"":"s"} combined</p>
      <h1 id="ti-h" class="ti__title cx-display" data-len="${Ke(e.subject)}">${d(e.subject||"Untitled sweep")}</h1>
      <span class="ti__brule" aria-hidden="true"></span>
      ${e.window?`<p class="ti__bsub">from ${d(B(e))}</p>`:""}
    </div>
    <div class="ti__block">
      <dl class="ti__facts">
        <div><dt>Videos analysed</dt><dd class="t-read">${u(a.video_count)}</dd></div>
        <div><dt>Segments</dt><dd class="t-read">${u(a.segments_total)}</dd></div>
        <div><dt>Comments read</dt><dd class="t-read">${u(a.comments_total)}</dd></div>
      </dl>
      <p class="cx-note">${e.controller?`Scored by <code>${d(e.controller)}</code>`:"Controller not recorded"}${i?`, finished ${d(i)}`:""}.</p>
      ${s?jt(s):""}
      ${e.status==="partial"&&n.length?`
        <p class="sp__partial cx-note">
          This sweep finished partly: ${u(n.length)} of
          ${u((a.video_count||0)+n.length)} videos could not be
          analysed, and every figure here covers the ${u(a.video_count)} that were.
          Why, on <button class="cx-xref" type="button" data-cx-xref="prov-failed">page
          <span data-cx-xref-page></span></button>.
        </p>`:""}
    </div>
    <nav class="toc" aria-label="The videos in this volume">
      <p class="cx-h3">Contents</p>
      <ol class="toc__list">
        ${t.map((c,r)=>`
          <li${c.analysed===!1?' class="is-failed"':""}>
            <span class="toc__n t-read">${String(r+1).padStart(2,"0")}</span>
            <button class="toc__t" type="button" data-cx-xref="mem-${d(c.video_id)}">${d(c.title||c.video_id)}</button>
            <span class="toc__pg t-read" data-cx-xref="mem-${d(c.video_id)}"><span data-cx-xref-page></span></span>
          </li>`).join("")}
      </ol>
    </nav>
  </section>`}function ve(e,s,a,t){if(!e||e.length<2)return"";const n=Math.min(...e,s.min??1/0),i=Math.max(...e,s.max??-1/0),o=Math.max(4,(i-n)*.12),c=Math.max(0,n-o),r=Math.min(100,i+o),l=r-c||1,h=v=>(v-c)/l*100,p=e.map((v,_)=>({v,i:_})).sort((v,_)=>v.v-_.v),$=new Array(e.length).fill(0);return p.forEach((v,_)=>{_&&h(v.v)-h(p[_-1].v)<3.2&&($[v.i]=$[p[_-1].i]+1)}),`
  <figure class="spr">
    <figcaption class="spr__cap"><b>${d(a)}</b>, one mark per video</figcaption>
    <div class="spr__axis">
      <span class="spr__band"
            style="left:${h(s.min).toFixed(3)}%;width:${(h(s.max)-h(s.min)).toFixed(3)}%"></span>
      <span class="spr__mean" style="left:${h(s.mean).toFixed(3)}%"></span>
      ${e.map((v,_)=>`
        <span class="spr__pt" style="left:${h(v).toFixed(3)}%;--lv:${$[_]}">${t?`<b aria-hidden="true">${t[_]}</b>`:""}<span class="sr-only">${t?`Video ${t[_]}, `:""}${j(v)}</span></span>`).join("")}
    </div>
    <div class="spr__ends"><span>${j(c)}</span><span>${j(r)}</span></div>
    <dl class="spr__key">
      <div><dt>Lowest</dt><dd class="t-read">${j(s.min)}</dd></div>
      <div class="is-mean"><dt>Mean</dt><dd class="t-read">${j(s.mean)}</dd></div>
      <div><dt>Highest</dt><dd class="t-read">${j(s.max)}</dd></div>
      <div><dt>Range</dt><dd class="t-read">${j(s.spread)}</dd></div>
      <div><dt>Standard deviation</dt><dd class="t-read">${j(s.stdev)}</dd></div>
    </dl>
  </figure>`}function fe(e,s=null){const a=e.summary||{},t=a.authenticity||{},n=a.brand_health||{},i=(e.members||[]).map((r,l)=>({m:r,n:String(l+1).padStart(2,"0")})).filter(({m:r})=>r.analysed!==!1),o=(r,l)=>Array.isArray(r)&&r.length===i.length&&r.every((h,p)=>i[p].m[l]===h),c=(r,l)=>o(r,l)?i.map(h=>h.n):null;return`
  <section class="sf" data-act="spread" aria-labelledby="sf-h">
    <h2 id="sf-h" class="sr-only">What the videos found together</h2>
    ${a.spread_verdict?`<p class="sf__verdict">${d(a.spread_verdict)}.</p>`:""}
    <p class="cx-lede">
      The average is the least informative number here. The range says how far
      apart the videos actually were.
    </p>
    <div class="sf__plots">
      ${ve(t.values,t,"Authenticity",c(t.values,"authenticity_score"))}
      ${ve(n.values,n,"Brand health",c(n.values,"brand_health_score"))}
    </div>
    <p class="sf__not cx-note">${[a.note,a.means_not].filter(Boolean).map(d).join(" ")}</p>

    ${e.bias_caveat?`<p class="sf__fn cav"><span aria-hidden="true">&dagger;</span> ${d(e.bias_caveat)}</p>`:`<p class="sf__fn cav">This sweep carries no caveat text of its own, which
           is unusual and is stated rather than passed over.</p>`}
  </section>`}function we(e){const s=e.members||[],a=s.filter(t=>t.analysed!==!1);return`
  <div class="mem__head" data-act="members">
    <h2 class="cx-h">The ${u(a.length)} videos, on one clock</h2>
    <p class="cx-lede">
      Every trace is drawn against the same clock, so a shorter video stops where
      it actually stops. The frame is each video&rsquo;s most contested moment.
      A title opens that video&rsquo;s own book.
    </p>
  </div>
  <ul class="mem" data-members data-cx-flow>
    ${s.map((t,n)=>{const i=t.analysed!==!1;return`
      <li class="mem__one${i?"":" is-failed"}" id="mem-${d(t.video_id)}" data-video="${d(t.video_id)}">
        <div class="mem__plate" data-plate="${d(t.video_id)}">
          <span class="mem__n t-read">${String(n+1).padStart(2,"0")}</span>
        </div>
        <div class="mem__body">
          <h3 class="mem__t">${i?`<a href="/brand/${encodeURIComponent(e.sweep_id)}/${encodeURIComponent(t.video_id)}"
                  data-open-member>${d(t.title||t.video_id)}</a>`:d(t.title||t.video_id)}</h3>
          <p class="mem__meta">
            ${[t.channel?d(t.channel):"",t.duration_s?ne(t.duration_s):"",t.comment_count?`${u(t.comment_count)} comments`:""].filter(Boolean).join('<span class="mem__sep" aria-hidden="true"></span>')}
          </p>
          ${i?`
            <div class="mem__trace" data-trace="${d(t.video_id)}">
              <p class="mem__loading">Reading this video&rsquo;s run</p>
            </div>
            <dl class="mem__nums">
              <div><dt>Authenticity</dt><dd class="t-read">${j(t.authenticity_score)}</dd></div>
              <div><dt>Brand health</dt><dd class="t-read">${j(t.brand_health_score)}</dd></div>
            </dl>`:`<p class="mem__failed">Not analysed. ${d((e.failed||[]).find(o=>o.video_id===t.video_id)?.reason||"No reason was recorded.")}</p>`}
        </div>
      </li>`}).join("")}
  </ul>`}function ds(e,s){if(!s.length)return`<p class="cx-note">No video in this sweep could be read, so there is
      nothing to count per channel.</p>`;const a=Object.fromEntries(ee.map(i=>[i,{read:0,total:0}]));let t=0,n=0;for(const{report:i,segments:o}of s){const c=it(o,i.comment_sentiment);for(const r of ee)a[r].read+=c[r].read,a[r].total+=c[r].total;for(const r of o){const l=Object.values(ct(r,i.comment_sentiment));l.length>=2&&(n+=1,new Set(l).size>1&&(t+=1))}}return`
    <ul class="cvx">
      ${ee.map(i=>{const o=a[i],c=o.total?o.read/o.total*100:0,r=se[i];return`
        <li class="cvx__row" data-channel="${i}" style="--ch:var(--ch-${i})">
          <p class="cvx__name"><i class="mo__mark" data-mark="${i}" aria-hidden="true"></i>${d(r.label)}
            <span>${d(r.reads)}</span></p>
          <span class="cvx__track" aria-hidden="true"><i style="--to:${c.toFixed(2)}%"></i></span>
          <p class="cvx__v"><span class="t-read">${D(c,1)}</span>
            ${u(o.read)} of ${u(o.total)} segments</p>
        </li>`}).join("")}
    </ul>
    <p class="sp__count cx-text">
      Across ${u(n)} segments where at least two channels returned a
      reading, ${u(t)}
      (${D(n?t/n*100:0,1)}) had the
      channels disagreeing with one another. That is the raw rate of
      disagreement, before the controller scored any of it.
    </p>`}function ls(e){const s=e.flatMap(({segments:n})=>n);if(!s.length)return"";const a=rt(s);if(!a.attributed)return`
    <div class="pairs pairs--none">
      <h3 class="cx-h3">Which channels the controller named</h3>
      <p class="cx-note">
        On none of the ${u(a.total)} segments in this sweep did the
        controller name which channels it thought were in conflict. That is a
        measured property of the model rather than a gap in this page. The
        down-weighting that depends on knowing which channel dissented runs off
        the pipeline&rsquo;s own channel labels instead, which need no model
        compliance.
      </p>
    </div>`;const t=Math.max(...a.pairs.map(n=>n.count),1);return`
  <div class="pairs">
    <h3 class="cx-h3">Which channels the controller named together</h3>
    <p class="cx-note">
      Counted on the ${u(a.attributed)} of ${u(a.total)} segments
      where the controller named any channel at all.
      ${a.unknown?`${u(a.unknown)} names it used were not recognised
        and are counted as unattributable rather than dropped into a bucket.`:""}
    </p>
    <ul class="pairs__list">
      ${a.pairs.map(n=>`
        <li>
          <span class="pairs__who">
            <i style="--ch:var(--ch-${n.a})"></i><i style="--ch:var(--ch-${n.b})"></i>
            ${d(se[n.a].short)} and ${d(se[n.b].short)}
          </span>
          <span class="pairs__track" aria-hidden="true">
            <i style="--to:${(n.count/t*100).toFixed(2)}%"></i></span>
          <span class="t-read">${u(n.count)}</span>
          <span class="pairs__share">${D(n.share*100,1)}</span>
        </li>`).join("")}
    </ul>
  </div>`}function ge(e,s=""){const a=[e.bias_caveat,e.vocal_caveat].filter(Boolean);return a.length?`
  <section class="lm" data-act="caveats" aria-labelledby="cv-h">
    <h2 id="cv-h" class="cx-h">What limits the reading</h2>
    <ol class="lm__notes">
      ${a.map((t,n)=>`
        <li class="lm__note">
          <p class="lm__k"><span class="lm__n">${n+1}</span>${t===e.bias_caveat?"Facial emotion":"Vocal prosody"}</p>
          <p class="cav">${d(t)}</p>
        </li>`).join("")}
    </ol>
    ${s}
  </section>`:`
    <section class="lm" data-act="caveats">
      <h2 class="cx-h">What limits the reading</h2>
      <p class="cav">This sweep carries no caveat text of its own, which
        is unusual and is stated rather than passed over.</p>
    </section>`}const Z=["POSITIVE","NEUTRAL","NEGATIVE"];function Fe(e,s,a){return`
  <div class="au__band" role="img" aria-label="${a}: ${Z.map(t=>`${u(e[t]||0)} ${t.toLowerCase()}`).join(", ")}, of ${u(s)} comments">
    ${Z.map(t=>`<i data-k="${t}" style="--n:${e[t]||0}"></i>`).join("")}
  </div>`}function be(e,s=""){const a=e.summary||{},t=a.comment_distribution||{},n=Object.values(t).reduce((o,c)=>o+c,0),i=nt(t);return`
  <section class="au" data-act="audience" aria-labelledby="au-h">
    <h2 id="au-h" class="cx-h">Every audience, pooled</h2>
    <p class="cx-lede">
      ${u(n)} comments across ${u(a.video_count)} videos,
      classified one at a time and counted together. No author identifier was
      stored at any point. Comments are one reading per video, not per moment.
    </p>
    ${n?`
    <figure class="au__fig">
      ${Fe(t,n,"Every audience pooled")}
      <dl class="au__nums">
        ${Z.map(o=>`
          <div data-k="${o}"><dt><i class="cm__glyph" aria-hidden="true"></i>${o.toLowerCase()}</dt>
            <dd class="t-read">${u(t[o]||0)}</dd>
            <dd class="au__pct">${D((t[o]||0)/n*100,1)}</dd></div>`).join("")}
      </dl>
    </figure>`:'<p class="cx-note">No comment distribution was recorded for this sweep.</p>'}
    ${i&&i.nearTie?`
      <p class="pool__tie cx-note">
        The top two are within ${D(i.margin*100,1)} of each other across the
        whole pool. Reporting the leading label as the audience verdict would
        overstate it, so the counts are given rather than one word.
      </p>`:""}
    ${s}
  </section>`}function hs(e,s){if(!s.length)return'<p class="cx-note">No video in this sweep could be read.</p>';const a=new Map(s.map(n=>[n.videoId,n]));return`
    <ul class="each">
      ${(e.members||[]).filter(n=>n.analysed!==!1).map(n=>{const i=(e.members||[]).indexOf(n),o=a.get(n.video_id),c=o?o.report.comment_sentiment||{}:{},r=c.distribution||{},l=Object.values(r).reduce((h,p)=>h+p,0);return`
        <li class="each__one">
          <p class="each__t"><span class="t-read">${String(i+1).padStart(2,"0")}</span>${d(n.title||n.video_id)}</p>
          ${l?`${Fe(r,l,`Video ${i+1}`)}
            <p class="each__v">${Z.map(h=>`${u(r[h]||0)} ${h.toLowerCase()}`).join(", ")}${c.label?`; classified <b>${d(String(c.label).toLowerCase())}</b>`:""}</p>`:'<p class="each__v is-absent">No comment distribution was recorded.</p>'}
        </li>`}).join("")}
    </ul>`}function Pe(e,s){const a=[];(e.subject||"").trim().toLowerCase()!==(s.subject||"").trim().toLowerCase()&&a.push("They are about different subjects, so any difference between them is a difference between two things rather than a change in one."),e.controller&&s.controller&&e.controller!==s.controller&&a.push(`They were scored by different controller models (${e.controller} and ${s.controller}). Swapping only the controller moved mean Authenticity across this project's corpus by 49.08 points, so these two numbers are not measuring the same thing.`);const t=((e.summary||{}).authenticity||{}).values||[],n=((s.summary||{}).authenticity||{}).values||[];return(t.length<2||n.length<2)&&a.push("One of them has fewer than two analysed videos, so it has no range to compare against."),e.window===s.window&&e.offset_days===s.offset_days&&a.push("They cover the same period, so there is no before and after between them."),a}function B(e){const s=is[e.window]||e.window||"an unrecorded period";return e.offset_days&&Number(e.offset_days)?`${s}, ending ${u(Number(e.offset_days))} days ago`:s}function ye(e,s,a=!1){return`
  <section class="cpp" data-act="compare" aria-labelledby="cp-h">
    <h2 id="cp-h" class="cx-h">Hold this against another period</h2>
    <p class="cx-lede">
      ${u(s.length)} other sweep${s.length===1?"":"s"} on
      this machine ${s.length===1?"covers":"cover"} the same
      subject. ${a?"Choosing one holds the two against each other measure by measure, and video by video where the same video is in both, or says why they cannot be compared.":"Choosing one puts both on a single scale with a divider you can drag between them, or says why the two cannot be compared."}
    </p>
    <p class="cx-note">This volume covers ${d(B(e))}.</p>
    <div class="cp__pick">
      ${s.map(t=>`
        <button class="chip" type="button" data-sib="${d(t.sweep_id)}"
                aria-pressed="false">${d(B(t))}
          <span class="chip__n t-read">${j((t.summary?.authenticity||{}).mean??t.authenticity)}</span>
        </button>`).join("")}
    </div>
  </section>`}function ps(e,s){const a=Pe(e,s);if(a.length)return`
    <div class="cp__refuse">
      <h3 class="cx-h">These two cannot honestly be compared</h3>
      <ol class="cp__why">
        ${a.map(r=>`<li class="cx-text">${d(r)}</li>`).join("")}
      </ol>
      <p class="cx-note">
        Both are still readable on their own, and each one&rsquo;s range is on
        its own page. What is refused here is putting them on one axis and
        calling the difference a change.
      </p>
    </div>`;const t=(e.summary||{}).authenticity||{},n=(s.summary||{}).authenticity||{},i=(e.summary||{}).brand_health||{},o=(s.summary||{}).brand_health||{},c=[["Authenticity",t.mean,n.mean],["Lowest video",t.min,n.min],["Highest video",t.max,n.max],["Range",t.spread,n.spread],["Brand health",i.mean,o.mean]];return`
  <div class="cp" data-cp style="--split:50%">
    <div class="cp__heads">
      <p class="cx-h3">${d(B(e))}</p>
      <p class="cx-h3 cp__right">${d(B(s))}</p>
    </div>

    <div class="cp__stage">
      <div class="cp__side cp__side--a">
        ${c.map(([r,l])=>`
          <div class="cp__row">
            <span class="cp__k">${d(r)}</span>
            <b class="t-read">${j(l)}</b>
          </div>`).join("")}
      </div>
      <div class="cp__side cp__side--b" aria-hidden="true">
        ${c.map(([r,,l])=>`
          <div class="cp__row">
            <span class="cp__k">${d(r)}</span>
            <b class="t-read">${j(l)}</b>
          </div>`).join("")}
      </div>

      <input class="cp__handle" type="range" min="0" max="100" value="50" step="0.5"
             aria-label="Drag between the two periods"
             data-split>
      <span class="cp__line" aria-hidden="true"></span>
    </div>

    <table class="cp__table">
      <caption class="sr-only">Both periods, and the difference between them</caption>
      <thead>
        <tr><th scope="col">Measure</th>
            <th scope="col">${d(B(e))}</th>
            <th scope="col">${d(B(s))}</th>
            <th scope="col">Change</th></tr>
      </thead>
      <tbody>
        ${c.map(([r,l,h])=>{const p=typeof l=="number"&&typeof h=="number"?h-l:null;return`
          <tr>
            <th scope="row">${d(r)}</th>
            <td class="t-read">${j(l)}</td>
            <td class="t-read">${j(h)}</td>
            <td class="t-read${p!=null&&Math.abs(p)>=5?" is-tear":""}">${p==null?"&mdash;":`${p>0?"+":""}${p.toFixed(2)}`}</td>
          </tr>`}).join("")}
      </tbody>
    </table>

    <p class="cx-note">
      Both sweeps were scored by <code>${d(e.controller||"an unrecorded model")}</code>.
      A change here is a change in what these videos about this subject did, not a
      measurement of the subject itself, and a handful of videos is too few to generalise from.
    </p>
  </div>`}function xe(e,s=!0){const a=e.selection||{},t=a.rejected||[],n=e.failed||[];return`
  <section class="prv" data-act="provenance" aria-labelledby="pr-h">
    <h2 id="pr-h" class="cx-h">Where these videos came from</h2>
    <dl class="prov">
      <div><dt>Searched as</dt><dd><code>${d(a.query_used||"not recorded")}</code></dd></div>
      <div><dt>Published after</dt><dd>${d(a.published_after||"not recorded")}</dd></div>
      ${a.published_before?`<div><dt>Published before</dt><dd>${d(a.published_before)}</dd></div>`:""}
      <div><dt>Considered</dt><dd>${u(a.considered)} videos</dd></div>
      <div><dt>Refused</dt><dd>${u(t.length)} videos</dd></div>
      <div><dt>Controller</dt><dd><code>${d(e.controller||"not recorded")}</code></dd></div>
    </dl>

    ${n.length?`
      <div class="prov__failed" id="prov-failed" tabindex="-1">
        <h3 class="cx-h3">Selected, then could not be analysed</h3>
        <ul class="prov__list">
          ${n.map(i=>`
            <li><b>${d(i.title||i.video_id||"A video")}</b>
              <span>${d(i.reason||"no reason recorded")}</span></li>`).join("")}
        </ul>
      </div>`:""}

    ${s?"<div data-pairs></div>":""}
  </section>`}function ke(e){const s=(e.selection||{}).rejected||[];return`
  <div class="ref__head">
    <h3 class="cx-h3">${s.length?`The ${u(s.length)} that were refused, and why`:"Nothing was refused"}</h3>
    <p class="ref__range" data-ref-range></p>
  </div>
  <ul class="prov__list ref__list" data-cx-flow>
    ${s.map(a=>`
      <li><b>${d(a.title||a.video_id||"A video")}</b>
        <span>${d(a.verdict||a.reason||"no reason recorded")}</span></li>`).join("")}
  </ul>
  ${s.length?"":`<p class="cx-note">Every video the search considered and
    selected was taken; none was turned away by the selection rules.</p>`}`}async function us(e){const s=(e.members||[]).filter(t=>t.analysed!==!1);return(await Promise.all(s.map(async t=>{try{const n=await ot(e.sweep_id,t.video_id),i=(n.all_segments||[]).filter(o=>typeof o.start_s=="number"&&typeof o.end_s=="number");return i.length?{m:t,videoId:t.video_id,report:n,segments:i}:null}catch{return null}}))).filter(Boolean)}function ms(e,s){if(!e.length){for(const t of w.querySelectorAll("[data-trace]"))t.innerHTML='<p class="mem__loading">This video&rsquo;s run could not be read.</p>';return}const a=Math.max(...e.map(({segments:t})=>Math.max(...t.map(n=>n.end_s))));for(const{m:t,report:n,segments:i}of e){const o=w.querySelector(`[data-trace="${CSS.escape(t.video_id)}"]`);if(o){const h=Math.max(...i.map($=>$.end_s));o.innerHTML=`<div class="mem__scaled"
        style="width:${(h/a*100).toFixed(2)}%"></div>`;const p=lt(h,i);ht(o.querySelector(".mem__scaled"),{report:n,segments:i,clock:p,compact:!0,label:t.title||t.video_id})}const c=i.reduce((h,p)=>(p.conflict_score??-1)>(h.conflict_score??-1)?p:h,i[0]),r=Ee(s,pt(n),c),l=w.querySelector(`[data-plate="${CSS.escape(t.video_id)}"]`);if(l&&r){const h=new Image;h.alt="",h.decoding="async",h.onerror=()=>h.remove(),h.src=r,l.prepend(h),l.classList.add("has-img")}}for(const t of w.querySelectorAll("[data-trace]"))t.querySelector(".mem__loading")&&!e.some(n=>n.m.video_id===t.dataset.trace)&&(t.innerHTML='<p class="mem__loading">This video&rsquo;s run could not be read.</p>')}const Re={week:7,month:30,half:182,year:365};function Se(e){const s=Number(e.offset_days||0);return[s,s+(Re[e.window]||0)]}function _s(e,s){const[a,t]=Se(e),n=i=>{const[o,c]=Se(i);return o>=t||a>=c};return[...s].sort((i,o)=>Number(n(o))-Number(n(i)))}function $s(e){const s=t=>{const n=t&&t.closest&&t.closest("[data-vid]"),i=t&&t.closest&&t.closest("[data-cx-spread]");i&&(n&&i.contains(n)?i.dataset.hl=n.dataset.vid:delete i.dataset.hl)},a=()=>{for(const t of e.querySelectorAll("[data-cx-spread][data-hl]"))delete t.dataset.hl};e.addEventListener("pointerover",t=>s(t.target)),e.addEventListener("focusin",t=>s(t.target)),e.addEventListener("pointerleave",a)}function vs(e){const s=e.querySelector("[data-vt-body]");if(!s)return;const a=s.closest("table");for(const t of a.querySelectorAll("[data-sort]"))t.addEventListener("click",()=>{const n=t.dataset.sort,i=t.closest("th"),o=i.getAttribute("aria-sort")!=="ascending";for(const h of a.querySelectorAll("th[aria-sort]"))h.removeAttribute("aria-sort");i.setAttribute("aria-sort",o?"ascending":"descending");const c=[...s.querySelectorAll("tr")],r=h=>{const p=h.getAttribute(`data-sort-${n}`);return p===null||p===""?null:Number(p)},l=He()?null:ce.getState(c);c.sort((h,p)=>{const $=r(h),v=r(p);return $===null&&v===null?Number(h.dataset.sortN)-Number(p.dataset.sortN):$===null?1:v===null?-1:o?$-v:v-$}),s.append(...c),l&&ce.from(l,{duration:.45,ease:"power2.inOut"}),qe(`Sorted by ${t.textContent.trim()}, ${o?"lowest":"highest"} first.`)})}function fs(e,s){const a=e.querySelector(".mx"),t=e.querySelector("[data-mx-detail]");if(!a||!t)return;const n=[...a.querySelectorAll("[data-cell]")],i=a.querySelectorAll("thead .mx__vid").length||1,o=c=>{const[r,l]=c.dataset.cell.split(":");t.innerHTML=Ht(s,r,Number(l))};for(const c of n)c.addEventListener("focus",()=>o(c)),c.addEventListener("pointerenter",()=>o(c)),c.addEventListener("click",()=>o(c));a.addEventListener("keydown",c=>{const r=n.indexOf(document.activeElement);if(r<0)return;const l={ArrowRight:1,ArrowLeft:-1,ArrowDown:i,ArrowUp:-i,Home:-r,End:n.length-1-r}[c.key];if(l===void 0)return;const h=n[r+l];h&&(c.preventDefault(),n[r].tabIndex=-1,h.tabIndex=0,h.focus())})}function ws(e,s){const a=e.querySelector("[data-sg-detail]");if(!a)return;const t=n=>{a.innerHTML=Jt(s,n.dataset.sign,Number(n.dataset.n))};for(const n of e.querySelectorAll(".sgx__dot"))n.addEventListener("focus",()=>t(n)),n.addEventListener("pointerenter",()=>t(n)),n.addEventListener("click",()=>t(n))}async function gs(){Be(),Ie({here:"/library"});const e=dt(),s=rs();if(!s){te("No sweep named","This address does not name a combined report.","Combined reports are listed in the library.",'<a class="btn" href="/library">Open the library</a>');return}let a=null;try{a=await le(s)}catch(f){f&&f.status===404?te("Not found","There is no sweep saved under that id.","It may have been removed from the outputs directory since the link was made.",'<a class="btn" href="/library">Open the library</a>'):te("Unreachable","The combined report could not be read.",`The backend answered: ${d(f&&f.message||"no reason given")}.`,'<a class="btn" href="/library">Open the library</a>');return}const[t,n]=await Promise.all([et().catch(()=>[]),tt(a.sweep_id||s).then(f=>f&&f.facts?f:null).catch(()=>null)]);let i=(t||[]).filter(f=>f.sweep_id!==a.sweep_id&&(f.subject||"").trim().toLowerCase()===(a.subject||"").trim().toLowerCase());i=_s(a,i);const o=n?qt(a,n):null;e&&(w.dataset.opening="yes");const c=()=>`
    <p class="ref__range ref__range--cont" data-ref-range></p>
    <ul class="prov__list ref__list" data-cx-flow></ul>`,r=()=>'<ul class="mem" data-cx-flow></ul>',l=()=>`<section class="cv" aria-labelledby="cv2-h">
          <h2 id="cv2-h" class="cx-h">What each channel managed to read</h2>
          <p class="cx-lede">Counted across every segment of every video in this sweep
            that could be read. A channel that returned nothing for a segment is
            counted as a gap, never as a neutral reading.</p>
          <div data-channels><p class="mem__loading">Reading the videos&rsquo; runs</p></div>
        </section>`,h=f=>g=>!g||!g.moment||!Number.isFinite(g.moment.start)?null:Ee(f,g.video_id,{start_s:g.moment.start,end_s:g.moment.end??g.moment.start}),p=o&&o.reading&&o.reading.product_groups,$=!!(o&&a.subject_kind==="brand"&&p&&p.length),v=o?await pe():null,_=o?[{id:"overview",label:"Overview",spreads:[q({key:"overview",plain:["verso","recto"],verso:$e(a,o),recto:Et(o)}),q({key:"overview-2",plain:["recto"],verso:Nt(o),recto:fe(a,o)})]},{id:"videos",label:"The videos",spreads:[q({key:"videos-table",wide:!0,verso:Ft(o)}),q({key:"videos-vs",verso:Pt(o),recto:Rt(o,h(v))}),q({key:"videos-tone",wide:!0,verso:Wt(o)}),q({key:"videos-moments",wide:!0,verso:It(o,h(v))}),q({key:"videos",verso:we(a),recto:r()})]},{id:"consensus",label:"Consensus",spreads:[...o.themes.length?[q({key:"consensus-matrix",wide:!0,verso:Ot(o,$?p:null)})]:[],q({key:"consensus",verso:Vt(o),recto:Dt(o)})]},...$?[{id:"products",label:"Products",spreads:[q({key:"products",verso:Ut(o),recto:zt(o)})]}]:[],{id:"audience",label:"Audience",spreads:[q({key:"audience",verso:Gt(o),recto:Yt(o)}),q({key:"audience-2",verso:Xt(o),recto:be(a)})]},...i.length?[{id:"period",label:"Another period",spreads:[q({key:"period",verso:`${ye(a,i,!0)}<div data-checks-host></div>`,recto:`<div class="cp__host" data-compare-host>
          <p class="cx-note">Choose a period on the facing page to hold it against this one.</p></div>`}),q({key:"period-2",verso:"<div data-twice-host></div>",recto:`<div data-themes-host></div>${os(a,Re[a.window]||0)}`})]}]:[],{id:"trust",label:"Trust",spreads:[q({key:"trust",verso:Zt(o),recto:Kt(o)}),q({key:"channels",verso:l(),recto:`<section class="prs" aria-labelledby="prs-h"><h2 id="prs-h" class="cx-h">Which channels disagreed</h2>
          <p class="cx-lede">Read off the controller's own record of which channels it saw in conflict, across every
            segment of every video.</p><div data-pairs></div></section>`}),q({key:"provenance",verso:ge(a),recto:xe(a,!1)}),q({key:"provenance-refused",verso:ke(a),recto:c()})]}].map(f=>({...f,html:re(f)})):[{id:"overview",label:"Overview",spreads:[q({key:"overview",plain:["verso","recto"],verso:$e(a),recto:fe(a)})]},{id:"videos",label:"The videos",spreads:[q({key:"videos",verso:we(a),recto:r()})]},{id:"channels",label:"Channels",spreads:[q({key:"channels",verso:l(),recto:ge(a)})]},{id:"audience",label:"Audience",spreads:[q({key:"audience",verso:be(a),recto:`<section class="ea" aria-labelledby="ea-h">
          <h2 id="ea-h" class="cx-h">Each audience on its own</h2>
          <p class="cx-lede">The pooled figure can hide a video whose audience said the
            opposite of the rest, so each is drawn separately on the same scale.</p>
          <div data-each><p class="mem__loading">Reading the videos&rsquo; runs</p></div>
        </section>`})]},...i.length?[{id:"period",label:"Another period",spreads:[q({key:"period",verso:ye(a,i),recto:`<div class="cp__host" data-compare-host>
          <p class="cx-note">Choose a period on the facing page to hold it against this one.</p>
        </div>`})]}]:[],{id:"provenance",label:"Provenance",spreads:[q({key:"provenance",verso:xe(a),recto:ke(a)})]}].map(f=>({...f,html:re(f)})),b=a.subject||"Combined report";w.dataset.codex="yes",w.innerHTML=Ye({title:d(b),chapters:_,backHref:"/library",backLabel:"Close the book"});const E=`sweep:${a.sweep_id||s}`;Qe(w,{link:w.querySelector("[data-cx-close]"),cover:e&&e.cover,before:()=>he(E,"close")}),window.addEventListener("pagehide",()=>he(E,"leave"));const k=Xe(w,{title:b,onSpread:f=>de(f)}),F=[...w.querySelectorAll("[data-members] > li")],y=[...w.querySelectorAll(".ref__list > li")];k&&(k.flow({chapter:"videos",items:F,cont:f=>q({key:`videos-${f}`,cont:!0,verso:r(),recto:r()})}),y.length&&k.flow({chapter:o?"trust":"provenance",items:y,cont:f=>q({key:`provenance-${f}`,cont:!0,verso:c(),recto:c()}),after:f=>{for(const g of f){const N=g.parentElement.querySelector("[data-ref-range]");if(!N)continue;const R=y.indexOf(g.firstElementChild);N.textContent=g.childElementCount?`${u(R+1)} to ${u(R+g.childElementCount)} of ${u(y.length)}`:`End of the list, all ${u(y.length)} shown`}}})),document.title=`${b} — BrandPulse`,delete document.documentElement.dataset.carrying,clearTimeout(window.__bpFallback),requestAnimationFrame(()=>Ze(w,e));for(const f of w.querySelectorAll("[data-open-member]"))f.addEventListener("click",()=>{Oe(f.closest(".mem__one").querySelector(".tp"))});if(o&&($s(w),vs(w),fs(w,o),ws(w,o),k)){w.addEventListener("click",f=>{const g=f.target.closest("[data-evv]"),N=f.target.closest("[data-evh]");if(g){const R=w.querySelector(`.vt__row[data-vid="${CSS.escape(g.dataset.evv)}"]`);if(!R)return;k.reveal(R);const C=R.closest("[data-cx-spread]");C&&(C.dataset.hl=g.dataset.evv)}else if(N){const R=w.querySelector(`#theme-${CSS.escape(N.dataset.evh)}`);if(!R)return;k.reveal(R);const C=R.querySelector("[data-cell]");C&&requestAnimationFrame(()=>C.focus({preventScroll:!0}))}});for(const f of w.querySelectorAll("[data-cx-goto-trust]"))f.addEventListener("click",g=>{g.preventDefault(),k.goChapter("trust")})}const m=w.querySelector("[data-compare-host]");for(const f of w.querySelectorAll("[data-sib]"))f.addEventListener("click",async()=>{for(const C of w.querySelectorAll("[data-sib]"))C.setAttribute("aria-pressed",String(C===f));m.innerHTML='<p class="cx-note">Reading that sweep</p>';let g=null,N=null;try{[g,N]=await Promise.all([le(f.dataset.sib),o?st(a.sweep_id,f.dataset.sib).catch(()=>null):Promise.resolve(null)])}catch{m.innerHTML='<p class="cx-note u-tear">That sweep could not be read.</p>';return}const R=Pe(a,g).length>0;if(o&&N&&N.comparable&&!R){const C=[B(a),B(g)];w.querySelector("[data-checks-host]").innerHTML=ts(N,C),m.innerHTML=ss(N,C),w.querySelector("[data-twice-host]").innerHTML=as(N,C),w.querySelector("[data-themes-host]").innerHTML=ns(N,C,[`python write_analysis.py --sweep ${a.sweep_id}`,`python write_analysis.py --sweep ${g.sweep_id}`]);for(const We of w.querySelectorAll('[data-cx-key^="period"]'))delete We.dataset.drawn;const J=m.closest("[data-cx-spread]");J&&!J.hidden&&de(J),k&&k.relayout()}else{m.innerHTML=ps(a,g);const C=w.querySelector("[data-checks-host]");C&&(C.innerHTML=""),x()}if(f.dataset.quiet){delete f.dataset.quiet;return}qe(R?"Those two cannot honestly be compared. The reasons are on the facing page.":`Comparing ${B(a)} with ${B(g)}.`)});const T=w.querySelector("[data-sib]");T&&(T.dataset.quiet="yes",T.click());function x(){const f=m.querySelector("[data-cp]"),g=m.querySelector("[data-split]");if(!f||!g)return;const N=()=>f.style.setProperty("--split",`${g.value}%`);g.addEventListener("input",N),N()}const[L,W]=await Promise.all([us(a),v?Promise.resolve(v):pe()]);ms(L,W),w.querySelector("[data-channels]").innerHTML=ds(a,L);const H=w.querySelector("[data-each]");H&&(H.innerHTML=hs(a,L)),w.querySelector("[data-pairs]").innerHTML=ls(L),k&&k.relayout()}gs();
