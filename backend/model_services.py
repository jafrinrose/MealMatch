"""Lazy local inference services for MealMatch's image and audio models."""

from __future__ import annotations

import base64
import io
import json
import os
import threading
import time
from typing import Iterator

import requests
from PIL import Image, ImageOps

from model_versions import MODEL_CACHE, WHISPER_REVISIONS
from ollama_server import ensure_running
from vision_suggestions import (
    SuggestionMerger,
    clean_qwen_items,
    is_repeating,
    salvage_items,
    vision_model_display_name,
)


MODEL_ROOT = MODEL_CACHE
MODEL_ROOT.mkdir(exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODEL_ROOT / "huggingface"))
WHISPER_MODEL_NAME = os.getenv("MEALMATCH_WHISPER_MODEL", "small.en")
VISION_LANGUAGE_MODEL_NAME = os.getenv("MEALMATCH_VISION_LANGUAGE_MODEL", "qwen2.5vl:3b")
OLLAMA_CHAT_URL = os.getenv("MEALMATCH_OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
VISION_TIMEOUT_SECONDS = int(os.getenv("MEALMATCH_VISION_TIMEOUT_SECONDS", "300"))
VISION_CONTEXT_TOKENS = int(os.getenv("MEALMATCH_VISION_CONTEXT_TOKENS", "8192"))
# 1600px is the evaluated configuration (docs/vision-model-evaluation.md); scan time is
# dominated by model loading and output length, not by this resolution.
VISION_MAX_IMAGE_SIDE = int(os.getenv("MEALMATCH_VISION_MAX_IMAGE_SIDE", "1600"))
# How long the model (about 4.6 GB) stays in memory after the last scan. Loading it
# took 1.4 s on the M4 Pro once its files were cached, and the app starts loading it
# when the Photo tab opens, so a short hold costs little time.
VISION_KEEP_ALIVE = os.getenv("MEALMATCH_VISION_KEEP_ALIVE", "5m")
# Each item costs about 50-55 output tokens. The earlier 1200 cut crowded photos
# off at about 22 items; 2048 leaves room for about 35, and a looping answer is
# stopped early instead (vision_suggestions.is_repeating).
VISION_MAX_OUTPUT_TOKENS = int(os.getenv("MEALMATCH_VISION_MAX_OUTPUT_TOKENS", "2048"))
# Four overlapping close-ups find small and labelled items a crowded photo leaves
# out, but on the frozen test they added 25 correct and 189 wrong items and cost
# four more model runs. They therefore run only when the user asks ("Look closer").
# Set to 1 to run them automatically after every whole photo, as in iteration 1.
VISION_CLOSE_UPS = os.getenv("MEALMATCH_VISION_CLOSE_UPS", "0") == "1"
VISION_CLOSE_UP_OVERLAP = 0.15
OLLAMA_GENERATE_URL = OLLAMA_CHAT_URL.replace("/api/chat", "/api/generate")

_speech_model = None
_speech_model_lock = threading.Lock()


def _json_object(value: str) -> dict:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            parsed = json.loads(value[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def build_pantry_vision_prompt() -> str:
    """Build the fixed prompt shared by production and household evaluation."""
    return """
You are analysing one household fridge, pantry, cupboard, shelf, drawer, or
grocery-table photograph for an inventory application. Systematically inspect
the entire image from top left to bottom right and list every reliably visible
food, drink, or cooking ingredient, whether packaged or unpackaged.

Use a plain ingredient name such as "milk", "broccoli", "eggs", or "rice".
Read visible packaging text when it helps identify the food, but include a brand
only when the generic food cannot be stated clearly. Count separate visible
items only when reasonably possible; otherwise use quantity 1 and the most
appropriate container unit.

Return each ingredient concept once, even when several containers of it are
visible. Never combine multiple foods in one ingredient string: lemon, lime and
orange must be three separate items. Prefer a useful pantry concept over brand
or marketing detail: use "chocolate syrup" instead of a brand name, "pasta"
instead of a pasta shape when uncertain, and "sausage" instead of a flavour.

Never include soap, detergent, cleaners, toiletries, medicines, paper products,
bags, shelves, appliances, cookware, or containers whose contents cannot be
identified. Do not infer hidden contents, invent food based on typical fridge
contents, or identify something that is too occluded or blurry to support. Do
not return vague guesses such as "canned food", "dairy product", "sauces" or
"packaged goods" when the actual ingredient cannot be identified.

Return JSON only:
{
  "items": [
    {
      "ingredient": "plain food name",
      "quantity": 1,
      "unit": "piece, box, loaf, bottle, can, jar, carton, packet, or bag",
      "category": "produce, dairy, protein, grains, beverage, condiment, or other",
      "visible_text": "short label text supporting the identification, or empty",
      "confidence": 0.0
    }
  ]
}
Confidence must be between 0 and 1. Return an empty items array when no food is
reliably visible. Do not return commentary or Markdown.
""".strip()


def _encode_image(image: Image.Image) -> str:
    image = image.copy()
    image.thumbnail((VISION_MAX_IMAGE_SIDE, VISION_MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def open_photo(image_path: str) -> Image.Image:
    with Image.open(image_path) as source:
        return ImageOps.exif_transpose(source).convert("RGB")


def encode_vision_image(image_path: str) -> str:
    """Normalize orientation and cap resolution for repeatable local inference."""
    return _encode_image(open_photo(image_path))


def photo_close_ups(image: Image.Image, overlap: float = VISION_CLOSE_UP_OVERLAP) -> list[Image.Image]:
    """Four overlapping quarters, so food on a boundary is whole in at least one."""
    width, height = image.size
    tile_width, tile_height = int(width * (0.5 + overlap / 2)), int(height * (0.5 + overlap / 2))
    return [
        image.crop((left, top, left + tile_width, top + tile_height))
        for top in (0, height - tile_height)
        for left in (0, width - tile_width)
    ]


def ask_vision_model(encoded_image: str, model_name: str = VISION_LANGUAGE_MODEL_NAME) -> dict:
    """One streamed answer, keeping every complete item.

    Streaming lets a looping answer be stopped as soon as it only repeats
    itself; closing the connection stops Ollama generating. done_reason is
    "length" when the output limit cut the answer off.
    """
    started = time.perf_counter()
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": build_pantry_vision_prompt(),
                "images": [encoded_image],
            }
        ],
        "stream": True,
        "format": "json",
        "keep_alive": VISION_KEEP_ALIVE,
        "options": {
            "temperature": 0.1,
            "num_ctx": VISION_CONTEXT_TOKENS,
            "num_predict": VISION_MAX_OUTPUT_TOKENS,
        },
    }
    try:
        response = requests.post(OLLAMA_CHAT_URL, json=payload, stream=True, timeout=VISION_TIMEOUT_SECONDS)
    except requests.ConnectionError:
        # Ollama was not running: start it (when local) and ask once more.
        if not ensure_running(OLLAMA_CHAT_URL):
            raise
        response = requests.post(OLLAMA_CHAT_URL, json=payload, stream=True, timeout=VISION_TIMEOUT_SECONDS)
    raw, done_reason, output_tokens = "", "", 0
    with response:
        if not response.ok:
            detail = response.text.strip()[:1000] or response.reason
            raise RuntimeError(f"Ollama returned HTTP {response.status_code}: {detail}")
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get("error"):
                raise RuntimeError(f"Ollama: {chunk['error']}")
            piece = chunk.get("message", {}).get("content", "")
            raw += piece
            output_tokens += 1
            if chunk.get("done"):
                done_reason = chunk.get("done_reason", "stop")
                output_tokens = chunk.get("eval_count", output_tokens)
                break
            if "}" in piece and is_repeating(salvage_items(raw)):
                done_reason = "repeating"
                break
            if time.perf_counter() - started > VISION_TIMEOUT_SECONDS:
                done_reason = "timeout"
                break
    return {
        "items": salvage_items(raw),
        "done_reason": done_reason or "incomplete",
        "output_tokens": output_tokens,
        "seconds": round(time.perf_counter() - started, 2),
    }


def identify_foods_with_qwen(
    image_path: str,
    model_name: str = VISION_LANGUAGE_MODEL_NAME,
) -> list[dict]:
    """Extract visible food from the whole photo in one pass.

    The result remains a suggestion: the mandatory confirmation screen is the
    only route from model output to persistent pantry state.
    """
    answer = ask_vision_model(encode_vision_image(image_path), model_name)
    cleaned = clean_qwen_items(answer["items"], model_name)
    for index, item in enumerate(cleaned, start=1):
        item["detection_id"] = f"suggestion-{index}"
    return sorted(cleaned, key=lambda item: item.get("confidence", 0), reverse=True)


def scan_pantry_photo(
    image: Image.Image,
    model_name: str = VISION_LANGUAGE_MODEL_NAME,
    close_ups: bool = VISION_CLOSE_UPS,
    earlier: list[dict] | None = None,
) -> Iterator[dict]:
    """Scan the whole photo, then any close-ups, yielding every pass's new suggestions.

    Passing `earlier`, the suggestions of a finished whole-photo pass, runs only
    the close-ups ("Look closer") and never repeats a food already suggested.
    A failed whole-photo pass raises; a failed close-up is reported and skipped.
    """
    views = [] if earlier is not None else [("whole photo", image)]
    if close_ups or earlier is not None:
        views += [(f"close-up {number}", tile) for number, tile in enumerate(photo_close_ups(image), start=1)]
    first = 1 if earlier is None else 2
    merger = SuggestionMerger(earlier or [])
    for number, (label, view) in enumerate(views, start=first):
        result = {"pass": label, "pass_number": number, "passes": first - 1 + len(views), "detections": [], "alternatives": []}
        try:
            answer = ask_vision_model(_encode_image(view), model_name)
        except Exception as error:
            if number == 1:
                raise RuntimeError(
                    f"{vision_model_display_name(model_name)} pantry-photo analysis was unavailable: {error}. "
                    f"Ensure Ollama is running and '{model_name}' is installed."
                ) from error
            yield {**result, "error": str(error)[:500]}
            continue
        cleaned = sorted(clean_qwen_items(answer["items"], model_name), key=lambda item: item["confidence"], reverse=True)
        new, alternatives = merger.add(cleaned)
        yield {
            **result,
            "detections": new,
            "alternatives": alternatives,
            "returned": len(cleaned),
            "done_reason": answer["done_reason"],
            "output_tokens": answer["output_tokens"],
            "seconds": answer["seconds"],
        }


def warm_vision_model(model_name: str = VISION_LANGUAGE_MODEL_NAME) -> bool:
    """Load the vision model into memory ahead of a scan (Ollama loads on an empty prompt).

    num_ctx must match the scan request, or Ollama reloads the model for the scan.
    """
    if not ensure_running(OLLAMA_GENERATE_URL):
        return False
    try:
        response = requests.post(
            OLLAMA_GENERATE_URL,
            json={"model": model_name, "keep_alive": VISION_KEEP_ALIVE, "options": {"num_ctx": VISION_CONTEXT_TOKENS}},
            timeout=VISION_TIMEOUT_SECONDS,
        )
        return response.ok
    except requests.RequestException:
        return False


def get_speech_model():
    """Load Whisper once. The startup warm-up and a first voice command can
    arrive together, so loading is locked instead of happening twice."""
    global _speech_model
    with _speech_model_lock:
        if _speech_model is None:
            from faster_whisper import WhisperModel

            _speech_model = WhisperModel(
                WHISPER_MODEL_NAME,
                device="cpu",
                compute_type="int8",
                download_root=str(MODEL_ROOT / "whisper"),
                revision=WHISPER_REVISIONS.get(WHISPER_MODEL_NAME),
            )
    return _speech_model


def speech_model_available() -> bool:
    """Whisper is loaded, or its files are in the local cache at the pinned version."""
    if _speech_model is not None:
        return True
    try:
        from faster_whisper.utils import download_model

        download_model(
            WHISPER_MODEL_NAME,
            cache_dir=str(MODEL_ROOT / "whisper"),
            revision=WHISPER_REVISIONS.get(WHISPER_MODEL_NAME),
            local_files_only=True,
        )
        return True
    except Exception:
        return False


def transcribe_audio(audio_path: str) -> dict:
    """Transcribe a user recording with pretrained Whisper weights."""
    model = get_speech_model()
    segments, info = model.transcribe(
        audio_path,
        language="en",
        beam_size=5,
        vad_filter=True,
    )
    text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    return {
        "text": text,
        "language": info.language,
        "language_probability": round(float(info.language_probability), 3),
        "model": f"Whisper {WHISPER_MODEL_NAME} via faster-whisper",
    }
