/* The opening and closing instruments share geometry, not a video backdrop. */
import { gsap, ScrollTrigger, motionMedia } from "./motion.js";

export const HERO_MARK = `<svg class="hero__glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M4.46 3L10.68 7L4.46 7ZM4.46 7.6L11.62 7.6L17.84 11.6L4.46 11.6ZM6.16 12.4L19.54 12.4L13.32 16.4L6.16 16.4ZM4.46 17L10.68 17L4.46 21Z"/></svg>`;

const CHANNELS = [
  ["transcript", "Words", "What was said"],
  ["facial", "Face", "The face on camera"],
  ["vocal", "Voice", "How it was said"],
  ["audience", "Audience", "What viewers wrote"],
];

export function instrumentMarkup(variant = "open") {
  const ticks = Array.from({ length: 96 }, (_, i) => {
    const a = i * Math.PI / 48;
    const inner = i % 8 === 0 ? 210 : i % 4 === 0 ? 216 : 222;
    return `<line x1="${250 + Math.cos(a) * inner}" y1="${250 + Math.sin(a) * inner}" x2="${250 + Math.cos(a) * 230}" y2="${250 + Math.sin(a) * 230}"/>`;
  }).join("");
  return `<div class="signal-object signal-object--${variant}" aria-hidden="true">
    <div class="signal-object__halo"></div>
    <div class="signal-object__shadow"></div>
    <div class="signal-object__rig">
      ${CHANNELS.map(([channel], i) => `<div class="signal-object__layer" style="--layer:${i};--signal:var(--ch-${channel})">
        <div class="signal-object__rim"></div>
        <svg class="signal-object__dial" viewBox="0 0 500 500"><g>${ticks}</g><circle cx="250" cy="250" r="198"/><circle class="signal-object__trace" cx="250" cy="250" r="188"/><text x="250" y="48" text-anchor="middle">0${i + 1} / ${channel.toUpperCase()}</text></svg>
        <i class="signal-object__point"></i>
      </div>`).join("")}
      <div class="signal-object__core"><span>BP</span><i></i><small>FOUR READINGS<br>ONE PERSPECTIVE</small></div>
    </div>
  </div>`;
}

export function heroMarkup() {
  return `<section class="hero" aria-labelledby="hero-title">
    <div class="hero__edition"><span>BRANDPULSE / INDEPENDENT PERSPECTIVES</span><span><i></i> BUILT TO LOOK CLOSER</span></div>
    <div class="hero__stage">
      <div class="hero__copy">
        <p class="hero__eyebrow">ONE VIDEO. FOUR WAYS OF SEEING.</p>
        <h1 class="hero__title" id="hero-title"><span>Words are only</span><em>one reading.</em></h1>
        <p class="hero__sub">So this takes four, side by side.<br>And finds where they disagree.</p>
        <div class="hero__actions"><a class="btn hero__cta" data-variant="solid" href="#film">See it on a real video <span aria-hidden="true">↗</span></a><span class="hero__scroll">SCROLL TO LOOK BENEATH <span aria-hidden="true">↓</span></span></div>
      </div>
      <div class="hero__instrument">${instrumentMarkup()}<div class="hero__spec" aria-hidden="true"><span>FIG. 01 / THE FOUR-CHANNEL INSTRUMENT</span><span>INDEPENDENT BY DESIGN</span></div></div>
    </div>
    <ul class="hero__feats">${CHANNELS.map(([channel, title, description], i) => `<li style="--signal:var(--ch-${channel})"><span class="hero__channel-no">0${i + 1}<i></i></span><div><strong>${title}</strong><span>${description}</span></div></li>`).join("")}</ul>
    <footer class="hero__foot"><span>Every model runs on this machine. Nothing is uploaded.</span><span>CM3070 / FINAL YEAR PROJECT</span></footer>
  </section>`;
}

let released = false;
let wired = false;
function release() { document.documentElement.classList.add("hero-in"); }
export function playHero() { released = true; if (wired) release(); }

/* Off-screen instruments stop their decorative rotation. All text remains
   visible without animation, including when the gate cannot be rendered. */
export function wireInstrument(section, closing = false) {
  if (!section) return;
  const observer = new IntersectionObserver(([entry]) => {
    section.dataset.inView = String(entry.isIntersecting);
  }, { rootMargin: "100px" });
  observer.observe(section);
  const media = motionMedia("(prefers-reduced-motion: no-preference)", () => {
    const rig = section.querySelector(".signal-object__rig");
    gsap.fromTo(rig, { rotationZ: closing ? -24 : -28 }, {
      rotationZ: closing ? 4 : -8, ease: "none",
      scrollTrigger: { trigger: section, start: closing ? "top bottom" : "top top", end: "bottom top", scrub: 1, refreshPriority: closing ? -2 : 0 },
    });
  });
  window.addEventListener("pagehide", (event) => {
    if (!event.persisted) { observer.disconnect(); media.revert(); }
  }, { once: true });
}

export function wireHero() {
  document.documentElement.classList.add("has-hero");
  const section = document.querySelector(".hero");
  ScrollTrigger.create({ trigger: section, start: "bottom top+=80",
    onEnter: () => document.documentElement.classList.add("is-past-hero"),
    onLeaveBack: () => document.documentElement.classList.remove("is-past-hero"),
  });
  wireInstrument(section);
  wired = true;
  if (released) release();
  else setTimeout(playHero, 30000);
}
