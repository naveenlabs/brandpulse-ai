"""build_pages.py — generate the four blind rating pages.

PROTOCOL.md §5. One self-contained HTML file per rater, opened with file://.
No server, no network, nothing leaves the machine.

Self-contained is a requirement, not a convenience: three of the four raters
receive this file by message and must be able to open it without a folder of
assets alongside it. So the audio and the frames are inlined as data URIs. The
media is deduplicated across the 30 hidden repeats, so a 150-presentation page
carries 120 items of media.

The properties this page must have, and why
-------------------------------------------
* **No system output of any kind appears in the file.** Not the channel labels,
  not a conflict score, not the transcript text, not the video title, the
  speaker's name or the brand. Not hidden with CSS, not in a data attribute, not
  in a comment. `verify_page.py` checks this mechanically, because a blinding
  property asserted by reading the code is not a property.

* **Items are identified by an opaque token, never by `uid`.** The natural
  `uid` is `<youtube_id>_<segment_id>`, and a YouTube id is a URL. A rater who
  pasted one into a browser would reach the source video, its title and — worst
  of all — its comment section, which is one of the four channels this bench is
  measuring. So the page carries `sha256(salt + uid)[:12]` and nothing else, and
  `_tokens.json` holds the mapping on this machine only. The salt is fixed so the
  tokens are reproducible, and the mapping file is never sent to a rater.

* **The transcript text is never rendered.** It is present in the audio, which
  the rater hears, and that is the point — a human judging sincerity hears the
  words. But rendering it as text would let a rater re-read and analyse it in a
  way the audio does not afford, which drifts the ground truth toward the
  text-only baseline this bench is trying to measure against (PROTOCOL.md §9.6).

* **Autosave on every answer**, with a storage probe up front, so a blocked-
  storage browser warns before an hour of work is lost. `vocal_bench`'s page
  established this and it is not optional.

* **Keyboard-first.** 150 items is a lot of mouse travel.

* **An explicit "can't tell" key.** Forcing a rating on an unratable item
  manufactures noise and calls it data.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from pathlib import Path

BENCH = Path(__file__).resolve().parent
SAMPLE = BENCH / "sample.json"
CLIPS = BENCH / "clips"
STRIPS = BENCH / "strips"
PAGES = BENCH / "pages"
TOKENS = BENCH / "_tokens.json"

# Fixed so tokens are reproducible across runs. Not a secret — it defeats casual
# lookup of a YouTube id by a rater, which is all it needs to do.
TOKEN_SALT = "baseline_bench/2026-09-06"
TOKEN_LEN = 12


def token_for(uid: str) -> str:
    return hashlib.sha256((TOKEN_SALT + uid).encode()).hexdigest()[:TOKEN_LEN]


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("pages")

# value -> (key, label, hint). Order is the on-screen order, top to bottom.
#
# The wording avoids two collisions deliberately, and verify_page.py enforces
# both: "Neutral" is a channel label in this system's own vocabulary and would
# prime a rater toward it, and "Nothing" is a brand name in this corpus.
SCALE = [
    (5, "5", "Clearly genuine",     "unmistakably sincere, means every word"),
    (4, "4", "Probably genuine",    "sounds like they mean it"),
    (3, "3", "Can't say either way", "plain delivery, no strong impression"),
    (2, "2", "Probably not",        "something is a bit off"),
    (1, "1", "Clearly not genuine", "forced, scripted, over-sold"),
    (0, "0", "Unratable",           "can't hear it or can't judge it at all"),
]

CSS = """
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 system-ui,"Segoe UI",Roboto,Helvetica,sans-serif;
     background:#12151a;color:#e8ecf1;-webkit-font-smoothing:antialiased}
.wrap{max-width:760px;margin:0 auto;padding:22px 20px 60px}
header{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
       padding-bottom:14px;border-bottom:1px solid #262c36;margin-bottom:22px}
h1{font-size:17px;margin:0;font-weight:600;letter-spacing:-.01em}
.count{font-variant-numeric:tabular-nums;color:#8a94a6;font-size:13px}
.bar{height:3px;background:#222834;border-radius:2px;overflow:hidden;margin-bottom:26px}
.bar i{display:block;height:100%;background:#4c8dff;transition:width .25s ease}
.strip{display:flex;gap:6px;margin-bottom:16px}
.strip img{width:0;flex:1 1 0;border-radius:7px;background:#1b202a;object-fit:cover;
           aspect-ratio:16/9;border:1px solid #262c36}
.noframes{padding:26px;text-align:center;color:#6d7789;background:#171b23;
          border:1px dashed #2c3340;border-radius:8px;margin-bottom:16px;font-size:13px}
audio{width:100%;margin-bottom:22px;filter:invert(.92) hue-rotate(180deg)}
.q{font-size:19px;font-weight:600;margin:0 0 16px;letter-spacing:-.01em}
.opts{display:flex;flex-direction:column;gap:7px}
button.opt{display:flex;align-items:center;gap:13px;width:100%;text-align:left;
   padding:11px 14px;border:1px solid #2a313d;border-radius:9px;background:#1a1f28;
   color:#e8ecf1;font:inherit;cursor:pointer;transition:.12s}
button.opt:hover{background:#222836;border-color:#3d4757}
button.opt:focus-visible{outline:2px solid #4c8dff;outline-offset:2px}
kbd{flex:none;width:26px;height:26px;display:grid;place-items:center;border-radius:6px;
    background:#2b323f;font:600 12px ui-monospace,monospace;color:#aeb8c8}
.lab{font-weight:600}
.hint{color:#7c8698;font-size:12.5px;margin-left:auto;text-align:right;max-width:48%}
.nav{display:flex;gap:10px;margin-top:22px;align-items:center}
.nav button{padding:8px 15px;border-radius:8px;border:1px solid #2a313d;background:#1a1f28;
            color:#aeb8c8;font:inherit;cursor:pointer}
.nav button:hover:not(:disabled){background:#222836;color:#e8ecf1}
.nav button:disabled{opacity:.35;cursor:default}
.note{color:#7c8698;font-size:12.5px;margin-left:auto}
.warn{background:#3a2419;border:1px solid #7a4a2a;color:#ffcda8;padding:11px 14px;
      border-radius:8px;margin-bottom:18px;font-size:13.5px}
.done{text-align:center;padding:34px 0}
.done h2{font-size:22px;margin:0 0 8px}
.done p{color:#8a94a6;margin:0 0 22px}
textarea{width:100%;height:230px;background:#0d1015;color:#9fb4d0;border:1px solid #2a313d;
   border-radius:9px;padding:12px;font:12px/1.5 ui-monospace,monospace;resize:vertical}
.actions{display:flex;gap:10px;justify-content:center;margin-bottom:18px;flex-wrap:wrap}
.actions button{padding:10px 18px;border-radius:8px;border:0;background:#4c8dff;color:#fff;
                font:600 14px inherit;cursor:pointer}
.actions button.ghost{background:#1a1f28;color:#aeb8c8;border:1px solid #2a313d}
.skipped{color:#ffcda8}
"""

JS = r"""
const ITEMS = window.__ITEMS__, RATER = window.__RATER__;
const KEY = 'baseline_bench_' + RATER;
let answers = {}, i = 0, storageOK = true;

try { localStorage.setItem(KEY + '_probe', '1'); localStorage.removeItem(KEY + '_probe'); }
catch (e) { storageOK = false; }
if (storageOK) { try { answers = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { answers = {}; } }

function save() {
  if (!storageOK) return;
  try { localStorage.setItem(KEY, JSON.stringify(answers)); } catch (e) { storageOK = false; render(); }
}
function firstUnanswered() {
  for (let k = 0; k < ITEMS.length; k++) if (!(ITEMS[k].pid in answers)) return k;
  return ITEMS.length;
}
function answer(v) {
  answers[ITEMS[i].pid] = v; save();
  i = Math.min(i + 1, ITEMS.length); render();
}
function render() {
  const done = Object.keys(answers).length, n = ITEMS.length;
  document.getElementById('count').textContent = Math.min(i + 1, n) + ' / ' + n;
  document.getElementById('progress').style.width = (done / n * 100) + '%';
  const root = document.getElementById('main');
  const warn = storageOK ? '' :
    '<div class="warn"><b>Your browser is blocking local storage.</b> Progress will not be ' +
    'saved if you close this tab. Finish in one sitting, or try a normal (non-private) window.</div>';

  if (i >= n) {
    const skipped = Object.values(answers).filter(v => v === 0).length;
    root.innerHTML = warn +
      '<div class="done"><h2>All ' + n + ' done. Thank you.</h2>' +
      '<p>' + (skipped ? '<span class="skipped">' + skipped + ' marked unratable.</span> ' : '') +
      'Send the file back, or copy the text below.</p>' +
      '<div class="actions">' +
      '<button onclick="dl()">Download my answers</button>' +
      '<button class="ghost" onclick="copyOut()">Copy to clipboard</button>' +
      '<button class="ghost" onclick="i=0;render()">Review from the start</button>' +
      '</div><textarea id="out" readonly>' + outText() + '</textarea></div>';
    return;
  }
  const it = ITEMS[i], prev = answers[it.pid];
  const strip = it.frames.length
    ? '<div class="strip">' + it.frames.map(f => '<img src="' + f + '" alt="">').join('') + '</div>'
    : '<div class="noframes">No picture available for this clip &mdash; audio only.</div>';
  root.innerHTML = warn + strip +
    '<audio controls autoplay src="' + it.audio + '"></audio>' +
    '<p class="q">Is this person being genuine here?</p><div class="opts">' +
    OPTS.map(o =>
      '<button class="opt" onclick="answer(' + o[0] + ')"' +
      (prev === o[0] ? ' style="border-color:#4c8dff;background:#1d2836"' : '') + '>' +
      '<kbd>' + o[1] + '</kbd><span class="lab">' + o[2] + '</span>' +
      '<span class="hint">' + o[3] + '</span></button>').join('') +
    '</div><div class="nav"><button onclick="i=Math.max(0,i-1);render()"' +
    (i === 0 ? ' disabled' : '') + '>&larr; Back</button>' +
    '<button onclick="i=firstUnanswered();render()">Jump to first unanswered</button>' +
    '<button onclick="saveNow()" title="Download what you have so far. ' +
    'You can keep going afterwards.">Save progress</button>' +
    '<span class="note">' + done + ' answered &middot; press 0&ndash;5</span></div>';
}
function outText() {
  const done = Object.keys(answers).length;
  return JSON.stringify({ rater: RATER, n: ITEMS.length,
    answered: done, complete: done === ITEMS.length,
    answers: ITEMS.map(it => ({ pid: it.pid, tok: it.tok, rating: answers[it.pid] ?? null })) }, null, 1);
}
function saveNow() {
  const done = Object.keys(answers).length;
  if (!done) { alert("Nothing to save yet \u2014 answer at least one clip first."); return; }
  dl();
}
function dl() {
  const b = new Blob([outText()], { type: 'application/json' });
  const a = document.createElement('a');
  const done = Object.keys(answers).length;
  a.href = URL.createObjectURL(b);
  a.download = 'ratings_' + RATER +
    (done === ITEMS.length ? '' : '_partial_' + done) + '.json';
  document.body.appendChild(a); a.click(); a.remove();
}
function copyOut() {
  const t = document.getElementById('out'); t.select();
  navigator.clipboard ? navigator.clipboard.writeText(t.value) : document.execCommand('copy');
}
document.addEventListener('keydown', e => {
  if (i >= ITEMS.length) return;
  if (e.key >= '0' && e.key <= '5') { e.preventDefault(); answer(parseInt(e.key, 10)); }
  else if (e.key === 'ArrowLeft' && i > 0) { i--; render(); }
});
i = firstUnanswered(); render();
"""


def data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def build(rater: str, order: list[dict], items: dict[str, dict]) -> str:
    """One page. Media is inlined once per uid and reused by the duplicate."""
    media: dict[str, dict] = {}
    for pres in order:
        uid = pres["uid"]
        if uid in media:
            continue
        it = items[uid]
        media[uid] = {
            "audio": data_uri(CLIPS / it["audio"], "audio/mpeg"),
            "frames": [data_uri(STRIPS / f, "image/jpeg") for f in it["frames"]],
        }

    # `pid` and the opaque `tok` are the ONLY item identifiers that reach the
    # page. `tok` pairs the hidden duplicates at scoring time without carrying a
    # YouTube id, a label, a score or a prediction.
    payload = [{"pid": p["presentation_id"], "tok": token_for(p["uid"]),
                "audio": media[p["uid"]]["audio"],
                "frames": media[p["uid"]]["frames"]} for p in order]

    return (
        f"<title>Rating {rater}</title>\n<style>{CSS}</style>\n"
        '<div class="wrap"><header><h1>Is this person being genuine?</h1>'
        '<span class="count" id="count"></span></header>'
        '<div class="bar"><i id="progress"></i></div><div id="main"></div></div>\n'
        f"<script>window.__RATER__={json.dumps(rater)};"
        f"const OPTS={json.dumps([[v, k, lab, hint] for v, k, lab, hint in SCALE])};"
        f"window.__ITEMS__={json.dumps(payload)};</script>\n"
        f"<script>{JS}</script>\n"
    )


def main() -> int:
    sample = json.loads(SAMPLE.read_text())
    items = {it["uid"]: it for it in sample["items"]}
    PAGES.mkdir(exist_ok=True)

    TOKENS.write_text(json.dumps({
        "salt": TOKEN_SALT, "length": TOKEN_LEN,
        "note": "local only — never sent to a rater (build_pages.py docstring)",
        "token_to_uid": {token_for(u): u for u in sorted(items)},
    }, indent=1))

    collisions = len(items) - len({token_for(u) for u in items})
    if collisions:
        raise SystemExit(f"token collision on {collisions} uids — raise TOKEN_LEN")

    for rater, order in sample["orders"].items():
        html = build(rater, order, items)
        out = PAGES / f"rate_{rater}.html"
        out.write_text(html)
        logger.info("%-8s %3d presentations  %5.1f MB  -> %s",
                    rater, len(order), len(html) / 1e6, out.name)
    logger.info("open with file:// — no server, nothing leaves the machine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
