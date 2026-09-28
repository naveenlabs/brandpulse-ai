"""
brand_terms.py - brand and product name recall, per Whisper candidate.

POST-HOC ANALYSIS. This was NOT pre-registered in CANDIDATE_MODELS.md. It was
written on 01 Sep 2026 after seeing that `base` transcribed "Dior Sauvage" as
"Dior Savash" while `large-v3` got it right. It is reported as exploratory, and
the pre-registered decision rule in report_whisper.py is not modified by it.

Why it exists: WER treats every word as equally important. For a brand-monitoring
product that assumption is wrong. A brand name is a rare token that carries the
entire meaning of the segment for this system's purpose - if the brand name is
mangled, the segment is useless to the product no matter how well the surrounding
filler was transcribed. WER therefore understates the damage for this application.

Method: the term list is taken from the HUMAN transcripts only, never from model
output. For each term, occurrences are counted in the normalised reference and
the normalised hypothesis, and recall is
    sum over terms of min(hyp_count, ref_count) / sum of ref_count
so a model cannot score by over-producing a term it did get right.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from wer import normalise

HERE = Path(__file__).parent

# Brand, product and model names appearing in the human transcripts. Chosen for
# being unambiguous proper nouns a brand-monitoring system would need to capture.
BRAND_TERMS = [
    "xiaomi", "angry birds", "samsung", "android", "apple",
    "dior", "sauvage", "chanel", "eau de toilette",
    "pixel", "night sight", "iphone", "fold",
    "macbook", "qwen", "draw things",
]

# Deliberately excluded, with reasons, so the list is not quietly convenient:
EXCLUDED = {
    "nothing": "brand name identical to a very common English word - counting it "
               "would measure luck at disambiguation, not name recognition",
    "m5 / m4": "chip names that normalise inconsistently ('m5' vs 'm 5') and would "
               "measure the normaliser rather than the model",
    "pro / ultra": "product-line suffixes, too generic to attribute to a brand",
}


def count_term(words: list[str], term: str) -> int:
    """Occurrences of a possibly multi-word term in a normalised word list."""
    parts = term.split()
    if len(parts) == 1:
        return words.count(parts[0])
    return sum(
        1 for i in range(len(words) - len(parts) + 1)
        if words[i:i + len(parts)] == parts
    )


def score(truth: dict[str, str], runs: dict[str, dict]) -> dict:
    ref_counts: dict[str, int] = {}
    ref_words = {cid: normalise(txt) for cid, txt in truth.items()}
    for term in BRAND_TERMS:
        ref_counts[term] = sum(count_term(w, term) for w in ref_words.values())

    total_ref = sum(ref_counts.values())
    results = {}
    for model, run in runs.items():
        hyp_words = {c["video_id"]: normalise(c["text"]) for c in run["clips"]}
        per_term = {}
        for term in BRAND_TERMS:
            if not ref_counts[term]:
                continue
            got = 0
            for cid, rw in ref_words.items():
                r = count_term(rw, term)
                h = count_term(hyp_words[cid], term)
                got += min(h, r)
            per_term[term] = (got, ref_counts[term])
        found = sum(g for g, _ in per_term.values())
        results[model] = {
            "found": found,
            "total": total_ref,
            "recall": found / total_ref if total_ref else 0.0,
            "per_term": per_term,
            "missed": [t for t, (g, r) in per_term.items() if g < r],
        }
    return {"ref_counts": ref_counts, "total": total_ref, "models": results}


def main() -> int:
    sys.path.insert(0, str(HERE))
    from report_whisper import load_clip_index, load_ground_truth, load_transcripts

    ids = [c["video_id"] for c in load_clip_index()]
    truth = load_ground_truth(ids)
    runs = load_transcripts()
    out = score(truth, runs)

    print("Brand and product name recall - POST-HOC, not pre-registered\n")
    print(f"{out['total']} brand-term occurrences across {len(ids)} clips, "
          f"{len([t for t, c in out['ref_counts'].items() if c])} distinct terms\n")

    print("Reference occurrences per term:")
    for t, c in sorted(out["ref_counts"].items(), key=lambda x: -x[1]):
        if c:
            print(f"  {t:<18}{c:>3}")
    print()

    print(f"{'model':<17}{'recall':>9}{'found':>8}  missed")
    print("-" * 70)
    ordered = sorted(out["models"].items(), key=lambda x: -x[1]["recall"])
    for model, r in ordered:
        missed = ", ".join(r["missed"]) or "-"
        print(f"{model:<17}{r['recall'] * 100:>8.1f}%{r['found']:>4}/{r['total']:<4}  {missed}")
    print()
    print("Excluded terms and why:")
    for t, why in EXCLUDED.items():
        print(f"  {t}: {why}")

    (HERE / "brand_terms_results.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {HERE / 'brand_terms_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
