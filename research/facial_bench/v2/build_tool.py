"""
build_tool.py — generate label_here.html from sample.json.

The tool is a single self-contained page opened with file://. It embeds the
sample *manifest* (paths, ids, order) but never the images, which are loaded
lazily from data/ — 648 4K stills would be ~500 MB inlined.

It shows a frame and eight buttons and **nothing else**: no prediction, no box,
no confidence, no v1 label (PROTOCOL.md §5.4, blinding).
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
MANIFEST = HERE / "sample.json"
OUT = HERE / "label_here.html"

# value -> (key, button label, hint). Order is the on-screen order.
CHOICES = [
    ("neutral",     "2", "Neutral",            "just talking, no strong expression"),
    ("happy",       "1", "Happy",              "smiling, pleased, amused"),
    ("angry",       "3", "Angry / frustrated", "irritated, annoyed, tense"),
    ("sad",         "4", "Sad / disappointed", "let down, downcast, resigned"),
    ("surprised",   "5", "Surprised",          "eyebrows up, mouth open, startled"),
    ("expr_unsure", "6", "Face, can't tell",   "a face is there, expression unreadable"),
    ("no_face",     "0", "No face",            "b-roll, product shot, empty scene"),
    ("face_unsure", "9", "Can't tell if face", "blurred, tiny, partial, ambiguous"),
]

CSS = """
:root{--bg:#fbfbfa;--fg:#1a1a19;--mut:#6b6b68;--line:#e3e3e0;--card:#fff;
 --accent:#2f6f4f;--warn:#8a4b2a;--pos:#2f6f4f;--neg:#a4432a;--neu:#5a5a72;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --bg:#1a1a19;--fg:#ececeb;--mut:#9a9a96;--line:#333331;--card:#232322;
 --accent:#7fc0a0;--warn:#d99b6a;--pos:#7fc0a0;--neg:#e08a68;--neu:#a0a0bc;}}
:root[data-theme="dark"]{--bg:#1a1a19;--fg:#ececeb;--mut:#9a9a96;--line:#333331;
 --card:#232322;--accent:#7fc0a0;--warn:#d99b6a;--pos:#7fc0a0;--neg:#e08a68;--neu:#a0a0bc;}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);margin:0;
 font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",sans-serif;}
.wrap{max-width:1120px;margin:0 auto;padding:16px 18px 150px;}
header{display:flex;align-items:baseline;gap:12px;margin-bottom:10px;flex-wrap:wrap}
h1{font-size:1.15rem;margin:0;letter-spacing:-.01em}
.sub{color:var(--mut);font-size:.85rem}
#warn{background:var(--warn);color:#fff;padding:10px 14px;border-radius:8px;margin-bottom:12px}
.stage{background:var(--card);border:1px solid var(--line);border-radius:12px;
 overflow:hidden;position:relative;}
.imgbox{background:#111;display:flex;align-items:center;justify-content:center;
 height:60vh;min-height:340px;overflow:auto;cursor:zoom-in;}
.imgbox.zoom{cursor:zoom-out;align-items:flex-start;justify-content:flex-start}
.imgbox img{max-width:100%;max-height:60vh;display:block;object-fit:contain}
.imgbox.zoom img{max-width:none;max-height:none;width:190%}
.meta{display:flex;gap:14px;align-items:center;padding:9px 14px;
 border-top:1px solid var(--line);font-size:.8rem;color:var(--mut);flex-wrap:wrap}
.tag{border:1px solid var(--line);border-radius:20px;padding:1px 9px}
.tag.done{color:var(--accent);border-color:var(--accent);font-weight:600}
.opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));
 gap:8px;margin-top:14px}
.opt{font:inherit;text-align:left;cursor:pointer;border:1px solid var(--line);
 background:var(--card);color:var(--fg);border-radius:9px;padding:9px 12px;transition:.12s}
.opt:hover{border-color:var(--accent)}
.opt.on{background:var(--accent);border-color:var(--accent);color:#fff}
.opt.on .h{color:rgba(255,255,255,.82)}
.opt b{display:block;font-size:.92rem}
.opt .k{float:right;font-weight:700;opacity:.5;font-size:.8rem}
.opt .h{display:block;color:var(--mut);font-size:.76rem;margin-top:2px}
.nav{display:flex;gap:8px;margin-top:12px;align-items:center}
.nav button{font:inherit;cursor:pointer;border:1px solid var(--line);background:transparent;
 color:var(--fg);border-radius:8px;padding:7px 14px}
.nav button:hover{border-color:var(--accent)}
.nav .sp{flex:1}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);
 border-top:1px solid var(--line);padding:9px 18px;display:flex;gap:14px;align-items:center}
.bar .track{flex:1;height:6px;background:var(--line);border-radius:3px;overflow:hidden}
.bar .fill{height:100%;width:0;background:var(--accent);transition:width .2s}
.bar button{font:inherit;cursor:pointer;border-radius:8px;padding:8px 15px;
 border:1px solid var(--line);background:transparent;color:var(--fg)}
#export{background:var(--accent);color:#fff;border:none;font-weight:600}
#export:disabled{opacity:.4;cursor:not-allowed}
.count{font-variant-numeric:tabular-nums;font-size:.85rem;color:var(--mut);min-width:104px}
details.help{margin:10px 0 0;font-size:.85rem;color:var(--mut)}
details.help summary{cursor:pointer;color:var(--accent)}
details.help ul{margin:8px 0 0;padding-left:18px}
details.help li{margin:3px 0}
kbd{border:1px solid var(--line);border-radius:4px;padding:0 5px;
 font:inherit;font-size:.8em;background:var(--bg)}
"""


def build() -> Path:
    if not MANIFEST.exists():
        raise SystemExit("sample.json not found — run `python sample.py` first.")
    m = json.loads(MANIFEST.read_text())

    # Only what the page needs. Split is embedded but never shown, so the rater
    # cannot tell dev from holdout while labelling.
    pres = [
        {"uid": p["uid"], "path": p["path"], "video": p["video_id"], "frame": p["frame"]}
        for p in m["presentations"]
    ]

    opts_html = "\n".join(
        f'      <button class="opt" data-v="{v}"><span class="k">{k}</span>'
        f'<b>{label}</b><span class="h">{hint}</span></button>'
        for v, k, label, hint in CHOICES
    )
    keymap = {k: v for v, k, _, _ in CHOICES}

    html = f"""<title>Facial Ground Truth — BrandPulse</title>
<style>{CSS}</style>
<div class="wrap">
  <header>
    <h1>Facial ground truth</h1>
    <span class="sub">{m['n_presentations']} frames · one click each · saves as you go</span>
  </header>

  <div id="warn" hidden>
    <b>Progress cannot be saved automatically in this browser.</b>
    Use <b>Save progress</b> often, and re-open with <b>Load progress</b>.
  </div>

  <div class="stage">
    <div class="imgbox" id="imgbox"><img id="frame" alt="frame"></div>
    <div class="meta">
      <span class="tag" id="pos"></span>
      <span class="tag" id="src"></span>
      <span class="tag done" id="mark"></span>
    </div>
  </div>

  <div class="opts">
{opts_html}
  </div>

  <div class="nav">
    <button id="prev">← Back</button>
    <button id="next">Skip →</button>
    <span class="sp"></span>
    <button id="jump">Jump to first unlabelled</button>
  </div>

  <details class="help">
    <summary>How to rate (read once)</summary>
    <ul>
      <li>Judge <b>only the largest face</b> in the frame. Ignore small background faces.</li>
      <li>A face on a screen inside the shot still counts as a face.</li>
      <li>Judge <b>this still alone</b>. Don't try to remember the video.</li>
      <li>Most frames will be <b>Neutral</b>. That is expected — don't hunt for emotion.</li>
      <li><b>Angry</b> and <b>Sad</b> are separate on purpose. Anger = tense, irritated.
          Sad = let down, deflated. If it's genuinely between them, use them as you see them;
          don't split the difference.</li>
      <li>Click the image to <b>zoom</b>. Faces can be small in a 4K frame.</li>
      <li>Use <b>Can't tell</b> freely. A guess is worse than an abstention here.</li>
      <li>Some frames repeat. That is deliberate and it is measuring consistency —
          just rate what you see, don't try to recall your earlier answer.</li>
      <li>Keys: <kbd>1</kbd>–<kbd>6</kbd>, <kbd>0</kbd>, <kbd>9</kbd> to rate ·
          <kbd>←</kbd> back · <kbd>→</kbd> skip · <kbd>z</kbd> zoom</li>
    </ul>
  </details>
</div>

<div class="bar">
  <span class="count" id="count"></span>
  <div class="track"><div class="fill" id="fill"></div></div>
  <button id="load">Load progress</button>
  <button id="save">Save progress</button>
  <button id="export" disabled>Export labels</button>
  <input type="file" id="file" accept="application/json" hidden>
</div>

<script>
const PRES = {json.dumps(pres)};
const KEYMAP = {json.dumps(keymap)};
const KEY = "facial_labels_v2";
const N = PRES.length;
let store = {{}}, ok = true, i = 0;

try {{ store = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ store = {{}}; }}
try {{ localStorage.setItem(KEY+"_probe","1"); localStorage.removeItem(KEY+"_probe"); }}
catch (e) {{ ok = false; document.getElementById("warn").hidden = false; }}

function save() {{
  if (!ok) return;
  try {{ localStorage.setItem(KEY, JSON.stringify(store)); }}
  catch (e) {{ ok = false; document.getElementById("warn").hidden = false; }}
}}

const img = document.getElementById("frame");
const box = document.getElementById("imgbox");

function preload(n) {{
  for (let k = 1; k <= 3; k++) {{
    const p = PRES[n + k];
    if (p) {{ const im = new Image(); im.src = p.path; }}
  }}
}}

function render() {{
  const p = PRES[i];
  img.src = p.path;
  box.classList.remove("zoom");
  document.getElementById("pos").textContent = (i + 1) + " of " + N;
  document.getElementById("src").textContent = p.frame;
  const v = store[p.uid];
  document.getElementById("mark").textContent = v ? "rated" : "";
  document.querySelectorAll(".opt").forEach(b =>
    b.classList.toggle("on", b.dataset.v === v));
  const n = Object.keys(store).length;
  document.getElementById("count").textContent = n + " / " + N + " rated";
  document.getElementById("fill").style.width = (n / N * 100) + "%";
  document.getElementById("export").disabled = n === 0;
  preload(i);
}}

function choose(v) {{
  store[PRES[i].uid] = v;
  save();
  if (i < N - 1) {{ i++; }}
  render();
}}

document.querySelectorAll(".opt").forEach(b =>
  b.addEventListener("click", () => choose(b.dataset.v)));
document.getElementById("prev").addEventListener("click", () => {{
  if (i > 0) {{ i--; render(); }} }});
document.getElementById("next").addEventListener("click", () => {{
  if (i < N - 1) {{ i++; render(); }} }});
document.getElementById("jump").addEventListener("click", () => {{
  const k = PRES.findIndex(p => !store[p.uid]);
  if (k >= 0) {{ i = k; render(); }} }});
box.addEventListener("click", () => box.classList.toggle("zoom"));

document.addEventListener("keydown", e => {{
  if (e.target.tagName === "INPUT") return;
  if (KEYMAP[e.key] !== undefined) {{ e.preventDefault(); choose(KEYMAP[e.key]); return; }}
  if (e.key === "ArrowLeft")  {{ e.preventDefault(); if (i > 0) {{ i--; render(); }} }}
  if (e.key === "ArrowRight") {{ e.preventDefault(); if (i < N - 1) {{ i++; render(); }} }}
  if (e.key === "z")          {{ box.classList.toggle("zoom"); }}
}});

function payload() {{
  return {{
    tool: "facial_bench/v2/label_here.html",
    saved_at: new Date().toISOString(),
    n_presentations: N,
    n_rated: Object.keys(store).length,
    labels: store
  }};
}}
function download(name) {{
  const blob = new Blob([JSON.stringify(payload(), null, 1)], {{type: "application/json"}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}}
document.getElementById("save").addEventListener("click", () => download("facial_labels_partial.json"));
document.getElementById("export").addEventListener("click", () => download("facial_labels_v2.json"));
document.getElementById("load").addEventListener("click", () => document.getElementById("file").click());
document.getElementById("file").addEventListener("change", ev => {{
  const f = ev.target.files[0];
  if (!f) return;
  const r = new FileReader();
  r.onload = () => {{
    try {{
      const d = JSON.parse(r.result);
      const lab = d.labels || d;
      let added = 0;
      for (const k in lab) {{ if (!(k in store)) added++; store[k] = lab[k]; }}
      save();
      const k = PRES.findIndex(p => !store[p.uid]);
      i = k >= 0 ? k : 0;
      render();
      alert("Loaded " + Object.keys(lab).length + " labels (" + added + " new).");
    }} catch (err) {{ alert("Could not read that file: " + err.message); }}
  }};
  r.readAsText(f);
}});

const first = PRES.findIndex(p => !store[p.uid]);
i = first >= 0 ? first : 0;
render();
</script>
"""
    OUT.write_text(html)
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"wrote {p.name} ({p.stat().st_size / 1024:.0f} KB)")
