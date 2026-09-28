"""
analyst_verify.py — nothing the model writes reaches the book unchecked.

Every piece of text the local model returns for the written report passes
through here. Each check is deterministic, each is unit-tested
(tests/test_analyst_verify.py), and each failure is logged with the exact text
that failed and why, so a run can be audited and the drop rate reported.

  V1  quotes     A quote must be the reviewer's or a commenter's own words: its
                 word sequence must occur, contiguously, in the text it cites.
                 Case, punctuation and spacing are forgiven; a changed, added
                 or missing word is not.
  V2  ids        Every piece of evidence cited (S<segment>, C<comment>,
                 T<topic>) must exist.
  V3  numbers    Every figure in a sentence must be a rounding of a number the
                 model was given, a timecode the video has, or a number in the
                 evidence it cites or in the product's own name. Proportion
                 words the verifier cannot check ("most comments", "half of
                 the viewers", "the majority") are refused outright.
  V4  claims     Prose may not say anyone was paid, sponsored, honest,
                 dishonest, lying, fake or a bot. Those questions belong to the
                 deterministic signs in analyst_facts, which show their
                 evidence; a sentence that answers them in prose is dropped.
  V5  shape      Word limits and list sizes.
  V6  privacy    @handles and URLs in any comment the book quotes are masked.

A failing sentence is dropped, never repaired: rewriting the model's words
would put words in its mouth that were never checked either.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# ── normalising ──────────────────────────────────────────────────────────────

_QUOTES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'",
                         "′": "'", "“": '"', "”": '"', "„": '"',
                         "″": '"', "–": "-", "—": "-", "−": "-"})
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def words(text: object) -> list[str]:
    """Lower-cased word tokens, with curly quotes straightened first."""
    return _WORD.findall(str(text or "").translate(_QUOTES).casefold())


def quote_in(quote: object, source: object) -> bool:
    """V1: the quote's words occur contiguously in the source's words."""
    q, s = words(quote), words(source)
    if not q or len(q) > len(s):
        return False
    first = q[0]
    for i in range(len(s) - len(q) + 1):
        if s[i] == first and s[i:i + len(q)] == q:
            return True
    return False


def word_count(text: object) -> int:
    return len(words(text))


def quote_home(quote: object, ordered: list[tuple[object, object]]) -> tuple[object, object] | None:
    """
    Where a quote is, among consecutive (id, text) pieces: (start id, end id), or None.

    Whisper cuts segments mid-sentence ("iOS actually adapts to how the" |
    "device is angled or propped"), so a speaker's one sentence can span two
    segments. A quote found in exactly one segment is at (id, id). Otherwise a
    quote found across exactly one adjacent pair -- and in neither half alone --
    is at (first id, second id). Found nowhere, in two places, or across more
    than two segments: None. The words are still verbatim and contiguous; only
    the segment cut is ignored. (Apple (Duo), 23 Sep 2026: 7 of 24 claims were
    dropped, every one across a cut.)
    """
    single = [sid for sid, text in ordered if quote_in(quote, text)]
    if len(single) == 1:
        return single[0], single[0]
    if single:
        return None
    pairs = [(a[0], b[0]) for a, b in zip(ordered, ordered[1:])
             if quote_in(quote, f"{a[1] or ''} {b[1] or ''}")]
    return pairs[0] if len(pairs) == 1 else None


_META = re.compile(r"(?:about\s+)?(?:the\s+)?(?:reviewer|reviewers|creator|creators|youtuber|youtubers|"
                   r"channel|host|presenter|influencer|video|review|content\s+creator)(?:'s)?", re.I)


def is_meta_topic(name: object) -> bool:
    """
    A topic about the person or the video rather than the product: "The
    reviewer", "About the creator", "The channel".

    Commenters do talk about the reviewer, so such a topic is kept as an
    audience topic. But the word "reviewer" is also the subject of nearly every
    sentence the report writes ("The reviewer concludes..."), so a stance check
    that treats it as a topic reads the sentence's subject as its object.
    Apple (Duo), 23 Sep 2026: a correct verdict was dropped for exactly that.
    """
    return bool(_META.fullmatch(" ".join(str(name or "").split())))


# ── V6 privacy ───────────────────────────────────────────────────────────────

_HANDLE = re.compile(r"(?<![\w@])@[\w.\-]{2,}")
_URL = re.compile(r"https?://([^/\s]+)\S*", re.I)


def mask_comment(text: object) -> str:
    """A commenter quoted in the book is never pointed at another person."""
    out = _URL.sub(lambda m: f"{m.group(1)}/…", str(text or ""))
    return _HANDLE.sub("@…", out)


# ── V3 numbers ───────────────────────────────────────────────────────────────

_TIME = re.compile(r"(?<![\d:])(\d{1,2}):([0-5]\d)(?![\d:])")
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(\s?%|\s?percent\b)?", re.I)
_NUMBER_WORDS = {w: i for i, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
     "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
     "eighteen", "nineteen", "twenty"])}
# "one" is a pronoun as often as a number ("the one moment", "one of"), and
# "zero" appears in the conflict scale's own wording; both are left alone.
_CHECKED_WORDS = {w: v for w, v in _NUMBER_WORDS.items() if v >= 2}
_NUMBER_WORD = re.compile(r"\b(" + "|".join(_CHECKED_WORDS) + r")\b", re.I)

QUANTIFIERS = (
    r"\bmajority\b",
    r"\bminority\b",
    r"\bmost\s+(?:of\s+(?:the\s+|these\s+|those\s+)?)?(?:comments?|commenters?|viewers?|people|"
    r"audiences?|segments?|videos?|reviewers?|moments?)\b",
    r"\b(?:a|one|two)\s+thirds?\s+of\b",
    r"\b(?:a|one|three)\s+quarters?\s+of\b",
    # "the second half of the video" is a time, not a proportion.
    r"(?<!first\s)(?<!second\s)(?<!latter\s)(?<!former\s)"
    r"\bhalf\s+of\s+(?:the\s+)?(?:comments?|commenters?|viewers?|people|audience|segments?|videos?)\b",
    r"\b(?:nearly|almost|virtually)\s+(?:all|every)\b",
    r"\beveryone\b",
    r"\bnobody\b",
    r"\bno\s+one\b",
    r"\bunanimous\w*",
    r"\boverwhelming\w*",
    r"\bmostly\b",
)

FORBIDDEN = (
    r"\bpaid\b", r"\bsponsor\w*", r"\bbrib\w*", r"\bdishonest\w*", r"\bhonest\w*",
    r"\blie[sd]?\b", r"\blying\b", r"\bliars?\b", r"\bfake\w*", r"\bbots?\b",
    r"\bscam\w*", r"\bmanipulat\w*", r"\bdecei\w*", r"\bdecept\w*", r"\bshill\w*",
    r"\bfraud\w*", r"\bgenuine\w*", r"\binauthentic\w*", r"\bauthentic\b",
    r"\btrustworth\w*", r"\bpromotional\b", r"\badvert\w*", r"\bfabricat\w*",
    r"\bcollu\w*", r"\bkickback\w*",
)

_FORBIDDEN_RE = [re.compile(p, re.I) for p in FORBIDDEN]
_QUANTIFIER_RE = [re.compile(p, re.I) for p in QUANTIFIERS]
_QUOTED = re.compile(r'"([^"]{2,400})"')


def numbers_in(obj) -> set[float]:
    """
    Every finite numeric leaf in a JSON-like value (bools excluded).

    Strings are not mined for digits: a timecode "2:09" in the sheet is a time,
    checked against the video's own times, and must not license the figures 2
    and 9.
    """
    out: set[float] = set()
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, bool) or cur is None:
            continue
        if isinstance(cur, (int, float)):
            if math.isfinite(cur):
                out.add(float(cur))
        elif isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple, set)):
            stack.extend(cur)
    return out


def percentages_in(obj) -> set[float]:
    """
    The numbers a sheet gives AS percentages: the values of keys naming one
    ("positive_pct"). A written "1%" must be one of these, or a percentage in
    the evidence it cites -- never a count wearing a percent sign. The second
    S27 run (24 Sep 2026) wrote "1% positive comments" from a count of 1.
    """
    out: set[float] = set()
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if "pct" in str(k) and isinstance(v, (int, float)) and not isinstance(v, bool) \
                        and math.isfinite(v):
                    out.add(float(v))
                else:
                    stack.append(v)
        elif isinstance(cur, (list, tuple)):
            stack.extend(cur)
    return out


def percentages_in_text(text: str) -> set[float]:
    """The percentages written in a piece of source text ("up to 50% faster")."""
    out: set[float] = set()
    for m in _NUMBER.finditer(str(text or "")):
        if m.group(3):
            whole = m.group(1).replace(",", "")
            dec = m.group(2) or ""
            out.add(float(f"{whole}.{dec}" if dec else whole))
    return out


def numbers_in_text(text: str) -> set[float]:
    """The numbers written in a piece of source text (a name, a quote)."""
    out: set[float] = set()
    for m in _NUMBER.finditer(str(text or "")):
        whole = m.group(1).replace(",", "")
        dec = m.group(2) or ""
        out.add(float(f"{whole}.{dec}" if dec else whole))
    return out


def _supported(value: float, places: int, allowed: set[float]) -> bool:
    """
    True when `value`, written to `places` decimals, is a rounding of an allowed number.

    A percentage must match a percentage the model was given; a share is never
    silently multiplied by 100, because a lean of 0.3 is not "30%" of anything.
    A whole number may round a decimal only when that decimal is at least 1:
    a conflict score of 0.789 does not license the figure "1".
    """
    for a in allowed:
        if places == 0:
            if a == value:
                return True
            # Either neighbour of .5 is accepted, so half-up and banker's
            # rounding of the same figure both pass.
            if abs(a) >= 1.0 and abs(a - value) <= 0.5 + 1e-9:
                return True
        elif abs(round(a, places) - value) < 1e-9:
            return True
    return False


# ── the checks, applied to one sentence ──────────────────────────────────────

@dataclass
class Context:
    """What a piece of prose may lean on."""
    allowed_numbers: set[float] = field(default_factory=set)
    allowed_times: set[str] = field(default_factory=set)
    segment_text: dict = field(default_factory=dict)     # segment id -> text
    comment_text: dict = field(default_factory=dict)     # comment index -> text
    topic_names: dict = field(default_factory=dict)      # topic index -> name
    names: str = ""                                      # brand, product, title
    allowed_pct: set | None = None                       # percentages the sheet gives; None: not held


_EVIDENCE = re.compile(r"^([SCT])(\d{1,5})$")


def check_evidence(ids, ctx: Context) -> tuple[list[str], list[str]]:
    """V2. Returns (valid ids, problems)."""
    valid, problems = [], []
    for raw in ids or []:
        m = _EVIDENCE.match(str(raw).strip())
        if not m:
            problems.append(f"evidence id not understood: {raw!r}")
            continue
        kind, num = m.group(1), int(m.group(2))
        table = {"S": ctx.segment_text, "C": ctx.comment_text, "T": ctx.topic_names}[kind]
        if num in table:
            valid.append(f"{kind}{num}")
        else:
            problems.append(f"cites {raw} which does not exist")
    return valid, problems


def _evidence_text(ids: list[str], ctx: Context) -> str:
    parts = []
    for i in ids:
        kind, num = i[0], int(i[1:])
        if kind == "S":
            parts.append(ctx.segment_text.get(num, ""))
        elif kind == "C":
            parts.append(ctx.comment_text.get(num, ""))
        else:
            parts.append(ctx.topic_names.get(num, ""))
    return " ".join(parts)


def check_prose(text: object, evidence, ctx: Context, *, max_words: int,
                require_evidence: bool = True) -> tuple[bool, list[str], list[str]]:
    """
    V1-V5 for one piece of prose. Returns (ok, problems, valid evidence ids).

    Quoted spans inside the prose must pass V1 against the evidence it cites,
    and are then set aside before the number and claim checks, because a
    reviewer's own words may contain anything.
    """
    problems: list[str] = []
    if not isinstance(text, str) or not text.strip():
        return False, ["empty"], []
    text = text.strip()
    ids, id_problems = check_evidence(evidence, ctx)
    problems.extend(id_problems)
    if require_evidence and not ids:
        problems.append("cites no evidence")
    problems.extend(_check_body(text, _evidence_text(ids, ctx), ctx.allowed_numbers,
                                ctx.allowed_times, ctx.names, max_words, ctx.allowed_pct))
    return (not problems), problems, ids


def _check_body(text: str, source: str, allowed_numbers: set[float], allowed_times: set[str],
                names: str, max_words: int, allowed_pct: set[float] | None = None) -> list[str]:
    """V1 and V3-V5 on one sentence, given the text of the evidence it cites."""
    problems: list[str] = []
    n_words = word_count(text)
    if n_words > max_words:
        problems.append(f"{n_words} words, limit {max_words}")

    bare = text.translate(_QUOTES)
    for q in _QUOTED.findall(bare):
        if not quote_in(q, source):
            problems.append(f"quote not found in its evidence: {q[:60]!r}")
    bare = _QUOTED.sub(" ", bare)

    for pattern in _FORBIDDEN_RE:
        m = pattern.search(bare)
        if m:
            problems.append(f"makes a claim only the signs may make: {m.group(0)!r}")
    for pattern in _QUANTIFIER_RE:
        m = pattern.search(bare)
        if m:
            problems.append(f"states a proportion that cannot be checked: {m.group(0)!r}")

    allowed = set(allowed_numbers) | numbers_in_text(source) | numbers_in_text(names)
    for m in _TIME.finditer(bare):
        if m.group(0) not in allowed_times:
            problems.append(f"timecode not in the video: {m.group(0)}")
    bare = _TIME.sub(" ", bare)
    pct_allowed = None if allowed_pct is None else set(allowed_pct) | percentages_in_text(source)
    for m in _NUMBER.finditer(bare):
        whole = m.group(1).replace(",", "")
        dec = m.group(2) or ""
        value = float(f"{whole}.{dec}" if dec else whole)
        if not _supported(value, len(dec), allowed):
            problems.append(f"figure not in the facts: {m.group(0).strip()}")
        elif m.group(3) and pct_allowed is not None and not _supported(value, len(dec), pct_allowed):
            problems.append(f"a percentage the facts do not give as one: {m.group(0).strip()}")
    for m in _NUMBER_WORD.finditer(bare):
        if not _supported(float(_CHECKED_WORDS[m.group(1).lower()]), 0, allowed):
            problems.append(f"figure not in the facts: {m.group(0)}")
    return problems


# ── consistency with a computed call ─────────────────────────────────────────
#
# The agreement sentence is the one piece of prose whose meaning code has
# already decided (analyst_facts.agreement). A sentence that says "they agree"
# over a call of "the reviewer is warmer" is wrong however well grounded its
# figures are, so its direction is checked against the call.

_SAYS_DISAGREE = re.compile(r"\b(?:disagree\w*|do(?:es)?\s+not\s+agree|do(?:es)?n'?t\s+agree|"
                            r"differ\w*|split|at\s+odds|diverge\w*)\b", re.I)
_SAYS_AGREE = re.compile(r"\b(?:agree\w*|in\s+line|align\w*|match\w*|same\s+view|"
                         r"no\s+clear\s+difference|see\s+it\s+the\s+same)\b", re.I)
_WARMER = r"(?:warmer|more\s+positive|more\s+favou?rable|more\s+enthusiastic|keener|happier)"
_REVIEWER_WARMER = re.compile(r"\breviewer\b[^.;]*\b" + _WARMER + r"\b|\baudience\b[^.;]*\b"
                              r"(?:cooler|more\s+negative|less\s+positive|more\s+critical)\b", re.I)
_AUDIENCE_WARMER = re.compile(r"\b(?:audience|comments?|viewers?)\b[^.;]*\b" + _WARMER +
                              r"\b|\breviewer\b[^.;]*\b(?:cooler|more\s+negative|less\s+positive|"
                              r"more\s+critical)\b", re.I)


def agreement_consistent(text: object, call: str) -> list[str]:
    """
    Problems with an agreement sentence's direction, given the computed call.

    no_clear_difference: may not say either side is warmer.
    reviewer_warmer / audience_warmer: may not say the two agree, and may not
    say the other side is the warmer one. An 'unknown' call accepts nothing
    directional.
    """
    t = str(text or "")
    says_agree = bool(_SAYS_AGREE.search(t)) and not _SAYS_DISAGREE.search(t)
    rw, aw = bool(_REVIEWER_WARMER.search(t)), bool(_AUDIENCE_WARMER.search(t))
    problems = []
    if call == "no_clear_difference" and (rw or aw):
        problems.append("says one side is warmer; the call found no clear difference")
    elif call == "reviewer_warmer" and (says_agree or aw):
        problems.append("contradicts the call: the reviewer is the warmer side")
    elif call == "audience_warmer" and (says_agree or rw):
        problems.append("contradicts the call: the audience is the warmer side")
    elif call not in ("no_clear_difference", "reviewer_warmer", "audience_warmer") and (rw or aw or says_agree):
        problems.append("states a direction the data could not establish")
    return problems


# ── consistency with what was actually said ──────────────────────────────────
#
# The first real run wrote a verdict saying the reviewer criticised the comfort
# of a shoe whose reviewer had said "They're definitely comfortable": every
# figure in it was grounded, and the sentence was still wrong. So a sentence
# that says a topic was praised or criticised is held to the claims and the
# comment counts code has already sorted by topic. Clause by clause: whose
# opinion it states (the audience when it names the comments or viewers, the
# reviewer otherwise), which way, and about which topic. A clause that says
# both, or says neither, is left alone rather than guessed at.
#
# A heuristic, and named as one. It catches the wrong-direction sentence it was
# written for and it is tested both ways; it cannot follow every construction
# English allows.

_POS = re.compile(r"\b(?:prais\w*|likes?|liked|liking|lov(?:e|es|ed|ing)|positive\w*|good|great|"
                  r"enjoy\w*|impress\w*|appreciat\w*|pleased|favou?r\w*|excit\w*|recommend\w*|"
                  r"welcom\w*|worth)\b", re.I)
_NEG = re.compile(r"\b(?:criticis\w*|criticiz\w*|critical\w*|critics?|complain\w*|dislik\w*|negative\w*|poor\w*|"
                  r"problem\w*|concern\w*|disappoint\w*|doubt\w*|skeptic\w*|sceptic\w*|flaw\w*|"
                  r"fault\w*|downside\w*|drawback\w*|frustrat\w*|unhappy|worse|worst|bad|"
                  r"lacklust\w*|overpriced|underwhelm\w*|mediocre|unimpress\w*|gimmick\w*)\b", re.I)
_NEGATION = {"not", "no", "never", "hardly", "without", "nor"}
_AUDIENCE = re.compile(r"\b(?:audience\w*|comments?|commenters?|viewers?|people|fans?|buyers?)\b", re.I)
_CLAUSE = re.compile(r"[.;:!?]|,?\s+(?:but|while|whereas|although|though|yet)\s+", re.I)


# A count's label is not a stance: "with 139 negative comments, 135 positive"
# lists figures, and read as words it made a clause look two-sided, so the
# "mostly negative" beside it went unread (S27 month, 24 Sep 2026).
_COUNT_LABEL = re.compile(r"\b\d[\d,.]*\s*%?\s+(?:(?:of\s+(?:the\s+|all\s+)?)?(?:audience\s+)?comments?\s+"
                          r"(?:being\s+|are\s+|were\s+|read\s+)?)?(?:positive|negative|neutral)(?:\s+comments?)?",
                          re.I)


def _polarity(clause: str) -> str | None:
    tokens = re.findall(r"[a-z']+", _COUNT_LABEL.sub(" ", clause).lower())
    pos = neg = 0
    for i, tok in enumerate(tokens):
        hit = "pos" if _POS.fullmatch(tok) else "neg" if _NEG.fullmatch(tok) else None
        if not hit:
            continue
        window = tokens[max(0, i - 3):i]
        flipped = any(w in _NEGATION or w.endswith("n't") for w in window)
        if (hit == "pos") != flipped:
            pos += 1
        else:
            neg += 1
    if pos and not neg:
        return "pos"
    if neg and not pos:
        return "neg"
    return None


def _mentions(clause: str, topic: dict) -> bool:
    if str(topic.get("name", "")).lower() == "other" or is_meta_topic(topic.get("name")):
        return False
    text = clause.lower()
    words = [str(topic.get("name", "")).lower()] + [str(a).lower() for a in topic.get("aspects") or []]
    return any(w and re.search(r"\b" + re.escape(w) + r"s?\b", text) for w in words)


def stance_problems(text: object, topics: list[dict]) -> list[str]:
    """Clauses that praise or criticise a topic the run has no such evidence for."""
    problems = []
    for clause in _CLAUSE.split(str(text or "")):
        if not clause.strip():
            continue
        polarity = _polarity(clause)
        if polarity is None:
            continue
        audience = bool(_AUDIENCE.search(clause))
        for t in topics or []:
            if not _mentions(clause, t):
                continue
            if audience:
                # The side the comments are said to take must be the side
                # their counts favour, not merely one they include (24 Sep 2026).
                counts = (t.get("audience") or {}).get("counts") or {}
                pos, neg = counts.get("POSITIVE", 0) or 0, counts.get("NEGATIVE", 0) or 0
                have = pos > neg if polarity == "pos" else neg > pos
                who = "the comments"
            else:
                st = (t.get("reviewer") or {}).get("stances") or {}
                have = st.get("praise" if polarity == "pos" else "criticism", 0) + st.get("mixed", 0)
                who = "the reviewer"
            if not have:
                way = "positive about" if polarity == "pos" else "negative about"
                problems.append(f"says {who} were {way} {t.get('name')}, which the run does not show")
    return problems


# ── the shape of two short fields ────────────────────────────────────────────

_CHANNEL_WORDS = {
    "words": r"\b(?:words?|transcript|said|says|saying|speech)\b",
    "face": r"\b(?:face|facial|expression)\b",
    "voice": r"\b(?:voice|vocal|tone of voice|sounds?)\b",
    "comments": r"\b(?:comments?|audience|viewers?|commenters?)\b",
}


def channels_named(text: object) -> int:
    """How many of the four readings a moment note names. It must name two to explain a mismatch."""
    t = str(text or "")
    return sum(1 for pattern in _CHANNEL_WORDS.values() if re.search(pattern, t, re.I))


# What a moment note says each reading was, checked against what it was. Stricter
# than _CHANNEL_WORDS: "said" and "sounds" name a channel well enough to count it,
# but in a claim they are as often about the subject ("as he said the price is
# high"), and a false match here drops a true note.
_CLAIM_CHANNELS = {
    "transcript": ("words", r"\b(?:words?|transcript)\b"),
    "facial": ("face", r"\b(?:face|facial|expression)\b"),
    "vocal": ("voice", r"\b(?:voice|vocal)\b"),
    "comment": ("comments", r"\b(?:comments?|audience|viewers?|commenters?)\b"),
}
_VALENCE_WORD = re.compile(r"\b(positive|negative|neutral)\b", re.I)
_CLAUSE_BREAK = re.compile(r"[,;:.]|\b(?:but|while|whereas|yet|although|though)\b", re.I)
# One item of a list of readings, cut off by the comma that separates it from
# the next: "The words", "face", "and comments all read positive".
_BARE_CHANNEL = re.compile(
    r"\s*(?:and\s+)?(?:the\s+)?(?:words?|transcript|face|facial|expression|voice|vocal"
    r"|comments?|audience|viewers?|commenters?)\s*", re.I)


def _clauses(text: str) -> list[str]:
    """The note's clauses, with a list of channel names kept on the clause that ends it."""
    out, carry = [], ""
    for piece in _CLAUSE_BREAK.split(text):
        if _BARE_CHANNEL.fullmatch(piece):
            carry += " " + piece
            continue
        out.append(carry + " " + piece)
        carry = ""
    return out


def _claims(clause: str) -> dict[str, str]:
    """{channel: VALENCE} for one clause: every channel it names takes its one valence word."""
    words = {w.upper() for w in _VALENCE_WORD.findall(clause)}
    if not words:
        return {}
    if len(words) > 1:
        # "the words read positive and the face reads negative": two claims
        # joined by "and". A part still holding two valence words is not judged.
        out: dict[str, str] = {}
        for part in re.split(r"\band\b", clause, flags=re.I):
            if len({w.upper() for w in _VALENCE_WORD.findall(part)}) == 1:
                out.update(_claims(part))
        return out
    (valence,) = words
    return {ch: valence for ch, (_, pattern) in _CLAIM_CHANNELS.items() if re.search(pattern, clause, re.I)}


def moment_claim_problems(text: object, valences: dict | None) -> list[str]:
    """
    A moment note that says a reading was something it was not.

    Added 24 Sep 2026 after the final user evaluation: on the Apple Duo book the
    0:40 note said the voice read positive where the card beside it showed
    neutral, and four of the five S27 member notes gave the face a reading at a
    moment where no face was read. A note is split into clauses at punctuation
    and at "but / while / whereas / yet / although / though" (a comma inside a
    list of readings does not end one); a clause with one valence word gives it
    to every channel the clause names. Only a definite contradiction is a
    problem: a clause with no valence word, or one that stays ambiguous, is
    left alone rather than guessed at.
    """
    labels = {k: (str(v).upper() if v else None) for k, v in (valences or {}).items()}
    problems: list[str] = []
    for clause in _clauses(str(text or "")):
        for channel, claimed in _claims(clause).items():
            name = _CLAIM_CHANNELS[channel][0]
            actual = labels.get(channel)
            if actual is None:
                problems.append(f"says the {name} read {claimed.lower()}; the {name} was not read at this moment")
            elif actual != claimed:
                problems.append(f"says the {name} read {claimed.lower()}; it read {actual.lower()}")
    return sorted(set(problems))


def is_generic_turn(label: object) -> bool:
    """A turn label that names the turn ("the tone peaks") instead of what was being said."""
    return bool(re.search(r"\b(?:tone|peaks?|dips?|turn\w*|warmest|coolest)\b", str(label or ""), re.I))


# ── the drop log ─────────────────────────────────────────────────────────────

@dataclass
class Log:
    """Every item proposed, kept or dropped, with why, counted per field."""
    proposed: int = 0
    kept: int = 0
    dropped: list = field(default_factory=list)
    by_field: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def _count(self, field_name: str, outcome: str) -> None:
        row = self.by_field.setdefault(field_name, {"kept": 0, "dropped": 0})
        row[outcome] += 1

    def keep(self, field_name: str = "item") -> None:
        self.proposed += 1
        self.kept += 1
        self._count(field_name, "kept")

    def note(self, field_name: str, what: str, before, after) -> None:
        """A correction that kept an item: recorded, never silent."""
        self.notes.append({"field": field_name, "what": what, "from": before, "to": after})

    def drop(self, field_name: str, reasons, text) -> None:
        self.proposed += 1
        self._count(field_name, "dropped")
        self.dropped.append({"field": field_name,
                             "reasons": list(reasons) if isinstance(reasons, (list, tuple)) else [str(reasons)],
                             "text": str(text)[:300]})

    def as_dict(self) -> dict:
        return {"proposed": self.proposed, "kept": self.kept, "by_field": self.by_field,
                "dropped": self.dropped, "notes": self.notes}


# ── the combined report: several videos at once ─────────────────────────────
#
# The same checks, with evidence scoped to a video: V2 is video 2, V2:S14 its
# segment 14, V2:C5 its comment 5, H3 a theme the set shares. A quote cited to
# V2:S14 may run into segment 15, because a claim may (quote_home).

@dataclass
class SetContext:
    """What a sentence about several videos may lean on."""
    allowed_numbers: set[float] = field(default_factory=set)
    allowed_times: set[str] = field(default_factory=set)
    videos: dict = field(default_factory=dict)      # n -> {"text", "segments": {id: text}, "next": {id: id}, "comments": {i: text}}
    themes: dict = field(default_factory=dict)      # k -> the theme's name, quotes and comments as one text
    names: str = ""
    allowed_pct: set | None = None


_SET_EVIDENCE = re.compile(r"^(?:V(\d{1,2})(?::([SC])(\d{1,5}))?|H(\d{1,2}))$")


def check_set_evidence(ids, ctx: SetContext) -> tuple[list[str], list[str]]:
    """V2 for the combined report. Returns (valid ids, problems)."""
    valid, problems = [], []
    for raw in ids or []:
        m = _SET_EVIDENCE.match(str(raw).strip())
        if not m:
            problems.append(f"evidence id not understood: {raw!r}")
            continue
        v, kind, num, h = m.groups()
        if h is not None:
            ok = int(h) in ctx.themes
        else:
            video = ctx.videos.get(int(v))
            ok = video is not None and (
                kind is None
                or (kind == "S" and int(num) in video.get("segments", {}))
                or (kind == "C" and int(num) in video.get("comments", {})))
        if ok:
            valid.append(str(raw).strip())
        else:
            problems.append(f"cites {raw} which does not exist")
    return valid, problems


def _set_evidence_text(ids: list[str], ctx: SetContext) -> str:
    parts = []
    for raw in ids:
        v, kind, num, h = _SET_EVIDENCE.match(raw).groups()
        if h is not None:
            parts.append(ctx.themes.get(int(h), ""))
            continue
        video = ctx.videos.get(int(v)) or {}
        if kind is None:
            parts.append(video.get("text", ""))
        elif kind == "S":
            sid = int(num)
            parts.append(video["segments"].get(sid, ""))
            after = (video.get("next") or {}).get(sid)
            if after is not None:
                parts.append(video["segments"].get(after, ""))
        else:
            parts.append(video["comments"].get(int(num), ""))
    return " ".join(parts)


def check_set_prose(text: object, evidence, ctx: SetContext, *, max_words: int,
                    require_evidence: bool = True) -> tuple[bool, list[str], list[str]]:
    """V1-V5 for one sentence about the set. Returns (ok, problems, valid ids)."""
    if not isinstance(text, str) or not text.strip():
        return False, ["empty"], []
    text = text.strip()
    ids, problems = check_set_evidence(evidence, ctx)
    if require_evidence and not ids:
        problems.append("cites no evidence")
    problems.extend(_check_body(text, _set_evidence_text(ids, ctx), ctx.allowed_numbers,
                                ctx.allowed_times, ctx.names, max_words, ctx.allowed_pct))
    return (not problems), problems, ids


_VIDEO_NUMBERS = re.compile(r"\bvideos?\s+((?:\d{1,2})(?:\s*(?:,|and|&)\s*\d{1,2})*)", re.I)
_UNIVERSAL = re.compile(r"\b(?:all|every|each|both)\b", re.I)


def _videos_named(clause: str) -> list[int]:
    out = []
    for m in _VIDEO_NUMBERS.finditer(clause):
        out.extend(int(x) for x in re.findall(r"\d{1,2}", m.group(1)))
    return out


def set_stance_problems(text: object, themes: list[dict], videos_analysed: int) -> list[str]:
    """
    Clauses that say reviewers or audiences praised or criticised a theme the
    set's own matrix does not show, clause by clause, as stance_problems does
    for one video. A clause that names videos ("video 2") is held to those
    videos' cells; one that says "all", "every", "each" or "both" is held to a
    row every video took the same side on.
    """
    problems = []
    for clause in _CLAUSE.split(str(text or "")):
        if not clause.strip():
            continue
        polarity = _polarity(clause)
        if polarity is None:
            continue
        audience = bool(_AUDIENCE.search(clause))
        named = _videos_named(clause)
        universal = bool(_UNIVERSAL.search(clause))
        for t in themes or []:
            if not _mentions(clause, t):
                continue
            cells = {c["n"]: c for c in t.get("cells") or [] if c.get("status") != "not_written"}
            who = "audiences" if audience else "reviewers"
            way = "positive about" if polarity == "pos" else "negative about"

            def favoured(counts):
                pos, neg = (counts or {}).get("POSITIVE", 0) or 0, (counts or {}).get("NEGATIVE", 0) or 0
                return pos > neg if polarity == "pos" else neg > pos

            def fits(c):
                if audience:
                    return favoured((c.get("audience") or {}).get("counts"))
                return c.get("stance") in (("praise", "mixed") if polarity == "pos" else ("criticism", "mixed"))

            for n in named:
                if n in cells and not fits(cells[n]):
                    problems.append(f"says video {n}'s {who[:-1]} was {way} {t['name']}, which its cell does not show")
            if not named:
                # Audiences as a whole on a theme: the pooled counts must favour
                # that side. Reviewers: at least one video must take it.
                ok = favoured((t.get("audience") or {}).get("counts")) if audience \
                    else any(fits(c) for c in cells.values())
                if not ok:
                    problems.append(f"says {who} were {way} {t['name']}, which the matrix does not show")
            if universal:
                row = t.get("audience" if audience else "reviewer") or {}
                side = ("positive" if polarity == "pos" else "negative") if audience else \
                       ("praise" if polarity == "pos" else "criticism")
                if not (row.get("label") == "agreed" and row.get("side") == side
                        and row.get("talked") == videos_analysed):
                    problems.append(f"says every video's {who[:-1]} was {way} {t['name']}, which the matrix does not show")
    return problems


_REVIEWER_WORDS = re.compile(r"\b(?:reviewer\w*|words|said|says|creator\w*|host)\b", re.I)
_AUDIENCE_WORDS = re.compile(r"\b(?:audience\w*|comments?|commenters?|viewers?)\b", re.I)


def names_dimension(text: object, dimension: str) -> bool:
    """Whether a sentence about the odd one out names the lean it stands apart on."""
    pattern = _REVIEWER_WORDS if dimension == "reviewer" else _AUDIENCE_WORDS
    return bool(pattern.search(str(text or "")))


# ── the audience as a whole ─────────────────────────────────────────────────
#
# The first S27 run wrote "The audience is generally positive, with 35%
# positive comments" over 35 positive and 38 negative comments, a lean of
# -0.03 called balanced. stance_problems holds a clause to a TOPIC's counts;
# a clause about the comments as a whole names no topic and went unchecked.
# It is now held to the computed call: saying the comments lean one way needs
# the audience lean's 95% interval to exclude zero on that side.

def audience_direction_problems(text: object, call: str, topics: list[dict] | None = None) -> list[str]:
    """Clauses that say the comments as a whole lean a way the computed call does not."""
    problems = []
    for clause in _CLAUSE.split(str(text or "")):
        if not clause.strip() or not _AUDIENCE.search(clause):
            continue
        if any(_mentions(clause, t) for t in topics or []):
            continue                    # about a topic: stance_problems holds it to that topic
        polarity = _polarity(clause)
        if polarity is None:
            continue
        want = "positive" if polarity == "pos" else "negative"
        if call != want:
            problems.append(f"says the comments lean {want}; the computed call is {call}")
    return problems


# Evidence ids belong in the evidence list, not in the sentence a reader sees.
# Only the citation shapes are refused -- "(H2)", "(V1, V3)", "V2:S14" -- never
# a bare H2 or S27, which are also the names of chips and phones.
_ID_IN_TEXT = re.compile(r"\((?:\s*(?:[VH]\d{1,2}(?::[SC]\d{1,5})?|[SCT]\d{1,5})\s*,?)+\)|\bV\d{1,2}:[SC]\d{1,5}\b")


_BARE_VIDEO_ID = re.compile(r"\bV\d{1,2}\b")


def ids_in_text(text: object, names: str = "") -> list[str]:
    """
    Evidence ids written into the sentence a reader sees. A bare "V3" is one
    too ("Videos V1, V3 and V4 praise it", S27, 24 Sep 2026) unless the same
    token is part of a real name in the titles or the subject.
    """
    t = str(text or "")
    m = _ID_IN_TEXT.search(t)
    if m:
        return [f"writes an evidence id into the sentence: {m.group(0)!r}"]
    for b in _BARE_VIDEO_ID.finditer(t):
        if not re.search(r"\b" + re.escape(b.group(0)) + r"\b", names or ""):
            return [f"writes an evidence id into the sentence: {b.group(0)!r}"]
    return []


def themes_named(text: object, themes: list[dict]) -> list[dict]:
    """The themes a sentence names, by name or aspect (never "Other" or one about the reviewer)."""
    return [t for t in themes or [] if _mentions(str(text or ""), t)]


# ── counts of videos on a theme ─────────────────────────────────────────────
#
# "with 4 videos praising the design and 2 criticising it" over a matrix row of
# 3 and 2 passed the figure check, because 4 was a number elsewhere in the
# sheet. A count stated for a theme is now held to that theme's own count.

_N = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
_SIDE = r"(prais\w*|critici[sz]\w*|lik(?:e|es|ed|ing)|lov(?:e|es|ed|ing)|complain\w*|fault\w*)"
_COUNT_THEN_VERB = re.compile(_N + r"\s+(?:out\s+)?(?:of\s+" + _N + r"\s+)?(?:the\s+)?(?:videos?|reviewers?|reviews?)"
                              r"\s+(?:\w+\s+){0,2}?" + _SIDE, re.I)
_VERB_THEN_COUNT = re.compile(_SIDE + r"\s+(?:in|by)\s+" + _N + r"(?:\s+(?:out\s+)?of\s+" + _N + r")?", re.I)
_WORDS_N = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10}


def _count(tok: str | None) -> int | None:
    if tok is None:
        return None
    return int(tok) if tok.isdigit() else _WORDS_N.get(tok.lower())


def theme_count_problems(text: object, themes: list[dict]) -> list[str]:
    """Counts of videos praising or criticising a theme, held to the matrix row."""
    problems = []
    for sentence in re.split(r"[.;!?]", str(text or "")):
        named = [t for t in themes or [] if _mentions(sentence, t)]
        if len(named) != 1:
            continue                      # no theme, or several: which count is meant is not decidable
        row = named[0].get("reviewer") or {}
        found = [(m.group(3), m.group(1), m.group(2)) for m in _COUNT_THEN_VERB.finditer(sentence)]
        found += [(m.group(1), m.group(2), m.group(3)) for m in _VERB_THEN_COUNT.finditer(sentence)]
        for verb, k, of in found:
            side = "criticism_in" if re.match(r"(critici|complain|fault)", verb, re.I) else "praise_in"
            want, total = row.get(side), row.get("talked")
            if _count(k) is not None and want is not None and _count(k) != want:
                problems.append(f"says {k} videos {verb} {named[0].get('name')}; the matrix shows {want}")
            if _count(of) is not None and total is not None and _count(of) != total:
                problems.append(f"says {k} of {of} for {named[0].get('name')}; {total} videos discuss it")
    return problems


# ── silence, and counts of comments ─────────────────────────────────────────
#
# Two sentences from the third S27 run passed every check and were wrong:
# "Video 5 does not mention the performance" over a cell where video 5 had a
# mixed view, and "the audience is negative about the design, with 2 negative
# comments" where 2 was the number of AUDIENCES leaning negative and the design
# drew 97 negative comments.

_SILENT = re.compile(r"\b(?:do(?:es)?\s*n[o']?t|did\s*n[o']?t|never)\s+(?:mention|discuss|talk\s+about|cover|address)\w*"
                     r"|\bsilent\s+(?:on|about)\b|\bleaves?\s+out\b", re.I)
_COMMENTS_N = re.compile(_N + r"\s+(positive|negative|neutral)\s+comments?", re.I)


def silence_problems(text: object, themes: list[dict]) -> list[str]:
    """A named video said not to discuss a theme must have a silent cell for it."""
    problems = []
    for sentence in re.split(r"[.;!?]", str(text or "")):
        if not _SILENT.search(sentence):
            continue
        named = [t for t in themes or [] if _mentions(sentence, t)]
        if len(named) != 1:
            continue
        cells = {c["n"]: c for c in named[0].get("cells") or []}
        for n in _videos_named(sentence):
            c = cells.get(n)
            if c is not None and c.get("status") != "not_written" and c.get("stance") != "silent":
                problems.append(f"says video {n} does not discuss {named[0].get('name')}; it does "
                                f"({c.get('stance')})")
    return problems


def comment_count_problems(text: object, topics: list[dict], overall: dict | None) -> list[str]:
    """
    "N negative comments" must be a real count: the named topic's own when the
    sentence names one topic, the whole audience's when it names none.
    """
    problems = []
    for sentence in re.split(r"[.;!?]", str(text or "")):
        found = list(_COMMENTS_N.finditer(sentence))
        if not found:
            continue
        named = [t for t in topics or [] if _mentions(sentence, t)]
        if len(named) > 1:
            continue                      # several topics: which count is meant is not decidable
        counts = ((named[0].get("audience") or {}).get("counts") if named else overall) or {}
        where = named[0].get("name") if named else "the comments as a whole"
        for m in found:
            k, label = _count(m.group(1)), m.group(2).upper()
            if k is not None and counts.get(label) is not None and k != counts[label]:
                problems.append(f"says {m.group(1)} {m.group(2).lower()} comments on {where}; "
                                f"there are {counts[label]}")
    return problems



# ── what a theme is called, and "the only one" ──────────────────────────────

_SAYS_SPLIT = re.compile(r"\b(?:split|divided|contested|point\s+of\s+contention)\b", re.I)
_SAYS_AGREED = re.compile(r"\b(?:agreed|consensus|reviewers\s+agree|agree\s+on)\b", re.I)
_ONLY = re.compile(r"\b(?:the\s+only|only\s+one|only\s+video|only\s+reviewer|alone\s+in)\b", re.I)


def label_word_problems(text: object, themes: list[dict]) -> list[str]:
    """Calling a theme split or agreed must match its row's label."""
    problems = []
    for sentence in re.split(r"[.;!?]", str(text or "")):
        named = [t for t in themes or [] if _mentions(sentence, t)]
        if len(named) != 1:
            continue
        label = (named[0].get("reviewer") or {}).get("label")
        if _SAYS_SPLIT.search(sentence) and label != "split":
            problems.append(f"calls {named[0].get('name')} split; its label is {label}")
        elif _SAYS_AGREED.search(sentence) and label not in ("agreed", "mostly"):
            problems.append(f"calls {named[0].get('name')} agreed; its label is {label}")
    return problems


def only_problems(text: object, themes: list[dict]) -> list[str]:
    """'The only one to praise X' must be true: exactly one video takes that side."""
    problems = []
    for sentence in re.split(r"[.;!?]", str(text or "")):
        if not _ONLY.search(sentence):
            continue
        named = [t for t in themes or [] if _mentions(sentence, t)]
        polarity = _polarity(sentence)
        if len(named) != 1 or polarity is None:
            continue
        row = named[0].get("reviewer") or {}
        k = row.get("praise_in" if polarity == "pos" else "criticism_in")
        if k != 1:
            problems.append(f"says only one video {'praises' if polarity == 'pos' else 'criticises'} "
                            f"{named[0].get('name')}; the matrix shows {k}")
    return problems


# ── a takeaway's specifics must come from its theme ─────────────────────────
#
# "Consider revising the camera bump ... as it has been criticized in two
# videos" passed every check on the S27 set: the count was the design theme's,
# and the camera bump appears in none of that theme's claims, quotes or
# comments. Advice may use general words freely; every other word must be
# found in the evidence of the theme it is about. Matched on a four-letter
# stem, so "pricing" finds "price" and "improved" finds "improvements".

ADVICE_WORDS = frozenset("""
    about above across after again against also although always among another answer answers anyone
    appeal appealing appeals apply around aside away based because become been before behind being
    below better between beyond both brand brands build campaign campaigns care careful case cases
    change changes clear clearer clearly close closely comment commented comments common concern
    concerned concerns consider considering continue continued could current customer customers
    decide demand detail details develop direct directly doing does done doubt doubts down during
    each earlier early either else emphasis emphasise emphasize emphasizing ensure even ever every
    expect expectation expectations explain explaining fact features feedback find first focus
    focusing follow from full fully further future gain give given going good great have having
    help helps here highlight highlighting highlights however idea ideas important improve
    improved improvement improving include including inform instead issue issues itself keep
    keeping know lead leading lean leaning leans less lessen like likely listen look looking lower
    made main make makes making many market marketing matter matters maybe mean means measure
    mention mentioned message messages messaging might mind more most much must need needs negative
    never next note noted offer offering often once only open other others over part people plan
    plans point points positive potential praise praised praises praising present prioritise
    prioritize priority problem problems product products promote promoting provide proving public
    question questions raise raised rather reason reasons reassure reduce reflect regard regarding
    related remain remains reply respond response review reviewer reviewers reviews revise revising
    right risk same says seen sell selling sentiment series should show showing shows side since
    some something speak specific stand stands start stay still stress strong strongly such suggest
    support sure take taking talk talking tell than that their them theme themes then there these
    they thing things this those though through time together towards trust under understand until
    upon users using value very video videos view viewer viewers views want watch watching well were
    what when where whether which while whole will with within without word words work working
    would write yours criticise criticised criticises criticising criticism criticize criticized
    criticizes criticizing critical audience audiences balanced split agreed agree address addressing
    quote quoted quotes meet meets expand expanding justify level levels
""".split())


def _stem(word: str) -> str:
    return word[:4]


# General words match on their stem too, so "user" is as general as "users".
# Words that say someone asked for something ("requested by reviewers") are
# NOT general: they are claims about the videos, and must be in the evidence
# (S27 month, 24 Sep 2026: "as requested by reviewers" over a video praising
# MagSafe).
_ADVICE_STEMS = frozenset(_stem(w) for w in ADVICE_WORDS)


def ungrounded_words(text: object, source: str, names: str = "") -> list[str]:
    """Words of four letters or more that are neither general advice nor in the source."""
    known = {_stem(w) for w in words(source) + words(names)}
    # A quoted span is already held word for word to its evidence (V1).
    bare = _QUOTED.sub(" ", str(text or "").translate(_QUOTES))
    out = []
    for w in words(bare):
        if len(w) < 4 or w.isdigit() or w in ADVICE_WORDS or _stem(w) in _ADVICE_STEMS or _stem(w) in known:
            continue
        if w not in out:
            out.append(w)
    return out


# A takeaway is advice; the figures behind it are printed beside it by code.
# One that argues from counts or names videos was measured conflating two
# themes' counts ("the camera bump ... criticized in two videos": two was the
# design's), so a takeaway may not carry them at all (24 Sep 2026).
_ADVICE_COUNTS = re.compile(r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|both|all)\s+"
                            r"(?:of\s+the\s+)?(?:videos?|reviewers?|reviews?|audiences?)\b"
                            r"|\bvideos?\s+\d+|\bin\s+(?:one|two|three|four|five|\d+)\s+(?:of\s+\w+\s+)?videos?\b", re.I)


def advice_problems(text: object) -> list[str]:
    m = _ADVICE_COUNTS.search(str(text or ""))
    return [f"argues from a count or names a video: {m.group(0)!r}; the figures are printed beside it"] if m else []
