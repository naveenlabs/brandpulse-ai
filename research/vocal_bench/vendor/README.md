# vendor/

Third-party code required to run one bench candidate. Not written for this project.

## vox-profile-release

Needed by `tiantiaf/wavlm-large-msp-podcast-emotion-dim` (the INTERSPEECH 2025
Speech Emotion Challenge winner). Its HuggingFace repo ships only `config.json`
and `model.safetensors`; the class that assembles them lives here.

| | |
|---|---|
| Source | https://github.com/tiantiaf0627/vox-profile-release |
| Commit | `85100e60844a3f324a139e24fb9225aa6d8e45d1` |
| Retrieved | 02 Sep 2026 |
| Licence | Responsible AI Source Code License v1.1 |

**Why it is vendored rather than pip-installed.** Its `setup.py` pins
`nvidia-cublas-cu12==12.1.3.1` and other CUDA wheels that do not exist for macOS,
so `pip install git+...` fails on this machine. Only two modules are actually
imported (`src/model/emotion/wavlm_emotion_dim.py` and its dependencies), and
pinning the commit here makes the bench reproducible without a working CUDA
install. The one extra PyPI dependency it needs, `loralib`, is installed normally.

**Not modified.** The tree is byte-identical to that commit with `.git` removed.

To refresh:

    git clone https://github.com/tiantiaf0627/vox-profile-release.git
    git -C vox-profile-release checkout 85100e60844a3f324a139e24fb9225aa6d8e45d1
