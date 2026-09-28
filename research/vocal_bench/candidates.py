"""
candidates.py - the vocal-emotion candidates, behind one interface.

Every candidate exposes `predict(wav_path) -> dict` returning at minimum:

    {"raw_label": str | None,   # the model's own label, verbatim, un-normalised
     "scores": {label: float},  # full distribution where available
     "valence": float | None}   # continuous valence, dimensional models only

Raw labels are kept verbatim and mapped to three classes downstream by
`report_bench.py`, never here. Keeping the mapping out of the model wrapper means
the mapping can be re-run, audited, or sensitivity-tested without re-running any
model, and an unmapped label surfaces as unmapped instead of being quietly
coerced to NEUTRAL - the exact defect `transcript_bench` found in the deployed
transcript channel.

Registry order matches CANDIDATE_MODELS.md section 4.
"""

from __future__ import annotations

import functools
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

PROJECT = Path(__file__).resolve().parents[2]

# emotion2vec labels are bilingual ("生气/angry"); split on "/" and keep the English.
def _english(label: str) -> str:
    return label.split("/")[-1].strip().lower()


# ──────────────────────────────────────────── former incumbent: SpeechBrain
#
# HISTORICAL. This was the deployed model when the bench ran (01-02 Sep 2026) and
# every incumbent number in VOCAL_MODEL_ANALYSIS.md comes from it. On 02 Sep 2026
# it was replaced in the pipeline by `audeering-msp-dim` read on arousal, on the
# strength of this bench.
#
# The loader below is a verbatim copy of `pipeline.audio_module._get_sb_classifier`
# and the forward pass in `run_speechbrain` a verbatim copy of that module's
# pre-swap `analyse_vocal_emotion`, both as they stood at the commit the bench ran
# on. They were originally imported from the pipeline so the incumbent would be
# benched exactly as deployed. Now that the pipeline no longer contains them,
# keeping the import would either break `run_bench.py` or force dead code to
# survive on the production path. Copying them here keeps the bench re-runnable
# and leaves production clean. If these numbers are ever re-derived, they are
# re-derived against this copy.

SPEECHBRAIN_SOURCE = "speechbrain/emotion-recognition-wav2vec2-IEMOCAP"
SPEECHBRAIN_SAVEDIR = str(PROJECT / "data" / "models" / "speechbrain_emotion")


@functools.lru_cache(maxsize=1)
def _speechbrain():
    try:
        from speechbrain.inference.classifiers import EncoderClassifier
    except ImportError:
        # SpeechBrain < 1.0 used a different import path
        from speechbrain.pretrained import EncoderClassifier  # type: ignore
    return EncoderClassifier.from_hparams(
        source=SPEECHBRAIN_SOURCE,
        savedir=SPEECHBRAIN_SAVEDIR,
        run_opts={"device": "cpu"},
    )


def run_speechbrain(wav_path: Path) -> dict:
    """The model that was deployed when this bench ran, called as it was called.

    SpeechBrain 1.x wav2vec2 models need their modules invoked directly:
    `encode_batch` calls `compute_features`, which this architecture does not
    have. That is why the forward pass is spelled out rather than delegated.
    """
    import torch
    import soundfile as sf

    clf = _speechbrain()
    data, _sr = sf.read(str(wav_path), dtype="float32")
    wav = torch.tensor(data).unsqueeze(0)
    lens = torch.tensor([1.0])
    with torch.no_grad():
        wav = wav.to(clf.device)
        lens = lens.to(clf.device)
        feats = clf.mods.wav2vec2(wav, lens)
        pooled = clf.mods.avg_pool(feats, lens)
        out = clf.mods.output_mlp(pooled).squeeze(1)
        probs = torch.softmax(out, dim=-1)[0]
        idx = torch.argmax(out, dim=-1)
        text = clf.hparams.label_encoder.decode_torch(idx)

    # IEMOCAP short codes -> full words, matching the pre-swap
    # audio_module._IEMOCAP_LABEL_MAP (removed from the pipeline on 02 Sep 2026).
    # Scores are aligned to the encoder's OWN index order (ind2lab), not to the
    # insertion order of lab2ind. On this checkpoint the two happen to coincide
    # (neu=0, ang=1, hap=2, sad=3), so relying on insertion order would have been
    # correct by luck; ind2lab is correct by construction.
    expand = {"neu": "neutral", "hap": "happy", "sad": "sad", "ang": "angry"}
    ind2lab = clf.hparams.label_encoder.ind2lab
    scores = {expand.get(str(ind2lab[i]).lower(), str(ind2lab[i]).lower()): float(probs[i])
              for i in range(len(ind2lab))}
    raw = str(text[0]).lower() if text else None
    return {"raw_label": expand.get(raw, raw) if raw else None,
            "scores": scores, "valence": None}


# ─────────────────────────────────────────────── transformers audio-classifiers

@functools.lru_cache(maxsize=4)
def _hf_pipe(model_id: str):
    from transformers import pipeline
    return pipeline("audio-classification", model=model_id)


def _run_hf(model_id: str, wav_path: Path) -> dict:
    import soundfile as sf
    data, _ = sf.read(str(wav_path), dtype="float32")
    out = _hf_pipe(model_id)(data, top_k=20)
    scores = {o["label"].lower(): float(o["score"]) for o in out}
    best = max(scores, key=scores.get)
    expand = {"neu": "neutral", "hap": "happy", "sad": "sad", "ang": "angry"}
    return {"raw_label": expand.get(best, best),
            "scores": {expand.get(k, k): v for k, v in scores.items()},
            "valence": None}


# ─────────────────────────────────────────────────────────── emotion2vec+ family

@functools.lru_cache(maxsize=4)
def _e2v(repo: str):
    from huggingface_hub import snapshot_download
    from funasr import AutoModel
    # modelscope (funasr's default hub) was unusable from this machine on
    # 01 Sep 2026 - repeated partial downloads that reset. The HuggingFace
    # mirror of the same checkpoint completed in 18 s.
    return AutoModel(model=snapshot_download(repo), disable_update=True,
                     disable_pbar=True, hub="hf")


def _run_e2v(repo: str, wav_path: Path) -> dict:
    res = _e2v(repo).generate(str(wav_path), granularity="utterance",
                              extract_embedding=False)
    r = res[0]
    scores = {_english(l): float(s) for l, s in zip(r["labels"], r["scores"])}
    best = max(scores, key=scores.get)
    return {"raw_label": best, "scores": scores, "valence": None}


# ────────────────────────────────────────────────────── audeering dimensional

@functools.lru_cache(maxsize=1)
def _audeering():
    import torch
    import torch.nn as nn
    from transformers import Wav2Vec2Processor
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
        # transformers 5.x requires these; the audeering model card's code was
        # written for 4.x and predates them. Empty because nothing is tied.
        all_tied_weights_keys = {}
        _tied_weights_keys = []

        def __init__(self, config):
            super().__init__(config)
            self.config = config
            self.wav2vec2 = Wav2Vec2Model(config)
            self.classifier = RegressionHead(config)
            self.init_weights()

        def forward(self, input_values):
            hidden = torch.mean(self.wav2vec2(input_values)[0], dim=1)
            return self.classifier(hidden)

    name = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
    return Wav2Vec2Processor.from_pretrained(name), EmotionModel.from_pretrained(name).eval()


def run_audeering(wav_path: Path) -> dict:
    """Dimensional: returns arousal, dominance, valence in [0, 1].

    Only `valence` is used for the three-class decision; arousal and dominance
    are recorded because they are free and may explain failures (a loud excited
    voice is high-arousal regardless of valence, which is the most likely reason
    the incumbent confuses enthusiasm with anger).
    """
    import torch
    import soundfile as sf

    proc, model = _audeering()
    data, _ = sf.read(str(wav_path), dtype="float32")
    x = proc(data, sampling_rate=16000)["input_values"][0]
    with torch.no_grad():
        out = model(torch.tensor(x).unsqueeze(0))[0].numpy()
    arousal, dominance, valence = (float(v) for v in out)
    return {"raw_label": None,
            "scores": {"arousal": arousal, "dominance": dominance, "valence": valence},
            "valence": valence}


# ──────────────────────────────────────────── WavLM MSP-Podcast (vendored deps)

@functools.lru_cache(maxsize=1)
def _wavlm():
    """INTERSPEECH 2025 Speech Emotion Challenge winner (SAILER, without transcript).

    Added 02 Sep 2026, after the first pass of this bench excluded it on
    integration cost. Excluding the strongest published candidate weakened the
    bench's central negative claim, so it was brought in rather than left out.

    Its HuggingFace repo ships only config.json + model.safetensors; the class
    that assembles them (LoRA rank 16, conv-output pooling, dual heads) lives in
    vox-profile-release, vendored under vendor/ with its commit pinned. See
    vendor/README.md for why it is vendored rather than pip-installed.
    """
    import sys
    vendor = Path(__file__).resolve().parent / "vendor" / "vox-profile-release" / "src"
    if not vendor.is_dir():
        raise RuntimeError(
            f"vox-profile-release not found at {vendor}. See vocal_bench/vendor/README.md."
        )
    for p in (str(vendor), str(vendor / "model" / "emotion")):
        if p not in sys.path:
            sys.path.append(p)
    from wavlm_emotion_dim import WavLMWrapper
    return WavLMWrapper.from_pretrained(
        "tiantiaf/wavlm-large-msp-podcast-emotion-dim").eval()


def run_wavlm(wav_path: Path) -> dict:
    """Dimensional: arousal, valence, dominance.

    NOTE the authors' own caveat, quoted from their example script: training
    filtered audio shorter than 3 s as giving "unreliable predictions". Some
    clips in this sample are shorter, so per-clip reliability is reported
    separately in the analysis rather than assumed uniform.
    """
    import torch
    import soundfile as sf

    model = _wavlm()
    data, _ = sf.read(str(wav_path), dtype="float32")
    with torch.no_grad():
        arousal, valence, dominance = model(torch.tensor(data).unsqueeze(0).float())
    a, v, d = float(arousal[0]), float(valence[0]), float(dominance[0])
    return {"raw_label": None,
            "scores": {"arousal": a, "dominance": d, "valence": v},
            "valence": v}


# ────────────────────────────────────────────────────────────────── registry

REGISTRY: dict[str, dict] = {
    "speechbrain-iemocap": {
        "fn": run_speechbrain, "kind": "categorical", "licence": "apache-2.0",
        "incumbent": True,
        # `incumbent` is unchanged: it names the baseline THIS bench compared
        # against, which is a fact about the experiment and must not be rewritten
        # by later events. It was deployed until 02 Sep 2026, when this bench
        # replaced it. The note records that; the flag records the protocol.
        "note": "IEMOCAP acted speech. Deployed model until 02 Sep 2026, "
                "replaced by audeering-msp-dim [arousal] on this bench's result",
    },
    "superb-wav2vec2-er": {
        "fn": lambda p: _run_hf("superb/wav2vec2-base-superb-er", p),
        "kind": "categorical", "licence": "apache-2.0",
        "note": "IEMOCAP acted speech, different training recipe",
    },
    "dpngtm-wav2vec2": {
        "fn": lambda p: _run_hf("Dpngtm/wav2vec2-emotion-recognition", p),
        "kind": "categorical", "licence": "mit",
        "note": "RAVDESS-family acted speech, 7 classes",
    },
    "emotion2vec-seed": {
        "fn": lambda p: _run_e2v("emotion2vec/emotion2vec_plus_seed", p),
        "kind": "categorical", "licence": "other (GitHub badge says MIT)",
        "note": "EmoBox academic data",
    },
    "emotion2vec-base": {
        "fn": lambda p: _run_e2v("emotion2vec/emotion2vec_plus_base", p),
        "kind": "categorical", "licence": "other (GitHub badge says MIT)",
        "note": "~42,500 h pseudo-labelled, ~90M params",
    },
    "emotion2vec-large": {
        "fn": lambda p: _run_e2v("emotion2vec/emotion2vec_plus_large", p),
        "kind": "categorical", "licence": "other (GitHub badge says MIT)",
        "note": "~42,500 h pseudo-labelled, ~300M params",
    },
    "wavlm-msp-dim": {
        "fn": run_wavlm, "kind": "dimensional", "licence": "Open RAIL (non-commercial)",
        "note": "INTERSPEECH 2025 challenge winner. MSP-Podcast, LoRA-tuned WavLM-large. "
                "Added after the first pass; NON-COMMERCIAL",
    },
    "audeering-msp-dim": {
        "fn": run_audeering, "kind": "dimensional", "licence": "cc-by-nc-sa-4.0",
        "note": "MSP-Podcast natural speech, valence/arousal/dominance. "
                "NON-COMMERCIAL - deployment blocker if it wins",
    },
}
