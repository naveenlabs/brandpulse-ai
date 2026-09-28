"""
reference.py — the analytic reference the controllers are scored against.

Every other bench in this project had to buy its ground truth with human
labelling, because "what emotion is this face showing" has no closed form. The
controller's task is different in kind, and that difference is the single most
important design fact about this bench:

    the controller is handed four discrete valence labels and asked whether they
    disagree. Whether they disagree is a *function* of those labels.

So the ground truth here is analytic. It is computed from the controller's own
INPUTS, never from any model's output, which satisfies step 2 of the bench method (README) in the
strongest available form — there is no rater to be inconsistent and no ceiling to
estimate.

What that buys, and what it does not:

  it DOES measure    whether a controller performs the task the deployed system
                     prompt specifies ("0.0 full agreement -> 1.0 all channels
                     disagree").
  it does NOT measure whether that task detects real inauthenticity. The labels
                     being compared come from channels measured at 34.2%, 48.9%,
                     67.8% and 78.7% accuracy. A controller that disagrees with
                     them may well be right.

PROTOCOL.md §5 states both, and no claim of the second kind is drawn from any
number this module produces.

The valence map is imported from the production orchestrator rather than
restated, so the reference cannot silently drift away from the rule the pipeline
applies when it decides whether to damp a segment.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PROJECT = BENCH.parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from pipeline.orchestrator import _VALENCE_WORDS  # noqa: E402

POSITIVE, NEUTRAL, NEGATIVE = "POSITIVE", "NEUTRAL", "NEGATIVE"

# The four channel keys as the payload names them. The controller is told these
# exact strings by the system prompt, so these are also the strings its
# `channels_in_conflict` answers are graded against.
CHANNELS = ("transcript_sentiment", "vocal_emotion",
            "facial_emotion", "video_comment_sentiment")

# Per-pair disagreement weights. PROTOCOL.md §5.1 fixed these before any run.
#
# A POSITIVE/NEGATIVE pair is a polar disagreement and weighs 1.0: the channels
# point at opposite ends of the axis, and that is the case the product cares
# about. A pair involving NEUTRAL weighs 0.5, because "said nothing in particular"
# against "was positive" is a real but weaker divergence than "was positive"
# against "was negative".
#
# The 0.5 is the bench's one free parameter. It is declared in advance, it is
# reported as a choice rather than a fact, and the PRIMARY metric (P1) does not
# depend on it at all — P1 is binary on "any disagreement". Only P2 uses it.
POLAR_WEIGHT = 1.0
ADJACENT_WEIGHT = 0.5   # varied in report_bench.sensitivity_adjacent_weight


def to_valence(raw: object) -> str | None:
    """Map one channel's label onto the valence axis, or None if it has none.

    Delegates to the production vocabulary. `surprise`, `unknown`, `none detected`
    and anything else off the axis return None, and a channel that returns None is
    excluded from every comparison below rather than coerced to NEUTRAL. Coercing
    it would manufacture agreements and disagreements that the pipeline itself
    does not believe in.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _VALENCE_WORDS.get(raw.strip().lower())


def channel_valences(spec: dict) -> dict[str, str]:
    """The readable valence of each of the four channels, keyed by payload name.

    `spec` is a plain dict of raw channel labels keyed by the payload's own
    channel names, e.g.
        {"transcript_sentiment": "POSITIVE", "vocal_emotion": "NEUTRAL",
         "facial_emotion": "none detected", "video_comment_sentiment": "POSITIVE"}

    Channels with no readable valence are omitted, so `len()` of the result is the
    number of channels actually taking part in the comparison.
    """
    out = {}
    for name in CHANNELS:
        v = to_valence(spec.get(name))
        if v is not None:
            out[name] = v
    return out


# ── The three reference quantities ────────────────────────────────────────────

def ref_any(valences: dict[str, str]) -> bool:
    """Is there any disagreement at all among the readable channels?"""
    return len(set(valences.values())) >= 2


def ref_polar(valences: dict[str, str]) -> bool:
    """Is some channel POSITIVE while another is NEGATIVE?

    The authenticity-relevant case, and the one the motivating measurement in
    PROTOCOL.md §1 is about. Distinguished from `ref_any` because a
    NEUTRAL-vs-POSITIVE split is a much weaker thing to call a conflict, and a
    reference that treated the two identically would overstate the incumbent's
    failure.
    """
    vs = set(valences.values())
    return POSITIVE in vs and NEGATIVE in vs


def ref_score(valences: dict[str, str]) -> float:
    """Graded disagreement in [0, 1]: the mean disagreement weight over all pairs.

    0.0 when every readable channel agrees; 1.0 when every pair is polar — the two
    endpoints the deployed system prompt defines. Fewer than two readable channels
    means there is nothing to compare, which is 0.0 and not "unknown": the
    controller is being asked how much the channels disagree, and one channel
    cannot disagree with itself.
    """
    names = sorted(valences)
    pairs = list(itertools.combinations(names, 2))
    if not pairs:
        return 0.0
    total = 0.0
    for a, b in pairs:
        va, vb = valences[a], valences[b]
        if va == vb:
            continue
        # Module-level lookup, not a captured constant: the sensitivity check in
        # report_bench rebinds ADJACENT_WEIGHT to show the ranking does not
        # depend on it.
        total += POLAR_WEIGHT if NEUTRAL not in (va, vb) else ADJACENT_WEIGHT
    return total / len(pairs)


def ref_channels_in_conflict(valences: dict[str, str]) -> set[str]:
    """The set of channels that disagree with at least one other channel.

    Empty when everything agrees. This is what a correct `channels_in_conflict`
    answer would contain, and P3 grades the model's answer against it.

    Note what it is NOT: the *majority* channels are included too, not only the
    dissenters. The system prompt says "list every channel you consider to be in
    conflict", and in a two-way split both sides are in conflict with each other.
    Grading only the minority side would penalise a correct reading of the
    instruction as written.
    """
    if not ref_any(valences):
        return set()
    return set(valences)


# ── The rule baseline, as a predictor ─────────────────────────────────────────

def rule_baseline(spec: dict) -> dict:
    """A complete controller, in six lines, with no LLM.

    Returns the same shape a model's parsed response has, so it drops straight
    into the same scoring path as every LLM candidate and cannot be advantaged by
    a different one.

    It scores 1.0 on P1 and P2 BY CONSTRUCTION, because it is the reference
    evaluated as a predictor. PROTOCOL.md §3.2 says so in advance and the write-up
    repeats it: this is not a win, it is the statement that the label-comparison
    sub-task has a closed form. What it cannot do for free is P5 — it has no
    access to the transcript text, so on the incongruence suite it is structurally
    incapable of scoring above zero, and that is exactly the point of running it.
    """
    v = channel_valences(spec)
    return {
        "conflict_score": ref_score(v),
        "channels_in_conflict": sorted(ref_channels_in_conflict(v)),
        "flags": [],
        "narrative": "",
    }


def constant_baseline(value: float) -> "callable":
    """A controller that ignores its input and always answers `value`.

    `always_zero` is the strategy the incumbent currently approximates on 98.3% of
    corpus segments; `always_flag` is its mirror. Both exist so that a metric
    which either of them could win is disqualified from being the primary one.
    MCC is the metric chosen for precisely this property: a constant predictor
    scores exactly 0.0 on it, whatever the class balance.
    """
    def predict(spec: dict) -> dict:
        return {"conflict_score": float(value), "channels_in_conflict": [],
                "flags": [], "narrative": ""}
    return predict


# ── Normalising a model's channel names ───────────────────────────────────────

# Models do not answer with the payload's exact keys. `llama3.2` was observed
# emitting `comment_sentiment` on 98 of 481 cached responses where the payload key
# is `video_comment_sentiment`. Grading that as a miss would measure naming
# pedantry rather than reasoning, so answers are normalised onto the four payload
# keys before comparison, using the alias sets the production damping rule already
# maintains plus the transcript and comment equivalents.
_ALIASES = {
    "transcript_sentiment": {
        "transcriptsentiment", "transcript", "text", "textsentiment",
        "speech", "words", "transcriptemotion", "spokenwords", "language",
    },
    "vocal_emotion": {
        "vocalemotion", "vocalprosody", "vocal", "voice", "prosody",
        "speechbrainemotion", "vocaltone", "tone", "audio", "vocalsentiment",
    },
    "facial_emotion": {
        "facialemotion", "facial", "face", "facialexpression", "expression",
        "visual", "faceemotion", "facialsentiment", "deepface", "vision",
    },
    "video_comment_sentiment": {
        "videocommentsentiment", "commentsentiment", "comment", "comments",
        "audience", "audiencesentiment", "viewercomments", "commentary",
    },
}


def _normalise(name: object) -> str:
    return "".join(c for c in str(name).lower() if c.isalnum())


def normalise_channels(raw: object) -> set[str]:
    """Map a model's `channels_in_conflict` answer onto the four payload keys.

    Unrecognised names are dropped rather than kept as-is. Keeping them would make
    P3's Jaccard punish a model twice for one hallucination — once for the missing
    real channel and once for the invented name — and dropping them is the reading
    that is kinder to the models. Hallucinated *payload* channels are a different
    matter and are counted separately in the write-up.
    """
    if not isinstance(raw, list):
        return set()
    out = set()
    for item in raw:
        n = _normalise(item)
        for key, alias in _ALIASES.items():
            if n == _normalise(key) or n in alias:
                out.add(key)
                break
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard index, with the empty/empty case defined as 1.0.

    Both empty means the model correctly reported no conflict when there was none;
    that is a hit, not an undefined ratio. P3 is only computed over probes where
    the reference is non-empty (PROTOCOL.md §5.2), so this branch is defensive
    rather than load-bearing, but it is defined rather than left to raise.
    """
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)
