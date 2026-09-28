/* ===========================================================================
   contract.js — what a channel reading means, and the constants this
   interface is allowed to print.

   This file mirrors pipeline/orchestrator.py. It does not get to have its own
   opinion: if the two disagree, the interface is describing a comparison the
   system did not make. tests/test_ui_contracts.py parses `_VALENCE_WORDS` and
   `CONFLICT_FLAG_THRESHOLD` out of orchestrator.py and fails if this file has
   drifted from them.

   Carried forward across two interface rebuilds (11 Sep 2026, and the one after it).
   It is the promise layer, not the visual one, and it has been correct each
   time. The visual layer has been replaced wholesale; this has not.
   ======================================================================== */

/**
 * The valence lexicon, copied from pipeline/orchestrator.py `_VALENCE_WORDS`.
 *
 * Note what is NOT here: "surprise". The orchestrator excludes it on purpose,
 * because surprise is not inherently positive or negative. A segment whose face
 * pooled to "surprise" therefore has no facial valence and the pen lifts off
 * the paper, exactly as it does for a segment with no face at all. How many
 * saved segments are in that state is corpus.surprise_segments in
 * ui_evidence/figures.json.
 */
export const VALENCE_WORDS = Object.freeze({
  positive: "POSITIVE", happy: "POSITIVE",
  neutral: "NEUTRAL",
  negative: "NEGATIVE", sad: "NEGATIVE", angry: "NEGATIVE",
  fear: "NEGATIVE", disgust: "NEGATIVE",
});

/** conflict_score at or above which the orchestrator flags a segment. */
export const CONFLICT_FLAG_THRESHOLD = 0.75;

/**
 * Coverage below which this interface tells the reader a channel is thin on a
 * given report. An editorial threshold for when to warn, not a measured
 * quantity. Duplicated as CHANNEL_COVERAGE_FLOOR in
 * ui_evidence/extract_figures.py; a test asserts the two agree.
 */
export const CHANNEL_COVERAGE_FLOOR = 0.5;

/**
 * When the top two comment classes are within this share of each other, the
 * interface says so rather than reporting the plurality label as if it settled
 * the matter. PROTOTYPE_FINDINGS.md §3 is exactly this problem: on one saved
 * report the split is 36 positive / 35 neutral and the aggregate reads POSITIVE.
 */
export const AGGREGATE_TIE_MARGIN = 0.05;

/** Map any channel label onto a valence, or null for "no usable reading". */
export function toValence(raw) {
  if (typeof raw !== "string") return null;
  return VALENCE_WORDS[raw.trim().toLowerCase()] || null;
}

/**
 * Read a vocal reading through both shapes that exist on disk.
 *
 * Reports written before the 02 Sep 2026 vocal-model swap store a bare
 * emotion word ("angry"); later ones store {label, arousal, valence,
 * dominance, reliability}. Every report shipped is the later shape,
 * but an older report copied in, and tests/fixtures/legacy_report_june.json,
 * are the first. Coding against either shape alone breaks the other.
 */
export function vocalLabel(vocal) {
  if (typeof vocal === "string") return vocal;
  if (vocal && typeof vocal === "object" && typeof vocal.label === "string") return vocal.label;
  return null;
}

/** The extra dimensional readings, present only on the newer report shape. */
export function vocalDimensions(vocal) {
  if (!vocal || typeof vocal !== "object") return null;
  const out = {};
  let any = false;
  for (const key of ["arousal", "valence", "dominance", "reliability"]) {
    if (typeof vocal[key] === "number") { out[key] = vocal[key]; any = true; }
  }
  return any ? out : null;
}

/** The four channels, in the order they are drawn and listed, everywhere. */
export const CHANNELS = Object.freeze(["transcript", "facial", "vocal", "audience"]);

/**
 * Per-channel identity, mark shape, and measured accuracy.
 *
 * Every accuracy here was measured on this project's own hand-labelled data, on
 * held-out speakers or unseen videos in each case, and every figure is
 * re-derived and re-verified against its source file by
 * ui_evidence/extract_figures.py. A test asserts this table agrees with
 * ui_evidence/figures.json, so a number cannot be edited here without the
 * evidence moving with it.
 *
 * `mark` is the shape drawn for the channel. It is redundant with colour on
 * purpose: no reading on this interface is carried by hue alone.
 */
export const CHANNEL_META = Object.freeze({
  transcript: {
    label: "Transcript sentiment",
    short: "Transcript",
    reads: "the words said",
    model: "cardiffnlp XLM-RoBERTa",
    mark: "square",
    accuracy: 67.8,
    sample: "199 segments, 4 unseen speakers",
    source: "transcript_bench/WINNER.md",
    perSegment: true,
  },
  facial: {
    label: "Facial emotion",
    short: "Facial",
    reads: "the face on camera",
    model: "DeepFace FER-2013 head, yunet detector",
    mark: "circle",
    accuracy: 34.2,
    sample: "39 of 114 frames, held-out speakers",
    source: "facial_bench/v2/FACIAL_MODEL_ANALYSIS_V2.md",
    perSegment: true,
    // The bench's finding, carried here so the interface cannot quote 34.2%
    // without also quoting what it is worse than.
    worseThanConstant: "below an always-NEUTRAL constant, which scores 67.5%",
  },
  vocal: {
    label: "Vocal prosody",
    short: "Vocal",
    reads: "how it was said",
    model: "audeering wav2vec2, read on arousal",
    mark: "triangle",
    accuracy: 48.9,
    sample: "23 of 47 clips, held-out speakers",
    source: "vocal_bench/VOCAL_MODEL_ANALYSIS.md",
    perSegment: true,
  },
  audience: {
    label: "Audience comments",
    short: "Audience",
    reads: "what viewers wrote",
    model: "cardiffnlp RoBERTa, fine-tuned here",
    mark: "diamond",
    accuracy: 78.7,
    sample: "118 of 150 comments, unseen videos",
    source: "comment_bench/v2/holdout/HOLDOUT_RESULT.md",
    // Comments are posted hours or days after the video and cannot be aligned
    // to a moment in it. One reading covers the whole video, by design — which
    // is why this pen is drawn flat and dashed across the entire time axis.
    perSegment: false,
  },
});

/** The two reference points the facial accuracy is only meaningful against. */
export const FACIAL_REFERENCES = Object.freeze({
  constant: { label: "always-NEUTRAL constant", value: 67.5, n: 114 },
  ceiling: { label: "human ceiling", value: 87.5, n: 48, kappa: 0.804 },
});

/**
 * Every channel valence for one segment, plus the video-level audience reading.
 * Channels with no usable reading are OMITTED rather than defaulted, so a caller
 * can tell three agreeing channels from one channel and two silences.
 */
export function segmentValences(segment, commentSentiment) {
  const out = {};
  const mo = (segment && segment.model_outputs) || {};

  const transcript = toValence((mo.transcript_sentiment || {}).label);
  if (transcript) out.transcript = transcript;

  const facial = toValence((mo.facial_emotion || {}).dominant);
  if (facial) out.facial = facial;

  const vocal = toValence(vocalLabel(mo.vocal_emotion));
  if (vocal) out.vocal = vocal;

  const audience = toValence((commentSentiment || {}).label);
  if (audience) out.audience = audience;

  return out;
}

/** The raw label a channel reported, before it is mapped onto a valence. */
export function rawReading(segment, channel, commentSentiment) {
  const mo = (segment && segment.model_outputs) || {};
  if (channel === "transcript") return (mo.transcript_sentiment || {}).label ?? null;
  if (channel === "facial") return (mo.facial_emotion || {}).dominant ?? null;
  if (channel === "vocal") return vocalLabel(mo.vocal_emotion);
  if (channel === "audience") return (commentSentiment || {}).label ?? null;
  return null;
}

/** The confidence a channel reported, or null where it reported none. */
export function readingConfidence(segment, channel, commentSentiment) {
  const mo = (segment && segment.model_outputs) || {};
  const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
  if (channel === "transcript") return num((mo.transcript_sentiment || {}).confidence);
  if (channel === "facial") return num((mo.facial_emotion || {}).confidence);
  if (channel === "vocal") {
    const dims = vocalDimensions(mo.vocal_emotion);
    return dims && typeof dims.arousal === "number" ? dims.arousal : null;
  }
  if (channel === "audience") return num((commentSentiment || {}).confidence);
  return null;
}

/**
 * How many frames a facial reading was pooled from, or null.
 *
 * Surfaced because it is the difference between "the face read negative across
 * this whole window" and "one frame out of seven said so". On the Samsung
 * report's highest-conflict segment it is 1.
 */
export function facialFrameCount(segment) {
  const fe = ((segment && segment.model_outputs) || {}).facial_emotion || {};
  return typeof fe.frame_count === "number" ? fe.frame_count : null;
}

/**
 * Per-channel coverage across a report: how many segments carry a usable
 * reading, and whether that is below the disclosure floor.
 */
export function coverage(segments, commentSentiment) {
  const out = {};
  for (const channel of CHANNELS) {
    const meta = CHANNEL_META[channel];
    if (!meta.perSegment) {
      const has = toValence((commentSentiment || {}).label) ? segments.length : 0;
      out[channel] = { read: has, total: segments.length, share: segments.length ? has / segments.length : 0, thin: !has };
      continue;
    }
    let read = 0;
    for (const segment of segments) {
      if (segmentValences(segment, commentSentiment)[channel]) read += 1;
    }
    const share = segments.length ? read / segments.length : 0;
    out[channel] = { read, total: segments.length, share, thin: share < CHANNEL_COVERAGE_FLOOR };
  }
  return out;
}

/**
 * Whether a comment distribution is close enough that reporting the plurality
 * as a verdict would overstate it.
 */
export function aggregateIsNearTie(distribution) {
  const counts = Object.values(distribution || {});
  const total = counts.reduce((a, b) => a + b, 0);
  if (!total || counts.length < 2) return null;
  const sorted = Object.entries(distribution).sort((a, b) => b[1] - a[1]);
  const margin = (sorted[0][1] - sorted[1][1]) / total;
  return {
    nearTie: margin <= AGGREGATE_TIE_MARGIN,
    margin,
    top: sorted[0],
    second: sorted[1],
    total,
  };
}

/* ---------------------------------------------------------------------------
   Reading the orchestrator's own audit trail.

   `_coerce_result` writes two kinds of line into every segment's
   `conflict_reasons`, and until now nothing has read either of them. They are
   the only record the system keeps of WHY a segment scored what it did.
   ------------------------------------------------------------------------ */

/**
 * The channel names the controller actually emits, mapped onto our four.
 *
 * The prompt (orchestrator.py:364-367) names the channels `transcript_sentiment`,
 * `facial_emotion`, `vocal_prosody` and `comment_sentiment`, but the payload it
 * is shown uses `video_comment_sentiment` (orchestrator.py:631), and a local LLM
 * echoes whichever it prefers. Counted across the whole corpus, six distinct
 * names appear for four channels: transcript_sentiment 3566, facial_emotion
 * 3057, video_comment_sentiment 1464, vocal_emotion 599, vocal_prosody 444,
 * comment_sentiment 11.
 *
 * Matching on a substring rather than an exact name is therefore the honest
 * reading. An unrecognised name returns null and is counted as unattributable
 * rather than silently dropped into a bucket.
 */
export function channelFromReason(name) {
  const key = String(name || "").trim().toLowerCase();
  if (!key) return null;
  if (key.includes("transcript")) return "transcript";
  if (key.includes("facial")) return "facial";
  if (key.includes("vocal")) return "vocal";
  if (key.includes("comment") || key.includes("audience")) return "audience";
  return null;
}

/**
 * The channels the controller named as being in conflict on one segment.
 *
 * Returned as a Set of our four channel keys, so the two vocal aliases collapse
 * to one channel rather than counting twice.
 */
export function conflictChannels(segment) {
  const out = new Set();
  const unknown = [];
  for (const reason of (segment && segment.conflict_reasons) || []) {
    if (typeof reason !== "string") continue;
    if (!reason.startsWith("channels_in_conflict: ")) continue;
    const raw = reason.slice("channels_in_conflict: ".length);
    const channel = channelFromReason(raw);
    if (channel) out.add(channel);
    else unknown.push(raw);
  }
  return { channels: out, unknown };
}

/**
 * The down-weighting the orchestrator applied to this segment, or null.
 *
 * The line it writes carries both numbers:
 *
 *   facial_channel_downweighted[structural]: 0.6000 -> 0.2052 (x0.342, ...)
 *
 * so the value before the weighting is READ, never reconstructed. That matters:
 * dividing the damped score back out would land on the same number here, but it
 * would be an inference presented as a measurement, and this project does not
 * do that.
 *
 * `trigger` is which of the two paths fired. Across the corpus it is
 * `structural` on all 489 damped segments and `attributed` on none, which is the
 * finding vocal_bench/DAMPING_FIX_RESULT.md predicted: the controller's own
 * attribution never fires, and the deterministic channel-label check is what
 * actually does the work.
 */
export function damping(segment) {
  for (const reason of (segment && segment.conflict_reasons) || []) {
    if (typeof reason !== "string") continue;
    const match = reason.match(
      /^(\w+)_channel_downweighted\[([^\]]+)\]:\s*([0-9.]+)\s*->\s*([0-9.]+)\s*\(x([0-9.]+)/);
    if (!match) continue;
    const before = Number(match[3]);
    const after = Number(match[4]);
    const weight = Number(match[5]);
    if (!Number.isFinite(before) || !Number.isFinite(after) || !Number.isFinite(weight)) {
      continue;
    }
    return {
      channel: channelFromReason(match[1]),
      trigger: match[2],
      before,
      after,
      weight,
    };
  }
  return null;
}

/**
 * How often each pair of channels was named in conflict together.
 *
 * This is the project's own thesis counted for the first time. The claim the
 * system rests on is that disagreement BETWEEN channels is the signal; this says
 * which channels actually do the disagreeing, over every segment in a report.
 *
 * Returns the six unordered pairs in a fixed order, each with its count and the
 * share of segments it appeared on, plus the per-channel totals. Pairs with a
 * count of zero are kept: a pair that never disagreed is a finding, not an
 * absence, and dropping it would leave the grid looking sparser than the data.
 */
export function disagreementPairs(segments) {
  const list = Array.isArray(segments) ? segments : [];
  const pairs = new Map();
  const singles = new Map();
  for (const channel of CHANNELS) singles.set(channel, 0);
  for (let i = 0; i < CHANNELS.length; i += 1) {
    for (let j = i + 1; j < CHANNELS.length; j += 1) {
      pairs.set(`${CHANNELS[i]}|${CHANNELS[j]}`, 0);
    }
  }

  let attributed = 0;
  let unknown = 0;
  for (const segment of list) {
    const read = conflictChannels(segment);
    unknown += read.unknown.length;
    if (read.channels.size === 0) continue;
    attributed += 1;
    const named = CHANNELS.filter((channel) => read.channels.has(channel));
    for (const channel of named) singles.set(channel, singles.get(channel) + 1);
    for (let i = 0; i < named.length; i += 1) {
      for (let j = i + 1; j < named.length; j += 1) {
        const key = `${named[i]}|${named[j]}`;
        pairs.set(key, (pairs.get(key) || 0) + 1);
      }
    }
  }

  const total = list.length;
  return {
    total,
    attributed,
    unknown,
    singles: CHANNELS.map((channel) => ({
      channel, count: singles.get(channel),
      share: total ? singles.get(channel) / total : 0,
    })),
    pairs: [...pairs.entries()].map(([key, count]) => {
      const [a, b] = key.split("|");
      return { a, b, count, share: total ? count / total : 0 };
    }),
  };
}
