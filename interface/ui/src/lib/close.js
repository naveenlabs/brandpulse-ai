/* The last section resolves the opening instrument into an invitation. */
import { count, esc, arrow } from "./format.js";
import { HERO_MARK, instrumentMarkup, wireInstrument } from "./hero.js";

export function closeMarkup(corpus = {}, pick = null) {
  const reports = corpus.report_count ?? 0;
  const film = pick?.href ? `<a class="close__quiet" href="${esc(pick.href)}">Open the one in the film ${arrow("next")}</a>` : "";
  return `<section class="close" id="close" aria-labelledby="close-h" data-close>
    <div class="close__edition"><span>THE NEXT PERSPECTIVE</span><span>YOUR VIDEO / YOUR MACHINE</span></div>
    <div class="close__display">
      <div class="close__stage">
        <p class="close__badge"><i></i>${reports > 0 ? `${esc(count(reports))} runs measured on this machine` : "Your first reading starts here"}</p>
        <h2 class="close__h" id="close-h">Now bring<br><em>your perspective.</em></h2>
        <p class="close__sub">Point it at a video of your own. Four independent readings. The agreement, the contradictions, and everything in between.</p>
        <a class="btn close__cta" data-variant="solid" href="/run">Analyse a video <span aria-hidden="true">↗</span></a>
        <p class="close__note">Four to nine minutes · Ollama running locally<br>Every score carries its limitations with it.</p>
      </div>
      <div class="close__instrument">${instrumentMarkup("close")}<span class="close__inscription" aria-hidden="true">ONE VIDEO. A WIDER VIEW.</span></div>
    </div>
    <div class="close__promise"><span>Nothing uploaded.</span><span>Every model local.</span><em>All four readings, kept in view.</em></div>
    <footer class="close__bar end" role="contentinfo">
      <a class="close__mark end__sig" href="/">${HERO_MARK}<span>BrandPulse</span></a>
      <div class="close__ends">${film}<a class="btn" href="/library">Read ${count(reports)} saved runs</a></div>
    </footer>
  </section>`;
}
export function wireClose() { wireInstrument(document.querySelector("[data-close]"), true); }
