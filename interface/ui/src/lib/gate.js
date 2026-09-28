/*
   gate.js — the door.

   The opening page opens behind deep water with the mark suspended in it. You
   touch it and it rings; you click and you are through. It shows on every visit
   to "/" and on no other address, because a marker who opens a report directly
   wants the report, not a performance.

   Three ways out, deliberately. A gate that cannot be dismissed is not a design
   flourish, it is a page nobody ever sees:

     1. Click, tap, Enter, or Space.
     2. Escape.
     3. On its own, once the page behind it has finished building.

   The third one is the safety. It runs off a hard timer that starts whether or
   not the page behind reports ready, so a failed fetch under the gate cannot
   strand a reader in front of it. And if the effect will not run at all, there
   is no gate: mountElemental returns null and the page shows immediately.

   Nothing here is remembered between visits. That is the brief. The examiner
   sees the launch every time they come back to the front door, and never when
   they refresh a report.
*/

import "../styles/gate.css";

import { mountElemental } from "../gl/elemental.js";
import { MS, reduced } from "./motion.js";

/* How long the water holds once the page behind it is built. Long enough to
   read the line and watch one ring cross the mark, short enough that nobody
   reaches for the mouse. Reduced motion gets a shorter hold: there is no
   animation to wait for, only the sentence to read. */
const HOLD_MS = 10000;
const HOLD_REDUCED_MS = 4000;

/* The ceiling. If the page behind never calls ready() — a fetch that hangs, a
   module that throws — the gate leaves anyway. */
const CEILING_MS = 4000;

/* The fade is the shared slow duration, read from tokens.css through MS so
   this cannot drift from the stylesheet that actually performs it. */
const fadeMs = () => MS.slow;

function markup() {
  /* Almost nothing. The mark in the water is the identity, so the words get out
     of its way: a quiet label in the corner, and one line telling you what to
     do. An earlier version stacked a heading, a sentence and a block button in
     the bottom-left corner, which fought the picture and won.

     The line is a real <button> rather than a caption. It is the only focusable
     thing on the screen, it is focused on arrival, and Enter and Space activate
     it natively -- so the instruction and the control are the same object
     instead of a label sitting next to a hidden one. */
  return `
    <h1 class="gate__name">BrandPulse AI</h1>
    <button class="gate__begin" type="button">
      <span class="gate__begin__say">Click anywhere to begin</span>
      <span class="gate__begin__key">or press space</span>
      <span class="gate__hold" aria-hidden="true"><i></i></span>
    </button>
  `;
}

/**
 * Raise the gate over the document.
 *
 * @param {Object}   [opts]
 * @param {Function} [opts.onEnter]  called once, after the gate has gone.
 * @returns {{ready: Function, dismiss: Function}|null}
 *          null when the effect cannot run, meaning there is no gate at all.
 */
export function mountGate({ onEnter } = {}) {
  const host = document.createElement("div");
  host.className = "gate";
  host.dataset.gate = "";

  /* A dialog in the accessibility tree, not just a coloured box. It owns the
     screen while it is up, so it says so. */
  host.setAttribute("role", "dialog");
  host.setAttribute("aria-modal", "true");
  host.setAttribute("aria-label", "BrandPulse AI");
  host.innerHTML = markup();

  const water = mountElemental(host);
  if (!water) return null;                       // no gate rather than a dead one

  const chassis = document.querySelector(".chassis");
  document.body.append(host);
  document.documentElement.classList.add("gated");
  if (chassis) chassis.inert = true;             // nothing behind is tabbable

  const enter = host.querySelector(".gate__begin");
  const hold = host.querySelector(".gate__hold");
  const bar = hold.querySelector("i");

  const previouslyFocused = document.activeElement;

  /* Focus goes into the dialog straight away, because a modal that owns the
     screen and focuses nothing strands a screen-reader user outside it. But
     focusing programmatically on arrival also paints a focus ring around the
     one control for someone who arrived with a mouse and has pressed nothing.

     So the gate starts "quiet": focused, reachable, ring suppressed. The first
     real key press drops the flag and the ring behaves normally from then on --
     and a keyboard user's first act is always a key press, so they never lose
     it when they need it. */
  host.dataset.quiet = "";
  enter.focus({ preventScroll: true });

  let onKey;
  let next = null;
  let gone = false;
  let holdTimer = 0;
  let ceilingTimer = 0;

  function dismiss() {
    if (gone) return;
    gone = true;
    clearTimeout(holdTimer);
    clearTimeout(ceilingTimer);

    /* Stop drawing before the fade, not after. Nine hundred milliseconds of
       ripple simulation behind an element that is on its way to zero opacity is
       nine hundred milliseconds the page behind could have spent laying out. */
    water.stop();

    /* Hand over BEFORE the fade, not after it.

       The gate takes most of a second to dissolve. Mounting the next screen in
       finish(), once that was over, meant the water faded onto the PAGE and the
       next screen then covered it up -- a clear flash of the finished document
       between the two, which is exactly what it should not show. Mounting it
       here, underneath, means the water dissolves onto it instead.

       It mounts paused. Whatever comes next is told to begin in finish(), when
       the gate is actually out of the way, so its opening is not playing to a
       covered screen. */
    next = onEnter ? onEnter() : null;

    host.classList.add("is-going");
    /* The chassis stays inert if something else has taken the screen -- that
       screen owns the tab order now, not the page behind both of them. */
    if (chassis && !next) chassis.inert = false;
    document.documentElement.classList.remove("gated");

    const finish = () => {
      /* Unbind here, and only here. An earlier version hung this off
         transitionend on the host, which was wrong twice over: transitionend
         bubbles, so the hold bar's own 280ms fade ended and tore down the key
         listener while the gate was still up, and Escape stopped working
         seconds after the gate appeared. Measured, not theorised. */
      document.removeEventListener("keydown", onKey);
      water.destroy();
      host.remove();

      /* Now, and only now, the screen underneath is visible. */
      if (next && next.start) { next.start(); return; }

      /* Send the caret somewhere real. Returning it to whatever had focus
         before the gate would put it back on <body>, which reads as nowhere.
         Skipped when another screen took over: it has its own focus to keep. */
      const main = document.getElementById("main");
      if (main) {
        main.setAttribute("tabindex", "-1");
        main.focus({ preventScroll: true });
      } else if (previouslyFocused && previouslyFocused.focus) {
        previouslyFocused.focus({ preventScroll: true });
      }
    };

    if (reduced()) finish();
    else setTimeout(finish, fadeMs());
  }

  /* A click anywhere on the water is a way through, and it also throws a ring
     from wherever the pointer was, so the last thing the gate does is answer. */
  host.addEventListener("click", (event) => {
    if (event.target.closest(".gate__begin")) return;   // the button has its own
    dismiss();
  });
  enter.addEventListener("click", dismiss);

  onKey = (event) => {
    delete host.dataset.quiet;
    if (event.key === "Escape") { dismiss(); return; }
    /* Keep the gate a real focus trap while it is up: one control, so Tab has
       nowhere else to go. */
    if (event.key === "Tab") { event.preventDefault(); enter.focus({ preventScroll: true }); }
  };
  document.addEventListener("keydown", onKey);

  /* There is deliberately no key handler on the button. An earlier version
     caught Space to ring the water instead of activating, which is a cute idea
     and a broken button: Space activating a <button> is the contract every
     keyboard and screen-reader user depends on, and a door that swallows it is
     a door that does not open. Enter and Space both dismiss, natively. The
     surface rings on its own timer regardless, so it is never dead. */

  function startHold() {
    if (gone || holdTimer) return;
    const ms = reduced() ? HOLD_REDUCED_MS : HOLD_MS;
    /* Show the wait rather than just serving it. A bar that visibly runs down
       tells a reader the page is going to open by itself; a page that sits
       still for ten seconds tells them it has hung. */
    hold.classList.add("is-running");
    bar.style.transitionDuration = `${ms}ms`;
    requestAnimationFrame(() => { bar.style.transform = "scaleX(1)"; });
    holdTimer = setTimeout(dismiss, ms);
  }

  ceilingTimer = setTimeout(startHold, CEILING_MS);

  return {
    /* Called by the page when its content is actually on the screen, so the
       gate never hands over to a half-built document. */
    ready() {
      clearTimeout(ceilingTimer);
      startHold();
    },
    dismiss,
  };
}
