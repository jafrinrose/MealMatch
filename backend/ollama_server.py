"""Keep the local Ollama server available to the text and photo models.

Every AI feature except speech goes through Ollama. When its server was never
started, or was quit while MealMatch was running, each feature used to fail
until someone restarted it by hand. A local server is now started on demand
(`ollama serve`) and the request is tried again once.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from urllib.parse import urlsplit

import requests

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
START_WAIT_SECONDS = float(os.getenv("MEALMATCH_OLLAMA_START_SECONDS", "20"))
_start_lock = threading.Lock()


def server_root(endpoint: str) -> str:
    """http://127.0.0.1:11434/api/chat -> http://127.0.0.1:11434"""
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.netloc}"


def is_running(endpoint: str, timeout: float = 2) -> bool:
    try:
        return requests.get(f"{server_root(endpoint)}/api/version", timeout=timeout).ok
    except requests.RequestException:
        return False


def installed_digests(endpoint: str) -> dict[str, str]:
    """Installed tag ("llama3.2:3b") -> manifest digest. Raises when the server cannot be reached."""
    response = requests.get(f"{server_root(endpoint)}/api/tags", timeout=5)
    response.raise_for_status()
    return {str(item.get("name", "")): str(item.get("digest", "")) for item in response.json().get("models", [])}


def installed_models(endpoint: str) -> set[str]:
    """Installed tags; empty when the server cannot be reached."""
    try:
        return set(installed_digests(endpoint))
    except requests.RequestException:
        return set()


def full_tag(name: str) -> str:
    return name if ":" in name else f"{name}:latest"


def _ollama_binary() -> str | None:
    candidates = [shutil.which("ollama"), "/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"]
    return next((path for path in candidates if path and os.access(path, os.X_OK)), None)


def ensure_running(endpoint: str) -> bool:
    """True once the server answers. A local server that is down is started first.

    A remote server (MEALMATCH_OLLAMA_*_URL pointing at another computer) is
    never started from here.
    """
    if is_running(endpoint):
        return True
    parts = urlsplit(endpoint)
    binary = _ollama_binary()
    if (parts.hostname or "") not in LOCAL_HOSTS or not binary:
        return False
    with _start_lock:
        if is_running(endpoint):
            return True
        environment = {**os.environ, "OLLAMA_HOST": f"{parts.hostname}:{parts.port or 11434}"}
        subprocess.Popen(
            [binary, "serve"],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # keeps running when the backend reloads or stops
        )
        deadline = time.monotonic() + START_WAIT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if is_running(endpoint):
                return True
    return False
