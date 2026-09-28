/* ===========================================================================
   written.js — the written report's pages, as printed in the book.

   The pipeline's last stage (pipeline/analyst.py) reads a finished run and
   writes it up: what the reviewer liked and disliked, what the audience talks
   about, whether the two agree, how far to trust the reading, and the signs of
   a commercial interest. This module prints that onto pages.

   Two kinds of thing arrive, and they are printed differently on purpose:

     facts     computed by code (analyst_facts.py): every figure, every level,
               every sign. Always present, even before the model has run.
     written   the model's words, each one checked against the run before it
               was kept (analyst_verify.py). A sentence the model wrote is
               marked as the model's; a sentence built by code where the
               model's did not pass is marked as that.

   Every sentence of the model's carries its evidence as buttons: a time goes
   to that moment, a comment number to that comment. Where the model has not
   run for a report, a page says so plainly and prints what it can.
   ======================================================================== */

import { count, esc, mmss, pct, confidence } from "./format.js";
import { tugBar, toneArc, timeBars, themeBars, dumbbells, signed } from "./charts.js";

/* ------------------------------------------------------- small parts ---- */

/** A quotation cut to `n` words, with an ellipsis where it was cut. */
export function cut(text, n) {
  const words = String(text || "").split(/\s+/).filter(Boolean);
  return words.length > n ? `${words.slice(0, n).join(" ")}\u2026` : words.join(" ");
}

/**
 * What the four readings of one moment were, in a sentence built from the
 * labels alone, so it cannot disagree with the grid printed above it. Printed
 * where the model's own note was dropped by the checks or not yet written.
 * Added 24 Sep 2026: the final user evaluation found a model note that said
 * the voice read positive beside a grid that said neutral.
 */
const READINGS = [["transcript", "words"], ["facial", "face"], ["vocal", "voice"], ["comment", "comments"]];
export function readingsSentence(valences) {
  const v = valences || {};
  const and = (xs) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
  const groups = new Map();
  const unread = [];
  for (const [key, name] of READINGS) {
    if (!v[key]) { unread.push(name); continue; }
    const value = String(v[key]).toLowerCase();
    if (!groups.has(value)) groups.set(value, []);
    groups.get(value).push(name);
  }
  const parts = [...groups.entries()].map(([value, names], i) =>
    (i === 0 ? `the ${and(names)} read ${value}` : `the ${and(names)} ${value}`));
  let said = "";
  if (parts.length === 1) {
    const [[value, names]] = [...groups.entries()];
    said = names.length === 1 ? `Only the ${names[0]} could be read: ${value}.`
      : `The ${and(names)} all read ${value}.`;
  } else if (parts.length === 2) {
    said = `${parts[0]}, and ${parts[1]}.`;
  } else if (parts.length > 2) {
    said = `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}.`;
  }
  said = said.charAt(0).toUpperCase() + said.slice(1);
  if (!parts.length) return "No channel could be read at this moment.";
  return unread.length ? `${said} The ${and(unread)} could not be read.` : said;
}

/**
 * IN SHORT (24 Sep 2026). Four of the five people in the final user
 * evaluation asked for a plain bottom line at the top of the book. What the
 * system can state is how much evidence the reading rests on, whether the
 * readings disagreed strongly anywhere, and whether a paid promotion was
 * declared -- and, because a verdict on honesty is exactly what it cannot give
 * (baseline_bench: rho = +0.0575 against people's ratings), it says that too.
 * Every clause is a fact the book already prints; no model writes this.
 */
const SHORT_COVER = {
  well_covered: "Plenty of evidence behind this reading.",
  partly_covered: "Some of the evidence behind this reading is thin.",
  thinly_covered: "The evidence behind this reading is thin.",
  unknown: "How much evidence is behind this reading is unknown.",
};
const SHORT_PAID = {
  present: "The creator declared a paid promotion.",
  absent: "No paid promotion was declared.",
  not_checked: "Whether a paid promotion was declared could not be checked.",
};
export function inShort(a) {
  const f = a && a.facts;
  if (!f) return "";
  const level = f.confidence && f.confidence.level;
  const flagged = Number(f.flagged) || 0;
  const conflict = flagged
    ? `${count(flagged)} of ${count(f.segments)} segments ${flagged === 1 ? "was" : "were"} flagged for strong disagreement.`
    : "No segment was flagged for strong disagreement.";
  const s1 = ((f.signs && f.signs.signs) || []).find((s) => s.id === "S1");
  const paid = SHORT_PAID[s1 && s1.state] || SHORT_PAID.not_checked;
  return `${SHORT_COVER[level] || SHORT_COVER.unknown} ${conflict} ${paid} It cannot say whether the reviewer is honest.`;
}

/** The plain line as printed on a title page. */
export function inShortBlock(text) {
  return text ? `<div class="ti__short" role="note"><p class="ti__shk">In short</p>
    <p class="ti__shp">${esc(text)}</p></div>` : "";
}

const LEVEL = {
  well_covered: { word: "Well covered", dots: 3 },
  partly_covered: { word: "Partly covered", dots: 2 },
  thinly_covered: { word: "Thinly covered", dots: 1 },
  unknown: { word: "Coverage unknown", dots: 0 },
};

/** Evidence ids as buttons. `lookup` resolves S (segment) ids to a time. */
export function chips(ids, lookup) {
  const out = (ids || []).map((id) => {
    const kind = id[0], n = Number(id.slice(1));
    if (kind === "S" && lookup.segment(n)) {
      return `<button class="ev" type="button" data-ev="${id}"
        aria-label="${mmss(lookup.segment(n).start_s)}, open this moment">${mmss(lookup.segment(n).start_s)}</button>`;
    }
    if (kind === "C" && lookup.comment(n)) {
      return `<button class="ev ev--c" type="button" data-ev="${id}"
        aria-label="comment ${n + 1}, read it">comment ${n + 1}</button>`;
    }
    if (kind === "T" && lookup.topic(id)) {
      return `<button class="ev ev--t" type="button" data-ev="${id}">${esc(lookup.topic(id).name)}</button>`;
    }
    return "";
  }).filter(Boolean);
  return out.length ? `<span class="evs">${out.join("")}</span>` : "";
}

/** Who wrote a sentence: the model, checked; or code, from the figures. */
export function source(item) {
  if (item && item.source === "template") {
    return `<span class="src src--code" title="The fact checks set the model's sentence aside, so this one was built from the figures by code.">from the figures</span>`;
  }
  if (item && item.source === "code") {
    return `<span class="src src--code" title="Written by code from the figures, by design: these are counts, and code states counts exactly.">from the figures</span>`;
  }
  return "";
}

/** The state of a page whose words the model has not written yet. */
export function notYet(what, command) {
  return `<div class="ny" role="note">
    <p class="ny__h">${esc(what)}</p>
    <p class="ny__p">Written by the local model at the end of a run. It has not been run
      for this report yet; everything on this page that is a figure is already here.</p>
    ${command ? `<p class="ny__cmd"><code>${esc(command)}</code></p>` : ""}
  </div>`;
}

export function levelPill(level, href) {
  const l = LEVEL[level] || LEVEL.unknown;
  return `<a class="lvl" href="${href}" data-lvl="${esc(level || "unknown")}" data-cx-goto-trust>
    <span class="lvl__dots" aria-hidden="true">${[1, 2, 3].map((i) => `<i${i <= l.dots ? " data-on" : ""}></i>`).join("")}</span>
    <span>${l.word}</span></a>`;
}

/* ------------------------------------------------------- overview ------- */

/**
 * The verdict at the top of the reading page. The model's where it passed;
 * otherwise the summary code writes from the run's own figures.
 */
export function verdictBlock(a, lookup, fallbackHtml) {
  const v = a && a.written && a.written.verdict;
  if (v && v.source === "model") {
    return `<p class="vd">${esc(v.text)}</p>${chips(v.evidence, lookup)}`;
  }
  return `<p class="vd vd--code">${fallbackHtml}</p>
    <p class="vd__src">${a && a.written ? "Written by code from the figures: the fact checks set the local model's own summary aside." : "Summarised from the figures. The written report has not been run for this video."}</p>`;
}

export function takeawaysPage(a, lookup, command) {
  const w = a && a.written;
  const items = (w && w.takeaways) || [];
  const dropped = w ? ((a.verifier && a.verifier.by_field && a.verifier.by_field.takeaway) || {}).dropped || 0 : 0;
  return `<section class="tk" aria-labelledby="tk-h">
    <h2 id="tk-h" class="cx-h">What to take from it</h2>
    ${!w ? notYet("Three takeaways for the brand", command) : items.length ? `
    <ol class="tk__list">${items.map((t, i) => `
      <li class="tk__item"><span class="tk__n" aria-hidden="true">${i + 1}</span>
        <div><p class="tk__text">${esc(t.text)}</p>${chips(t.evidence, lookup)}</div></li>`).join("")}
    </ol>` : `<p class="cx-note">None of the model's takeaways passed the checks, so none is printed.</p>`}
    ${w && dropped ? `<p class="cx-note tk__dropped">${dropped} further ${dropped === 1 ? "takeaway was" : "takeaways were"} written and
      dropped because ${dropped === 1 ? "it" : "they"} did not hold up against the run.</p>` : ""}
    <p class="cx-note">Written by the local model from the figures in this book; every sentence
      cites where it comes from, and was checked against the run before it was kept.</p>
  </section>`;
}

/** Reviewer against audience: the tug bar, then brand health and the audience in words. */
export function agreementPage(a, lookup) {
  const f = a.facts;
  const w = a.written;
  const call = f.agreement.call;
  const head = {
    reviewer_warmer: "The reviewer is warmer than the audience",
    audience_warmer: "The audience is warmer than the reviewer",
    no_clear_difference: "No clear difference between reviewer and audience",
    unknown: "Reviewer and audience cannot be compared",
  }[call] || "Reviewer and audience";
  const part = (item, label) => (item ? `
    <div class="ag__part"><p class="ag__k">${label}</p>
      <p class="ag__words">${esc(item.text)} ${source(item)}</p>${chips(item.evidence, lookup)}</div>` : "");
  return `<section class="ag" aria-labelledby="ag-h">
    <h2 id="ag-h" class="cx-h">${head}</h2>
    <figure class="ag__fig">${tugBar(f)}
      <figcaption class="cx-note">Each mark is a lean from all negative (&minus;1) to all positive
        (+1), with its 95% interval. The reviewer is read from the words (transcript model, tested
        at ${f.confidence.accuracy.transcript ?? "an unrecorded"}%), the audience from the comments
        (comment model, ${f.confidence.accuracy.comment ?? "unrecorded"}%). One side is called warmer only
        when the interval of the gap between them excludes zero.</figcaption></figure>
    ${w ? `${part(w.agreement_words, "Do they agree?")}${part(w.brand_health_words, "Brand health, in words")}`
      : `<p class="ag__words">${esc(templateAgreement(f))}</p>
        <div class="ag__part"><p class="ag__k">Brand health, in figures</p>
          <p class="ag__words">Of ${count(f.audience.n)} comments, ${count(f.audience.counts.POSITIVE)} read
            positive, ${count(f.audience.counts.NEUTRAL)} neutral and ${count(f.audience.counts.NEGATIVE)}
            negative. The written report puts this into words once it has been run.</p></div>`}
  </section>`;
}

function templateAgreement(f) {
  return {
    reviewer_warmer: "The reviewer is measurably warmer than the audience.",
    audience_warmer: "The audience is measurably warmer than the reviewer.",
    no_clear_difference: "There is no clear difference between the reviewer and the audience.",
  }[f.agreement.call] || "The two cannot be compared on this report.";
}

/* ------------------------------------------------------- what they said -- */

export function tonePage(a, report, lookup) {
  const f = a.facts;
  const labels = {};
  for (const t of (a.written && a.written.turn_labels) || []) labels[t.seg] = t.label;
  const flagged = (report.all_segments || []).filter((s) => s.flagged);
  const turns = f.tone.turns;
  return `<section class="tn" aria-labelledby="tn-h">
    <div class="tn__head">
      <h2 id="tn-h" class="cx-h">How the tone moved</h2>
      <p class="cx-lede">How positive the reviewer's words read, moment by moment, smoothed over a
        minute: solid above the line, hatched below it. ${flagged.length
          ? `The pink ticks are the ${flagged.length === 1 ? "moment" : `${flagged.length} moments`} the controller flagged.` : ""}</p>
    </div>
    <figure class="tn__fig">${toneArc({ points: f.tone.points, turns, flagged, duration: f.duration_s, labels })}</figure>
    ${turns.length ? `<ol class="tn__turns">${turns.map((t, i) => `
      <li><span class="tn__n">${i + 1}</span>
        <span class="tn__what">${labels[t.seg] ? esc(labels[t.seg]) : t.kind === "peak" ? "Peak" : "Dip"}</span>
        ${chips([`S${t.seg}`], lookup)}</li>`).join("")}</ol>`
      : `<p class="cx-note">The tone never turned by enough to mark: no peak or dip stood more than
        ${(0.2).toFixed(1)} above its surroundings.</p>`}
  </section>`;
}

export function timePage(a, command) {
  const topics = (a.reading && a.reading.topics) || [];
  return `<section class="tt" aria-labelledby="tt-h">
    <h2 id="tt-h" class="cx-h">Where the time went</h2>
    ${!a.reading ? notYet("The topics the video covered", command) : `
    <p class="cx-lede">The reviewer's claims, grouped into topics, and the time spent on each.
      Each bar is split by how the transcript model read those seconds.</p>
    ${timeBars(topics) || `<p class="cx-note">The local model found no claims about the product to group.</p>`}
    <p class="tt__key" aria-hidden="true"><i class="k k--pos"></i>positive <i class="k k--neu"></i>neutral
      <i class="k k--neg"></i>negative</p>`}
  </section>`;
}

export function topicsPage(a, command) {
  const topics = (a.reading && a.reading.topics) || [];
  return `<section class="tv" aria-labelledby="tv-h">
    <h2 id="tv-h" class="cx-h">Reviewer and audience, topic by topic</h2>
    ${!a.reading ? notYet("The reviewer and the audience on each topic", command) : `
    <p class="cx-lede">For each topic, how the reviewer's words about it read
      <i class="k k--r" aria-hidden="true"></i> against how the comments about it read
      <i class="k k--a" aria-hidden="true"></i>, on one scale from all negative to all positive.</p>
    ${dumbbells(topics) || `<p class="cx-note">No topic had readings from either side.</p>`}
    <p class="cx-note"><b>&ldquo;No clear difference&rdquo; does not mean the two sides agree.</b>
      It means there were too few comments on that topic to be sure they differ, even where the
      two marks look far apart. Topics and which comments belong to them are the local model's
      grouping; how each side reads is the two benched classifiers'.</p>`}
  </section>`;
}

/** The claim cards, flowed across as many pages as they need. */
export function claimItems(a, lookup) {
  const claims = (a.reading && a.reading.claims) || [];
  const topicName = (id) => (lookup.topic(id) || {}).name || "";
  const group = (stances, title, lede) => {
    const mine = claims.filter((c) => stances.includes(c.stance));
    if (!mine.length) return [];
    const head = document.createElement("li");
    head.className = "cl__head";
    head.innerHTML = `<h3 class="cx-h3">${title}</h3><p class="cx-note">${lede}</p>`;
    return [head, ...mine.map((c) => {
      const li = document.createElement("li");
      li.className = "cl";
      li.dataset.stance = c.stance;
      li.innerHTML = `
        <p class="cl__meta">${topicName(c.topic) ? `<span class="cl__topic">${esc(topicName(c.topic))}</span>` : ""}
          ${chips([`S${c.seg}`], lookup)}</p>
        <p class="cl__claim">${esc(c.claim)}</p>
        <blockquote class="cl__quote">&ldquo;${esc(c.quote)}&rdquo;</blockquote>`;
      return li;
    })];
  };
  return [
    ...group(["praise"], "What the reviewer liked", "In their own words, in the order they said them."),
    ...group(["criticism"], "What they did not like", "The same, for the criticisms."),
    ...group(["mixed", "neutral"], "Mixed or neutral", "Claims that were neither clearly for nor against."),
  ];
}

/* ------------------------------------------------------- audience ------- */

export function talkPage(a, lookup, command) {
  const topics = ((a.reading && a.reading.topics) || []).filter((t) => t.audience.comments);
  const w = a.written;
  return `<section class="tl" aria-labelledby="tl-h">
    <h2 id="tl-h" class="cx-h">How people talk about it</h2>
    ${w && w.audience_words ? `<p class="tl__words">${esc(w.audience_words.text)} ${source(w.audience_words)}</p>
      ${chips(w.audience_words.evidence, lookup)}` : ""}
    ${!a.reading ? notYet("What the comments talk about", command) : `
    ${themeBars(topics) || `<p class="cx-note">No comment was about anything the model could name.</p>`}
    <p class="tt__key" aria-hidden="true"><span class="th__keyl">complaints</span><span class="th__keyr">praise</span></p>
    <p class="cx-note">Which comments belong to which topic is the local model's reading; whether each
      is positive or negative is the benched comment model's (tested at
      ${a.facts.confidence.accuracy.comment ?? "an unrecorded"}% on unseen videos).</p>`}
  </section>`;
}

export function askPage(a, lookup, command) {
  const questions = ((a.reading && a.reading.questions) || []).slice(0, 3);
  /* One voice per topic, never the same comment twice: a comment about two
     topics is its best example for both, and printing it twice read as a bug. */
  const shown = new Set(questions.map((q) => q.i));
  const voices = [];
  for (const t of (a.reading && a.reading.topics) || []) {
    const ex = t.audience.examples.find((e) => !shown.has(e.i));
    if (!ex || t.name.toLowerCase() === "other") continue;
    shown.add(ex.i);
    voices.push({ topic: t.name, ex });
    if (voices.length === 2) break;
  }
  return `<section class="ak" aria-labelledby="ak-h">
    <h2 id="ak-h" class="cx-h">What they ask, and in their words</h2>
    ${!a.reading ? notYet("The questions and voices of the audience", command) : `
    ${questions.length ? `<ul class="ak__qs">${questions.map((q) => `
      <li><p class="ak__q">&ldquo;${esc(cut(q.quote, 26))}&rdquo;</p>${chips([`C${q.i}`], lookup)}</li>`).join("")}</ul>`
      : `<p class="cx-note">Nobody asked a question in the comments that were read.</p>`}
    <div class="ak__voices">${voices.map((v) => `
      <figure class="ak__voice"><figcaption class="cl__topic">${esc(v.topic)}</figcaption>
        <blockquote>&ldquo;${esc(cut(v.ex.quote, 30))}&rdquo;</blockquote>
        ${chips([`C${v.ex.i}`], lookup)}</figure>`).join("")}</div>
    <p class="cx-note">Usernames and links are removed before any comment is quoted.</p>`}
  </section>`;
}

/* ------------------------------------------------------- moments -------- */

/** The mark on a moment note code built from the readings. */
export const CODE_READINGS = `<span class="src src--code" title="Built by code from the four readings above; the local model's own note was set aside by the fact checks or has not been written.">from the readings</span>`;

export function oddMomentsPage(a, report, lookup, frameFor, command) {
  const moments = a.facts.moments;
  const notes = {};
  for (const n of (a.written && a.written.moment_notes) || []) notes[n.seg] = n.text;
  const NAMES = { transcript: "words", facial: "face", vocal: "voice", comment: "comments" };
  const card = (m) => {
    const img = frameFor(m);
    const readings = ["transcript", "facial", "vocal", "comment"].map((k) => {
      const v = m.valences[k];
      return `<li data-v="${v ? esc(v.toLowerCase()) : "none"}"><span class="om__ch">${NAMES[k]}</span>
        <span class="om__v">${v ? esc(v.toLowerCase()) : "no reading"}</span></li>`;
    }).join("");
    const said = m.text.split(/\s+/).slice(0, 32).join(" ");
    return `<article class="om" aria-label="${esc(`The moment at ${m.time}`)}">
      <div class="om__frame">${img ? `<img src="${img}" alt="" loading="lazy" decoding="async">` : `<span class="om__none">No frame for this second</span>`}</div>
      <p class="om__when"><span class="t-time">${esc(m.time)}</span>
        <span class="om__c${m.flagged ? " is-flagged" : ""}">conflict ${confidence(m.conflict)}${m.flagged ? ", flagged" : ""}${m.damped ? ", down-weighted" : ""}</span></p>
      <blockquote class="om__said">&ldquo;${esc(said)}${said.length < m.text.length ? "…" : ""}&rdquo;</blockquote>
      <ul class="om__reads">${readings}</ul>
      ${notes[m.seg] ? `<p class="om__note">${esc(notes[m.seg])}</p>`
        : `<p class="om__note">${esc(readingsSentence(m.valences))} ${CODE_READINGS}</p>`}
      <button class="cx-btn" type="button" data-ev="S${m.seg}">Open this moment</button>
    </article>`;
  };
  return `<section class="omx" aria-labelledby="om-h">
    <div class="omx__head">
      <h2 id="om-h" class="cx-h">The moments that do not add up</h2>
      <p class="cx-lede">The ${moments.length === 1 ? "moment" : `${moments.length} moments`} where the four readings disagreed most,
        highest first: what was said, what each channel read, and why they do not match.</p>
    </div>
    ${moments.length ? `<div class="omx__grid">${moments.map(card).join("")}</div>`
      : `<p class="cx-text">No moment of this video scored any conflict: all four readings agreed
        wherever they could be read.</p>`}
  </section>`;
}

/* ------------------------------------------------------- trust ---------- */

export function trustPage(a) {
  const c = a.facts.confidence;
  const l = LEVEL[c.level] || LEVEL.unknown;
  const value = (k) => (k.unit === "comments" ? count(k.value)
    : k.value == null ? "no conflict" : pct(k.value * 100, 0));
  const target = (k) => (k.target == null ? "no floor recorded"
    : k.id === "comments" ? `at least ${count(k.target)}`
    : k.id === "transcript" ? `at least ${pct(k.target * 100, 0)} of segments`
    : `no more than ${pct(k.target * 100, 0)}`);
  return `<section class="tr" aria-labelledby="tr-h">
    <h2 id="tr-h" class="cx-h">How far to trust this reading</h2>
    <div class="tr__level" data-lvl="${esc(c.level)}">
      <span class="lvl__dots lvl__dots--big" aria-hidden="true">${[1, 2, 3].map((i) => `<i${i <= l.dots ? " data-on" : ""}></i>`).join("")}</span>
      <p class="tr__word">${l.word}</p>
    </div>
    <p class="cx-text">${esc(c.means_not)}</p>
    <table class="tr__checks">
      <thead><tr><th scope="col">Check</th><th scope="col">This video</th><th scope="col">Needs</th><th scope="col"><span class="sr-only">Result</span></th></tr></thead>
      <tbody>${c.checks.map((k) => `
        <tr data-pass="${k.passed === true ? "yes" : k.passed === false ? "no" : "unknown"}">
          <th scope="row">${esc(k.label)}</th><td class="t-read">${value(k)}</td><td>${target(k)}</td>
          <td class="tr__res">${k.passed === true ? "met" : k.passed === false ? "not met" : "unknown"}</td></tr>`).join("")}
      </tbody></table>
    <div class="tr__ceiling"><p class="ag__k">What no report here can promise</p>
      <p class="cx-note">${esc(c.ceiling.text)}</p></div>
  </section>`;
}

const STATE = { present: "Present", absent: "Absent", not_checked: "Not checked" };

export function signsPage(a, lookup) {
  const s = a.facts.signs;
  const meta = a.video_meta || {};
  const evidence = (sign) => {
    const e = sign.evidence || {};
    if (sign.id === "S1") {
      const bits = [];
      if (e.label === true) bits.push("The creator ticked YouTube's &ldquo;includes paid promotion&rdquo; box.");
      if (e.label === false) bits.push("YouTube's paid-promotion box is not ticked; creators set it themselves and it is off by default.");
      for (const h of (e.description || []).slice(0, 2)) bits.push(`Description: &ldquo;${esc(cut(h.context, 14))}&rdquo;`);
      return bits.join(" ");
    }
    if (sign.id === "S2") {
      return (e.speech || []).slice(0, 3).map((h) => `&ldquo;${esc(h.match)}&rdquo; ${chips([`S${h.seg}`], lookup)}`).join(" ")
        + ((e.speech || []).length > 3 ? ` and ${e.speech.length - 3} more` : "");
    }
    if (sign.id === "S3") return (e.description || []).slice(0, 2).map((h) => `&ldquo;${esc(cut(h.context, 14))}&rdquo;`).join(" ");
    if (sign.id === "S4") {
      const g = e.agreement || {};
      return g.gap == null ? "" : `Gap ${signed(g.gap)}, 95% interval ${signed(g.low)} to ${signed(g.high)}.`;
    }
    if (sign.id === "S5") {
      const ids = [...new Set([...(e.positive_flagged || []), ...(e.controller_flag || [])])];
      return ids.length ? chips(ids.map((i) => `S${i}`), lookup) : "";
    }
    return "";
  };
  const why = meta.fetched === false && meta.error
    ? `<p class="cx-note">Signs 1 and 3 need the video's own details from YouTube, which were not
        available for this report (${esc(meta.error)}).</p>`
    : !meta.fetched
      ? `<p class="cx-note">Signs 1 and 3 need the video's own details from YouTube, which are
          fetched when the written report is run.</p>` : "";
  return `<section class="sg" aria-labelledby="sg-h">
    <h2 id="sg-h" class="cx-h">Could this be paid?</h2>
    <p class="sg__sum"><span class="t-read">${s.present}</span> of ${s.checked} checked
      ${s.checked === 1 ? "sign is" : "signs are"} present</p>
    <ol class="sg__list">${s.signs.map((sign) => `
      <li class="sg__row" data-state="${sign.state}">
        <span class="sg__mark" aria-hidden="true"></span>
        <div class="sg__body">
          <p class="sg__name">${esc(sign.name)} <span class="sg__kind">${sign.kind === "fact" ? "fact" : "inference"}</span></p>
          <p class="sg__state">${STATE[sign.state]}</p>
          ${sign.state === "present" ? `<p class="sg__ev">${evidence(sign)}</p>`
            : sign.id === "S1" && sign.state === "absent" ? `<p class="sg__ev">${evidence(sign)}</p>` : ""}
        </div></li>`).join("")}
    </ol>
    <p class="sg__disc">${esc(s.disclaimer)}</p>
    ${why}
  </section>`;
}

