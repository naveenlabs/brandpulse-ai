/* ===========================================================================
   announce.js — the page's voice.

   A screen reader hears nothing when part of a page is rewritten. It hears a
   live region. This module owns the one place in the document where text can
   be put in order to be spoken, and it is a module of its own for a single
   structural reason: the region has to outlive every re-render.

   run.js replaces the whole of [data-run] on each state change, so a region
   written into that markup is destroyed and rebuilt on every transition, and
   a rebuilt region announces nothing — assistive technology tracks the node,
   not the selector. The regions below are appended to <body>, outside the
   subtree any page module rewrites, exactly once per document.

   Two regions, not one. The WAI-ARIA status/alert split is the difference
   between "stage 3 of 4 started", which should wait for a gap in whatever the
   reader is doing, and "the run failed after six minutes", which should not.

   Written 12 Sep 2026. Measured before it existed: the only aria-live on /run
   was the theme toggle's, for a job that takes four to nine minutes. A reader
   using a screen reader started an analysis and was never told it advanced a
   stage, finished, was cancelled, or died.
   ======================================================================== */

const POLITE_ID = "bp-live-polite";
const ALERT_ID = "bp-live-alert";

/**
 * Find or create one region. Returns whether it had to be created, because a
 * region the screen reader has not registered yet cannot speak (see below).
 */
function region(id, role, politeness) {
  const existing = document.getElementById(id);
  if (existing) return { node: existing, fresh: false };

  const node = document.createElement("p");
  node.id = id;
  node.className = "sr-only";
  node.setAttribute("role", role);
  node.setAttribute("aria-live", politeness);
  // Atomic because these are whole sentences replaced wholesale, not a
  // counter ticking. Without it a reader may be given only the words that
  // changed, which here is the difference between "stage 3 of 4, scoring
  // cross-modal conflicts" and "3".
  node.setAttribute("aria-atomic", "true");
  document.body.appendChild(node);
  return { node, fresh: true };
}

/**
 * Put both regions in the document before anything needs to speak.
 *
 * Call this at boot. A live region has to be present and registered before
 * its content changes; one created and filled in the same task is routinely
 * missed, which is the classic way an announcement gets built and never
 * heard. Mounting early makes announce()'s deferred path the rare case
 * rather than the normal one.
 */
export function mountAnnouncer() {
  region(POLITE_ID, "status", "polite");
  region(ALERT_ID, "alert", "assertive");
}

/**
 * Say something.
 *
 * @param {string} message  plain text; this lands in textContent, never HTML
 * @param {{urgent?: boolean}} options  urgent interrupts, the default waits
 */
export function announce(message, { urgent = false } = {}) {
  const text = String(message == null ? "" : message).replace(/\s+/g, " ").trim();
  if (!text) return;

  const { node, fresh } = urgent
    ? region(ALERT_ID, "alert", "assertive")
    : region(POLITE_ID, "status", "polite");

  // Identical text is not re-spoken by screen readers anyway, and every caller
  // here announces on change rather than on poll, so an identical message means
  // nothing has changed and silence is the correct behaviour.
  if (node.textContent === text) return;

  if (fresh) requestAnimationFrame(() => { node.textContent = text; });
  else node.textContent = text;
}
