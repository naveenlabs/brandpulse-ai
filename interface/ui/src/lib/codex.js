/* ===========================================================================
   codex.js — the report is the volume that was on the shelf, opened.

   The page builds its content; this module binds it. It owns five things:
   the spreads, the navigation between them, the turn, the flow of long
   material across as many spreads as it needs, and the cover opening and
   closing at either end of a reading.

   FIVE DECISIONS, EACH OF WHICH REPLACED SOMETHING THAT WAS MEASURED WRONG.

   1. A SPREAD IS SIZED TO THE WINDOW, AND CONTENT DECIDES HOW MANY THERE ARE.

      The first build of this book had one spread per chapter with a minimum
      height and no maximum, so a chapter that held more simply grew: 1,358px
      for the overview, 4,146px for the evidence. That is a long column with a
      gutter drawn down it, not a book. Here every spread is laid out at the
      height the window can show, and material that cannot fit -- the
      comments, the videos of a sweep, the refused videos -- is MEASURED and
      carried over onto further spreads at item boundaries. Nothing is shrunk
      to fit and nothing is clipped; an item taller than a whole page is given
      a page to itself and that one page grows.

   2. EVERY SPREAD IS IN THE DOCUMENT.

      Spreads that are not on the desk carry `hidden`. The report's wiring --
      the moment, the ledger, the transport, the comments -- binds once, to
      real elements, and pagination MOVES those elements between pages rather
      than rebuilding them, so nothing is ever wired twice or against a node
      that has gone. Find-in-page and a screen reader's document walk still
      reach every chapter.

   3. THE PAGE THAT TURNS IS THE PAGE YOU WERE READING.

      The last build turned a blank sheet over the spread, so leaving a page
      looked like a curtain being drawn over it. Now the leaf's front face is
      the outgoing page and its back face is the incoming one, both built as
      inert, aria-hidden copies of the live HTML -- never a screenshot, so the
      type stays type -- and removed the moment the leaf lands. The incoming
      spread is already laid out underneath before the leaf moves, so nothing
      pops in behind it. A fold-out turns like any other spread: its one
      sheet is copied at full width and the half that goes over is cut from
      that copy, so turning into, out of or between fold-outs is the same
      gesture as turning any page.

   4. THE HINGE IS THE GUTTER, AND THE PERSPECTIVE IS SOLVED, NOT GUESSED.

      A leaf hinged at the gutter swings its far edge toward the viewer, and
      under perspective P a point at depth z is drawn P / (P - z) larger. The
      largest z is the page's own width, so the height a turning leaf gains at
      each end is (H / 2) * W / (P - W). That is set equal to the room actually
      reserved above and below the block -- measured off the document at the
      start of each turn -- and solved for P. The leaf cannot reach the
      chapter bar or anything under the book, on any screen, by construction.

   5. THE URL KNOWS WHERE YOU ARE.

      The spread is written into the hash with replaceState, so a refresh or a
      copied link reopens the same spread, and Back still leaves the book in
      one step instead of walking back through every page turned.
   ======================================================================== */

import { reduced } from "./motion.js";
import { openVolume, closeVolume } from "./leaf.js";
import { applyTheme, currentTheme } from "./theme.js";

/* One leaf turn. Long enough to be read as a page, short enough that a reader
   turning through a chapter is never waiting on it. */
const TURN_MS = 720;
/* The leaf is a chain of this many strips so the surface can bend. Each strip
   carries a copy of its slice of the page, so this is also the number of
   copies per face; eight softens the curve while keeping the clone count bounded. */
const STRIPS = 8;
/* A paper leaf bends more freely than the clothbound cover (0.22 radians). */
const CURL = 0.38;
/* How dark a strip gets when it faces fully away from the light. */
const SHADE = 0.38;
/* Two turns closer together than this are a reader flicking through, not
   reading, and the second one is taken without animation rather than queued. */
const RAPID_MS = 260;

/* The one breakpoint the spread depends on. Below it the book is a single
   page and is read downward; codex.css states the same width. */
const WIDE_QUERY = "(min-width: 1100px)";

/* READ AS ONE PAGE (25 Sep 2026, INCLUSIVE_DESIGN.md I2).

   The same book, every chapter shown in order down one column, at any width:
   the layout below 1100px, which already reads downward, used everywhere.
   Asked for with ?read=page, which the document's head turns into
   <html data-read="page"> before first paint; vite.config.js re-emits the
   narrow layout under that attribute and holds the spread layout off it.
   Nothing is written twice -- it is the same DOM, the same pages, the same
   wiring. It serves a screen reader (one continuous document), a reader at
   400% zoom, anyone who would rather scroll, and printing, which uses it. */
export const readsAsPage = () => document.documentElement.dataset.read === "page";
export const isWide = () => !readsAsPage() && window.matchMedia(WIDE_QUERY).matches;

const el = (tag, cls) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
};

export const ARROW = (dir) => `<svg class="cx-arrow" viewBox="0 0 16 11" width="15" height="11"
  aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4"
  style="transform:rotate(${dir === "prev" ? 180 : 0}deg)"><path d="M0 5.5H14.6M10.3 1.2 14.9 5.5 10.3 9.8"/></svg>`;

/* ------------------------------------------------------------ markup ---- */

/**
 * One spread: a verso and a recto, or a single fold-out sheet.
 *
 * Running heads and folios are written by wireCodex once the book is laid
 * out, because a page's number depends on how many spreads the material
 * before it needed. `plain` names the pages that carry no running head: a
 * title page and a full-bleed plate, as in any printed book.
 */
export function spread({ key, verso = "", recto = "", wide = false, plain = [], cont = false }) {
  const page = (side, body) => `
    <div class="cx__page cx__page--${side}${plain.includes(side) ? " is-plain" : ""}" data-cx-page>
      <p class="cx__run" data-cx-run aria-hidden="true"></p>
      <div class="cx__body">${body}</div>
      <p class="cx__folio" data-cx-folio aria-hidden="true"></p>
    </div>`;
  const attrs = `data-cx-spread data-cx-key="${key}" tabindex="-1"${cont ? " data-cx-cont" : ""}`;
  if (wide) {
    return `<div class="cx__spread" ${attrs} data-wide>
      <div class="cx__pages">${page("fold", verso)}</div></div>`;
  }
  return `<div class="cx__spread" ${attrs}>
    <div class="cx__pages">${page("verso", verso)}${page("recto", recto)}</div></div>`;
}

/* A title is set at the size its length allows. "Apple" is a display line;
   an eighty-character video title set at that size ran to five lines and
   pushed its page 366px past the window. It is stepped down, never cut. */
export function titleLength(text) {
  const n = String(text || "").length;
  return n > 30 ? "l" : n > 14 ? "m" : "s";
}

/** A chapter: one or more spreads under one entry in the contents. */
export function chapter({ id, label, spreads }) {
  return `<section class="cx__chapter" data-cx-chapter="${id}" data-cx-label="${label}"
    aria-label="${label}">${spreads.join("")}</section>`;
}

/** The bar, the stage and the book. `title` arrives escaped. */
export function codexShell({ title, chapters, backHref, backLabel }) {
  const toc = chapters.map((c, i) => `
    <li><a class="cx__ch" href="#${c.id}" data-cx-goto="${c.id}">
      <span class="cx__chn">${i + 1}</span><span class="cx__chl">${c.label}</span></a></li>`).join("");

  return `<div class="cx" data-cx>
    <div class="cx__bar">
      <a class="cx__close" href="${backHref}" data-cx-close>${ARROW("prev")}<span>${backLabel}</span></a>
      <nav class="cx__toc" aria-label="Chapters of ${title}"><ol>${toc}</ol></nav>
      ${readsAsPage()
        ? `<a class="cx__mode" href="${location.pathname}">Read as a book</a>`
        : `<a class="cx__mode" href="${location.pathname}?read=page">Read as one page</a>`}
      <p class="cx__where" data-cx-where aria-live="polite"></p>
    </div>
    <div class="cx__stage">
      <button class="cx__turnbtn cx__turnbtn--prev" type="button" data-cx-prev>
        ${ARROW("prev")}<span>Previous</span></button>
      <div class="cx__book" data-cx-book>${chapters.map((c) => c.html).join("")}</div>
      <button class="cx__turnbtn cx__turnbtn--next" type="button" data-cx-next>
        ${ARROW("next")}<span>Next</span></button>
    </div>
  </div>`;
}

/* ------------------------------------------------------------ the book -- */

/**
 * Bind a built book.
 *
 * @param {HTMLElement} host
 * @param {object} opts
 * @param {string}   opts.title     the running head on every verso
 * @param {function} opts.onSpread  (spread, chapter) after the desk changes
 */
export function wireCodex(host, opts = {}) {
  const book = host.querySelector("[data-cx-book]");
  if (!book) return null;
  const bar = host.querySelector(".cx__bar");
  const prevBtn = host.querySelector("[data-cx-prev]");
  const nextBtn = host.querySelector("[data-cx-next]");
  const where = host.querySelector("[data-cx-where]");
  const links = [...host.querySelectorAll("[data-cx-goto]")];
  const title = opts.title || "";

  let spreads = [];
  let at = 0;
  let wide = isWide();
  let total = 0;
  let turn = null;
  let lastNav = 0;
  const flows = [];
  /* A spread named in the address that does not exist yet. Continuation
     spreads are made by the flows, after this function has returned, so a
     link to the third spread of comments cannot be honoured at boot; it is
     held here and honoured on the first layout that contains it. Measured:
     a refresh on #audience-3 reopened the book at the overview. */
  let pendingKey = decodeURIComponent(location.hash.replace(/^#/, "")) || null;

  /* --- the room the book is given -------------------------------------

     The block is given exactly the height between the chapter bar and the
     line at the foot of the page, so the bar, the book and that line are one
     screen and the page itself does not scroll. codex.css set this from
     fixed lengths -- a masthead of 4.75rem, a bar of 3.5rem -- and at
     1512x860 the book ended 49px short of the window on four chapters while
     the overview ran 25px past it, all above a footer a scroll further down.
     Every length is measured here instead, so a bar that wraps, the member
     bar on a report opened from a combined one, or a late typeface cannot
     throw it off. The clamp is the fallback's own, from codex.css: below
     30rem a page is too short to read and the window scrolls instead; above
     58rem a very tall screen is left space rather than given a page too tall
     to read comfortably. */
  const cx = host.querySelector("[data-cx]");
  const foot = document.querySelector("[data-footer]");
  function fit() {
    if (!cx) return;
    if (!wide) { cx.style.removeProperty("--cx-h"); return; }
    const cs = getComputedStyle(book);
    const reserveTop = parseFloat(cs.paddingTop) || 0;
    const reserveBottom = parseFloat(cs.paddingBottom) || 0;
    const b = book.getBoundingClientRect();
    const top = b.top + window.scrollY + reserveTop;
    const after = host.getBoundingClientRect().bottom - b.bottom;
    const line = foot ? foot.getBoundingClientRect().height : 0;
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const h = window.innerHeight - top - reserveBottom - after - line;
    cx.style.setProperty("--cx-h", `${Math.floor(Math.min(58 * rem, Math.max(30 * rem, h)))}px`);
  }
  fit();

  const chapters = () => [...book.querySelectorAll("[data-cx-chapter]")];
  const chapterOf = (s) => s.closest("[data-cx-chapter]");
  const isFold = (s) => s.hasAttribute("data-wide");
  const pagesOf = (s) => [...s.querySelectorAll(":scope > .cx__pages > [data-cx-page]")];

  /* One side of a spread as the turn needs it: the page to copy, the width to
     lay the copy out at, and how far to shift it. A spread's side is a whole
     page. A fold-out's side is half of its one sheet, so the copy is laid out
     at the sheet's full width -- the fold-out's own layout, not a squeezed
     one -- and shifted so the wanted half shows. The hinge is still the
     middle of the block; the fold-out simply has no gutter drawn there. */
  function halfOf(s, side, half) {
    const pages = pagesOf(s);
    if (isFold(s)) {
      const w = s.querySelector(".cx__pages").getBoundingClientRect().width || 2 * half;
      return { page: pages[0], width: w, shift: side === "l" ? 0 : half - w };
    }
    return { page: side === "l" ? pages[0] : pages[1], width: half, shift: 0 };
  }

  /* --- numbering ------------------------------------------------------ */

  function number() {
    spreads = [...book.querySelectorAll("[data-cx-spread]")];
    let p = 0;
    for (const s of spreads) {
      const label = chapterOf(s).dataset.cxLabel;
      const pages = pagesOf(s);
      if (isFold(s)) {
        p += 2;
        s.dataset.cxPages = `${p - 1} and ${p}`;
        pages[0].dataset.cxFolio = String(p - 1);
        pages[0].querySelector("[data-cx-run]").textContent = `${title}, ${label}`;
        pages[0].querySelector("[data-cx-folio]").textContent = `${p - 1} and ${p}, folded out`;
        continue;
      }
      pages.forEach((pg, i) => {
        p += 1;
        pg.dataset.cxFolio = String(p);
        pg.querySelector("[data-cx-run]").textContent = i === 0 ? title : label;
        pg.querySelector("[data-cx-folio]").textContent = String(p);
      });
      s.dataset.cxPages = `${p - 1} and ${p}`;
    }
    total = p;

    /* Cross-references print the page a thing is actually on, which is only
       known now: the chapters before it may have flowed onto more spreads. */
    for (const ref of host.querySelectorAll("[data-cx-xref]")) {
      const target = book.querySelector(`#${CSS.escape(ref.dataset.cxXref)}`);
      const pg = target && target.closest("[data-cx-page]");
      const out = ref.querySelector("[data-cx-xref-page]");
      if (out) out.textContent = pg && pg.dataset.cxFolio ? pg.dataset.cxFolio : "";
    }
  }

  /* --- painting the desk ---------------------------------------------- */

  function describe() {
    const s = spreads[at];
    const ch = chapterOf(s);
    const own = [...ch.querySelectorAll("[data-cx-spread]")];
    const label = ch.dataset.cxLabel;
    if (!wide) {
      const first = own[0].dataset.cxPages.split(" and ")[0];
      const last = own[own.length - 1].dataset.cxPages.split(" and ")[1];
      return `${label}, pages ${first} to ${last} of ${total}`;
    }
    const part = own.length > 1 ? `, spread ${own.indexOf(s) + 1} of ${own.length}` : "";
    return isFold(s)
      ? `${label}${part}, pages ${s.dataset.cxPages} of ${total}, folded out`
      : `${label}${part}, pages ${s.dataset.cxPages} of ${total}`;
  }

  function paint() {
    const cur = spreads[at];
    const ch = chapterOf(cur);
    const all = readsAsPage();
    for (const c of chapters()) c.hidden = !all && c !== ch;
    for (const s of spreads) s.hidden = !all && (wide ? s !== cur : chapterOf(s) !== ch);

    const id = ch.dataset.cxChapter;
    for (const l of links) {
      if (l.dataset.cxGoto === id) l.setAttribute("aria-current", "true");
      else l.removeAttribute("aria-current");
    }

    const chs = chapters();
    const ci = chs.indexOf(ch);
    const atStart = wide ? at === 0 : ci === 0;
    const atEnd = wide ? at === spreads.length - 1 : ci === chs.length - 1;
    const aim = (i) => (wide ? describeTarget(i) : chs[i] && chs[i].dataset.cxLabel);
    prevBtn.disabled = atStart;
    nextBtn.disabled = atEnd;
    prevBtn.setAttribute("aria-label", atStart ? "Previous, this is the start of the book"
      : `Previous, ${aim(wide ? at - 1 : ci - 1)}`);
    nextBtn.setAttribute("aria-label", atEnd ? "Next, this is the end of the book"
      : `Next, ${aim(wide ? at + 1 : ci + 1)}`);

    where.textContent = all ? `${chs.length} chapters, ${total} pages, on one page` : describe();
    host.dataset.cxMode = isFold(cur) ? "fold" : "spread";

    const key = cur.dataset.cxKey;
    if (all) { markScrollers(); if (opts.onSpread) opts.onSpread(cur, ch); return; }
    const url = pendingKey ? `${location.pathname}${location.search}#${pendingKey}`
      : at === 0
      ? `${location.pathname}${location.search}`
      : `${location.pathname}${location.search}#${key}`;
    try { history.replaceState(history.state, "", url); } catch { /* sandboxed */ }

    markScrollers();
    if (opts.onSpread) opts.onSpread(cur, ch);
  }

  /* A page whose content is taller than the page scrolls inside itself, and a
     region that scrolls has to be reachable from the keyboard: Safari will not
     scroll an unfocusable one with the arrow keys at all. Only a page that
     actually overflows is made a stop, so the Tab order is not padded with
     every page of the book. Flagged by axe-core as scrollable-region-focusable
     on 25 Sep 2026 (INCLUSIVE_DESIGN.md A17). */
  function markScrollers() {
    for (const body of book.querySelectorAll("[data-cx-spread]:not([hidden]) .cx__body")) {
      const pg = body.closest("[data-cx-page]");
      if (body.scrollHeight - body.clientHeight > 2) {
        body.tabIndex = 0;
        body.setAttribute("role", "region");
        body.setAttribute("aria-label", `Page ${pg ? pg.dataset.cxFolio : ""}, which scrolls`);
      } else if (body.hasAttribute("tabindex")) {
        body.removeAttribute("tabindex");
        body.removeAttribute("role");
        body.removeAttribute("aria-label");
      }
    }
  }

  const describeTarget = (i) => {
    const s = spreads[i];
    if (!s) return "";
    return `${chapterOf(s).dataset.cxLabel}, pages ${s.dataset.cxPages}`;
  };

  /* --- focus ---------------------------------------------------------

     Focus stays on the control that was used, because a reader pressing Next
     wants to press it again. It moves only when the thing it was on has gone
     -- a control inside the page that was turned away, or a button that has
     just become disabled at the end of the book. */
  function settleFocus() {
    const a = document.activeElement;
    const lost = !a || a === document.body || a.closest("[hidden]")
      || (a instanceof HTMLButtonElement && a.disabled);
    if (lost && a !== document.body) spreads[at].focus({ preventScroll: true });
  }

  /* --- moving --------------------------------------------------------- */

  function ensureTop() {
    const mast = document.querySelector(".masthead");
    const floor = mast ? mast.getBoundingClientRect().bottom : 0;
    const top = bar.getBoundingClientRect().top;
    if (top < floor - 1 || top > window.innerHeight * 0.5) {
      window.scrollTo({ top: window.scrollY + top - floor, behavior: "instant" });
    }
  }

  function show(target, { animate = true } = {}) {
    pendingKey = null;
    const to = Math.max(0, Math.min(spreads.length - 1, target));
    if (turn) turn.finish();
    if (to === at) return;
    const now = performance.now();
    const rapid = now - lastNav < RAPID_MS;
    lastNav = now;

    const from = at;
    const a = spreads[from];
    const b = spreads[to];
    const turnable = animate && !rapid && wide && !reduced() && !a.hidden;

    if (turnable) {
      turn = pageTurn(from, to);
      return;
    }
    at = to;
    paint();
    ensureTop();
    if (animate && !rapid) settle(b);
    settleFocus();
  }

  /* The quiet change: reduced motion, the single-page layout, and a reader
     flicking through faster than a leaf can land. A short fade tells the
     reader something changed without moving anything. The fold-out used to be
     here too, and the reader noticed: every page of the book turned except
     the fold-outs and the page after each one (24 Sep 2026). */
  function settle(s) {
    if (typeof s.animate !== "function") return;
    s.animate([{ opacity: reduced() ? 0.55 : 0 }, { opacity: 1 }],
      { duration: reduced() ? 140 : 220, easing: "ease-out" });
  }

  function step(dir) {
    if (wide) { show(at + dir); return; }
    const chs = chapters();
    const next = chs[chs.indexOf(chapterOf(spreads[at])) + dir];
    if (next) show(spreads.indexOf(next.querySelector("[data-cx-spread]")));
  }

  function goChapter(id) {
    const ch = book.querySelector(`[data-cx-chapter="${CSS.escape(id)}"]`);
    if (!ch) return;
    /* On one page every chapter is already there: go to it, and take the
       keyboard with you. */
    if (readsAsPage()) {
      const head = ch.querySelector("h1, h2");
      ch.scrollIntoView({ block: "start" });
      if (head) { head.setAttribute("tabindex", "-1"); head.focus({ preventScroll: true }); }
      return;
    }
    show(spreads.indexOf(ch.querySelector("[data-cx-spread]")));
  }

  /* --- the turn ------------------------------------------------------- */

  function pageTurn(fromIdx, toIdx) {
    const dir = toIdx > fromIdx ? "next" : "prev";
    const from = spreads[fromIdx];
    const to = spreads[toIdx];
    ensureTop();

    const fromPages = from.querySelector(".cx__pages");
    const fr = fromPages.getBoundingClientRect();
    const br = book.getBoundingClientRect();
    const half = fr.width / 2;
    const stays = dir === "next" ? "l" : "r";
    const goes = dir === "next" ? "r" : "l";
    let H = fr.height;

    /* Everything visible is covered BEFORE the desk changes: the half that
       stays put, and the leaf's front face, which is the page being turned.
       Only then is the new spread shown underneath, so there is no frame in
       which the reader sees the new spread without the old one on top of it. */
    const stage = el("div", "cx__turn");
    stage.setAttribute("aria-hidden", "true");
    stage.style.left = `${fr.left - br.left}px`;
    stage.style.top = `${fr.top - br.top}px`;
    stage.style.width = `${fr.width}px`;

    const still = slice(halfOf(from, stays, half), half);
    still.classList.add("cx__still");
    still.style.left = dir === "next" ? "0px" : `${half}px`;

    const under = el("div", "cx__cast cx__cast--under");
    const over = el("div", "cx__cast cx__cast--over");
    under.dataset.side = dir === "next" ? "r" : "l";
    over.dataset.side = dir === "next" ? "l" : "r";

    const leaf = buildLeaf(dir, half, halfOf(from, goes, half));
    leaf.root.style.left = dir === "next" ? `${half}px` : "0px";

    stage.append(still, over, under, leaf.root);
    const size = (h) => {
      stage.style.height = `${h}px`;
      for (const e of [still, leaf.root]) e.style.height = `${h}px`;
      for (const c of stage.querySelectorAll(".cx__proxy")) {
        c.style.minHeight = `${h}px`;
        c.style.height = `${h}px`;
      }
    };
    size(H);
    book.appendChild(stage);

    at = toIdx;
    paint();
    const tr = to.querySelector(".cx__pages").getBoundingClientRect();
    H = Math.max(H, tr.height);
    size(H);
    keepScroll(stage);

    /* Solved, not chosen -- see the header. The floor is the line at the foot
       of the page when there is one: the book now ends just above it, and a
       leaf solved against the window would swing over it. */
    const barBottom = bar.getBoundingClientRect().bottom;
    const floor = foot ? Math.min(window.innerHeight, foot.getBoundingClientRect().top) : window.innerHeight;
    const room = Math.min(tr.top - barBottom, floor - (tr.top + H));
    const m = Math.max(10, (Number.isFinite(room) ? room : 24) - 6);
    const P = Math.max(1800, half + (H * half) / (2 * m));
    stage.style.perspective = `${P.toFixed(0)}px`;
    stage.style.perspectiveOrigin = `${half}px ${H / 2}px`;

    let raf = 0;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      cancelAnimationFrame(raf);
      clearTimeout(guard);
      stage.remove();
      turn = null;
      settleFocus();
    };
    /* A starved frame loop must never leave a copy of a page on the desk. */
    const guard = setTimeout(finish, TURN_MS + 900);

    /* Two frames later, so the incoming page has been laid out AND its
       canvases redrawn at their real size before they are copied onto the
       back of the leaf. One frame was measured to be too early: a
       requestAnimationFrame queued from the click runs before that frame's
       layout, so the transport's ResizeObserver had not yet redrawn its
       lanes and the copy showed them stretched from the size they had while
       hidden. That face is edge-on at the start, so the delay is invisible. */
    raf = requestAnimationFrame(() => { raf = requestAnimationFrame(() => {
      leaf.fillBack(halfOf(to, stays, half), H);
      const t0 = performance.now();
      const frame = (now) => {
        const t = Math.min(1, (now - t0) / TURN_MS);
        if (reduced()) { finish(); return; }
        const e = t * t * t * (t * (6 * t - 15) + 10);
        leaf.pose(e);
        const th = Math.PI * e;
        const reach = half * Math.abs(Math.cos(th));
        const lift = Math.sin(th);
        under.style.setProperty("--w", `${(th < Math.PI / 2 ? reach * 1.15 : 0).toFixed(1)}px`);
        under.style.setProperty("--o", (th < Math.PI / 2 ? lift * 0.55 : 0).toFixed(3));
        over.style.setProperty("--w", `${(th > Math.PI / 2 ? reach * 1.15 : 0).toFixed(1)}px`);
        over.style.setProperty("--o", (th > Math.PI / 2 ? lift * 0.5 : 0).toFixed(3));
        if (t < 1) raf = requestAnimationFrame(frame);
        else finish();
      };
      raf = requestAnimationFrame(frame);
    }); });

    return { finish };
  }

  /* A chain of strips hinged at the gutter. The registered mechanism from
     leaf.js -- each strip nested in the last and adding a little rotation, so
     the chain's tangent sweeps an arc and the surface bends rather than
     pivoting like a door -- with a page on each face instead of a cover.
     `turning` and the side given to fillBack are halfOf() results. */
  function buildLeaf(dir, half, turning) {
    const root = el("div", "cx__leaf");
    root.dataset.dir = dir;
    root.style.width = `${half}px`;
    const sw = half / STRIPS;
    const strips = [];
    let parent = root;
    for (let i = 0; i < STRIPS; i += 1) {
      const s = el("div", "cx__strip");
      s.style.width = `${sw}px`;
      const front = el("div", "cx__face cx__face--front");
      const back = el("div", "cx__face cx__face--back");
      const copy = proxy(turning.page, turning.width);
      copy.style.left = `${turning.shift - (dir === "next" ? i * sw : half - (i + 1) * sw)}px`;
      front.append(copy, el("div", "cx__sh"));
      back.append(el("div", "cx__sh"));
      s.append(front, back);
      if (i === STRIPS - 1) s.classList.add("is-edge");
      parent.appendChild(s);
      parent = s;
      strips.push({ s, back });
    }

    return {
      root,
      fillBack(side, h) {
        strips.forEach(({ back }, i) => {
          const copy = proxy(side.page, side.width);
          copy.style.minHeight = `${h}px`;
          copy.style.height = `${h}px`;
          copy.style.left = `${side.shift - (dir === "next" ? half - (i + 1) * sw : i * sw)}px`;
          back.insertBefore(copy, back.firstChild);
        });
        keepScroll(root);
      },
      /* The registered applyTurn, run on this chain. `sign` flips the whole
         thing for a leaf hinged on its right edge. */
      pose(e) {
        const sign = dir === "next" ? -1 : 1;
        const th = Math.PI * e;
        const beta = CURL * Math.sin(Math.PI * e);
        const tt = th + beta;
        const td = (2 * beta) / STRIPS;
        root.style.transform = `rotateY(${(sign * tt * 180 / Math.PI).toFixed(2)}deg)`;
        strips.forEach(({ s }, i) => {
          if (i > 0) s.style.transform = `rotateY(${(-sign * td * 180 / Math.PI).toFixed(3)}deg)`;
          const l1 = Math.abs(Math.cos(tt - i * td));
          const l2 = Math.abs(Math.cos(tt - (i + 1) * td));
          s.style.setProperty("--a1", ((1 - l1) * SHADE).toFixed(3));
          s.style.setProperty("--a2", ((1 - l2) * SHADE).toFixed(3));
          s.style.setProperty("--gl", (Math.sin(th) * l1 * l1 * 0.09).toFixed(3));
        });
      },
    };
  }

  /* --- flowing long material across spreads ----------------------------

     `items` are elements the page built and wired. They are moved, never
     cloned or rebuilt, so their listeners and state go with them. */

  function runFlow(f) {
    const ch = book.querySelector(`[data-cx-chapter="${CSS.escape(f.chapter)}"]`);
    if (!ch) return;
    for (const old of ch.querySelectorAll("[data-cx-cont]")) old.remove();
    const first = ch.querySelector("[data-cx-flow]");
    if (!first) return;
    if (f.prepare) f.prepare();
    for (const r of ch.querySelectorAll("[data-cx-flow]")) r.replaceChildren();

    if (!wide) {
      first.append(...f.items);
      if (f.after) f.after([first]);
      return;
    }

    /* Measured while laid out but invisible: the chapter is taken out of the
       flow and hidden from sight, never from layout, so every width and
       height below is the one the reader will see. */
    const wasHidden = ch.hidden;
    const hiddenSpreads = [...ch.querySelectorAll("[data-cx-spread]")].filter((s) => s.hidden);
    ch.hidden = false;
    for (const s of hiddenSpreads) s.hidden = false;
    ch.classList.add("cx--measure");

    /* The room a region has: from its own top to the folio, less the page's
       gap above the folio and a few pixels of slack. The slack is not a
       guess at the font: it absorbs the sub-line drift between a layout
       measured now and the same text after a late face or an emoji glyph has
       loaded, which was measured at up to 15px on the Duo comments. */
    const SLACK = 8;
    const capacity = (region) => {
      const pg = region.closest("[data-cx-page]");
      const folio = pg.querySelector("[data-cx-folio]");
      const gap = parseFloat(getComputedStyle(pg).rowGap) || 0;
      return folio.getBoundingClientRect().top - gap - region.getBoundingClientRect().top - SLACK;
    };

    /* Every flow region the chapter was built with, in reading order -- a
       chapter can open with flow on both of its first pages -- then as many
       more as the material needs. */
    const regions = [...ch.querySelectorAll("[data-cx-flow]")];
    const caps = regions.map(capacity);
    first.append(...f.items);
    const gap = parseFloat(getComputedStyle(first).rowGap) || 0;
    const heights = f.items.map((it) => it.getBoundingClientRect().height);
    first.replaceChildren();

    let n = 1;
    const more = () => {
      n += 1;
      const last = [...ch.querySelectorAll("[data-cx-spread]")].pop();
      last.insertAdjacentHTML("afterend", f.cont(n));
      const added = [...ch.querySelectorAll("[data-cx-spread]")].pop();
      for (const r of added.querySelectorAll("[data-cx-flow]")) {
        regions.push(r);
        caps.push(capacity(r));
      }
    };

    let r = 0;
    let used = 0;
    let placed = 0;
    f.items.forEach((it, i) => {
      const need = (placed ? gap : 0) + heights[i];
      if (placed && used + need > caps[r] + 0.5) {
        r += 1;
        if (!regions[r]) more();
        used = 0;
        placed = 0;
      }
      regions[r].appendChild(it);
      used += (placed ? gap : 0) + heights[i];
      placed += 1;
    });

    /* Checked against the real layout, not only the estimate. Anything that
       made a region taller once it was actually placed -- a line that broke
       differently beside its neighbours, a glyph from a fallback face --
       sends that region's last item on to the next one. */
    for (let i = 0; i < regions.length; i += 1) {
      const reg = regions[i];
      while (reg.childElementCount > 1 && reg.getBoundingClientRect().height > caps[i] + 0.5) {
        if (!regions[i + 1]) more();
        regions[i + 1].insertBefore(reg.lastElementChild, regions[i + 1].firstChild);
      }
    }

    ch.classList.remove("cx--measure");
    ch.hidden = wasHidden;
    if (f.after) f.after(regions);
  }

  /**
   * Register material that may need more than one spread. `cont(n)` returns
   * the markup of the nth spread of the chapter, holding two [data-cx-flow]
   * regions; `after(regions)` is told where everything landed.
   */
  function flow(f) {
    flows.push(f);
    relayout();
  }

  function relayout() {
    const current = spreads[at];
    const ch = current ? chapterOf(current) : null;
    const index = current && ch ? [...ch.querySelectorAll("[data-cx-spread]")].indexOf(current) : 0;
    if (turn) turn.finish();
    for (const f of flows) runFlow(f);
    number();
    /* The same spread if it still exists; otherwise the nearest one in the
       same chapter, never a jump to somewhere the reader was not. */
    if (current && current.isConnected) at = spreads.indexOf(current);
    else if (ch) {
      const own = [...ch.querySelectorAll("[data-cx-spread]")];
      at = spreads.indexOf(own[Math.min(index, own.length - 1)]);
    }
    if (pendingKey) {
      const hit = spreads.findIndex((s) => s.dataset.cxKey === pendingKey);
      if (hit >= 0) { at = hit; pendingKey = null; }
    }
    if (at < 0) at = 0;
    paint();
  }

  /* --- wiring --------------------------------------------------------- */

  prevBtn.addEventListener("click", () => step(-1));
  nextBtn.addEventListener("click", () => step(1));
  for (const l of links) {
    l.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
      event.preventDefault();
      goChapter(l.dataset.cxGoto);
    });
  }
  host.addEventListener("click", (event) => {
    const ref = event.target.closest("[data-cx-xref]");
    if (!ref) return;
    const target = book.querySelector(`#${CSS.escape(ref.dataset.cxXref)}`);
    const s = target && target.closest("[data-cx-spread]");
    if (!s) return;
    event.preventDefault();
    show(spreads.indexOf(s));
    target.setAttribute("tabindex", "-1");
    requestAnimationFrame(() => target.focus({ preventScroll: true }));
  });

  /* Left and right turn the page, and nothing else is intercepted. A key is
     left alone whenever the focus is in a field, on a control that uses the
     arrows itself -- the transport, the ledger, the comparison's divider --
     or carries a modifier. */
  const owned = (t) => {
    if (!t || !t.closest) return false;
    const tag = t.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable
      /* A grid and a tab list use the arrows themselves. At the theme grid's
         first and last cell its handler stood aside, and Left or Right turned
         the page out from under the reader (INCLUSIVE_DESIGN.md A14). */
      || t.closest("[data-transport], [role=slider], [data-ledger], [role=grid], [role=tablist]") !== null;
  };
  window.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey
      || event.metaKey || event.shiftKey) return;
    if (owned(event.target) || readsAsPage()) return;
    if (event.key === "ArrowRight") { event.preventDefault(); step(1); }
    else if (event.key === "ArrowLeft") { event.preventDefault(); step(-1); }
  });

  /* A hash typed into the address bar, or followed from a link inside the
     page, opens that spread. Our own writes use replaceState, which fires no
     hashchange, so this only ever answers the reader. */
  window.addEventListener("hashchange", () => {
    const key = decodeURIComponent(location.hash.replace(/^#/, ""));
    const hit = spreads.findIndex((s) => s.dataset.cxKey === key);
    if (hit >= 0) show(hit);
  });

  /* Pagination depends on the page's size, so a real change of size lays the
     book out again. The breakpoint does too: the single-page layout has no
     spreads to fill. */
  const mq = window.matchMedia(WIDE_QUERY);
  mq.addEventListener("change", () => { wide = isWide(); fit(); relayout(); });

  /* PRINTING IS READING AS ONE PAGE, ON PAPER (R5).

     Printed as the book, only the spread on the desk printed -- every other
     spread carries `hidden` -- and the dark paper's near-white ink printed at
     1.19:1 once the browser dropped the backgrounds (verify_ui.py check 21,
     25 Sep 2026). So for the length of a print the book becomes the one-page
     reading in the paper display, and goes back afterwards. Chosen here rather
     than in a print stylesheet because every page but the current one carries
     `hidden`, and no stylesheet in this project may give [hidden] a display
     back (tests/test_ui_contracts.py, TestHidingActuallyHides). */
  let printing = null;
  window.addEventListener("beforeprint", () => {
    const root = document.documentElement;
    printing = { read: root.dataset.read || null, theme: currentTheme() };
    root.dataset.read = "page";
    if (printing.theme !== "field") applyTheme("field", { persist: false });
    wide = isWide();
    fit();
    paint();
  });
  window.addEventListener("afterprint", () => {
    if (!printing) return;
    const root = document.documentElement;
    if (printing.read) root.dataset.read = printing.read;
    else delete root.dataset.read;
    if (printing.theme !== "field") applyTheme(printing.theme, { persist: false });
    printing = null;
    wide = isWide();
    fit();
    relayout();
  });
  let lastSize = `${window.innerWidth}x${window.innerHeight}`;
  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    /* The block follows the window at once; only the re-pagination, which
       moves every comment, waits for the resize to settle. */
    if (turn) turn.finish();
    fit();
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const size = `${window.innerWidth}x${window.innerHeight}`;
      if (size === lastSize) return;
      lastSize = size;
      if (wide && flows.length) relayout();
    }, 220);
  });
  /* Measured again once the real faces have loaded: a paragraph set in the
     fallback serif is a different height from the same one in Newsreader,
     and the chapter bar is set in Archivo. */
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      fit();
      if (flows.length) relayout();
      /* Everything that can make a spread has run by now; a name that still
         matches nothing never will, and must not hijack a later layout. */
      pendingKey = null;
    });
  }

  number();
  /* A link or a refresh that names a spread opens at it -- now if the spread
     exists, or when the flow that makes it has run. */
  if (pendingKey) {
    const hit = spreads.findIndex((s) => s.dataset.cxKey === pendingKey);
    if (hit >= 0) { at = hit; pendingKey = null; }
  }
  paint();

  return {
    go: show,
    step,
    goChapter,
    flow,
    relayout,
    at: () => at,
    current: () => spreads[at],
    isWide: () => wide,
    /** Bring forward the spread holding `element`, wherever it has flowed. */
    reveal(element) {
      const s = element && element.closest("[data-cx-spread]");
      if (s) show(spreads.indexOf(s));
    },
  };
}

/* ------------------------------------------------------------ copies ---- */

/* Scroll each copy under `root` to where its original was, so the page that
   turns over is the part of it the reader was looking at. */
function keepScroll(root) {
  for (const c of root.querySelectorAll("[data-cx-scroll]")) {
    const body = c.querySelector(".cx__body");
    if (body) body.scrollTop = Number(c.dataset.cxScroll) || 0;
  }
}

/* An inert, unreadable-to-assistive-technology copy of a live page, for the
   length of one turn. Ids are stripped so the document never holds two
   elements with one id, and canvases are repainted from the originals --
   cloneNode copies a canvas element but not a single pixel of it, and the
   transport's four lanes would otherwise turn over blank. */
function proxy(page, width) {
  const copy = page.cloneNode(true);
  copy.classList.add("cx__proxy");
  copy.setAttribute("aria-hidden", "true");
  copy.inert = true;
  copy.removeAttribute("data-cx-page");
  for (const e of copy.querySelectorAll("[id]")) e.removeAttribute("id");
  copy.style.width = `${width}px`;
  /* A page taller than the block is read by scrolling inside it, and
     cloneNode does not carry a scroll position: noted here, applied by
     keepScroll once the copy is in the document and has its height. */
  const body = page.querySelector(".cx__body");
  if (body && body.scrollTop) copy.dataset.cxScroll = String(body.scrollTop);
  const src = page.querySelectorAll("canvas");
  const dst = copy.querySelectorAll("canvas");
  src.forEach((c, i) => {
    const d = dst[i];
    if (!d || !c.width || !c.height) return;
    d.width = c.width;
    d.height = c.height;
    try { d.getContext("2d").drawImage(c, 0, 0); } catch { /* a tainted or WebGL canvas stays blank */ }
  });
  return copy;
}

/* The half of the spread that stays still while the leaf turns. A whole page
   is its own copy; half of a fold-out is a window onto a copy of the sheet. */
function slice({ page, width, shift }, half) {
  const copy = proxy(page, width);
  if (!shift && width === half) return copy;
  const win = el("div", "cx__window");
  win.style.width = `${half}px`;
  copy.style.left = `${shift}px`;
  win.appendChild(copy);
  return win;
}

/* ------------------------------------------------- opening and closing -- */

const BOOK = 0.887 / 1.33;   /* the volume's proportion, from shelfgeom.js */

/* Where the closed volume sits on the desk. A cover is hinged at the spine
   and this book's spine is the gutter, so the closed board lies on the RECTO
   with its left edge on the gutter and swings open to the left, over the
   verso -- the way a book on a desk actually opens. The last build landed it
   on the verso, hinged at the page's outer edge, which is the wrong side of
   the book. On a single page the spine is the page's left edge. Never
   stretched: whichever of height or width binds first decides the size. */
function desk(root) {
  const pages = root.querySelector("[data-cx-spread]:not([hidden]) .cx__pages");
  if (!pages) return null;
  const box = pages.getBoundingClientRect();
  const mast = document.querySelector(".masthead");
  const ceiling = (mast ? mast.getBoundingClientRect().bottom : 0) + 6;
  const floor = window.innerHeight - 6;
  const wide = isWide();
  const spine = wide ? box.left + box.width / 2 : box.left;
  const room = wide ? box.width / 2 : box.width;
  /* The part of the page block actually on screen. The closed volume is set
     a little inside it and centred on it, so there is room both above and
     below for the board to grow toward the viewer as it swings. Landed at
     the block's full height it was measured running 66px past the foot of
     the window mid-swing. */
  const top = Math.max(box.top, ceiling);
  const H = Math.max(160, Math.min(box.bottom, floor) - top);
  let h = H * 0.9;
  let w = h * BOOK;
  if (w > room) { w = room; h = w / BOOK; }
  const to = { x: spine, y: top + (H - h) / 2, w, h };
  /* The board's growth at each end is (h / 2) * w / (P - w); the room it has
     is the smaller of the gaps to the masthead and to the foot of the window.
     Solved for P, as the page turn is. */
  const m = Math.max(12, Math.min(to.y - ceiling, floor - (to.y + h)));
  const P = Math.max(1750, w + (h * w) / (2 * m));
  return { to, P, origin: { x: spine, y: to.y + h / 2 } };
}

/**
 * The carried volume flies from the shelf to the desk and opens onto the
 * first spread. Returns false, and draws nothing, whenever it cannot: no
 * carried volume, reduced motion, nothing measurable. The page is then simply
 * there, which is the normal path rather than a degraded one.
 */
export function openBook(root, carried) {
  const at = carried ? desk(root) : null;
  const release = () => {
    const wasOpening = root.hasAttribute("data-opening");
    delete root.dataset.opening;
    const book = root.querySelector("[data-cx]");
    if (wasOpening && book && !reduced()) {
      book.animate([{ opacity: 0 }, { opacity: 1 }],
        { duration: 460, easing: "cubic-bezier(.2,.7,.2,1)" });
    }
  };
  if (!at) { release(); return false; }
  const played = openVolume(document.body, {
    cover: carried.cover,
    from: carried.rect,
    to: at.to,
    perspective: at.P,
    origin: at.origin,
    /* The book is revealed whole the moment the board is far enough open to
       see past -- the real first spread, already laid out, fading up under
       the board that is still swinging over it. */
    onReveal: release,
  });
  if (!played) release();
  return played;
}

/**
 * The reverse, on the way out: the board swings back over the pages and the
 * closed volume leaves the desk, then the navigation happens. Only possible
 * when this page was opened from the shelf and so holds the painted cover;
 * any other close is a plain link, and the navigation never waits on the
 * animation -- a guard sends it after a fixed ceiling whatever happens.
 */
export function wireClose(root, { link, cover, before }) {
  if (!link) return;
  let closing = false;
  link.addEventListener("click", (event) => {
    if (closing) { event.preventDefault(); return; }
    if (before) before();
    if (!cover || reduced() || event.defaultPrevented || event.button !== 0
      || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const at = desk(root);
    if (!at) return;
    event.preventDefault();
    const href = link.href;
    let gone = false;
    const leave = () => { if (!gone) { gone = true; window.location.assign(href); } };
    setTimeout(leave, 1900);
    closing = true;
    const played = closeVolume(document.body, {
      cover, to: at.to, perspective: at.P, origin: at.origin, onDone: leave,
      onCover: () => { root.dataset.closing = "yes"; },
    });
    if (!played) leave();
  });
}
