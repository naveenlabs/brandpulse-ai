# Screen-reader, keyboard and phone script

Rewritten 25 Sep 2026 for the interface as it is now (gate, boot screen, landing
film, shelf and list, the book, Reduce motion, Read as one page). The 12 Sep
version described pages that no longer exist and was never run.

**Status: NOT YET RUN.** The procedure records planned checks only. It does not
constitute evaluation evidence until the Result column records an executed run.

## What this is and is not

This procedure is intended for a developer acceptance check using VoiceOver on
macOS, keyboard-only navigation and a phone. It can verify that the interface is
operable under those conditions, but it cannot establish usability for people
who rely on assistive technology in daily life. NVDA and JAWS on Windows remain
outside the tested scope.

The automated checks in `verify_ui.py` prove the right text is in the right
place. Only a real screen reader proves it is *spoken*, in order, without being
cut off or repeated.

## Setup (about 2 minutes)

```bash
cd brandpulse_ai
source .venv/bin/activate
python -m flask --app app run --port 5001
```

Open Safari (VoiceOver works best with Safari) at `http://127.0.0.1:5001/`.
VoiceOver on/off: **Cmd + F5**. "VO" means **Control + Option**.
Read next item: **VO + Right arrow**. Headings menu: **VO + U**, then Left/Right to "Headings".

> **Do not delete anything.** Some steps reach the Delete button. Every time,
> press **Keep it** (or Escape). "Delete permanently" really deletes the report.

Write what you HEAR, word for word where it matters, in the Result column. A step
that half-worked is written as half-worked. ~30 minutes in total.

## Part 1 — the opening (gate, boot, landing)

| # | Do this | What should happen | Result |
|---|---|---|---|
| 1.1 | Load `/` with VoiceOver on. Do not touch anything. | The gate's button is announced (its name, then "button"). | |
| 1.2 | Press **Enter**. | The boot screen: "Continue, button", then the whole boot log is read as its description (models, four channels, "facial reads below a constant"). | |
| 1.3 | While the log is being read, press **Control** alone, then **VO + Right**. | The boot screen **stays** (a modifier or a VoiceOver command must not dismiss it). | |
| 1.4 | Wait 15 seconds. | It is still there: a keyboard reader is not timed out. | |
| 1.5 | Press **Enter** on Continue. | The landing: focus lands on the main content. | |
| 1.6 | Open the headings menu (VO + U). | One level-1 heading, then the section headings, including all four film parts: "A second. Four sides.", "The words. The undertow.", the third one, "Nothing hidden. Nothing sent." | |
| 1.7 | Read through the film section with VO + Right. | All four parts are read in order, including "Facial accuracy: 34.2% … We publish both." and the link "Open this analysis". | |
| 1.8 | Press **Tab** until "Open this analysis" is focused. | The film scrolls to its last part so the focused link is on screen. | |

## Part 2 — Reduce motion

| # | Do this | What should happen | Result |
|---|---|---|---|
| 2.1 | Tab to "Reduce motion" in the top bar. | "Reduce motion, toggle button, not pressed" (wording varies). | |
| 2.2 | Press **Space**. | It says it is pressed and announces "Motion reduced. Nothing on the page will move on its own." Nothing on screen keeps moving. | |
| 2.3 | Reload the page. | Still reduced (remembered). Press it again to turn motion back on. | |

## Part 3 — the Library

| # | Do this | What should happen | Result |
|---|---|---|---|
| 3.1 | Go to `/library` (wide window). Read from the top. | A heading saying how many analyses are saved, then — in full — the facial bias caveat and the vocal caveat. | |
| 3.2 | Press **Tab** until an entry "Take down A brand: …" is focused. | It appears on screen at the bottom left and its name is read with both scores. | |
| 3.3 | Press **Enter**. | The volume comes off the shelf; focus moves to "Open the report"; its title and scores are announced. | |
| 3.4 | Tab to **Delete**, press **Space**. | The question "Delete … and the N video reports inside it? This cannot be undone." is read; focus on "Delete permanently". | |
| 3.5 | **Press Escape** (do not confirm). | The question closes; focus returns to Delete. Nothing was deleted. | |
| 3.6 | Tab to "Put it back", press Space. | The volume goes back; focus returns to the entry that took it down. | |
| 3.7 | Tab to "Show as a list", press Enter. | The list replaces the shelf and says so. Each set has a Delete button (press **Keep it** if you try it). | |
| 3.8 | Press "Show as a shelf". | The shelf comes back. | |

## Part 4 — one report (the book)

| # | Do this | What should happen | Result |
|---|---|---|---|
| 4.1 | Open any video's report from a set. Read the first page. | The title (level-1 heading), the facts, "In short", and "If you are the person in this frame, page N is written to you." | |
| 4.2 | Press the "page N" button in that sentence. | The book opens at "If you are the person in this video", read in full, including "There is no way to contest a reading in this build." | |
| 4.3 | Press **Right arrow** twice, then Left once. | Each turn announces the chapter and page numbers once. | |
| 4.4 | Tab to "Read as one page", press Enter. | The whole report on one page; the headings menu lists every chapter. | |
| 4.5 | In one-page view, find the Evidence table and Tab into it. | One Tab stop reaches a row; **Down/Up arrows** move row by row and each row's time and readings are read. | |
| 4.6 | Find the facial bias caveat. | Read in full, not cut off. | |

## Part 5 — Analyse (the run form)

| # | Do this | What should happen | Result |
|---|---|---|---|
| 5.1 | Go to `/run`. Tab to the first field. | Its label and its hint are read together. | |
| 5.2 | With the fields empty, press **Enter** on the submit button. | Focus moves to the first empty field; it is announced as invalid, with "Paste the address of a YouTube video." | |
| 5.3 | Do not start a real run (it takes 4–9 minutes and needs Ollama). | — | |

## Part 6 — without JavaScript

In Safari: Develop ▸ Disable JavaScript, then reload each page.

| # | Page | What should happen | Result |
|---|---|---|---|
| 6.1 | `/` | One heading, then plain text saying what the system does and where it is weak. | |
| 6.2 | `/library` and a report | The bias caveat and the vocal caveat, in full, and a working link onward. | |

## Part 7 — keyboard only, VoiceOver off (about 5 minutes)

Unplug or ignore the mouse. Use Tab, Shift+Tab, Enter, Space, arrows, Escape.

| # | Task | Done? Where did you get stuck? | Result |
|---|---|---|---|
| 7.1 | From `/`, get past both opening screens. | | |
| 7.2 | Open a report from the Library, turn three pages, find the page written to the person in the video. | | |
| 7.3 | Turn Reduce motion on and off. | | |
| 7.4 | Was the focus ring visible at every step? Note any step where you lost it. | | |

## Part 8 — on your phone (about 5 minutes)

Open `http://<this Mac's address>:5001/` on the same Wi-Fi (or skip if not reachable).

| # | Task | What should happen | Result |
|---|---|---|---|
| 8.1 | Landing, held upright then sideways. | Nothing runs off the side; the film's readings and "Skip sequence" can be reached sideways. | |
| 8.2 | Library. | A list, with the caveat; nothing hidden behind the bottom edge. | |
| 8.3 | A report, then "Read as one page", then pinch-zoom to 200%. | Text wraps; you never have to scroll sideways to read a line. | |

## Recording the result

Fill the Result column, then record, with the date: what failed,
what was fixed because of it, and what was not. A run that found nothing is
worth recording too — say that it was a developer check on VoiceOver only.
