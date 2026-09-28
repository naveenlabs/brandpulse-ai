#!/usr/bin/env python3
"""
build_typing_page.py - generate type_here.html, the local ground-truth typing tool.

Generated rather than hand-written so the clip list always matches _clip_index.json.

The page is opened from disk (file://), so the clip data is inlined: fetch() is
blocked by CORS on file:// and would leave the page empty. Audio is referenced by
relative path rather than embedded, which keeps the file small and avoids a 22 MB
base64 blob.

Deliberately shows no model output of any kind. The typist must not see a machine
guess before writing their own (TYPING_GUIDE.md rule 7).

Usage
-----
    python research/whisper_bench/build_typing_page.py
"""

from __future__ import annotations

import json
from pathlib import Path

BENCH = Path(__file__).resolve().parent
INDEX = BENCH / "_clip_index.json"
OUT = BENCH / "type_here.html"

data = json.loads(INDEX.read_text())
clips = data["clips"]

cards = []
for i, c in enumerate(clips, 1):
    cards.append(f"""
  <section class="card" data-vid="{c['video_id']}">
    <header>
      <div class="num">{i}<span>/12</span></div>
      <div class="meta">
        <strong>{c['channel']}</strong>
        <span class="dur">{c['duration_s']:.0f} seconds</span>
      </div>
      <div class="state" data-state="{c['video_id']}">empty</div>
    </header>
    <audio controls preload="none" src="clips/{c['video_id']}.wav"></audio>
    <div class="speed">
      Speed:
      <button type="button" data-rate="0.6">0.6x</button>
      <button type="button" data-rate="0.8">0.8x</button>
      <button type="button" data-rate="1" class="on">1x</button>
      <button type="button" data-rate="1.25">1.25x</button>
      <button type="button" data-rate="-10">&#8630; back 10s</button>
    </div>
    <textarea data-uid="{c['video_id']}" rows="7"
      placeholder="Type exactly what you hear&#10;&#10;Don't worry about punctuation or capitals.&#10;Do spell product names correctly.&#10;Use [unclear] only if you truly cannot make a word out."></textarea>
    <div class="count" data-count="{c['video_id']}">0 words</div>
  </section>""")

html = f"""<title>Whisper Ground Truth</title>
<style>
  :root {{
    --bg:#f6f7f9; --card:#fff; --ink:#16181d; --muted:#6b7280;
    --line:#e3e6ea; --accent:#2563eb; --ok:#059669; --warn:#b45309;
  }}
  :root:not([data-theme="light"]) {{ }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0f1115; --card:#171a21; --ink:#e8eaed; --muted:#9aa1ab;
      --line:#262b34; --accent:#60a5fa; --ok:#34d399; --warn:#fbbf24;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#0f1115; --card:#171a21; --ink:#e8eaed; --muted:#9aa1ab;
    --line:#262b34; --accent:#60a5fa; --ok:#34d399; --warn:#fbbf24;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    padding:0 16px 120px;
  }}
  .wrap {{ max-width:780px; margin:0 auto; }}
  h1 {{ font-size:22px; margin:28px 0 4px; letter-spacing:-.01em; }}
  .sub {{ color:var(--muted); margin:0 0 20px; font-size:14px; }}
  .rules {{
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:14px 18px; margin-bottom:24px; font-size:14px;
  }}
  .rules ul {{ margin:8px 0 0; padding-left:20px; }}
  .rules li {{ margin:4px 0; }}
  .card {{
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:16px 18px; margin-bottom:16px;
  }}
  .card header {{ display:flex; align-items:center; gap:12px; margin-bottom:12px; }}
  .num {{ font-weight:700; font-size:19px; }}
  .num span {{ color:var(--muted); font-weight:400; font-size:13px; }}
  .meta {{ flex:1; display:flex; flex-direction:column; }}
  .meta strong {{ font-size:14px; }}
  .dur {{ color:var(--muted); font-size:12.5px; }}
  .state {{
    font-size:11.5px; text-transform:uppercase; letter-spacing:.05em;
    color:var(--muted); border:1px solid var(--line); border-radius:99px;
    padding:3px 10px;
  }}
  .state.done {{ color:var(--ok); border-color:var(--ok); }}
  audio {{ width:100%; margin-bottom:10px; }}
  .speed {{ font-size:12.5px; color:var(--muted); margin-bottom:10px; }}
  .speed button {{
    font:inherit; background:transparent; color:var(--muted);
    border:1px solid var(--line); border-radius:6px; padding:3px 9px;
    margin-left:4px; cursor:pointer;
  }}
  .speed button.on {{ color:var(--accent); border-color:var(--accent); }}
  textarea {{
    width:100%; font:14.5px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;
    background:var(--bg); color:var(--ink); border:1px solid var(--line);
    border-radius:8px; padding:11px 13px; resize:vertical;
  }}
  textarea:focus {{ outline:2px solid var(--accent); outline-offset:-1px; }}
  .count {{ font-size:12px; color:var(--muted); margin-top:6px; text-align:right; }}
  .bar {{
    position:fixed; left:0; right:0; bottom:0; background:var(--card);
    border-top:1px solid var(--line); padding:12px 16px;
  }}
  .bar .inner {{
    max-width:780px; margin:0 auto; display:flex; align-items:center; gap:14px;
  }}
  .prog {{ flex:1; }}
  .track {{ height:6px; background:var(--line); border-radius:99px; overflow:hidden; }}
  .fill {{ height:100%; width:0%; background:var(--ok); transition:width .25s; }}
  .ptext {{ font-size:12.5px; color:var(--muted); margin-top:5px; }}
  button.primary {{
    font:inherit; font-weight:600; background:var(--accent); color:#fff;
    border:0; border-radius:8px; padding:10px 18px; cursor:pointer;
  }}
  button.primary:disabled {{ opacity:.45; cursor:not-allowed; }}
  .warn {{
    background:#fef3c7; color:#7c2d12; border:1px solid #fcd34d;
    border-radius:8px; padding:10px 14px; margin-bottom:18px; font-size:13.5px;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) .warn {{
      background:#3b2f14; color:#fde68a; border-color:#78350f;
    }}
  }}
</style>

<div class="wrap">
  <h1>Whisper Ground Truth</h1>
  <p class="sub">12 clips &middot; {data['total_minutes']:.1f} minutes total &middot; type what you hear</p>

  <div id="storagewarn" class="warn" hidden>
    <strong>Autosave is not working in this browser.</strong>
    Your typing is <em>not</em> being saved. Click Export before closing the tab,
    or open this file in Chrome instead.
  </div>

  <div class="rules">
    <strong>Quick rules</strong>
    <ul>
      <li>Type what was <em>said</em>, including stumbles and repeated words.</li>
      <li>Punctuation and capitals are ignored by the scorer &mdash; don't bother.</li>
      <li><strong>Do spell product and brand names correctly.</strong> That's the part that matters.</li>
      <li>Skip "uh" and "um". Keep real words like "like" and "basically".</li>
      <li>Use <code>[unclear]</code> only if you genuinely cannot make a word out.</li>
      <li>Don't look at any model's output first.</li>
    </ul>
  </div>
{''.join(cards)}
</div>

<div class="bar">
  <div class="inner">
    <div class="prog">
      <div class="track"><div class="fill" id="fill"></div></div>
      <div class="ptext" id="ptext">0 of 12 done</div>
    </div>
    <button class="primary" id="export" disabled>Export</button>
  </div>
</div>

<script>
const KEY = "whisper_ground_truth_v1";
let store = {{}};
let storageOK = true;

try {{
  store = JSON.parse(localStorage.getItem(KEY) || "{{}}");
}} catch (e) {{ storageOK = false; }}

function save() {{
  if (!storageOK) return;
  try {{ localStorage.setItem(KEY, JSON.stringify(store)); }}
  catch (e) {{ storageOK = false; document.getElementById("storagewarn").hidden = false; }}
}}

// Probe storage up front so the warning appears before any work is lost.
try {{
  localStorage.setItem(KEY + "_probe", "1");
  localStorage.removeItem(KEY + "_probe");
}} catch (e) {{
  storageOK = false;
  document.getElementById("storagewarn").hidden = false;
}}

const words = s => s.trim() ? s.trim().split(/\\s+/).length : 0;

function refresh() {{
  const areas = document.querySelectorAll("textarea");
  let done = 0;
  areas.forEach(a => {{
    const uid = a.dataset.uid;
    const n = words(a.value);
    document.querySelector(`[data-count="${{uid}}"]`).textContent =
      n + (n === 1 ? " word" : " words");
    const st = document.querySelector(`[data-state="${{uid}}"]`);
    // 15 words is roughly 6 seconds of speech - enough to count as started,
    // low enough not to nag on a short clip.
    if (n >= 15) {{ st.textContent = "done"; st.classList.add("done"); done++; }}
    else if (n > 0) {{ st.textContent = "in progress"; st.classList.remove("done"); }}
    else {{ st.textContent = "empty"; st.classList.remove("done"); }}
  }});
  document.getElementById("fill").style.width = (done / areas.length * 100) + "%";
  document.getElementById("ptext").textContent = done + " of " + areas.length + " done";
  document.getElementById("export").disabled = done === 0;
}}

document.querySelectorAll("textarea").forEach(a => {{
  const uid = a.dataset.uid;
  if (store[uid]) a.value = store[uid];
  a.addEventListener("input", () => {{ store[uid] = a.value; save(); refresh(); }});
}});

document.querySelectorAll(".speed button").forEach(b => {{
  b.addEventListener("click", () => {{
    const audio = b.closest(".card").querySelector("audio");
    const rate = parseFloat(b.dataset.rate);
    if (rate === -10) {{ audio.currentTime = Math.max(0, audio.currentTime - 10); return; }}
    audio.playbackRate = rate;
    b.parentElement.querySelectorAll("button").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
  }});
}});

document.getElementById("export").addEventListener("click", () => {{
  const out = {{
    generated: new Date().toISOString(),
    transcripts: {{}}
  }};
  document.querySelectorAll("textarea").forEach(a => {{
    out.transcripts[a.dataset.uid] = a.value.trim();
  }});
  const blob = new Blob([JSON.stringify(out, null, 1)], {{type: "application/json"}});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "ground_truth.json";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}});

refresh();
</script>
"""

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({len(html)/1024:.0f} KB, {len(clips)} clips)")
