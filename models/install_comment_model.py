#!/usr/bin/env python3
"""
install_comment_model.py — install the fine-tuned comment-sentiment model.

`pipeline/comment_module.py` loads `models/comment_sentiment_ft/` when its
`config.json` exists, and otherwise falls back to the public base checkpoint
(`cardiffnlp/twitter-roberta-base-sentiment-latest`), which is measurably weaker
on unseen videos: 69.3% against 78.7% (models/README.md). The weights are
499 MB, too large for an ordinary git repository, so they travel as a release
archive and are installed with this script.

Exact adopted weights (the model every recorded result was produced with):

    python models/install_comment_model.py --url <archive URL>
    python models/install_comment_model.py --from-dir <folder with the four files>

Every file must match `comment_sentiment_ft.sha256`, or nothing is installed.

Retrained from this repository's own labelled data:

    python research/comment_bench/v2/finetune_cardiffnlp.py --install
    python models/install_comment_model.py --from-dir comment_bench/v2/finetuned --retrained

A retrain is not guaranteed to be byte-identical to the adopted model, so its
hashes are not checked and `--check` will not report it as the adopted model.

Maintenance:

    python models/install_comment_model.py --check           # exact model installed?
    python models/install_comment_model.py --pack out.zip    # build the release archive

The installed folder is only ever replaced by a complete copy: the files are
assembled in a temporary folder beside it and moved into place with one rename.
An existing folder is never deleted; with --force it is kept beside the new one
as `comment_sentiment_ft.previous-<timestamp>`.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

MODELS = Path(__file__).resolve().parent
TARGET = MODELS / "comment_sentiment_ft"
MANIFEST = MODELS / "comment_sentiment_ft.sha256"

# Where the release archive is published. Empty until the author uploads it;
# --url always takes precedence.
RELEASE_URL = ""

CHUNK = 1 << 20
DOWNLOAD_TIMEOUT_S = 60


class InstallError(Exception):
    """Nothing was installed; the message says why."""


def expected(manifest: Path = MANIFEST) -> dict[str, str]:
    """{file name: sha256} from a `sha256sum`-format manifest."""
    out: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split()
            out[name] = digest
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def problems(folder: Path, want: dict[str, str]) -> list[str]:
    """Why `folder` is not the adopted model; empty when it is."""
    out = []
    for name, digest in want.items():
        path = folder / name
        if not path.is_file():
            out.append(f"missing {name}")
        elif sha256(path) != digest:
            out.append(f"{name} differs from the adopted model")
    return out


def install_from(folder: Path, *, exact: bool = True, force: bool = False,
                 target: Path = TARGET, manifest: Path = MANIFEST) -> Path:
    """Copy the model files from `folder` into `target`, verified, in one rename."""
    want = expected(manifest)
    folder = Path(folder)
    if exact:
        bad = problems(folder, want)
        if bad:
            raise InstallError(f"{folder} is not the adopted model: " + "; ".join(bad))
    else:
        missing = [name for name in want if not (folder / name).is_file()]
        if missing:
            raise InstallError(f"{folder} is incomplete: missing " + ", ".join(missing))

    if target.exists():
        if exact and not problems(target, want):
            print(f"already installed: {target}")
            return target
        if not force:
            raise InstallError(f"{target} already exists and is not this model; "
                               "rerun with --force to keep it aside and replace it")

    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        for name in want:
            shutil.copy2(folder / name, staging / name)
        if exact and problems(staging, want):
            raise InstallError("the copy did not verify; nothing was installed")
        staging.chmod(0o755)          # mkdtemp makes it owner-only
        if target.exists():
            aside = target.with_name(f"{target.name}.previous-{time.strftime('%Y%m%d-%H%M%S')}")
            target.rename(aside)
            print(f"previous folder kept as {aside}")
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"installed ({'adopted model, verified' if exact else 'retrained, not the adopted weights'}): {target}")
    return target


def unpack(archive: Path, into: Path, names: set[str]) -> None:
    """
    Extract exactly the expected files, by base name, from a zip.

    Only the names in the manifest are written, and each under its base name
    inside `into`, so an archive entry such as `../../x` cannot write outside it.
    """
    with zipfile.ZipFile(archive) as z:
        found: dict[str, zipfile.ZipInfo] = {}
        for info in z.infolist():
            base = Path(info.filename).name
            if info.is_dir() or base not in names:
                continue
            if base in found:
                raise InstallError(f"the archive holds {base} twice")
            found[base] = info
        missing = sorted(names - found.keys())
        if missing:
            raise InstallError("the archive is missing " + ", ".join(missing))
        for base, info in found.items():
            with z.open(info) as src, open(into / base, "wb") as dst:
                shutil.copyfileobj(src, dst, CHUNK)


def download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "brandpulse-model-installer"})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S) as response, \
            open(dest, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            block = response.read(CHUNK)
            if not block:
                break
            out.write(block)
            done += len(block)
            if total:
                print(f"\r  {done / 1e6:7.1f} of {total / 1e6:.1f} MB", end="", flush=True)
    print()


def install_from_url(url: str, *, force: bool = False, target: Path = TARGET,
                     manifest: Path = MANIFEST) -> Path:
    want = expected(manifest)
    with tempfile.TemporaryDirectory(prefix=".download.", dir=target.parent) as tmp:
        archive = Path(tmp) / "model.zip"
        print(f"downloading {url}")
        download(url, archive)
        files = Path(tmp) / "files"
        files.mkdir()
        unpack(archive, files, set(want))
        return install_from(files, exact=True, force=force, target=target, manifest=manifest)


def pack(out: Path, *, source: Path = TARGET, manifest: Path = MANIFEST) -> str:
    """Write the release archive from a verified install; return its sha256."""
    want = expected(manifest)
    bad = problems(source, want)
    if bad:
        raise InstallError(f"{source} is not the adopted model: " + "; ".join(bad))
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as z:
        for name in want:
            z.write(source / name, f"{source.name}/{name}")
    return sha256(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    how = ap.add_mutually_exclusive_group()
    how.add_argument("--url", help="release archive to download and install")
    how.add_argument("--from-dir", type=Path, help="folder holding the four model files")
    how.add_argument("--check", action="store_true", help="is the adopted model installed?")
    how.add_argument("--pack", type=Path, metavar="OUT.zip", help="build the release archive")
    ap.add_argument("--retrained", action="store_true",
                    help="with --from-dir: accept a retrained model without the hash check")
    ap.add_argument("--force", action="store_true",
                    help="replace an existing, different folder (kept aside, never deleted)")
    args = ap.parse_args(argv)

    try:
        if args.check:
            bad = problems(TARGET, expected()) if TARGET.exists() else ["not installed"]
            print("adopted model installed" if not bad else "not the adopted model: " + "; ".join(bad))
            return 0 if not bad else 1
        if args.pack:
            digest = pack(args.pack)
            print(f"wrote {args.pack}  sha256 {digest}")
            return 0
        if args.from_dir:
            install_from(args.from_dir, exact=not args.retrained, force=args.force)
            return 0
        if args.retrained:
            ap.error("--retrained goes with --from-dir")
        url = args.url or RELEASE_URL
        if not url:
            ap.error("no archive URL: pass --url (RELEASE_URL is not set yet), or use --from-dir")
        install_from_url(url, force=args.force)
        return 0
    except InstallError as exc:
        print(f"not installed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
