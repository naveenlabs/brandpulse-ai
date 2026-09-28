/* ===========================================================================
   theme.js — the one source of the current theme.

   Added 24 Sep 2026 with the cohesion pass. Before it, the theme lived in
   three places that did not agree: the attribute on <html>, localStorage,
   and a `themechange` event that five renderers listened for and nothing
   ever dispatched. The library's WebGL room, both proof charts' grounds and
   the film's pixel arc therefore kept the palette they were mounted with,
   and a reader who switched the display mid-page got a light page around a
   dark scene until they reloaded.

   Now there is one writer (applyTheme) and one event, and every renderer
   subscribes to the same thing:

     currentTheme()    "bench" | "field", read from the attribute
     sceneMode()       "dark" | "light", the vocabulary the vendored scene
                       components take
     applyTheme(next)  set it, remember it, tell everyone; no animation
     onThemeChange(fn) subscribe; returns an unsubscribe
     token(name)       a computed custom property, for canvases that must
                       draw with the page's own colours

   The first paint is decided before any of this loads, by the inline script
   in each document's head; that is what keeps a reload from flashing the
   wrong ground. This module takes over from the first interaction.
   ======================================================================== */

export const THEME_KEY = "brandpulse-theme";
export const THEME_EVENT = "themechange";

const root = document.documentElement;
let settle = 0;

/** The theme the page is showing now. */
export function currentTheme() {
  return root.dataset.theme === "field" ? "field" : "bench";
}

/** The same fact in the vocabulary the scene components take. */
export function sceneMode() {
  return currentTheme() === "field" ? "light" : "dark";
}

/** A computed custom property off the root, trimmed. */
export function token(name) {
  return getComputedStyle(root).getPropertyValue(name).trim();
}

/**
 * Set the theme, remember it, and tell every renderer.
 *
 * The attribute change is wrapped in `is-theming`, which suspends every CSS
 * transition for the one frame the swap takes (tokens.css). Without it, the
 * elements that transition their colours faded across while their grounds
 * had already switched, and for a quarter of a second the page was two
 * themes at once.
 *
 * The event is dispatched synchronously, after the attribute is set, so a
 * listener that reads a token reads the new value.
 */
export function applyTheme(next, { persist = true } = {}) {
  const theme = next === "field" ? "field" : "bench";
  if (theme === currentTheme() && root.dataset.theme) return theme;

  root.classList.add("is-theming");
  root.dataset.theme = theme;
  if (persist) {
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* private window: fine */ }
  }
  /* Force the new values through style before transitions come back, or the
     browser may batch both changes into one frame and animate anyway. */
  void root.offsetWidth;
  window.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: { theme } }));
  /* Transitions come back once the new values have painted. A timer rather
     than a frame callback: this is not movement, and it must run even in a
     background tab that is following another tab's switch. */
  clearTimeout(settle);
  settle = setTimeout(() => root.classList.remove("is-theming"), 80);
  return theme;
}

/** Be told when the theme changes. Returns an unsubscribe. */
export function onThemeChange(fn) {
  const handler = (event) => fn((event.detail && event.detail.theme) || currentTheme());
  window.addEventListener(THEME_EVENT, handler);
  return () => window.removeEventListener(THEME_EVENT, handler);
}

/* Another tab of this product changed the display. Follow it, without the
   sweep and without writing it back, so two open pages cannot disagree about
   which room they are in. */
window.addEventListener("storage", (event) => {
  if (event.key !== THEME_KEY) return;
  if (event.newValue === "field" || event.newValue === "bench") {
    applyTheme(event.newValue, { persist: false });
  }
});
