/* format.js — every string this interface prints from a number.

   Centralised so a figure cannot acquire a different number of decimal places
   on a different page and look like a different measurement. */

/** Seconds to m:ss. Used for every timecode. */
export function mmss(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "—";
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** A score out of 100, always to two places, because the pipeline emits two. */
export function score(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "—";
}

/** A model confidence or conflict score, always to three places. */
export function confidence(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "—";
}

/** A percentage to one place. */
export function pct(value, places = 1) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(places)}%` : "—";
}

/** A count with a thousands separator. */
export function count(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-GB") : "—";
}

/** Escape text that came from a comment, a transcript or a filename. */
export function esc(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * "Apple (Iphone 17 Pro Max - 1).json" -> { brand, product }.
 *
 * app.py builds these names from the brand and product fields, sanitising each
 * to [A-Za-z0-9] plus underscores, so this split is reading back a structure
 * the server wrote rather than guessing at one.
 */
export function splitReportName(filename) {
  const base = String(filename || "").replace(/\.json$/i, "");
  const match = base.match(/^(.*?)\s*\(([^)]*)\)\s*$/);
  return match
    ? { brand: match[1].trim(), product: match[2].trim() }
    : { brand: base.trim(), product: "" };
}

/** A file's mtime (seconds or ms) as "29 Jun 2026", or "" when absent. */
export function savedOn(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "";
  const ms = value > 1e12 ? value : value * 1000;
  return new Date(ms).toLocaleDateString("en-GB",
    { day: "numeric", month: "short", year: "numeric" });
}

/**
 * A label the pipeline printed in whatever case it chose ("POSITIVE", "fear")
 * set in sentence case for display. Presentational only: the reading itself
 * is never changed, and a grid of mixed-case raw strings reads as a bug.
 */
export function sentence(text) {
  const s = String(text ?? "");
  return s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s;
}

/* THE ONE ARROW.

   Drawn, never typed: a glyph arrow takes the font's weight and sits on the
   font's baseline, so a "↗" on one page and a "->" on another and an SVG on
   a third were three different arrows. This is the book's page-turn arrow,
   and it is used only where something MOVES the reader -- to another page,
   down the page, back to where they were. An action that starts work
   carries its words and no arrow. */
const ARROW_TURN = { next: 0, prev: 180, down: 90, up: -90 };

export function arrow(dir = "next") {
  const turn = ARROW_TURN[dir] ?? 0;
  return `<svg class="arrow" viewBox="0 0 16 11" width="15" height="11" aria-hidden="true"
    focusable="false" fill="none" stroke="currentColor" stroke-width="1.4"${
    turn ? ` style="transform:rotate(${turn}deg)"` : ""}><path d="M0 5.5H14.6M10.3 1.2 14.9 5.5 10.3 9.8"/></svg>`;
}
