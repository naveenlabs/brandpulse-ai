/*
   boot.js — the second screen.

   The water gate opens onto this: the system starting up on green phosphor,
   typing out what it loaded and finishing by reporting its own weakest channel.

   Why a boot log is allowed to stand between a reader and the page at all: every
   line of it is true and every figure was measured on this project's own data,
   so it is the product introducing itself rather than a delay dressed as one.
   The lines live in gl/crt.js next to the renderer that types them.

   Same contract as the gate, for the same reason. Three ways out, independent of
   each other, and no screen at all if the effect cannot run:

     1. Click, tap, Enter, or Space -- which first finishes the typing, so a
        reader who presses early sees the whole log rather than losing it.
     2. Escape, which leaves immediately.
     3. On its own, a short hold after the last character lands.
*/

import "../styles/boot.css";

import { mountCrt, LOG_TEXT, TYPE_MS } from "../gl/crt.js";
import { MS, reduced } from "./motion.js";

/* How long the finished log stays up before it lets go. Long enough to read the
   last two lines, which are the ones that matter. */
const HOLD_MS = 1600;
const HOLD_REDUCED_MS = 2600;

/* The ceiling. If the renderer never reports the log finished -- a lost context,
   a frame loop that stops -- the screen leaves anyway. Sized off the log's own
   measured typing time rather than a guess, so editing the log cannot strand
   anyone behind it. */
const CEILING_MS = () => TYPE_MS + 4000;

export function mountBoot({ onDone, autoStart = true } = {}) {
  const host = document.createElement("div");
  host.className = "boot";
  host.dataset.boot = "";
  host.setAttribute("role", "dialog");
  host.setAttribute("aria-modal", "true");
  host.setAttribute("aria-label", "BrandPulse AI starting up");

  /* The log as real text, not only as pixels. A screen reader gets the same
     nineteen lines the canvas is drawing -- including its last line, which is
     the instruction, so there is no caption underneath repeating it. */
  /* A real control to continue with, holding the log as its description, so
     focus has somewhere to be inside this dialog and a screen reader reads the
     log when it arrives there. Until 25 Sep 2026 the dialog had nothing
     focusable at all: the gate's focused button was deleted under the reader
     and focus fell to <body> (INCLUSIVE_DESIGN.md A6). The button shows itself
     only to keyboard focus -- a pointer reader clicks anywhere, as before. */
  host.innerHTML = `
    <pre class="boot__text sr-only" id="boot-log">${LOG_TEXT.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]))}</pre>
    <button class="boot__go" type="button" data-boot-go aria-describedby="boot-log">Continue</button>
  `;
  const go = host.querySelector("[data-boot-go]");

  let crt = null;
  let leaveTimer = 0;
  let ceilingTimer = 0;
  let gone = false;
  let onKey;

  function leave() {
    if (gone) return;
    gone = true;
    clearTimeout(leaveTimer);
    clearTimeout(ceilingTimer);
    document.removeEventListener("keydown", onKey);
    host.classList.add("is-going");
    const finish = () => {
      if (crt) crt.destroy();
      host.remove();
      if (chassis) chassis.inert = false;
      document.documentElement.classList.remove("booting");
      const main = document.getElementById("main");
      if (main) {
        main.setAttribute("tabindex", "-1");
        main.focus({ preventScroll: true });
      }
      if (onDone) onDone();
    };
    if (reduced()) finish();
    else setTimeout(finish, MS.slow);
  }

  /* An early press finishes the log rather than throwing it away: the reader
     asked to get on with it, not to be told less. The second press leaves. */
  let hurried = false;
  function hurryOrLeave() {
    if (hurried || !crt) { leave(); return; }
    hurried = true;
    crt.finish();
  }

  document.documentElement.classList.add("booting");
  document.body.append(host);

  const chassis = document.querySelector(".chassis");
  if (chassis) chassis.inert = true;

  /* Arrived by keyboard: the reader is given the log for as long as they want
     it and leaves with Continue, which is what its own last line says. A
     pointer reader keeps the timed exit. WCAG 2.2.1 -- a keyboard or screen
     reader user can be halfway through the log when a timer takes it away. */
  go.focus({ preventScroll: true });
  const byKeys = go.matches(":focus-visible");

  crt = mountCrt(host, {
    autoStart,
    onTyped() {
      if (gone) return;
      clearTimeout(ceilingTimer);
      if (byKeys) return;
      leaveTimer = setTimeout(leave, reduced() ? HOLD_REDUCED_MS : HOLD_MS);
    },
  });

  /* No WebGL, no boot screen. The page is behind it and wants to be seen. */
  if (!crt) {
    document.documentElement.classList.remove("booting");
    host.remove();
    if (chassis) chassis.inert = false;
    if (onDone) onDone();
    return null;
  }

  host.addEventListener("click", hurryOrLeave);

  /* Keys that are not a request to continue: a modifier on its own, and any
     chord -- VoiceOver's commands are Control+Option chords, and until 25 Sep
     2026 the first one pressed dismissed the screen it was trying to read.
     Enter and Space on the button are left to its own click. */
  const MODIFIERS = ["Shift", "Control", "Alt", "Meta", "CapsLock", "Fn", "OS"];
  onKey = (event) => {
    if (event.key === "Escape") { leave(); return; }
    if (event.key === "Tab") { event.preventDefault(); go.focus({ preventScroll: true }); return; }
    if (MODIFIERS.includes(event.key) || event.ctrlKey || event.altKey || event.metaKey) return;
    if (event.target === go && (event.key === "Enter" || event.key === " ")) return;
    hurryOrLeave();
  };
  document.addEventListener("keydown", onKey);

  if (autoStart && !byKeys) ceilingTimer = setTimeout(leave, CEILING_MS());

  return {
    leave,
    /* Called by the screen above once it has finished getting out of the way. */
    start() {
      if (crt) crt.start();
      if (!byKeys) ceilingTimer = setTimeout(leave, CEILING_MS());
    },
  };
}
