import { defineConfig } from "vite";
import { resolve } from "node:path";

/**
 * The interface builds to ../static/, which is what Flask serves and what is
 * committed. There is no dev server in the demo path: `flask run` alone serves
 * the finished build, because this is demonstrated at an exam on a laptop and
 * cannot depend on a second process.
 *
 * base: "/static/" because Flask mounts this directory at /static, while the
 * documents are served from /, /run, /library, /library/<filename>,
 * /brand/<id>, /brand/<id>/<video> and /accessibility. An asset URL therefore
 * has to be absolute and prefixed, or a
 * page one level deep would resolve its scripts against the wrong directory.
 *
 * Every dependency is bundled from node_modules into that output. Nothing is
 * fetched from a CDN at runtime, and neither are the typefaces: the product's
 * claim is that no data leaves the machine, and a page that phoned out to
 * render itself would contradict that claim in front of a marker.
 *
 * `server.proxy` exists only for development. It lets `vite dev` hand the API
 * calls to the real Flask process on 5057 so the interface can be built
 * against real reports rather than fixtures. Nothing in the built output knows
 * this block exists: every request the shipped interface makes is relative and
 * same-origin, and a test asserts it.
 */

/**
 * THE REDUCE MOTION SWITCH, IN CSS (25 Sep 2026, INCLUSIVE_DESIGN.md I1).
 *
 * The masthead's Reduce motion button sets <html data-motion="off">. Every
 * stylesheet already says what reduced motion looks like, inside
 * `@media (prefers-reduced-motion: reduce)`, and a media query cannot see an
 * attribute. Rather than write each of those twenty-odd blocks a second time
 * by hand -- two copies that would drift -- this re-emits them at build time:
 *
 *   @media (prefers-reduced-motion: reduce) { X }   -> also  :root[data-motion="off"] X
 *   @media (prefers-reduced-motion: no-preference) { Y }  -> :root:not([data-motion="off"]) Y
 *
 * so the switch turns off exactly what the OS setting turns off, and turns on
 * nothing the OS setting would not. A plain PostCSS plugin object: Vite runs
 * PostCSS already, so this adds no dependency. Rules inside nested at-rules
 * (@keyframes) are left alone -- a keyframe is not a selector.
 */
/**
 * READ AS ONE PAGE, IN CSS (25 Sep 2026, INCLUSIVE_DESIGN.md I2).
 *
 * The book has two layouts and the width chooses: spreads at 1100px and up,
 * one column below. <html data-read="page"> asks for the one column at any
 * width -- and printing asks for it too (codex.js). So the spread rules are
 * held off the attribute and the one-column rules are re-emitted under it,
 * both wrapped in :where() so no selector gains specificity and the cascade
 * resolves exactly as it does at the width each layout was written for.
 */
const WIDE_BOOK = /^\(\s*min-width\s*:\s*1100px\s*\)(\s+and\s+\(\s*max-width\s*:\s*1379\.98px\s*\))?$/;
const NARROW_BOOK = /^\(\s*max-width\s*:\s*1099\.98px\s*\)$/;
const ONE_PAGE = ':where(:root[data-read="page"])';
const NOT_ONE_PAGE = ':where(:root:not([data-read="page"]))';
const onePageSwitch = () => ({
  postcssPlugin: "brandpulse-one-page",
  AtRule: {
    media(atRule) {
      const params = atRule.params.trim();
      if (WIDE_BOOK.test(params)) {
        atRule.each((node) => {
          if (node.type !== "rule" || node.__bpPage) return;
          node.__bpPage = true;
          node.selector = node.selector.split(",").map((x) => `${NOT_ONE_PAGE} ${x.trim()}`).join(", ");
        });
      } else if (NARROW_BOOK.test(params)) {
        if (atRule.__bpPage) return;
        atRule.__bpPage = true;
        const copies = [];
        atRule.each((node) => {
          if (node.type !== "rule") return;
          const copy = node.clone();
          copy.selector = node.selector.split(",").map((x) => `${ONE_PAGE} ${x.trim()}`).join(", ");
          copy.__bpPage = true;
          copies.push(copy);
        });
        atRule.after(copies);
      }
    },
  },
});
onePageSwitch.postcss = true;

const REDUCE = /^\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)$/;
const PREFER = /^\(\s*prefers-reduced-motion\s*:\s*no-preference\s*\)$/;
function scoped(selector, prefix, rootForm) {
  return selector.split(",").map((part) => {
    const sel = part.trim();
    if (/^html\b/.test(sel)) return sel.replace(/^html/, `html${rootForm}`);
    if (/^:root\b/.test(sel)) return sel.replace(/^:root/, `:root${rootForm}`);
    return `${prefix} ${sel}`;
  }).join(", ");
}
const motionSwitch = () => ({
  postcssPlugin: "brandpulse-motion-switch",
  AtRule: {
    media(atRule) {
      const params = atRule.params.trim();
      if (REDUCE.test(params)) {
        if (atRule.__bpMotion) return;
        atRule.__bpMotion = true;
        const copies = [];
        atRule.each((node) => {
          if (node.type !== "rule") return;
          const copy = node.clone();
          copy.selector = scoped(node.selector, ':root[data-motion="off"]', '[data-motion="off"]');
          copies.push(copy);
        });
        atRule.after(copies);
      } else if (PREFER.test(params)) {
        atRule.each((node) => {
          if (node.type !== "rule" || node.__bpMotion) return;
          node.__bpMotion = true;
          node.selector = scoped(node.selector, ':root:not([data-motion="off"])', ':not([data-motion="off"])');
        });
      }
    },
  },
});
motionSwitch.postcss = true;

export default defineConfig({
  base: "/static/",
  css: { postcss: { plugins: [motionSwitch(), onePageSwitch()] } },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      ["/reports", "/evidence", "/analyse", "/sweep", "/sweeps"].map((path) => [
        path, { target: "http://127.0.0.1:5057", changeOrigin: false },
      ]),
    ),
  },
  build: {
    outDir: resolve(import.meta.dirname, "../static"),
    emptyOutDir: true,
    assetsDir: "assets",
    target: "es2022",
    cssCodeSplit: true,
    sourcemap: false,
    rollupOptions: {
      input: {
        opening: resolve(import.meta.dirname, "index.html"),
        report: resolve(import.meta.dirname, "report.html"),
        run: resolve(import.meta.dirname, "run.html"),
        library: resolve(import.meta.dirname, "library.html"),
        sweep: resolve(import.meta.dirname, "brand.html"),
        statement: resolve(import.meta.dirname, "accessibility.html"),
      },
    },
  },
});
