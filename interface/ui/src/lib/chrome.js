/* ===========================================================================
   chrome.js — the masthead, the footer, and the theme control.

   Mounted by every page. The mark is drawn rather than lettered: this product
   is an instrument, so its identity is its own subject, four tracks against
   one clock with the playhead standing where they stop agreeing.
   ======================================================================== */

import { sweepTheme, reduced, reducedBySystem, motionSwitchedOff, setMotionOff, onReducedChange } from "./motion.js";
import { announce } from "./announce.js";
import { currentTheme, onThemeChange } from "./theme.js";

const PAGES = [
  ["/", "Opening"],
  ["/run", "Analyse"],
  ["/library", "Library"],
  /* In the same place on every page (WCAG 3.2.3, 3.2.6): what works, what does
     not, and who the reports are about (INCLUSIVE_DESIGN.md I4). */
  ["/accessibility", "Accessibility"],
];

/* The two displays, by the words a reader uses for them. The attribute
   values stay "bench" and "field" because every stylesheet keys off them. */
const DISPLAYS = [
  ["bench", "Dark"],
  ["field", "Light"],
];

/* The mark. Four slices of a play triangle with the third pushed out of line:
   the same object the water gate refracts and the same one the hero carries, so
   the door, the boot screen, the hero and every page after them are showing one
   identity rather than three. */
const MARK = `
<svg class="mark__glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
  <path d="M4.46 3L10.68 7L4.46 7Z
           M4.46 7.6L11.62 7.6L17.84 11.6L4.46 11.6Z
           M6.16 12.4L19.54 12.4L13.32 16.4L6.16 16.4Z
           M4.46 17L10.68 17L4.46 21Z"/>
</svg>`;

/* The burger, as three paths that become a cross. Drawn rather than lettered so
   the open and closed states are one object rotating, not two icons swapped. */
const BURGER = `
<svg viewBox="0 0 22 14" aria-hidden="true" focusable="false">
  <path class="b1" d="M1 1 H21"/>
  <path class="b2" d="M1 7 H21"/>
  <path class="b3" d="M1 13 H21"/>
</svg>`;

export function mountMasthead(host, { here = "" } = {}) {
  if (!host) return;
  const theme = currentTheme();

  /* One markup tree serves every width. On a wide screen the links sit along
     the bar; below that the same elements are collected into a panel behind a
     button. The switch is a checkbox and a media query -- no JavaScript decides
     which layout is showing, so there is nothing to get out of step with the
     viewport and nothing to run on resize.

     The checkbox keeps a real, focusable input rather than a hidden one: it is
     what makes the menu operable from the keyboard without a single handler. */
  /* The menu toggle is named on the checkbox itself (aria-label="Menu"); the
     <label> beside it carries no name of its own, because aria-label is not
     permitted on a <label> -- axe-core flagged it on every page below 900px
     (25 Sep 2026, INCLUSIVE_DESIGN.md). */
  host.innerHTML = `
    <a class="mark" href="/">${MARK}<span>BrandPulse</span></a>

    <input class="navtoggle" type="checkbox" id="nav-open" aria-label="Menu">
    <label class="scrim" for="nav-open" aria-hidden="true"></label>
    <label class="burger" for="nav-open">${BURGER}</label>

    <div class="navpanel">
      <nav class="nav" aria-label="Sections">
        ${PAGES.map(([href, label]) => `
          <a href="${href}"${href === here ? ' aria-current="page"' : ""}>${label}</a>`).join("")}
      </nav>
      <div class="display" role="group" aria-label="Display">
        ${DISPLAYS.map(([value, label]) => `
        <button class="display__opt" type="button" data-theme-set="${value}"
                aria-pressed="${theme === value}">${label}</button>`).join("")}
      </div>
      <div class="display display--motion" role="group" aria-label="Motion">
        <button class="display__opt" type="button" data-motion-toggle
                aria-pressed="${reduced()}">Reduce motion<span class="sr-only" data-motion-why></span></button>
      </div>
      <a class="pill" href="/run">Analyse a video</a>
    </div>`;

  /* THE DISPLAY SWITCH SAYS WHICH DISPLAY IT IS ON.

     It was a 26px lit rectangle with no words, whose only statement of state
     was a fill that changed from grey to white, so nothing on screen said
     what it did or which way it was set. Two named options with the current
     one pressed is a control nobody has to learn: the choice is the label,
     and the state is visible without hovering. */
  const options = [...host.querySelectorAll("[data-theme-set]")];
  const reflect = (value) => {
    for (const option of options) {
      option.setAttribute("aria-pressed", String(option.dataset.themeSet === value));
    }
  };
  for (const option of options) {
    option.addEventListener("click", () => {
      const next = option.dataset.themeSet;
      if (next === currentTheme()) return;
      sweepTheme(next);
    });
  }
  /* Kept true whoever changed it: this control, another tab, or anything
     else that calls applyTheme. */
  onThemeChange(reflect);

  /* REDUCE MOTION, ON THE PAGE AS WELL AS IN THE SYSTEM (25 Sep 2026).

     Three of five people in the final evaluation asked for a way to turn the
     motion off (D5). The operating-system setting is honoured everywhere and
     always has been, but most readers who need it have never found it, and a
     reader with a migraine, a vestibular condition, a slow laptop or a
     projector needs it on this page now. One button, worded like the setting
     it mirrors, pressed when motion is reduced. When the OS already asks for
     reduced motion the page cannot overrule it, so the button stays pressed
     and says why rather than pretending to be switchable. */
  const motionBtn = host.querySelector("[data-motion-toggle]");
  const why = host.querySelector("[data-motion-why]");
  const reflectMotion = () => {
    motionBtn.setAttribute("aria-pressed", String(reduced()));
    const locked = reducedBySystem();
    motionBtn.setAttribute("aria-disabled", String(locked));
    why.textContent = locked ? " (set by your system)" : "";
  };
  motionBtn.addEventListener("click", () => {
    if (reducedBySystem()) {
      announce("Motion is reduced by your system setting, so the page keeps it reduced.");
      return;
    }
    const off = !motionSwitchedOff();
    setMotionOff(off);
    announce(off ? "Motion reduced. Nothing on the page will move on its own."
      : "Motion back on.");
  });
  onReducedChange(reflectMotion);
  reflectMotion();

  /* Following a link closes the panel. Without this, returning to a page with
     the browser's back button can restore a checked checkbox and an open menu
     over content the reader did not ask to cover. */
  host.querySelectorAll(".navpanel a").forEach((link) => {
    link.addEventListener("click", () => {
      const box = host.querySelector(".navtoggle");
      if (box) box.checked = false;
    });
  });

  /* Escape closes an open menu and puts the keyboard back on its toggle. The
     panel is a checkbox and CSS, so it had no way out but pressing the toggle
     again -- which a keyboard reader inside the panel first has to find. */
  host.addEventListener("keydown", (event) => {
    const box = host.querySelector(".navtoggle");
    if (event.key !== "Escape" || !box || !box.checked) return;
    box.checked = false;
    box.focus({ preventScroll: true });
  });
}

export function mountFooter(host, { tests } = {}) {
  if (!host) return;
  /* THE TWO BOOKS CARRY ONE LINE, NOT THE BAND.

     A report is a book sized to one screen, and the three-column band under
     it was a second page the reader had to scroll to, saying what the opening
     page already says. The library and the opening page dropped it for the
     same reason. Asked for on 23 Sep 2026: "the footer of the report page is
     ugly ... put a very simple one". Both lines are true of every report: the
     analysis ran here, and the controller is a local model (README, "Engineering
     rules"). No middle dot between the two halves of the first line:
     the build separates with rules and words, never a dot pressed into
     service as one (tests/test_ui_contracts.py). */
  if (host.dataset.footer === "slim") {
    host.classList.add("end", "end--slim");
    host.innerHTML = `
    <p class="end__sig">BrandPulse, a CM3070 final-year project</p>
    <p>Read on this machine, by a local model</p>`;
    holdUntilSettled(host);
    return;
  }
  host.innerHTML = `
    <div class="foot__grid">
      <div>
        <h2 class="t-label">What this reads</h2>
        <p>Four channels read one video independently: the words, the face, the
           voice, and what the room wrote underneath. A local model is asked
           where those four accounts stop matching. They are never fused into
           one number.</p>
      </div>
      <div>
        <h2 class="t-label">Where the data stays</h2>
        <p>On this machine. The controller is reached at
           <code>localhost:11434</code>, and nothing is fetched from anywhere
           to render this page, including the typefaces it is set in.</p>
      </div>
      <div>
        <h2 class="t-label">Where the numbers came from</h2>
        <p>Every figure here was measured on this project&rsquo;s own
           hand-labelled data and is re-derived from its source by
           <code>ui_evidence/extract_figures.py</code>${
             typeof tests === "number"
               ? `. ${tests.toLocaleString("en-GB")} tests pass against it`
               : ""}. Nothing is illustrative.</p>
      </div>
    </div>
    <p class="foot__sig t-micro u-faint">CM3070 final-year project</p>`;
  holdUntilSettled(host);
}

/* THE FOOTER DOES NOT FLOAT IN AN EMPTY PAGE.

   Every page mounts its chrome first and renders its own content after, which
   even against a local server is about a seventh of a second later. For that
   seventh the footer is the ONLY block in the document, so it sits wherever an
   empty page leaves it -- measured at y=535 on the report at 1440x900, halfway
   up the window and well above the fold. It reads as a flash of some other
   page arriving between the shelf and the book, which is exactly what it was
   reported as.

   The boot panel is the signal, and a reliable one: every page in this build
   renders by replacing its main element wholesale, which removes it. Two ways
   out, because a footer that never arrives is worse than one that arrives
   late -- a page with no boot panel has nothing to wait for and shows it at
   once, and a six-second stop releases it anyway if a page never finishes. */
function holdUntilSettled(host) {
  let stop = 0;
  let watch = null;
  /* hasAttribute, not dataset.waiting. The attribute is written valueless in
     the markup, so dataset gives back the empty string -- which is falsy, so a
     truthiness guard here returns early every time and the footer is held for
     the life of the page. It is invisible rather than mistimed, which is the
     harder kind of bug to notice: the flash it was meant to remove is gone
     either way. */
  const release = () => {
    if (!host.hasAttribute("data-waiting")) return;
    host.removeAttribute("data-waiting");
    if (watch) watch.disconnect();
    clearTimeout(stop);
  };

  const main = document.querySelector("main");
  const boot = main && main.querySelector("[data-boot]");
  /* No boot panel means nothing to wait for: this page had its content before
     the footer did. Release rather than return -- the attribute is in the
     static markup now, so returning here would leave the footer held for good. */
  if (!main || !boot) { release(); return; }

  watch = new MutationObserver(() => { if (!boot.isConnected) release(); });
  watch.observe(main, { childList: true, subtree: true });
  stop = setTimeout(release, 6000);
}

export function mountAll({ here, tests } = {}) {
  /* The bundle is running, which is all the no-script timer exists to find
     out (each document's head). From here every page renders its own error
     state if its data fails, so the "needs JavaScript" core must not come
     back. It used to be cleared here (B1, 12 Sep); after the redesigns each
     page cleared it only once all its reads had finished, so a library read
     slower than four seconds put the fallback -- "this browser is not running
     JavaScript", and a second h1 -- on screen for good beside the shelf
     (INCLUSIVE_DESIGN.md A10). */
  clearTimeout(window.__bpFallback);
  /* A bundle that arrived after the timer fired (a slow first load) takes the
     page back from the fallback rather than rendering beside it. */
  document.documentElement.classList.add("js");
  mountMasthead(document.querySelector("[data-chrome]"), { here });
  mountFooter(document.querySelector("[data-footer]"), { tests });
}

export { reduced };
