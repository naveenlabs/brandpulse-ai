"""
candidates.py — every facial-emotion candidate behind one interface.

The bench separates two failures that `pipeline/visual_module.py` currently
couples, because `PROTOTYPE_FINDINGS.md` shows they are independent:

  detection      §9 found 15 of 77 segments where DeepFace reported a confident
                 emotion on frames containing no human being at all, and §12D
                 reproduced it on a second video at 34 of 375 detections.
  classification §12D found 37.2 per cent "sad" on 341 genuine faces of a speaker
                 the author verified as never sad.

Swapping the emotion model cannot fix the first, and swapping the detector cannot
fix the second, so they are benched separately and every classifier is scored on
**identical crops** produced by one fixed detector. Any difference between two
classifiers is then a property of the classifier.

Label mapping — fixed before any candidate was scored
-----------------------------------------------------
Candidates disagree on taxonomy (7-class FER2013, 8-class AffectNet with
contempt, and one continuous valence output), so everything is mapped to the same
three classes the rest of this project uses:

    NEGATIVE  anger/angry, sad/sadness, disgust, fear, contempt
    NEUTRAL   neutral
    POSITIVE  happy/happiness, surprise

Anything else is recorded as unmapped and **never silently coerced to NEUTRAL** —
a model that emits a class this bench cannot place must show up as a gap, not as
a free neutral prediction.

`surprise -> POSITIVE` is a judgement call and is declared as one. It is the same
call `vocal_bench/CANDIDATE_MODELS.md` §3 made, for the same reason: in product
review footage surprise is overwhelmingly delight rather than alarm. The count of
surprise predictions is reported separately so the effect is visible, and the
sensitivity check with surprise mapped to NEUTRAL is reported whenever it changes
a conclusion.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
VENDOR = BENCH / "vendor"

NEGATIVE, NEUTRAL, POSITIVE = "NEGATIVE", "NEUTRAL", "POSITIVE"

THREE_CLASS: dict[str, str] = {
    "angry": NEGATIVE, "anger": NEGATIVE,
    "sad": NEGATIVE, "sadness": NEGATIVE,
    "disgust": NEGATIVE, "disgusted": NEGATIVE,
    "fear": NEGATIVE, "fearful": NEGATIVE,
    "contempt": NEGATIVE,
    "neutral": NEUTRAL,
    "happy": POSITIVE, "happiness": POSITIVE,
    "surprise": POSITIVE, "surprised": POSITIVE,
}

# The alternative reading of the one judgement call above, used for the
# sensitivity check. Nothing else differs.
THREE_CLASS_SURPRISE_NEUTRAL = {**THREE_CLASS, "surprise": NEUTRAL, "surprised": NEUTRAL}


def to_three(label: str | None, mapping: dict[str, str] | None = None) -> str | None:
    """Map a model's own label to the three-class scale, or None if unmapped."""
    if not isinstance(label, str) or not label.strip():
        return None
    return (mapping or THREE_CLASS).get(label.strip().lower())


# ── Face detectors ────────────────────────────────────────────────────────────
#
# Every backend DeepFace 0.0.100 exposes that loads in this venv. `centerface` is
# excluded: it raises `UnboundLocalError: cannot access local variable 'boxes_np'`
# inside deepface's own wrapper on frames with no detection, which is an upstream
# defect, not a property of the detector. `mediapipe` and `dlib` are excluded
# because neither library is installed and neither is worth a new dependency when
# five backends already run. Both exclusions are recorded rather than hidden.

DETECTORS: dict[str, dict] = {
    "opencv":     {"family": "Haar cascade",   "incumbent": True,
                   "note": "deployed in visual_module.py; chosen for speed at 1 fps"},
    "ssd":        {"family": "ResNet-10 SSD",  "incumbent": False,
                   "note": "OpenCV DNN face detector, 300x300 input"},
    "mtcnn":      {"family": "MTCNN cascade",  "incumbent": False,
                   "note": "three-stage CNN cascade"},
    "retinaface": {"family": "RetinaFace",     "incumbent": False,
                   "note": "single-stage detector with landmark supervision"},
    "yunet":      {"family": "YuNet",          "incumbent": False,
                   "note": "OpenCV Zoo 2023-03 ONNX model, designed for edge use"},
    "yolov8n":    {"family": "YOLOv8n-face",   "incumbent": False,
                   "note": "face-finetuned YOLOv8 nano"},
}

EXCLUDED_DETECTORS = {
    "centerface": "deepface 0.0.100 raises UnboundLocalError ('boxes_np') on frames "
                  "with no detection — upstream defect, not a detector property",
    "mediapipe":  "library not installed; five backends already cover the comparison",
    "dlib":       "library not installed; five backends already cover the comparison",
    "fastmtcnn":  "facenet-pytorch not installed; plain mtcnn is benched instead",
}

# The detector used to cut the crops every classifier sees. Fixed here so the
# classification bench measures classifiers and nothing else.
#
# It is deliberately NOT the incumbent: opencv's own detection errors would then
# contaminate every classifier equally and hide the classifier comparison behind
# them. Among the alternatives, retinaface was chosen **a priori**, before Bench A
# ran, because PROTOTYPE_FINDINGS.md §9's own proposed fix names it and because it
# is the strongest-precision option in the FER literature. Whether that a-priori
# choice was right is checked against Bench A's measured result afterwards and
# reported in FACIAL_MODEL_ANALYSIS.md either way. Stating the order matters:
# picking the crop detector after seeing which one wins would be selection on the
# outcome.
CROP_DETECTOR = "retinaface"


def detect(frame_path: str | Path, backend: str, *, align: bool = False) -> list[dict]:
    """
    Run one detector over one frame.

    Returns a list of {box, confidence, crop} for every region the backend
    returns with confidence > 0. DeepFace with enforce_detection=False returns a
    single whole-frame region with confidence 0 when it finds nothing; that is a
    non-detection and is filtered out here rather than counted as a face.

    Never raises: a backend that fails on a frame yields [] and the caller records
    it, matching the graceful-degradation rule the pipeline follows.
    """
    from deepface import DeepFace

    try:
        regions = DeepFace.extract_faces(
            img_path=str(frame_path), detector_backend=backend,
            enforce_detection=False, align=align,
        )
    except Exception:                                   # noqa: BLE001
        return []

    out = []
    for r in regions:
        conf = float(r.get("confidence", 0.0) or 0.0)
        if conf <= 0.0:
            continue
        fa = r.get("facial_area", {}) or {}
        out.append({
            "box": [int(fa.get("x", 0)), int(fa.get("y", 0)),
                    int(fa.get("w", 0)), int(fa.get("h", 0))],
            "confidence": round(conf, 6),
            "crop": r.get("face"),          # float array in [0,1], RGB
        })
    return out


# ── Emotion classifiers ───────────────────────────────────────────────────────

@dataclass
class Classifier:
    """One emotion candidate. Loads lazily so an unused candidate costs nothing."""
    name: str
    source: str                       # where the weights come from
    licence: str
    training_data: str
    published: str                    # the number its own card/paper reports
    n_classes: int
    incumbent: bool = False
    extras: tuple[str, ...] = ()      # non-categorical outputs, e.g. valence
    _loader: Callable[[], Callable] | None = field(default=None, repr=False)
    _fn: Callable | None = field(default=None, repr=False)

    def predict(self, crop_rgb_uint8) -> dict:
        """
        Classify one face crop.

        crop_rgb_uint8 : HxWx3 uint8 RGB face crop, identical across candidates.

        Returns {"raw": {label: prob}, "top": label, "three": CLASS|None,
                 "extra": {...}}. Never raises; on failure returns top=None so a
        single bad crop cannot abort a sweep.
        """
        if self._fn is None:
            self._fn = self._loader()
        try:
            raw, extra = self._fn(crop_rgb_uint8)
        except Exception as exc:                        # noqa: BLE001
            return {"raw": {}, "top": None, "three": None, "extra": {},
                    "error": f"{type(exc).__name__}: {exc}"}
        if not raw:
            return {"raw": {}, "top": None, "three": None, "extra": extra}
        top = max(raw, key=lambda k: raw[k])
        return {"raw": {k: round(float(v), 6) for k, v in raw.items()},
                "top": top, "three": to_three(top), "extra": extra}


def _hf_loader(model_id: str, processor_cls: str | None = None,
               label_override: list[str] | None = None):
    """Build a HuggingFace image classifier callable."""
    def load():
        import torch
        from transformers import AutoModelForImageClassification
        model = AutoModelForImageClassification.from_pretrained(model_id)
        model.eval()
        if processor_cls is None:
            from transformers import AutoImageProcessor
            proc = AutoImageProcessor.from_pretrained(model_id)
        else:
            # Two candidates ship a preprocessor_config.json transformers 5.x
            # cannot read: HardlyHumans has do_resize set to a model name instead
            # of a boolean and no image_processor_type at all, and Tanneru names
            # the removed "BeitFeatureExtractor". Both are built explicitly here
            # with the standard settings their own config records (224px, mean
            # and std 0.5). The workaround is declared in FACIAL_MODEL_ANALYSIS.md
            # because a broken published preprocessor is itself evidence about a
            # candidate's provenance.
            import transformers
            cls = getattr(transformers, processor_cls)
            proc = cls(do_resize=True, size={"height": 224, "width": 224},
                       do_rescale=True, do_normalize=True,
                       image_mean=[0.5, 0.5, 0.5], image_std=[0.5, 0.5, 0.5])
        if label_override is not None:
            # This model publishes LABEL_0..LABEL_n in config.json and names the
            # real class order only in its README. The order is taken from there
            # and is **verified empirically** by report_bench.label_order_check()
            # before any score is reported, because a card can be wrong and a
            # silently wrong permutation would invalidate every number it produces.
            if len(label_override) != model.config.num_labels:
                raise ValueError(
                    f"{model_id}: label_override has {len(label_override)} entries, "
                    f"model has {model.config.num_labels} classes")
            id2label = dict(enumerate(label_override))
        else:
            id2label = model.config.id2label

        def fn(crop):
            inputs = proc(images=crop, return_tensors="pt")
            with torch.no_grad():
                logits = model(**inputs).logits[0]
            probs = torch.softmax(logits, dim=-1).numpy()
            raw = {str(id2label[i]).lower(): float(probs[i]) for i in range(len(probs))}
            return raw, {}
        return fn
    return load


def _deepface_loader():
    """
    The incumbent's emotion head, called on a crop the bench supplies.

    Two details have to match `pipeline/visual_module.py` exactly or the incumbent
    would be benched as something it is not:

      - `EmotionClient.predict` does its own greyscale conversion and resize to
        48x48 internally, so it is handed the colour crop, not a pre-reduced one.
      - It converts with `cv2.COLOR_BGR2GRAY`, and the pipeline reaches it through
        `DeepFace.analyze`, which reads frames with OpenCV in BGR order. The bench
        supplies RGB crops for every candidate, so this one is flipped back to BGR
        first. The channel order changes the greyscale weights, and getting it
        wrong would quietly bench a different model.

    `run_classify.py --anchor` verifies the whole path end to end by reproducing
    the saved run's per-segment labels, so this is checked rather than asserted.
    """
    def load():
        import numpy as np
        from deepface import DeepFace
        model = DeepFace.build_model("Emotion", task="facial_attribute")
        labels = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

        def fn(crop):
            bgr = np.ascontiguousarray(crop, dtype=np.uint8)[:, :, ::-1]
            preds = np.asarray(model.predict(np.ascontiguousarray(bgr))).reshape(-1)
            total = float(preds.sum()) or 1.0
            return {labels[i]: float(preds[i]) / total for i in range(len(labels))}, {}
        return fn
    return load


def _dan_loader():
    """DAN AffectNet-8, vendored. Class order taken from the repo's own demo.py."""
    def load():
        import sys
        import numpy as np
        import torch
        from PIL import Image
        from torchvision import transforms
        sys.path.insert(0, str(VENDOR / "dan"))
        from dan import DAN                                   # noqa: E402

        labels = ["neutral", "happy", "sad", "surprise",
                  "fear", "disgust", "anger", "contempt"]
        ckpt_path = VENDOR / "dan" / "affectnet8_epoch5_acc0.6209.pth"
        model = DAN(num_head=4, num_class=8, pretrained=False)
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        missing, unexpected = model.load_state_dict(ckpt["model_state_dict"], strict=False)
        if missing or unexpected:
            raise RuntimeError(
                f"DAN checkpoint did not load cleanly: missing={list(missing)[:5]} "
                f"unexpected={list(unexpected)[:5]}")
        model.eval()
        tf = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])

        def fn(crop):
            t = tf(Image.fromarray(crop)).unsqueeze(0)
            with torch.no_grad():
                out, _, _ = model(t)
            probs = torch.softmax(out[0], dim=-1).numpy()
            return {labels[i]: float(probs[i]) for i in range(len(labels))}, {}
        return fn
    return load


def _emotiefflib_loader(model_name: str):
    """
    EmotiEffNet (HSEmotion / EmotiEffLib), AffectNet-8, via the ONNX engine.

    Why ONNX and not the `hsemotion` package. `hsemotion` 0.3.0 ships whole
    pickled `timm` EfficientNet modules. Unpickling one against timm 1.0.29 raises
    `AttributeError: 'DepthwiseSeparableConv' object has no attribute 'conv_s2d'`,
    because the pickle carries a class reference and timm's internals moved. The
    same weights are published as ONNX by the maintained successor library, which
    has no such coupling. Measured here on 03 Sep 2026; recorded because "the
    published pip package cannot load its own weights on a current stack" is a
    real deployability fact about a candidate, not an incidental setup problem.

    The `_va_mtl` checkpoint appends valence and arousal to the class scores. They
    are returned in `extra` rather than folded into the categorical output, so the
    dimensional reading can be scored as its own arm — the same move that turned
    the vocal channel around (`vocal_bench/VOCAL_MODEL_ANALYSIS.md` §4-5).
    """
    # Class order as published in the library's own source. Verified empirically
    # rather than trusted: the loader asserts that the label the library returns
    # for a crop is the class this order puts at the argmax, so a reordering
    # upstream fails loudly instead of silently permuting every prediction.
    AFFECTNET8 = ["anger", "contempt", "disgust", "fear",
                  "happiness", "neutral", "sadness", "surprise"]

    def load():
        import numpy as np
        from emotiefflib.facial_analysis import EmotiEffLibRecognizer
        rec = EmotiEffLibRecognizer(engine="onnx", model_name=model_name, device="cpu")
        is_mtl = "_mtl" in model_name

        def fn(crop):
            label, scores = rec.predict_emotions(crop, logits=True)
            scores = np.asarray(scores, dtype="float64").reshape(-1)
            extra = {}
            if is_mtl:
                extra = {"valence": float(scores[-2]), "arousal": float(scores[-1])}
                scores = scores[:-2]
            if len(scores) != len(AFFECTNET8):
                raise RuntimeError(
                    f"{model_name}: expected {len(AFFECTNET8)} class scores, got {len(scores)}")
            claimed = (label[0] if isinstance(label, (list, tuple)) else label)
            expected = AFFECTNET8[int(np.argmax(scores))]
            if str(claimed).strip().lower() != expected:
                raise RuntimeError(
                    f"{model_name}: library reports '{claimed}' but this class order "
                    f"puts '{expected}' at the argmax — the order has changed")
            e = np.exp(scores - scores.max())
            probs = e / e.sum()
            return {AFFECTNET8[i]: float(probs[i]) for i in range(len(probs))}, extra
        return fn
    return load


# Tanneru's config.json carries LABEL_0..LABEL_6. Its model card lists the class
# order explicitly ("The model predicts the following 7 basic emotion classes:")
# and that order is used here. run_classify.py re-checks it against the other
# candidates before scoring, so a wrong card fails loudly.
TANNERU_LABELS = ["anger", "disgust", "fear", "happy", "neutral", "sad", "surprise"]

CLASSIFIERS: dict[str, Classifier] = {
    "deepface_fer": Classifier(
        name="deepface_fer", source="deepface 0.0.100 built-in Emotion model",
        licence="MIT (deepface)", training_data="FER-2013",
        published="57.4% (author's own figure, sefiks.com, 2018 model)",
        n_classes=7, incumbent=True, _loader=_deepface_loader()),

    "trpakov_vit": Classifier(
        name="trpakov_vit", source="trpakov/vit-face-expression",
        licence="apache-2.0", training_data="FER-2013",
        published="71.16% test accuracy (model card)",
        n_classes=7, _loader=_hf_loader("trpakov/vit-face-expression")),

    "motheecreator_vit": Classifier(
        name="motheecreator_vit", source="motheecreator/vit-Facial-Expression-Recognition",
        licence="not declared on the model card",
        training_data="FER-2013 + MMI + AffectNet",
        published="84.34% eval accuracy (model card)",
        n_classes=7, _loader=_hf_loader("motheecreator/vit-Facial-Expression-Recognition")),

    "dima806_vit": Classifier(
        name="dima806_vit", source="dima806/facial_emotions_image_detection",
        licence="apache-2.0", training_data="not stated on the model card",
        published="90.92% accuracy (model card)",
        n_classes=7, _loader=_hf_loader("dima806/facial_emotions_image_detection")),

    "hardlyhumans_vit": Classifier(
        name="hardlyhumans_vit", source="HardlyHumans/Facial-expression-detection",
        licence="not declared on the model card",
        training_data="FER-2013 + AffectNet",
        published="92.2% accuracy (model card)",
        n_classes=8, _loader=_hf_loader("HardlyHumans/Facial-expression-detection",
                                        processor_cls="ViTImageProcessor")),

    "tanneru_beit_large": Classifier(
        name="tanneru_beit_large",
        source="Tanneru/Facial-Emotion-Detection-FER-RAFDB-AffectNet-BEIT-Large",
        licence="apache-2.0", training_data="FER-2013 + RAF-DB + AffectNet",
        published="73.57% accuracy, macro-F1 0.6965 (model card)",
        n_classes=7,
        _loader=_hf_loader("Tanneru/Facial-Emotion-Detection-FER-RAFDB-AffectNet-BEIT-Large",
                           processor_cls="BeitImageProcessor",
                           label_override=TANNERU_LABELS)),

    "dan_affectnet8": Classifier(
        name="dan_affectnet8", source="yaoing/DAN, released AffectNet-8 checkpoint",
        licence="MIT", training_data="AffectNet-8",
        published="62.09% AffectNet-8 (repository README)",
        n_classes=8, _loader=_dan_loader()),

    "emotieffnet_b0_va": Classifier(
        name="emotieffnet_b0_va", source="emotiefflib 1.1.1 (ONNX), enet_b0_8_va_mtl",
        licence="apache-2.0 (library)", training_data="VGGFace2 then AffectNet, multi-task",
        published="61.93% AffectNet-8, 64.94% AffectNet-7 (repository README)",
        n_classes=8, extras=("valence", "arousal"),
        _loader=_emotiefflib_loader("enet_b0_8_va_mtl")),

    "emotieffnet_b2": Classifier(
        name="emotieffnet_b2", source="emotiefflib 1.1.1 (ONNX), enet_b2_8",
        licence="apache-2.0 (library)", training_data="VGGFace2 then AffectNet",
        published="63.03% AffectNet-8, 66.29% AffectNet-7 (repository README)",
        n_classes=8, _loader=_emotiefflib_loader("enet_b2_8")),
}

INCUMBENT = "deepface_fer"
