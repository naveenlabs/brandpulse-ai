"""
build_rating_page.py - generate the local audio-rating page for vocal ground truth.

Produces rate_here.html, opened directly from disk (file://). No server, no
network, nothing leaves the machine.

The one rule the page enforces structurally
-------------------------------------------
**The transcript is never rendered.** Not hidden with CSS, not in a data
attribute, not in a comment - the segment text is simply never written into the
HTML. If the rater could read the words they would rate the words, and the whole
point of this channel is to measure whether the VOICE agrees with the words. A
ground truth contaminated by the transcript would make the bench measure nothing.

`verify_page.py` checks this property mechanically rather than trusting review.

Design notes
------------
* Clips are presented in a pre-shuffled order (set in cut_clips.py) so the rater
  never hears one speaker in an unbroken block. A drifting impression of a voice
  would otherwise colour every clip in that block.
* Autosave to localStorage on every keystroke or click, with a storage probe up
  front so a blocked-storage browser warns before an hour of work is lost.
* Keyboard 1-5 and 0, because 150 clips is a lot of mouse travel.
* An explicit "can't tell" option. Forcing a rating on an unratable clip
  manufactures noise and calls it data; those clips are excluded from scoring and
  their count is reported.
"""

from __future__ import annotations

import json
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
INDEX = BENCH_DIR / "_clip_index.json"
OUT = BENCH_DIR / "rate_here.html"

SCALE = [
    (1, "Clearly negative", "annoyed, disappointed, critical, harsh"),
    (2, "Slightly negative", "a bit flat, unimpressed, reserved"),
    (3, "Neutral", "even, matter-of-fact, just explaining"),
    (4, "Slightly positive", "mildly warm, interested, pleased"),
    (5, "Clearly positive", "enthusiastic, excited, delighted"),
]


def build() -> str:
    index = json.loads(INDEX.read_text())
    clips = sorted(index["clips"], key=lambda c: c["order"])

    # ONLY these fields reach the page. Note the absence of "text" and "channel":
    # the transcript would contaminate the rating, and the speaker name would
    # invite consistency-by-speaker rather than clip-by-clip judgement.
    payload = [{"uid": c["uid"], "dur": round(c["duration"], 1)} for c in clips]

    cards = []
    for i, c in enumerate(payload):
        buttons = "".join(
            f'<button class="opt" data-uid="{c["uid"]}" data-v="{v}" '
            f'title="{desc}">{v}</button>'
            for v, _lab, desc in SCALE
        )
        cards.append(f"""
<div class="card" id="card{i}" data-uid="{c['uid']}">
  <div class="head"><span class="num">{i + 1} / {len(payload)}</span>
    <span class="dur">{c['dur']}s</span>
    <span class="done" id="done-{c['uid']}"></span></div>
  <audio controls preload="none" src="clips/{c['uid']}.wav"></audio>
  <div class="ctl"><button class="replay" data-uid="{c['uid']}">&#8630; replay</button></div>
  <div class="opts">{buttons}
    <button class="opt skip" data-uid="{c['uid']}" data-v="0"
            title="genuinely cannot judge the tone">can't tell</button></div>
</div>""")

    scale_rows = "".join(
        f"<tr><td class='k'>{v}</td><td><b>{lab}</b></td><td class='d'>{desc}</td></tr>"
        for v, lab, desc in SCALE
    )

    return f"""<title>Vocal Tone Rating</title>
<style>
:root {{
  --bg:#fbfbfa; --fg:#1a1a19; --mut:#6b6b68; --line:#e3e3e0; --card:#fff;
  --accent:#2f6f4f; --warn:#8a4b2a;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#1a1a19; --fg:#ececeb; --mut:#9a9a96; --line:#333331; --card:#232322;
    --accent:#7fc0a0; --warn:#d99b6a;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#1a1a19; --fg:#ececeb; --mut:#9a9a96; --line:#333331; --card:#232322;
  --accent:#7fc0a0; --warn:#d99b6a;
}}
* {{ box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--fg); margin:0;
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif; }}
.wrap {{ max-width:680px; margin:0 auto; padding:28px 20px 120px; }}
h1 {{ font-size:1.5rem; margin:0 0 4px; letter-spacing:-.01em; }}
.sub {{ color:var(--mut); margin:0 0 24px; }}
.box {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:16px 18px; margin:0 0 20px; }}
.box h2 {{ font-size:.95rem; margin:0 0 10px; text-transform:uppercase;
  letter-spacing:.06em; color:var(--mut); }}
table {{ border-collapse:collapse; width:100%; }}
td {{ padding:3px 8px 3px 0; vertical-align:top; }}
td.k {{ font-weight:700; color:var(--accent); width:1.6em; }}
td.d {{ color:var(--mut); }}
.rule {{ border-left:3px solid var(--warn); padding:2px 0 2px 12px; margin:12px 0 0;
  color:var(--fg); }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:14px 16px; margin:0 0 14px; }}
.card.rated {{ border-color:var(--accent); }}
.head {{ display:flex; gap:12px; align-items:center; margin-bottom:8px;
  font-size:.82rem; color:var(--mut); }}
.num {{ font-weight:600; color:var(--fg); }}
.done {{ margin-left:auto; color:var(--accent); font-weight:600; }}
audio {{ width:100%; height:36px; }}
.ctl {{ margin:8px 0 10px; }}
.replay, .opt {{ font:inherit; cursor:pointer; border:1px solid var(--line);
  background:transparent; color:var(--fg); border-radius:7px; padding:7px 12px; }}
.replay {{ font-size:.85rem; color:var(--mut); }}
.opts {{ display:flex; gap:7px; flex-wrap:wrap; }}
.opt {{ min-width:44px; font-weight:600; }}
.opt:hover {{ border-color:var(--accent); }}
.opt.on {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
.skip {{ min-width:auto; font-weight:400; font-size:.85rem; color:var(--mut); }}
.bar {{ position:fixed; left:0; right:0; bottom:0; background:var(--card);
  border-top:1px solid var(--line); padding:10px 20px;
  display:flex; gap:14px; align-items:center; }}
.bar .track {{ flex:1; height:6px; background:var(--line); border-radius:3px;
  overflow:hidden; }}
.bar .fill {{ height:100%; width:0; background:var(--accent); transition:width .2s; }}
#export {{ background:var(--accent); color:#fff; border:none; border-radius:7px;
  padding:9px 18px; font:inherit; font-weight:600; cursor:pointer; }}
#export:disabled {{ opacity:.4; cursor:not-allowed; }}
#warn {{ background:var(--warn); color:#fff; padding:10px 14px; border-radius:8px;
  margin-bottom:16px; }}
</style>

<div class="wrap">
<h1>Vocal tone rating</h1>
<p class="sub">{len(payload)} clips &middot; {index['total_seconds'] / 60:.0f} minutes of audio
&middot; your ratings save automatically</p>

<div id="warn" hidden>Your browser is blocking local storage, so progress will
NOT be saved. Fix that before continuing, or you will lose your work.</div>

<div class="box">
  <h2>What to judge</h2>
  <p style="margin:0 0 10px">Listen to <b>how the voice sounds</b> and rate it:</p>
  <table>{scale_rows}</table>
  <div class="rule"><b>Judge the sound, not the words.</b> Someone can say
  something critical in a cheerful voice, or praise something in a flat, bored
  one. Rate the <i>voice</i>. If the words and the tone disagree, that is exactly
  the case this whole channel exists to catch &mdash; go with the tone.</div>
  <div class="rule" style="border-color:var(--accent)">Use <b>can't tell</b>
  freely. Too short, too quiet, background music, laughter only &mdash; skip it.
  A guessed rating is worse than no rating.</div>
  <p style="margin:12px 0 0; color:var(--mut); font-size:.9rem">
  Keys <b>1</b>&ndash;<b>5</b> rate, <b>0</b> marks can't-tell, <b>space</b>
  replays. First impression is usually right &mdash; don't overthink, and take a
  break around clip 75.</p>
</div>

{''.join(cards)}
</div>

<div class="bar">
  <span id="count">0 / {len(payload)}</span>
  <div class="track"><div class="fill" id="fill"></div></div>
  <button id="export" disabled>Export ratings</button>
</div>

<script>
const KEY = "vocal_ratings_v1";
const N = {len(payload)};
let store = {{}}, ok = true;

try {{ store = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ ok = false; }}
try {{ localStorage.setItem(KEY+"_p","1"); localStorage.removeItem(KEY+"_p"); }}
catch (e) {{ ok = false; document.getElementById("warn").hidden = false; }}

function save() {{
  if (!ok) return;
  try {{ localStorage.setItem(KEY, JSON.stringify(store)); }}
  catch (e) {{ ok = false; document.getElementById("warn").hidden = false; }}
}}

function paint(uid) {{
  const v = store[uid];
  document.querySelectorAll('.opt[data-uid="'+uid+'"]').forEach(b =>
    b.classList.toggle("on", v !== undefined && String(v) === b.dataset.v));
  const card = document.querySelector('.card[data-uid="'+uid+'"]');
  if (card) card.classList.toggle("rated", v !== undefined);
  const tick = document.getElementById("done-"+uid);
  if (tick) tick.textContent = v === undefined ? "" : (v === 0 ? "skipped" : "rated");
}}

function refresh() {{
  const n = Object.keys(store).length;
  document.getElementById("count").textContent = n + " / " + N;
  document.getElementById("fill").style.width = (n / N * 100) + "%";
  document.getElementById("export").disabled = n === 0;
}}

document.querySelectorAll(".opt").forEach(b => {{
  b.addEventListener("click", () => {{
    store[b.dataset.uid] = parseInt(b.dataset.v, 10);
    save(); paint(b.dataset.uid); refresh();
    const card = b.closest(".card");
    const next = card.nextElementSibling;
    if (next && next.classList.contains("card")) {{
      next.scrollIntoView({{behavior:"smooth", block:"center"}});
      const a = next.querySelector("audio");
      if (a) {{ a.play().catch(() => {{}}); }}
    }}
  }});
}});

document.querySelectorAll(".replay").forEach(b => {{
  b.addEventListener("click", () => {{
    const a = b.closest(".card").querySelector("audio");
    a.currentTime = 0; a.play().catch(() => {{}});
  }});
}});

// Keyboard: act on whichever card is nearest the middle of the viewport.
function focused() {{
  const mid = window.innerHeight / 2;
  let best = null, dist = Infinity;
  document.querySelectorAll(".card").forEach(c => {{
    const r = c.getBoundingClientRect();
    const d = Math.abs((r.top + r.bottom) / 2 - mid);
    if (d < dist) {{ dist = d; best = c; }}
  }});
  return best;
}}

document.addEventListener("keydown", e => {{
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const card = focused();
  if (!card) return;
  if (e.key >= "0" && e.key <= "5") {{
    e.preventDefault();
    const btn = card.querySelector('.opt[data-v="'+e.key+'"]');
    if (btn) btn.click();
  }} else if (e.key === " ") {{
    e.preventDefault();
    const a = card.querySelector("audio");
    a.currentTime = 0; a.play().catch(() => {{}});
  }}
}});

document.getElementById("export").addEventListener("click", () => {{
  const out = {{ generated: new Date().toISOString(), scale: "1=clearly negative .. 5=clearly positive, 0=cant tell", ratings: store }};
  const blob = new Blob([JSON.stringify(out, null, 1)], {{type:"application/json"}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "vocal_ground_truth.json";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}});

Object.keys(store).forEach(paint);
refresh();
</script>
"""


if __name__ == "__main__":
    html = build()
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html) / 1024:.0f} KB)")
