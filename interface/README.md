# Building the interface

`python -m flask --app app run` serves the finished interface on its own. There
is no dev server in the demonstration path: `interface/static/` is the committed build
output and it is what ships. The demonstration build runs on a laptop without
depending on a second process.

```bash
python -m flask --app app run          # serves the committed build at :5000
```

## Rebuilding it

Four steps. Only the fourth is needed after an ordinary change to `interface/ui/src/`.

```bash
cd interface/ui && npm install                   # once, or after a dependency change
python interface/ui_build/fetch_fonts.py         # needs network; only to change the faces
python interface/ui_build/make_grain.py          # only to change the grain
python interface/ui_build/build_frames.py        # needs data/; after any new analysis
cd interface/ui && npm run build                 # -> ../static/, the committed output
```

### 1. Vendor the typefaces — `interface/ui_build/fetch_fonts.py`

Downloads four families from the Google Fonts repository, subsets them to the
characters this interface can print, converts them to woff2, and writes them
into `interface/ui/public/fonts/` with their SIL Open Font Licences.

| Family | Axes | Role |
|---|---|---|
| Bricolage Grotesque | opsz, wdth, wght | Display. Only ever large. |
| IBM Plex Sans | wdth, wght | Interface text. |
| IBM Plex Mono | 400, 600 | Every number a model measured. |
| Source Serif 4 | opsz, wght + italic | Words a person actually said. |

427 KB total. The licences ship beside the fonts because redistributing an OFL
font without its licence text violates it, and this repo is a submitted
artefact. A test asserts each `OFL-*.txt` is present and is the real licence.

### 2. Generate the grain — `interface/ui_build/make_grain.py`

A deterministic 180×180 noise tile. Generated rather than produced with an SVG
`feTurbulence` filter, because that filter is re-rasterised by the compositor
when its layer changes, which costs frames on exactly the pinned sections this
interface leans on. A static tile is painted once.

### 3. Derive the imagery — `interface/ui_build/build_frames.py`

Reads `data/<video_id>/frames/`, which `pipeline/downloader.py` extracted at
1 fps, and writes into `interface/ui/public/frames/`:

* **336 plates** at 1440 px, one per segment midpoint — the image the report
  contemplates at full scale, and the texture the separation shader samples
* **489 window frames** at 560 px, every second inside a flagged segment, so
  the page can show every frame a contested reading was pooled over
* **4 sprite grids**, 320 px tiles, for the scrubbed filmstrip
* `manifest.json`, the only thing the interface consults, so it never requests
  a frame that is not there

32 MB out of the 2.0 GB on disk. A report whose frames have not been derived
still renders: the plate draws the absence and names this command.

### 4. Build — `npm run build`

Vite, multi-page, `base: "/static/"`, output to `../static/` with
`emptyOutDir`. GSAP, ScrollTrigger and Lenis are bundled from `node_modules`;
nothing is fetched at runtime. `interface/ui/public/` is copied verbatim, so the fonts,
the grain and the frames land next to the compiled assets.

Output: four documents, five stylesheets, six modules, 42 MB including imagery.

## Licences of what is vendored

| | Version | Licence |
|---|---|---|
| GSAP + ScrollTrigger | 3.15.0 | GSAP standard "no charge" licence — free for commercial and non-commercial use, all plugins included. Its attribution strings must not be removed, and are not. |
| Lenis | 1.3.26 | MIT |
| Vite | 6.4.3 | MIT (build-time only, not shipped) |
| Bricolage Grotesque, IBM Plex Sans, IBM Plex Mono, Source Serif 4 | — | SIL OFL 1.1, shipped with their licence text |

## Verifying it

`pytest` covers what can be read off the source and the build (122 tests). The
rest needs a browser and is deliberately outside the suite, because `playwright`
is not in `requirements.txt` and a deployment should never pull a browser down.

```bash
python -m flask --app app run --port 5057 &

python evaluation/ui_evidence/extract_figures.py           # re-derive every printed figure
python evaluation/ui_evidence/verify_ui.py                 # requests, contrast, keyboard, fps, reduced motion
python evaluation/ui_evidence/verify_tests_bite.py         # break 24 guarded things, check the tests fail
python evaluation/ui_evidence/shoot.py                     # screenshots, both themes, two widths
```

Install the browser once with
`pip install playwright && python -m playwright install chromium`.
