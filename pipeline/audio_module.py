"""
audio_module.py — Audio channel analysis

Pipeline:
  Whisper      → timestamped transcript segments (defines segment boundaries)
  HuggingFace  → transcript sentiment per segment (POSITIVE / NEUTRAL / NEGATIVE)
  audeering    → dimensional vocal arousal per segment, thresholded to 3 classes
  pyAudioAnalysis → energy + spectral centroid per segment (ShortTermFeatures)
  autocorrelation → pitch_mean per segment (numpy, no extra dep)

All models are lazy-loaded on first call and cached for the lifetime of the process.

Segment schema (one dict per Whisper segment):
  {
    "segment_id":          int,
    "start_time":          float,   # seconds
    "end_time":            float,   # seconds
    "text":                str,     # Whisper transcript
    "transcript_sentiment": {
        "label":      str,          # "POSITIVE" | "NEUTRAL" | "NEGATIVE"
        "confidence": float,        # 0.0 – 1.0
    },
    "vocal_emotion": {
        "label":       str,         # "POSITIVE" | "NEUTRAL" | "NEGATIVE" | "unknown"
        "arousal":     float|None,  # 0.0 – 1.0, the dimension the label is read from
        "valence":     float|None,  # 0.0 – 1.0, recorded but NOT used (see below)
        "dominance":   float|None,  # 0.0 – 1.0, recorded but NOT used
        "reliability": float,       # measured held-out accuracy of this channel
    },
    "pitch_mean":          float,   # Hz (0.0 = unvoiced / silence)
    "energy_mean":         float,   # normalised RMS energy (pyAudioAnalysis scale)
    "spectral_centroid":   float,   # Hz
  }

Field rename, 02 Sep 2026: `speechbrain_emotion` (a bare IEMOCAP word) became
`vocal_emotion` (a dict). Three reasons, in order of weight:

  1. The model is no longer SpeechBrain, so the old name was actively misleading.
     `vocal_bench/CANDIDATE_MODELS.md` §9 flagged this rename as an open question
     before any result was seen; this is that question being answered.
  2. The channel now emits the same POSITIVE/NEUTRAL/NEGATIVE vocabulary as the
     other three channels. Previously the orchestrator was handed "happy" or
     "angry" and had to translate to a valence direction itself, unprompted and
     unverified. The orchestrator's stated job is comparing valence direction
     across channels; giving it four channels that already speak one vocabulary
     removes a translation step that was never measured.
  3. The channel is measurably unreliable (see below) and must be able to say so.
     A bare string has nowhere to carry `reliability`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
from scipy.io import wavfile as scipy_wavfile

logger = logging.getLogger(__name__)

# ── Configuration (overridable via environment) ───────────────────────────────

# Transcription model. Chosen by measurement, not inheritance: benched against
# 11 other checkpoints in whisper_bench/ on 12 hand-typed clips (8.72 min, 6
# speakers). It scores 1.91% WER against base's 3.13% (paired bootstrap
# p = 0.0212) while remaining statistically indistinguishable from the outright
# best model, large-v3 (p = 0.6994), at 3.6x its speed.
#
# The deciding factor was brand-name recall, which is what this product exists
# to get right: base transcribed "Dior Sauvage" as "Dior Savash". Turbo recovers
# 93.3% of brand-term occurrences against base's 70.0% - though that measure is
# post-hoc and substantially carried by one accented speaker. See
# whisper_bench/WHISPER_MODEL_ANALYSIS.md sections 4 and 6, which also record
# why the pre-registered decision rule was overridden and how.
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")
# Transcript sentiment model. Chosen by measurement, not by citation: it won the
# 16-candidate bench in transcript_bench/ on 400 hand-labelled segments from 8 videos.
# Against the previous DistilBERT SST-2 + 0.70-confidence construction it raised
# NEUTRAL recall 0.045 -> 0.795 and three-class accuracy 0.463 -> 0.647
# (exact McNemar p < 0.00001). See transcript_bench/WINNER.md.
SENTIMENT_MODEL_ID = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

# ── Vocal emotion ─────────────────────────────────────────────────────────────
#
# Adopted 02 Sep 2026, replacing speechbrain/emotion-recognition-wav2vec2-IEMOCAP.
# Benched in vocal_bench/ against 7 alternatives and 2 degenerate baselines on 150
# hand-rated clips with a speaker-disjoint holdout. Read the two numbers that
# matter together, because neither is good news on its own:
#
#   * The model this replaces scored 34.0% three-class accuracy against a 50.0%
#     "always say NEUTRAL" floor — significantly WORSE than a constant
#     (exact McNemar p = 0.0070). It was not weak; it was harmful.
#   * This model, read on arousal, scores 60.0% on selection and 48.9% on unseen
#     speakers. Decisively better than the incumbent on selection (p = 0.0001),
#     and it does not fall below the floor. It does not reliably beat the floor
#     either — nothing tested did.
#
# So this is an adoption of the least-bad option inside a channel that is known
# to be weak, not the adoption of a model that works. The channel is explicitly
# down-weighted downstream (orchestrator.VOCAL_ONLY_CONFLICT_WEIGHT) and carries
# VOCAL_CAVEAT on every report. See vocal_bench/VOCAL_MODEL_ANALYSIS.md §8.
#
# LICENCE: cc-by-nc-sa-4.0 — NON-COMMERCIAL. BrandPulse is framed as a B2B
# product, so this checkpoint could not ship in a commercial deployment as-is.
# Every configuration in the bench that showed any signal was non-commercially
# licensed; every permissively-licensed model measured sat at the bottom of the
# table. That constraint is a measured finding of this project, not a footnote,
# and it is recorded in VOCAL_MODEL_ANALYSIS.md §5b.
VOCAL_MODEL_ID = os.getenv(
    "VOCAL_MODEL_ID", "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
)

# The model emits arousal, dominance and valence in [0, 1]. The pipeline reads
# AROUSAL, and this is the substantive change — swapping the model alone would
# have kept the same defect.
#
# Measured on 147 rated clips: arousal correlates with a human's reading of vocal
# positivity at Spearman rho = +0.413, valence at +0.045. Arousal beat valence in
# 6 of 6 paired comparisons across models, splits and the two-model ensemble
# (sign test p = 0.031). On professionally-presented product-review speech, what a
# listener hears as vocal positivity tracks the speaker's ENERGY, and the previous
# design was reading the dimension that carries almost no signal here.
VOCAL_DIMENSION = "arousal"

# Decision thresholds on that dimension: below AROUSAL_LOW -> NEGATIVE,
# [AROUSAL_LOW, AROUSAL_HIGH) -> NEUTRAL, >= AROUSAL_HIGH -> POSITIVE.
#
# These are FROZEN bench values, not tuned here. They were fitted by grid search
# on the vocal_bench SELECTION split only (2 speakers, 100 clips) and then applied
# unchanged to the 4 held-out speakers, where they scored 48.9%. Re-fitting them on
# pipeline data would destroy the only out-of-sample evidence this channel has.
AROUSAL_LOW = 0.40
AROUSAL_HIGH = 0.65

# Measured three-class accuracy of this configuration on the speaker-disjoint
# holdout (23 of 47 clips correct). Used, not just documented: it is the
# reliability the channel reports to the orchestrator, and it is the damping
# factor applied to a conflict that rests on this channel alone.
#
# 0.489 is deliberately not rounded to a comfortable number. It is a count.
VOCAL_CHANNEL_RELIABILITY = 0.489

# Segments shorter than this are skipped for the vocal model and pyAudioAnalysis
# (models need at least a few hundred milliseconds of audio)
MIN_SEGMENT_DURATION_S = 0.5

# The sentiment model has a native three-class head, so NEUTRAL is a class the model
# was trained to predict rather than one manufactured from low confidence. The previous
# implementation used a two-class model plus a 0.70 confidence cut-off; measured on
# hand-labelled data that rule fired on 3.2% of segments against a true NEUTRAL rate of
# 39.0%, and a second, unrelated two-class model failed identically under it
# (transcript_bench/WINNER.md Section 3). The threshold has been removed, not retuned.
#
# Label strings are normalised because heads disagree on casing and ordering.
_SENTIMENT_LABEL_MAP = {
    "POSITIVE": "POSITIVE", "POS": "POSITIVE", "LABEL_2": "POSITIVE",
    "NEUTRAL":  "NEUTRAL",  "NEU": "NEUTRAL",  "LABEL_1": "NEUTRAL",
    "NEGATIVE": "NEGATIVE", "NEG": "NEGATIVE", "LABEL_0": "NEGATIVE",
}

# Segments separated by more than this many seconds of silence are never merged:
# a long speechless stretch is an edit or a music bed, not a pause mid-sentence.
# 2.0 s is the 95th percentile of the 203 inter-segment gaps measured across the
# 12-video transcript-bench corpus (31 Aug 2026); median gap is 0.48 s.
MAX_MERGE_GAP = 2.0

# pyAudioAnalysis short-term window / step (seconds)
ST_WIN_S = 0.025   # 25 ms window
ST_STEP_S = 0.010  # 10 ms step

# Pitch (F0) analysis window / step (seconds).
# Wider than ST_WIN_S because autocorrelation needs at least ~2 periods of the
# lowest searched pitch (50 Hz → 40 ms) to lock on; 50 ms gives margin.
# F0 is estimated per-frame and averaged over voiced frames only (see
# _estimate_pitch_hz_framewise) — speech constantly alternates voiced/unvoiced,
# so estimating once over a whole multi-second segment washes out periodicity.
PITCH_WIN_S = 0.050   # 50 ms window
PITCH_STEP_S = 0.025  # 25 ms hop

# ── Lazy model singletons ─────────────────────────────────────────────────────

_whisper_model = None
_sentiment_pipe = None
_vocal_model = None   # (processor, model) tuple once loaded


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        import whisper as _whisper
        logger.info("Loading Whisper model (%s) …", WHISPER_MODEL_SIZE)
        _whisper_model = _whisper.load_model(WHISPER_MODEL_SIZE)
        logger.info("Whisper ready.")
    return _whisper_model


def _get_sentiment_pipe():
    global _sentiment_pipe
    if _sentiment_pipe is None:
        from transformers import pipeline as hf_pipeline
        logger.info("Loading sentiment model (%s) …", SENTIMENT_MODEL_ID)
        _sentiment_pipe = hf_pipeline(
            "text-classification",
            model=SENTIMENT_MODEL_ID,
            top_k=None,   # return scores for all labels
            truncation=True,
            max_length=512,
        )
        logger.info("Sentiment model ready.")
    return _sentiment_pipe


def _build_emotion_model_class():
    """Define the audeering dimensional-regression architecture.

    The checkpoint ships weights but not the class that assembles them: a
    wav2vec2 encoder, mean-pooled over time, into a small regression head
    emitting three continuous values. The architecture is reproduced from the
    model card rather than imported, because the only packaged copy of it lives
    in `vocal_bench/candidates.py`, and a bench directory must not sit on the
    production import path.

    Defined inside a function so that importing this module does not import
    torch — the Flask app imports it at startup and most requests never touch
    the vocal channel.
    """
    import torch
    import torch.nn as nn
    from transformers.models.wav2vec2.modeling_wav2vec2 import (
        Wav2Vec2Model, Wav2Vec2PreTrainedModel)

    class RegressionHead(nn.Module):
        def __init__(self, config):
            super().__init__()
            self.dense = nn.Linear(config.hidden_size, config.hidden_size)
            self.dropout = nn.Dropout(config.final_dropout)
            self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

        def forward(self, features, **kwargs):
            x = self.dropout(features)
            x = torch.tanh(self.dense(x))
            x = self.dropout(x)
            return self.out_proj(x)

    class EmotionModel(Wav2Vec2PreTrainedModel):
        # transformers 5.x requires both attributes on every PreTrainedModel
        # subclass. The model card's code predates them, so loading it verbatim
        # raises AttributeError on this project's pinned version. Empty because
        # this architecture ties no weights.
        all_tied_weights_keys: dict = {}
        _tied_weights_keys: list = []

        def __init__(self, config):
            super().__init__(config)
            self.config = config
            self.wav2vec2 = Wav2Vec2Model(config)
            self.classifier = RegressionHead(config)
            self.init_weights()

        def forward(self, input_values):
            hidden = torch.mean(self.wav2vec2(input_values)[0], dim=1)
            return self.classifier(hidden)

    return EmotionModel


def _get_vocal_model():
    """Lazily load the dimensional vocal-emotion model. Cached for the process."""
    global _vocal_model
    if _vocal_model is None:
        from transformers import Wav2Vec2Processor

        logger.info("Loading vocal emotion model (%s) …", VOCAL_MODEL_ID)
        model_cls = _build_emotion_model_class()
        processor = Wav2Vec2Processor.from_pretrained(VOCAL_MODEL_ID)
        model = model_cls.from_pretrained(VOCAL_MODEL_ID).eval()
        _vocal_model = (processor, model)
        logger.info("Vocal emotion model ready (reading %s).", VOCAL_DIMENSION)
    return _vocal_model


# ── Audio I/O helpers ─────────────────────────────────────────────────────────

def _load_wav_int16(audio_path: Path) -> tuple[np.ndarray, int]:
    """
    Load a WAV file as a mono int16 numpy array + sample rate.

    pyAudioAnalysis.ShortTermFeatures.feature_extraction() internally divides
    by 2^15, so it expects raw int16 values in the range [-32768, 32767].
    Returning int16 here avoids a silent double-normalisation bug.

    The pipeline's own audio is always 16-bit PCM (downloader.extract_audio asks
    ffmpeg for pcm_s16le), which passes through unchanged. Other sample formats
    are scaled into the int16 range by their own convention before mixing down.
    """
    sr, data = scipy_wavfile.read(str(audio_path))
    if np.issubdtype(data.dtype, np.floating):          # float WAV: samples in [-1, 1]
        data = np.clip(data, -1.0, 1.0) * 32767.0
    elif data.dtype == np.int32:                        # 32-bit PCM
        data = data / 65536.0
    elif data.dtype == np.uint8:                        # 8-bit PCM: unsigned, centred on 128
        data = (data.astype(np.float64) - 128.0) * 256.0
    if data.ndim > 1:
        data = data.mean(axis=1)
    if data.dtype != np.int16:
        data = data.astype(np.int16)
    return data, sr


def _slice_int16(data: np.ndarray, sr: int, start_s: float, end_s: float) -> np.ndarray:
    """Slice a 1-D int16 array to [start_s, end_s] seconds."""
    start = max(0, int(start_s * sr))
    end = min(len(data), int(end_s * sr))
    return data[start:end]


def _int16_to_float32(data: np.ndarray) -> np.ndarray:
    """Normalise int16 → float32 in [-1, 1] for pitch estimation."""
    return data.astype(np.float32) / 32768.0


# ── Pitch estimation (autocorrelation, numpy only) ───────────────────────────

def _estimate_pitch_hz(signal_f32: np.ndarray, sr: int) -> float:
    """
    Estimate mean fundamental frequency (F0) via normalized autocorrelation.

    Searches in the human vocal range 50–500 Hz.
    Returns 0.0 for unvoiced / silence segments.
    """
    if len(signal_f32) == 0:
        return 0.0

    # Voiced energy check — skip nearly silent signals
    rms = float(np.sqrt(np.mean(signal_f32 ** 2)))
    if rms < 1e-4:
        return 0.0

    # Lag bounds corresponding to 50–500 Hz
    lag_min = max(1, int(sr / 500))
    lag_max = int(sr / 50)

    if len(signal_f32) < lag_max * 2:
        return 0.0

    # Zero-mean
    sig = signal_f32 - signal_f32.mean()

    # Autocorrelation via FFT (O(n log n))
    n = len(sig)
    fft_vals = np.fft.rfft(sig, n=2 * n)
    acf = np.fft.irfft(fft_vals * np.conj(fft_vals))[:n]
    if acf[0] < 1e-10:
        return 0.0
    acf /= acf[0]  # normalise to 1 at lag 0

    search_region = acf[lag_min : lag_max + 1]
    if len(search_region) == 0:
        return 0.0

    peak_rel = int(np.argmax(search_region))
    peak_lag = peak_rel + lag_min
    peak_val = float(acf[peak_lag])

    # Only return a pitch if the autocorrelation peak is strong enough
    if peak_val < 0.3:
        return 0.0

    return float(sr / peak_lag)


def _estimate_pitch_hz_framewise(signal_f32: np.ndarray, sr: int) -> float:
    """
    Estimate mean F0 over a multi-second segment by running per-frame
    autocorrelation and averaging only the voiced frames.

    Why this exists
    ---------------
    `_estimate_pitch_hz` runs a single autocorrelation over whatever signal it
    is given. Calling it once on a whole 5–17 s segment mixes voiced speech,
    silent pauses, breaths, and unvoiced consonants together — the periodicity
    gets washed out and the result almost always falls below the voicing
    threshold, returning 0.0. Real speech alternates voiced/unvoiced several
    times per second, so F0 must be estimated on short frames (like energy and
    spectral centroid already are) and then aggregated over the frames that are
    actually voiced.

    Returns 0.0 only when NO frame in the segment is voiced.
    """
    if len(signal_f32) == 0:
        return 0.0

    win = int(PITCH_WIN_S * sr)
    step = int(PITCH_STEP_S * sr)
    if win <= 0 or step <= 0:
        return 0.0

    # Segment shorter than a single analysis window: fall back to one estimate
    # (which itself returns 0.0 if the slice is too short to be reliable).
    if len(signal_f32) < win:
        return _estimate_pitch_hz(signal_f32, sr)

    voiced_pitches: list[float] = []
    for start in range(0, len(signal_f32) - win + 1, step):
        f0 = _estimate_pitch_hz(signal_f32[start : start + win], sr)
        if f0 > 0.0:
            voiced_pitches.append(f0)

    if not voiced_pitches:
        return 0.0

    return float(np.mean(voiced_pitches))


# ── Stage 1: Whisper transcription ────────────────────────────────────────────

def transcribe(audio_path: Path) -> list[dict]:
    """
    Transcribe audio with Whisper and return one dict per detected segment.

    Segment boundaries produced here drive every downstream module — they are
    the temporal anchors for DeepFace pooling, vocal-model slicing, and
    pyAudioAnalysis extraction.

    Parameters
    ----------
    audio_path : Path to the 16 kHz mono WAV produced by downloader.py

    Returns
    -------
    list of dicts with keys: segment_id, start_time, end_time, text
    (transcript_sentiment is added by add_transcript_sentiment)

    Raises
    ------
    FileNotFoundError : audio_path does not exist
    RuntimeError      : Whisper model fails to load or transcribe
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = _get_whisper()
    logger.info("Transcribing %s with Whisper (%s)…", audio_path.name, WHISPER_MODEL_SIZE)

    try:
        result = model.transcribe(
            str(audio_path),
            language="en",
            verbose=False,
            fp16=False,   # FP32 throughout: Whisper's fp16 path is CUDA-only
        )
    except Exception as exc:
        raise RuntimeError(f"Whisper transcription failed: {exc}") from exc

    raw_segments = result.get("segments", [])
    if not raw_segments:
        logger.warning("Whisper returned zero segments for %s — audio may be silent or non-speech.", audio_path.name)

    segments = [
        {
            "segment_id": int(seg["id"]),
            "start_time": float(seg["start"]),
            "end_time":   float(seg["end"]),
            "text":       seg["text"].strip(),
        }
        for seg in raw_segments
    ]

    logger.info("Whisper: %d segments detected.", len(segments))
    return segments


# ── Stage 2: Transcript sentiment ─────────────────────────────────────────────

def add_transcript_sentiment(segments: list[dict]) -> list[dict]:
    """
    Run three-class sentiment on each segment's transcript text.

    The model emits POSITIVE / NEUTRAL / NEGATIVE directly; the reported confidence
    is the winning class's own probability. No confidence threshold is applied —
    see the note on _SENTIMENT_LABEL_MAP for why the previous one was removed.

    Modifies segments in-place, returns the same list. A failure on one segment is
    recorded as NEUTRAL with confidence 0.0 and never aborts the run.
    """
    pipe = _get_sentiment_pipe()

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            seg["transcript_sentiment"] = {"label": "NEUTRAL", "confidence": 1.0}
            continue

        try:
            results = pipe(text)[0]  # list of {"label": ..., "score": ...}
            scores = {r["label"]: r["score"] for r in results}
            best_label = max(scores, key=scores.__getitem__)

            label = _SENTIMENT_LABEL_MAP[best_label.strip().upper()]
            confidence = scores[best_label]

        except KeyError:
            # An unrecognised label means the configured model does not match the
            # schema this pipeline expects. Degrade, but say so loudly: silently
            # mapping it to NEUTRAL would corrupt the channel without a trace.
            logger.error(
                "Sentiment model %s returned unmapped label %r for segment %d — "
                "check SENTIMENT_MODEL_ID.",
                SENTIMENT_MODEL_ID, best_label, seg["segment_id"],
            )
            label, confidence = "NEUTRAL", 0.0

        except Exception as exc:
            logger.warning(
                "Sentiment analysis failed for segment %d ('%s…'): %s",
                seg["segment_id"], text[:30], exc,
            )
            label, confidence = "NEUTRAL", 0.0

        seg["transcript_sentiment"] = {"label": label, "confidence": round(confidence, 4)}

    return segments


# ── Stage 3: dimensional vocal emotion ───────────────────────────────────────

def _unknown_vocal(reason: str) -> dict:
    """The vocal reading used when no measurement could be taken.

    `label` is "unknown", never "NEUTRAL". Coercing an absent measurement to
    NEUTRAL is exactly the defect transcript_bench found in the deployed
    transcript channel: it manufactures a confident-looking reading out of a
    failure, and it is invisible afterwards. Reliability is 0.0 so that anything
    downstream weighting by it discounts this reading completely.
    """
    return {"label": "unknown", "arousal": None, "valence": None,
            "dominance": None, "reliability": 0.0, "reason": reason}


def classify_arousal(value: float | None) -> str:
    """Map a continuous dimension score in [0, 1] onto the three-class vocabulary.

    Bands are half-open and ordered low → high:
        value <  AROUSAL_LOW                     → "NEGATIVE"
        AROUSAL_LOW <= value < AROUSAL_HIGH      → "NEUTRAL"
        value >= AROUSAL_HIGH                    → "POSITIVE"

    The direction is empirical, not assumed: on this material a low-energy
    delivery is what a human listener rated negative and a high-energy delivery
    is what they rated positive. The thresholds were fitted on the bench's
    selection split and are frozen (see AROUSAL_LOW / AROUSAL_HIGH).

    A missing value returns "unknown" rather than being coerced to a class.
    """
    if value is None:
        return "unknown"
    if value < AROUSAL_LOW:
        return "NEGATIVE"
    if value < AROUSAL_HIGH:
        return "NEUTRAL"
    return "POSITIVE"


def analyse_vocal_emotion(audio_path: Path, segments: list[dict]) -> list[dict]:
    """
    Read vocal emotion for each segment from the dimensional model's arousal axis.

    Loads the full WAV once and slices per-segment to avoid repeated file I/O.
    Segments shorter than MIN_SEGMENT_DURATION_S are marked "unknown" rather than
    sent to the model (wav2vec2 needs a few hundred milliseconds to produce
    anything meaningful).

    All three dimensions are stored even though only `arousal` drives the label.
    They cost nothing extra — the model emits all three in one forward pass — and
    keeping valence on the record is what makes the "we were reading the wrong
    dimension" finding auditable on real pipeline output rather than only on
    bench clips.

    Modifies segments in-place, returns the same list. A failure on one segment is
    recorded as unknown and never aborts the run.

    Raises
    ------
    FileNotFoundError : audio_path does not exist
    """
    import torch

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    processor, model = _get_vocal_model()
    data_int16, sr = _load_wav_int16(audio_path)

    for seg in segments:
        seg_id = seg["segment_id"]
        duration = seg["end_time"] - seg["start_time"]

        if duration < MIN_SEGMENT_DURATION_S:
            logger.debug("Segment %d too short (%.2fs) — skipping vocal emotion.",
                         seg_id, duration)
            seg["vocal_emotion"] = _unknown_vocal("segment_too_short")
            continue

        slice_int16 = _slice_int16(data_int16, sr, seg["start_time"], seg["end_time"])
        if len(slice_int16) == 0:
            seg["vocal_emotion"] = _unknown_vocal("empty_slice")
            continue

        try:
            slice_f32 = _int16_to_float32(slice_int16)
            inputs = processor(slice_f32, sampling_rate=sr)["input_values"][0]
            with torch.no_grad():
                out = model(torch.tensor(inputs).unsqueeze(0))[0].numpy()
            # Output order is fixed by the checkpoint: arousal, dominance, valence.
            arousal, dominance, valence = (float(v) for v in out)
        except Exception as exc:
            logger.warning("Vocal emotion failed on segment %d: %s", seg_id, exc)
            seg["vocal_emotion"] = _unknown_vocal("model_error")
            continue

        dimension = {"arousal": arousal, "valence": valence,
                     "dominance": dominance}[VOCAL_DIMENSION]

        seg["vocal_emotion"] = {
            "label":       classify_arousal(dimension),
            "arousal":     round(arousal, 4),
            "valence":     round(valence, 4),
            "dominance":   round(dominance, 4),
            "reliability": VOCAL_CHANNEL_RELIABILITY,
        }
        logger.debug("Segment %d → vocal %s (arousal %.3f, valence %.3f)",
                     seg_id, seg["vocal_emotion"]["label"], arousal, valence)

    return segments


# ── Stage 4: pyAudioAnalysis prosody ─────────────────────────────────────────

def extract_prosody(audio_path: Path, segments: list[dict]) -> list[dict]:
    """
    Extract scalar prosodic features per segment using pyAudioAnalysis +
    numpy autocorrelation.

    pyAudioAnalysis ShortTermFeatures.feature_extraction() returns a matrix
    of shape (n_features, n_frames).  We take the mean across frames per
    segment.  Feature indices used:
      1 → energy (normalised RMS, pyAudioAnalysis internal scale)
      3 → spectral_centroid (normalised 0–1; converted to Hz by * sr/2)

    Pitch (F0) is estimated separately via autocorrelation because
    pyAudioAnalysis does not expose fundamental frequency in its standard
    feature set.

    Modifies segments in-place, returns the same list.

    Raises
    ------
    FileNotFoundError : audio_path does not exist
    """
    from pyAudioAnalysis import ShortTermFeatures

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    data_int16, sr = _load_wav_int16(audio_path)
    data_f32 = _int16_to_float32(data_int16)  # for pitch autocorrelation

    # pyAudioAnalysis window/step in samples
    win_samples  = int(ST_WIN_S  * sr)
    step_samples = int(ST_STEP_S * sr)

    for seg in segments:
        seg_id  = seg["segment_id"]
        start_s = seg["start_time"]
        end_s   = seg["end_time"]
        duration = end_s - start_s

        # Defaults used when segment is too short or extraction fails
        seg.setdefault("pitch_mean",        0.0)
        seg.setdefault("energy_mean",       0.0)
        seg.setdefault("spectral_centroid", 0.0)

        if duration < MIN_SEGMENT_DURATION_S:
            logger.debug("Segment %d too short (%.2fs) — skipping prosody.", seg_id, duration)
            continue

        slice_int16 = _slice_int16(data_int16, sr, start_s, end_s)
        slice_f32   = _slice_int16(data_f32, sr, start_s, end_s)

        if len(slice_int16) < win_samples:
            logger.debug("Segment %d shorter than analysis window — skipping prosody.", seg_id)
            continue

        # ── pyAudioAnalysis features ──────────────────────────────────────
        try:
            # feature_extraction divides internally by 2^15; pass int16 values
            features, _names = ShortTermFeatures.feature_extraction(
                slice_int16.astype(float),   # it calls np.double() internally
                sr,
                win_samples,
                step_samples,
            )
            # features: shape (n_feats, n_frames) — mean across time axis
            energy_mean       = float(np.mean(features[1]))
            # Spectral centroid is normalised [0,1]; convert to Hz
            spectral_centroid = float(np.mean(features[3])) * (sr / 2)

        except Exception as exc:
            logger.warning("pyAudioAnalysis failed on segment %d: %s", seg_id, exc)
            energy_mean       = 0.0
            spectral_centroid = 0.0

        # ── Pitch via framewise autocorrelation (voiced frames averaged) ──
        try:
            pitch_mean = _estimate_pitch_hz_framewise(slice_f32, sr)
        except Exception as exc:
            logger.warning("Pitch estimation failed on segment %d: %s", seg_id, exc)
            pitch_mean = 0.0

        seg["pitch_mean"]        = round(pitch_mean, 2)
        seg["energy_mean"]       = round(energy_mean, 6)
        seg["spectral_centroid"] = round(spectral_centroid, 2)

        logger.debug(
            "Segment %d → pitch=%.1f Hz  energy=%.4f  spectral_centroid=%.1f Hz",
            seg_id, pitch_mean, energy_mean, spectral_centroid,
        )

    return segments


# ── Public wrapper ────────────────────────────────────────────────────────────

def _merge_short_segments(
    segments: list[dict],
    min_duration: float = 3.0,
    max_gap: float = MAX_MERGE_GAP,
) -> list[dict]:
    """
    Merge consecutive short segments so that each result reaches min_duration.

    Two conditions gate a merge, and both matter:

    ``accumulated < min_duration``
        The test is on the segment being *built*, not on the one arriving. Testing
        the arriving segment alone lets an unbroken run of sub-threshold segments
        append to the same accumulator without limit. Measured on the 12-video
        transcript-bench corpus (31 Aug 2026), that produced a 121-second, 435-word
        "segment" assembled from 65 Whisper segments, and 11 segments over 45 s in
        total. Those blocks span several topics, so no single sentiment label can
        describe them - they degrade every downstream channel that consumes a
        segment as one unit.

    ``gap <= max_gap``
        Silence is a boundary. Merging across a long speechless stretch joins
        material either side of an edit or a music bed. One 21-second intro gap in
        the corpus was being bridged this way.

    A trailing segment that is still short is folded back into its predecessor,
    unless a large gap separates them - in which case it is left short, honestly,
    rather than glued across a scene break.

    Modifies nothing in place: returns new dicts with segment_id renumbered from 0.
    """
    if not segments:
        return segments

    merged = [segments[0].copy()]
    for seg in segments[1:]:
        accumulated = merged[-1]["end_time"] - merged[-1]["start_time"]
        gap = seg["start_time"] - merged[-1]["end_time"]
        if accumulated < min_duration and gap <= max_gap:
            merged[-1]["end_time"] = seg["end_time"]
            merged[-1]["text"] = (merged[-1]["text"] + " " + seg["text"]).strip()
        else:
            merged.append(seg.copy())

    if len(merged) > 1:
        tail = merged[-1]
        tail_short = (tail["end_time"] - tail["start_time"]) < min_duration
        if tail_short and (tail["start_time"] - merged[-2]["end_time"]) <= max_gap:
            merged.pop()
            merged[-1]["end_time"] = tail["end_time"]
            merged[-1]["text"] = (merged[-1]["text"] + " " + tail["text"]).strip()

    for i, seg in enumerate(merged):
        seg["segment_id"] = i
    logger.info(
        "Segment merge: %d → %d segments (min_duration=%.1fs, max_gap=%.1fs)",
        len(segments), len(merged), min_duration, max_gap,
    )
    return merged


def build_audio_channel(audio_path: Path) -> list[dict]:
    """
    Run the complete audio analysis pipeline on a single WAV file.

    Stages (in order):
      1. Whisper large-v3-turbo    → segment boundaries + text
      2. XLM-RoBERTa sentiment     → transcript_sentiment per segment
      3. audeering wav2vec2 (dim.) → vocal_emotion per segment, read on arousal
      4. pyAudioAnalysis           → energy_mean + spectral_centroid per segment
      5. Autocorrelation           → pitch_mean per segment

    Parameters
    ----------
    audio_path : Path to 16 kHz mono WAV file produced by downloader.py

    Returns
    -------
    list of fully annotated segment dicts (see module docstring for schema)
    """
    audio_path = Path(audio_path)

    segments = transcribe(audio_path)
    if not segments:
        logger.warning("No speech segments found — returning empty list.")
        return []

    segments = _merge_short_segments(segments, min_duration=3.0)
    segments = add_transcript_sentiment(segments)
    segments = analyse_vocal_emotion(audio_path, segments)
    segments = extract_prosody(audio_path, segments)

    return segments
