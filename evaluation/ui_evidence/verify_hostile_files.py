"""
verify_hostile_files.py — can a saved file make a page run script?

Every page reads its data from JSON files this machine wrote: the reports in
outputs/, the written reports beside them, and each five-video set's record,
combined report and comparison. This script serves hostile versions of real
ones to a real browser and checks that no script runs. Nothing is written to
disk: every hostile file is substituted in the browser, by route interception.

Two kinds of hostility, because they are defended in two different places:

  text     Script-bearing markup in every text field (titles, transcripts,
           comments, reasons). Defended at each sink: esc() or .textContent
           (tests/test_ui_contracts.py, TestUntrustedTextReachesTheDomSafely).
  numbers  Markup in place of a number, one field name at a time: ids, counts,
           accuracies. The pipeline only writes numbers there, and pages print
           some of them straight into attributes and style values. Defended once,
           at load, by asReport / asAnalysis / asSweep in ui/src/lib/api.js.
           Poisoning a field NAME poisons every numeric value under that name,
           so a name that passes has no path under it that injects.

Also checked on every page: no link points at a javascript: address.

Measured on 26 Sep 2026, before the load-time guard, on the build as it then
was: segment ids and the audience's class counts ran script on the report page,
as did nine number fields of the written report, thirteen of the combined
report, and the class counts in a set's record. So did one text path: the
written report's key moments printed each channel's reading and the moment's
time unescaped (lib/written.js; the combined book's copy already escaped
them). The Library listings never did. After the fixes this script passes.

Needs a running server holding at least one report, and one set with a written
combined report for the set pages; a copy of the app is safer than the real
Library, though nothing here writes. Real Chrome, as the other harness scripts.

    python evaluation/ui_evidence/verify_hostile_files.py --base http://127.0.0.1:5057
    python evaluation/ui_evidence/verify_hostile_files.py --base ... --report "Nike (Mind 001).json" --sweep <id>

Exit status 0 when nothing ran, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

MARK = "window.__hostile=(window.__hostile||0)+1"
TEXT = [f'<img src=x onerror="{MARK}">',
        f'"><svg onload="{MARK}">',
        f"</script><script>{MARK}</script>",
        f"' onmouseover='{MARK}' x='"]
NUMBER = f'1"><img src=x onerror="{MARK}">'
TEXT_ALL = " ".join(TEXT)


def get(base: str, path: str):
    with urllib.request.urlopen(base + urllib.parse.quote(path)) as response:
        return json.load(response)


def number_names(node, out: set) -> set:
    """Every key that holds a number somewhere in `node`."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out.add(key)
            number_names(value, out)
    elif isinstance(node, list):
        for value in node:
            number_names(value, out)
    return out


def poison_number(node, name: str):
    """`node` with every numeric value under key `name` replaced by markup."""
    if isinstance(node, dict):
        return {k: NUMBER if k == name and isinstance(v, (int, float)) and not isinstance(v, bool)
                else poison_number(v, name) for k, v in node.items()}
    if isinstance(node, list):
        return [poison_number(v, name) for v in node]
    return node


def poison_text(node, depth: int = 0):
    """`node` with markup appended to every string that is not an id, a label or a date."""
    keep = re.compile(r"^(POSITIVE|NEUTRAL|NEGATIVE|[A-Za-z0-9_-]{11}|\d{4}-\d\d-\d\d.*|[a-z_]+)$")
    if isinstance(node, dict):
        return {k: poison_text(v, depth + 1) for k, v in node.items()}
    if isinstance(node, list):
        return [poison_text(v, depth + 1) for v in node]
    if isinstance(node, str) and node and not keep.match(node):
        return f"{node} {TEXT_ALL}"
    return node


class Browser:
    def __init__(self, playwright, base: str):
        self.base = base
        self.browser = playwright.chromium.launch(channel="chrome")

    def visit(self, path: str, replace: dict[str, str], *, then=None) -> dict:
        """Open `path` with the listed API paths answered by the given bodies; turn every spread."""
        context = self.browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")

        def router(route, _request):
            where = urllib.parse.unquote(urllib.parse.urlsplit(route.request.url).path)
            if route.request.method == "GET" and where in replace:
                return route.fulfill(status=200, content_type="application/json", body=replace[where])
            return route.continue_()

        context.route(re.compile(r".*/(reports|sweeps)(/.*)?$"), router)
        page = context.new_page()
        page.goto(self.base + path, wait_until="load")
        page.wait_for_timeout(1500)
        if then:
            then(page)
        for _ in range(40):
            page.evaluate("document.querySelectorAll('*').forEach(e => e.dispatchEvent("
                          "new MouseEvent('mouseover', {bubbles: true})))")
            following = page.query_selector("[data-cx-next]:not([disabled])")
            if not following or not following.is_visible():
                break
            try:
                following.click(timeout=1000)
            except Exception:  # noqa: BLE001 - a spread that will not turn ends the walk
                break
            page.wait_for_timeout(100)
        result = {
            "ran": page.evaluate("window.__hostile || 0"),
            "javascript_links": page.evaluate(
                "[...document.querySelectorAll('a[href]')].filter(a => "
                "/^\\s*javascript:/i.test(a.getAttribute('href'))).length"),
        }
        context.close()
        return result

    def close(self):
        self.browser.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="http://127.0.0.1:5057")
    parser.add_argument("--report", help="a report file name (default: the newest)")
    parser.add_argument("--sweep", help="a set id with a written combined report (default: the first)")
    args = parser.parse_args(argv)
    base = args.base.rstrip("/")

    reports = get(base, "/reports")
    sweeps = get(base, "/sweeps")
    name = args.report or (reports[0]["filename"] if reports else None)
    if name is None:
        print("no report on this server")
        return 1
    sid = args.sweep
    if sid is None:
        for s in sweeps:
            if (get(base, f"/sweeps/{s['sweep_id']}/analysis") or {}).get("written"):
                sid = s["sweep_id"]
                break

    # What each surface serves, and the page that reads it.
    surfaces = [("report", f"/reports/{name}", f"/library/{urllib.parse.quote(name)}"),
                ("written report", f"/reports/{name}/analysis", f"/library/{urllib.parse.quote(name)}"),
                ("report listing", "/reports", "/library"),
                ("set listing", "/sweeps", "/library")]
    compare = None
    if sid:
        record = get(base, f"/sweeps/{sid}")
        member = next((m["video_id"] for m in record.get("members", []) if m.get("analysed")), None)
        surfaces += [("set record", f"/sweeps/{sid}", f"/brand/{sid}"),
                     ("combined report", f"/sweeps/{sid}/analysis", f"/brand/{sid}")]
        if member:
            surfaces += [("set member", f"/sweeps/{sid}/members/{member}", f"/brand/{sid}/{member}"),
                         ("member's written report", f"/sweeps/{sid}/members/{member}/analysis",
                          f"/brand/{sid}/{member}")]
        subject = record.get("subject")
        sibling = next((s["sweep_id"] for s in sweeps
                        if s["sweep_id"] != sid and s.get("subject") == subject), None)
        if sibling and get(base, f"/sweeps/{sid}/compare/{sibling}").get("comparable"):
            compare = (f"/sweeps/{sid}/compare/{sibling}", sibling)
    else:
        print("no set with a written combined report: the set pages are not checked")

    failures = []
    with sync_playwright() as playwright:
        browser = Browser(playwright, base)

        def check(label, page_path, replace, then=None):
            outcome = browser.visit(page_path, replace, then=then)
            if outcome["ran"] or outcome["javascript_links"]:
                failures.append(label)
                print(f"  RAN   {label}: {outcome}")
            return outcome

        for label, api, page_path in surfaces:
            data = get(base, api)
            print(f"{label} ({api})")
            check(f"{label}: text", page_path, {api: json.dumps(poison_text(data))})
            names = sorted(number_names(data, set()))
            for key in names:
                check(f"{label}: number {key}", page_path, {api: json.dumps(poison_number(data, key))})
            print(f"  text and {len(names)} number fields")

        if compare:
            api, sibling = compare
            data = get(base, api)

            def open_it(page):
                page.eval_on_selector(f'[data-sib="{sibling}"]', "e => e.click()")
                page.wait_for_timeout(800)

            print(f"comparison ({api})")
            names = sorted(number_names(data, set()))
            for key in names:
                check(f"comparison: number {key}", f"/brand/{sid}",
                      {api: json.dumps(poison_number(data, key))}, then=open_it)
            print(f"  {len(names)} number fields")
        browser.close()

    print("RESULT:", "FAIL " + ", ".join(failures) if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
