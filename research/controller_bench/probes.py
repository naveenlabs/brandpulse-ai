"""
probes.py — the two constructed test sets.

The natural corpus exercises **8** of the controller's possible input
configurations and its comment channel is POSITIVE on all 12 videos
(PROTOCOL.md §1). A bench run only on that corpus would be measuring the models
on a sliver of the input space, in a region where the right answer barely varies.
So the primary test set is constructed.

Two suites, with opposite purposes, and the second exists so the bench is not
rigged:

  probe_suite()        108 payloads covering every channel configuration.
                       Ground truth is analytic (reference.py). The label-only
                       rule baseline can, by construction, get every one of these
                       right, so this suite can only ever show an LLM failing to
                       match a function.

  incongruence_suite() 36 payloads whose channel labels all AGREE but whose
                       transcript text does or does not carry sarcasm, faint
                       praise, a disclosed sponsorship or an approving sentence
                       about a defect. The rule baseline is structurally
                       incapable of scoring above zero here. This is the only
                       axis on which an LLM can beat it, and it is included for
                       exactly that reason.

Both build real segment dicts and hand them to the production
`build_segment_payload`. Nothing here reimplements the payload. `facial_bench`
Amendment A3 is the precedent: benching a payload shape the pipeline does not
actually emit invalidated a completed sweep once already.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from pipeline.audio_module import AROUSAL_HIGH, AROUSAL_LOW  # noqa: E402
from pipeline.visual_module import FACIAL_CHANNEL_RELIABILITY  # noqa: E402
from pipeline.orchestrator import VOCAL_ONLY_CONFLICT_WEIGHT  # noqa: E402

VALENCES = ("POSITIVE", "NEUTRAL", "NEGATIVE")

# The facial channel's four levels, in DeepFace's own vocabulary.
#
# `None` is a level, not a gap. It is the ONLY facial value present in the entire
# cached corpus (those videos were downloaded audio-only), so a bench that omitted
# it would exercise a configuration the deployed system has never once produced.
#
# `surprise`, `fear` and `disgust` are deliberately absent. `surprise` has no
# valence on the pipeline's own map and would make the reference undefined for a
# third of the grid; `fear` and `disgust` map to NEGATIVE exactly as `sad` does,
# so they would triple the grid to test the same reference value three times.
FACIAL_LEVELS = ("happy", "neutral", "sad", None)

# Every probe carries the SAME carrier text. That is the design, not laziness: any
# variation in a model's answer across two probes with the same configuration is
# then, necessarily, variation caused by something other than the channel labels.
#
# The sentence is deliberately flat — a checkable fact about a product, with no
# evaluative word in it — so that a model reading the text instead of the labels
# finds nothing to read.
CARRIER_TEXT = ("The unit measures a hundred and sixty millimetres tall and ships "
                "with a two metre cable in the box.")

# Fixed non-label payload fields. Held constant across all 108 probes for the same
# reason as the text.
FIXED_PITCH_HZ = 142.0
FIXED_ENERGY = 0.041
FIXED_CONFIDENCE = 0.85
PROBE_START_S = 30.0
PROBE_END_S = 36.5

# Arousal values consistent with each vocal label under the deployed thresholds,
# so that a model reading the number and a model reading the word are told the
# same thing. Derived from AROUSAL_LOW / AROUSAL_HIGH rather than typed, so a
# threshold change breaks this loudly instead of silently benching a payload the
# pipeline could not produce.
_AROUSAL = {
    "NEGATIVE": round(AROUSAL_LOW / 2, 4),
    "NEUTRAL":  round((AROUSAL_LOW + AROUSAL_HIGH) / 2, 4),
    "POSITIVE": round((AROUSAL_HIGH + 1.0) / 2, 4),
}


def _segment(seg_id: int, text: str, transcript: str, vocal: str,
             facial: str | None) -> dict:
    """One fully-enriched segment dict, in the exact shape the pipeline builds."""
    return {
        "segment_id": seg_id,
        "start_time": PROBE_START_S,
        "end_time": PROBE_END_S,
        "text": text,
        "transcript_sentiment": {"label": transcript, "confidence": FIXED_CONFIDENCE},
        "vocal_emotion": {
            "label": vocal,
            "arousal": _AROUSAL[vocal],
            "valence": _AROUSAL[vocal],
            "dominance": _AROUSAL[vocal],
            "reliability": VOCAL_ONLY_CONFLICT_WEIGHT,
        },
        "facial_emotion": {
            "dominant": facial,
            "confidence": 0.0 if facial is None else FIXED_CONFIDENCE,
            "frame_count": 0 if facial is None else 6,
            "reliability": FACIAL_CHANNEL_RELIABILITY,
        },
        "pitch_mean": FIXED_PITCH_HZ,
        "energy_mean": FIXED_ENERGY,
    }


def _spec(transcript: str, vocal: str, facial: str | None, comment: str) -> dict:
    """The raw channel labels, for reference.channel_valences.

    `facial_emotion` is passed as the literal string the payload will show the
    model — "none detected" when there is no face — so the reference is computed
    from what the controller actually sees and not from an internal None.
    """
    return {
        "transcript_sentiment": transcript,
        "vocal_emotion": vocal,
        "facial_emotion": "none detected" if facial is None else facial,
        "video_comment_sentiment": comment,
    }


def probe_suite() -> list[dict]:
    """The 108-probe configuration grid. Deterministic, ordered, no seed needed.

    3 transcript x 3 vocal x 4 facial x 3 comment = 108, each presented once.

    Ordered by the product of the four loops rather than shuffled. There is no
    rater to fatigue and no ordering effect to defend against: each call is
    independent, stateless and made at temperature 0.
    """
    out = []
    for i, (t, v, f, c) in enumerate(
            itertools.product(VALENCES, VALENCES, FACIAL_LEVELS, VALENCES)):
        out.append({
            "probe_id": f"grid_{i:03d}",
            "suite": "grid",
            "segment": _segment(i, CARRIER_TEXT, t, v, f),
            "comment_sentiment": {"label": c, "confidence": FIXED_CONFIDENCE},
            "spec": _spec(t, v, f, c),
        })
    return out


# ── The incongruence suite ────────────────────────────────────────────────────
#
# 24 incongruent items and 12 congruent controls. In every one of the 36, all four
# channel labels AGREE, so `reference.ref_score` is 0.0 for all of them and the
# rule baseline necessarily answers 0.0 for all of them. The distinction lives
# entirely in the transcript text.
#
# Ground truth is BY CONSTRUCTION: an item is positive because it was written to
# contain an incongruence, in the same way a unit test's expected value is what it
# is because the test author wrote it. That is a real limitation and PROTOCOL.md
# §4.3 states it in advance — this suite can show that a capability exists or is
# absent; it cannot show how often the capability matters on real footage.
#
# Every item is published verbatim in the write-up so a reader can disagree with
# any of them individually.
#
# The channel labels for each item are the ones the pipeline's own models would
# plausibly assign to that surface text, which is the whole trap: sarcasm reads as
# positive to a sentiment classifier, so the labels agree while the meaning does
# not.
#
# The facial word is DERIVED from the agreed valence rather than listed per item.
# It was listed per item in the first draft and three items were written with a
# `neutral` face against a POSITIVE agreed valence, which silently broke the whole
# design guarantee — those three had a real cross-channel disagreement and the
# rule baseline scored 0.25 on them instead of 0.0. The unit test caught it. The
# fix is structural: with the facial word derived, the guarantee cannot be broken
# by editing the table.
_FACIAL_FOR = {"POSITIVE": "happy", "NEUTRAL": "neutral", "NEGATIVE": "sad"}

_INCONGRUENT = [
    # (text, agreed_valence, why it is incongruent)
    ("Oh, fantastic, they removed the charger from the box. Really generous of them.",
     "POSITIVE", "sarcasm: praise for a removal the speaker resents"),
    ("It only overheats when you actually use it, so that's basically never a problem.",
     "POSITIVE", "approving sentence describing a defect"),
    ("Full disclosure, the brand paid for this trip and sent me the unit for free. Anyway, it's incredible.",
     "POSITIVE", "disclosed sponsorship immediately followed by unqualified praise"),
    ("I mean, it's fine. It's fine. Everything about it is fine, I guess.",
     "POSITIVE", "faint praise by repetition; enthusiasm absent"),
    ("Battery life is amazing, if you don't mind charging it twice a day.",
     "POSITIVE", "superlative undercut by the conditional that follows"),
    ("This is easily the best phone I have ever had to send back twice.",
     "POSITIVE", "superlative whose object is a repeated failure"),
    ("They finally fixed the thing they broke last year, so well done to them.",
     "POSITIVE", "praise for the repair of a self-inflicted problem"),
    ("Love the new design. Love that it costs four hundred more. Love everything about it.",
     "POSITIVE", "sarcasm by anaphora on a price increase"),
    ("Look, I'm contractually obliged to say I enjoyed it, and I did enjoy it.",
     "POSITIVE", "praise explicitly framed as compelled"),
    ("The camera is great. Not as great as the one it replaced, but great.",
     "POSITIVE", "praise retracted mid-sentence and then restated"),
    ("Honestly it's a great little device for the money, assuming you already own the ecosystem, "
     "a case, the adapter, and a lot of patience.",
     "POSITIVE", "praise conditioned into meaninglessness"),
    ("Everyone in the comments said it was terrible, and they're right, but I still love it.",
     "POSITIVE", "endorsement of a criticism the speaker then ignores"),
    ("I'm being told through my earpiece that I love this product.",
     "POSITIVE", "explicit attribution of the opinion to someone else"),
    ("What a beautifully engineered way to lose all your data.",
     "POSITIVE", "aesthetic praise attached to a catastrophic outcome"),
    ("Nothing wrong with it at all, and I've only mentioned three things wrong with it.",
     "POSITIVE", "self-contradiction within one sentence"),
    ("It's genuinely impressive how confidently they shipped this unfinished.",
     "POSITIVE", "admiration directed at the shipping of a defect"),
    ("Ten out of ten. Would not buy again.",
     "POSITIVE", "maximum score paired with a refusal to repurchase"),
    ("Great value, provided your definition of value has recently changed.",
     "POSITIVE", "praise whose premise is withdrawn by the qualifier"),
    ("So the good news is it's waterproof. The bad news is I found that out the hard way.",
     "POSITIVE", "positive framing of an accident"),
    ("A masterclass in removing features people liked.",
     "POSITIVE", "praise vocabulary applied to a loss"),
    ("Perfect. Absolutely perfect. Now let me show you the crack.",
     "POSITIVE", "superlative immediately falsified by the next clause"),
    ("Best in class, if the class is phones that do this one thing badly.",
     "POSITIVE", "superlative whose scope is redefined into an insult"),
    ("It's amazing, and I want to be clear that I'm not being paid to say that. Anymore.",
     "POSITIVE", "disclaimer that reverses itself on the final word"),
    ("I have never been happier to stop using a phone.",
     "POSITIVE", "happiness attached to abandoning the product"),
]

_CONGRUENT = [
    ("The screen gets bright enough to read outdoors, and the hinge feels solid after a month.",
     "POSITIVE"),
    ("Charging from empty took just under an hour on the bundled adapter.",
     "NEUTRAL"),
    ("I have used it as my main phone for six weeks and I would buy it again.",
     "POSITIVE"),
    ("It weighs a hundred and ninety grams and measures seven point eight millimetres thick.",
     "NEUTRAL"),
    ("The battery died before lunch on every one of the five days I tested it.",
     "NEGATIVE"),
    ("Photos in daylight are sharp and the colours are accurate.",
     "POSITIVE"),
    ("There are three colours available and two storage tiers.",
     "NEUTRAL"),
    ("The software crashed four times during setup and lost my settings twice.",
     "NEGATIVE"),
    ("Build quality is excellent and the speakers are genuinely loud.",
     "POSITIVE"),
    ("It runs the same processor as last year's model at the same clock speed.",
     "NEUTRAL"),
    ("I cannot recommend it at this price when the previous model is half the cost.",
     "NEGATIVE"),
    ("Everything I asked it to do, it did, quickly and without fuss.",
     "POSITIVE"),
]


def incongruence_suite() -> list[dict]:
    """36 probes: 24 incongruent, 12 congruent controls.

    All four channel labels agree in every item, so `ref_score` is 0.0 throughout
    and `rule_baseline` answers 0.0 throughout. A model scores here only by
    reading the transcript.

    The 12 controls are what stop this suite rewarding a model that raises every
    score: P5 is the incongruent detection rate MINUS the control false-alarm
    rate, so a model that flags all 36 scores 0.0, exactly as it should.
    """
    out = []
    for i, (text, valence, _why) in enumerate(_INCONGRUENT):
        facial = _FACIAL_FOR[valence]
        out.append({
            "probe_id": f"incong_{i:02d}",
            "suite": "incongruence",
            "expected_conflict": True,
            "segment": _segment(1000 + i, text, valence, valence, facial),
            "comment_sentiment": {"label": valence, "confidence": FIXED_CONFIDENCE},
            "spec": _spec(valence, valence, facial, valence),
        })
    for i, (text, valence) in enumerate(_CONGRUENT):
        facial = _FACIAL_FOR[valence]
        out.append({
            "probe_id": f"control_{i:02d}",
            "suite": "incongruence",
            "expected_conflict": False,
            "segment": _segment(2000 + i, text, valence, valence, facial),
            "comment_sentiment": {"label": valence, "confidence": FIXED_CONFIDENCE},
            "spec": _spec(valence, valence, facial, valence),
        })
    return out


# Items whose hand-assigned transcript label does NOT match the label the
# deployed classifier actually produces for that text. Measured, not guessed:
# `cache/incongruence_label_check.json`, PROTOCOL.md Amendment A2.
#
# These five are unsound for the suite's purpose. The premise is that all four
# channel labels agree, so that only a controller reading the TEXT can find the
# incongruence — but for these five the transcript channel already reports the
# negativity, so in a real run they would never reach the controller with
# agreeing labels. They are kept in the suite (removing them after the fact would
# be selecting items on a property measured after construction) and excluded from
# the restricted P5, which is reported alongside the full one.
UNSOUND_ITEMS = frozenset({"incong_01", "incong_11", "incong_14",
                           "incong_16", "incong_18"})


def sound_incongruent_ids() -> list[str]:
    """The 19 incongruent items whose labels the real classifier reproduces."""
    return [p["probe_id"] for p in incongruence_suite()
            if p["expected_conflict"] and p["probe_id"] not in UNSOUND_ITEMS]


def incongruence_rationales() -> list[tuple[str, str]]:
    """(text, why-it-is-incongruent) for every positive item, for the write-up.

    Published so the construction can be audited item by item rather than trusted.
    """
    return [(text, why) for text, _v, why in _INCONGRUENT]


if __name__ == "__main__":
    grid = probe_suite()
    inc = incongruence_suite()
    print(f"grid suite         : {len(grid)} probes, "
          f"{len({p['probe_id'] for p in grid})} unique ids")
    print(f"incongruence suite : {len(inc)} probes "
          f"({sum(p['expected_conflict'] for p in inc)} positive, "
          f"{sum(not p['expected_conflict'] for p in inc)} control)")

    from reference import channel_valences, ref_any, ref_polar, ref_score
    from collections import Counter
    c = Counter()
    for p in grid:
        v = channel_valences(p["spec"])
        c[(len(v), ref_any(v), ref_polar(v))] += 1
    print("\n(readable channels, any disagreement, polar) -> count")
    for k, n in sorted(c.items()):
        print(f"  {k} -> {n}")
    print("\nref_score distribution:",
          dict(Counter(round(ref_score(channel_valences(p['spec'])), 4)
                       for p in grid).most_common()))
