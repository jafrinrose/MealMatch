"""Check or download every pretrained model MealMatch uses, at the evaluated versions.

Versions are pinned in model_versions.py. Ollama models are pulled only when
missing: pulling an installed tag again could replace it with a newer upstream
build, so each installed model is instead checked against its recorded digest.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess

import requests

from model_versions import (
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    MODEL_CACHE,
    OLLAMA_MODELS,
    TESTED_OLLAMA_VERSION,
    WHISPER_REVISIONS,
)
from ollama_server import full_tag, installed_digests

OLLAMA_URL = "http://127.0.0.1:11434"
WHISPER_MODEL = "small.en"


def download_whisper(local_only: bool) -> None:
    from faster_whisper.utils import download_model

    download_model(
        WHISPER_MODEL,
        cache_dir=str(MODEL_CACHE / "whisper"),
        revision=WHISPER_REVISIONS[WHISPER_MODEL],
        local_files_only=local_only,
    )


def download_embedding_model(local_only: bool) -> None:
    from huggingface_hub import snapshot_download

    # Only the PyTorch weights, configuration and vocabulary: the repository also
    # holds ONNX, OpenVINO, TensorFlow and Rust copies (about 800 MB) the app never loads.
    snapshot_download(
        EMBEDDING_MODEL,
        revision=EMBEDDING_REVISION,
        cache_dir=str(MODEL_CACHE / "huggingface"),
        allow_patterns=["*.json", "model.safetensors", "vocab.txt"],
        local_files_only=local_only,
    )


def check_ollama_models(installed: dict[str, str], wanted: dict[str, str]) -> tuple[list[str], list[str]]:
    """Missing tags, and installed tags whose build differs from the evaluated one."""
    missing = [name for name in wanted if full_tag(name) not in installed]
    different = [name for name, digest in wanted.items() if full_tag(name) in installed and installed[full_tag(name)] != digest]
    return missing, different


def check() -> bool:
    ready = True
    if not shutil.which("ollama"):
        print("Ollama is not installed. Install it from https://ollama.com/download")
        return False
    try:
        installed = installed_digests(OLLAMA_URL)
        version = requests.get(f"{OLLAMA_URL}/api/version", timeout=5).json().get("version", "unknown")
    except requests.RequestException:
        print("Ollama is installed but its local server is not running. Start Ollama or run 'ollama serve'.")
        return False
    if version != TESTED_OLLAMA_VERSION:
        print(f"Note: Ollama {version} is installed; the evaluations used {TESTED_OLLAMA_VERSION}. Answers and timings may differ slightly.")

    missing, different = check_ollama_models(installed, OLLAMA_MODELS)
    if missing:
        print("Missing Ollama models: " + ", ".join(missing))
        ready = False
    for name in different:
        print(f"{name} is a different build from the evaluated one (expected digest {OLLAMA_MODELS[name][:12]}, "
              f"found {installed[full_tag(name)][:12]}). The upstream tag has changed, so results may differ from docs/.")
        ready = False
    for label, download in (("Whisper " + WHISPER_MODEL, download_whisper), (EMBEDDING_MODEL, download_embedding_model)):
        try:
            download(local_only=True)
        except Exception:
            print(f"{label} is not downloaded at the pinned version.")
            ready = False

    if ready:
        print("Ollama and all required models are ready, at the evaluated versions.")
    return ready


def install() -> bool:
    if not shutil.which("ollama"):
        print("Install Ollama from https://ollama.com/download first.")
        return False
    try:
        installed = installed_digests(OLLAMA_URL)
    except requests.RequestException:
        print("Start Ollama (or run 'ollama serve') first.")
        return False
    for model in OLLAMA_MODELS:
        if full_tag(model) in installed:
            continue
        print(f"Pulling {model}...")
        if subprocess.run(["ollama", "pull", model], check=False).returncode:
            return False
    print(f"Downloading Whisper {WHISPER_MODEL} and {EMBEDDING_MODEL} into {MODEL_CACHE}...")
    download_whisper(local_only=False)
    download_embedding_model(local_only=False)
    return check()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check only; do not download models")
    args = parser.parse_args()
    # Checked before any Ollama pull, so a run from the wrong Python stops at
    # once instead of after several gigabytes of downloads.
    missing = [name for name in ("faster_whisper", "huggingface_hub") if importlib.util.find_spec(name) is None]
    if missing:
        print("Missing Python packages: " + ", ".join(missing) + ". Activate the backend environment "
              "(source backend/venv/bin/activate) and install backend/requirements.txt, then run this again.")
        raise SystemExit(1)
    success = check() if args.check else install()
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
