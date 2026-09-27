#!/usr/bin/env python3
"""Compare three literature-backed ASR families on MealMatch commands.

This is the final cross-family evaluation. The earlier Whisper-size benchmark
is retained as a capacity-screening experiment and selected ``small.en`` as the
Whisper representative. Every candidate here receives the same frozen WAV
manifest and is scored by the same WER and downstream intent functions.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:  # package import in tests; direct import when executed as a script
    from .evaluate_whisper import (
        load_manifest,
        route_cooking_intent,
        select_model,
        summarize,
        wav_duration,
        word_error_counts,
    )
except ImportError:
    from evaluate_whisper import (
        load_manifest,
        route_cooking_intent,
        select_model,
        summarize,
        wav_duration,
        word_error_counts,
    )


CANDIDATES = {
    "whisper-small.en": {
        "family": "Whisper",
        "backend": "faster-whisper",
        "checkpoint": "small.en",
        "decoding": "beam size 5 with VAD",
    },
    "distil-whisper-small.en": {
        "family": "Distil-Whisper",
        "backend": "faster-whisper",
        "checkpoint": "distil-small.en",
        "decoding": "beam size 5 with VAD",
    },
    "wav2vec2-base-960h": {
        "family": "wav2vec 2.0",
        "backend": "transformers-ctc",
        "checkpoint": "facebook/wav2vec2-base-960h",
        "revision": "22aad52",
        "decoding": "greedy CTC",
    },
}


def read_pcm16(path: Path) -> tuple[np.ndarray, int]:
    """Load the evaluator's mono PCM fixtures without optional audio packages."""
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("ASR benchmark audio must be mono 16-bit PCM")
        sample_rate = source.getframerate()
        frames = source.readframes(source.getnframes())
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    return audio, sample_rate


def load_transcriber(candidate: dict, cache_root: Path):
    """Return (transcribe, loaded object) for one deployable inference stack."""
    if candidate["backend"] == "faster-whisper":
        from faster_whisper import WhisperModel

        model = WhisperModel(
            candidate["checkpoint"],
            device="cpu",
            compute_type="int8",
            download_root=str(cache_root / "whisper"),
        )

        def transcribe(path: Path) -> tuple[str, float]:
            segments, info = model.transcribe(
                str(path), language="en", beam_size=5, vad_filter=True
            )
            transcript = " ".join(
                segment.text.strip() for segment in segments if segment.text.strip()
            ).strip()
            return transcript, float(info.language_probability)

        return transcribe, model

    if candidate["backend"] == "transformers-ctc":
        import torch
        from transformers import AutoModelForCTC, AutoProcessor

        checkpoint = candidate["checkpoint"]
        revision = candidate.get("revision")
        processor = AutoProcessor.from_pretrained(
            checkpoint, revision=revision, cache_dir=str(cache_root / "huggingface")
        )
        model = AutoModelForCTC.from_pretrained(
            checkpoint, revision=revision, cache_dir=str(cache_root / "huggingface")
        )
        model.eval()

        def transcribe(path: Path) -> tuple[str, float]:
            audio, sample_rate = read_pcm16(path)
            inputs = processor(audio, sampling_rate=sample_rate, return_tensors="pt")
            with torch.inference_mode():
                logits = model(**inputs).logits
            token_ids = torch.argmax(logits, dim=-1)
            transcript = processor.batch_decode(token_ids)[0].strip()
            return transcript, 1.0

        return transcribe, (processor, model)

    raise ValueError(f"Unsupported ASR backend: {candidate['backend']}")


def render_report(result: dict) -> str:
    lines = [
        "# Cross-family cooking ASR evaluation",
        "",
        f"**Generated:** {result['generated_at']}",
        f"**Audio:** {result['manifest_source']}",
        f"**Files per candidate:** {result['record_count']}",
        "",
        "| Candidate | Family | WER | Overall intent | Clean intent | Noisy intent | Failures | Median latency | Median RTF |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, details in result["models"].items():
        summary = details["summary"]
        clean = summary["by_condition"]["clean"]
        noisy = summary["by_condition"]["noise_10db"]
        lines.append(
            f"| {key} | {details['candidate']['family']} | {summary['wer']:.3f} | "
            f"{summary['intent_accuracy']:.1%} | {clean['intent_accuracy']:.1%} | "
            f"{noisy['intent_accuracy']:.1%} | {summary['failure_rate']:.1%} | "
            f"{summary['median_latency_ms']:.0f} ms | {summary['median_real_time_factor']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Frozen selection",
            "",
            f"**Selected:** {result['selected_model'] or 'none'}",
            "",
            result["selection"].get("rule", result["selection"].get("reason", "")),
            "",
            "The candidates use their normal deployable decoding stacks rather than an artificial shared decoder: faster-whisper uses beam search and VAD, while wav2vec 2.0 uses greedy CTC decoding. The benchmark therefore compares end-to-end product pipelines on identical audio, not isolated encoder quality.",
            "",
            "Synthetic speech supports fast reproducibility but does not replace the planned participant study with real accents, hesitations, microphone distances and kitchen sounds.",
            "",
        ]
    )
    return "\n".join(lines)


def run(manifest_path: Path, output_dir: Path, candidate_keys: list[str]) -> dict:
    manifest = load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_root = Path(__file__).resolve().parents[1] / ".model_cache"
    model_results = {}

    for key in candidate_keys:
        if key not in CANDIDATES:
            raise ValueError(f"Unknown candidate {key!r}; choose from {sorted(CANDIDATES)}")
        candidate = CANDIDATES[key]
        load_started = time.perf_counter()
        transcribe, loaded = load_transcriber(candidate, cache_root)
        load_seconds = time.perf_counter() - load_started

        first_path = manifest_path.parent / manifest["records"][0]["path"]
        transcribe(first_path)  # warm-up excluded from measured latency
        records = []
        for index, fixture in enumerate(manifest["records"], start=1):
            audio_path = manifest_path.parent / fixture["path"]
            started = time.perf_counter()
            transcript = ""
            language_probability = 0.0
            error = ""
            try:
                transcript, language_probability = transcribe(audio_path)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = (time.perf_counter() - started) * 1000
            word_errors, reference_words = word_error_counts(
                fixture["reference"], transcript
            )
            predicted_intent = route_cooking_intent(transcript)
            duration = float(
                fixture.get("duration_seconds") or wav_duration(audio_path)
            )
            records.append(
                {
                    **fixture,
                    "transcript": transcript,
                    "predicted_intent": predicted_intent,
                    "intent_correct": not error
                    and predicted_intent == fixture["intent"],
                    "word_errors": word_errors,
                    "reference_words": reference_words,
                    "latency_ms": round(latency_ms, 2),
                    "real_time_factor": round((latency_ms / 1000) / duration, 4),
                    "language_probability": round(language_probability, 4),
                    "error": error,
                }
            )
            print(
                f"[{key} {index}/{len(manifest['records'])}] {fixture['id']}",
                flush=True,
            )

        model_results[key] = {
            "candidate": candidate,
            "load_seconds": round(load_seconds, 3),
            "summary": summarize(records),
            "records": records,
        }
        del loaded, transcribe
        gc.collect()

    summaries = {key: value["summary"] for key, value in model_results.items()}
    selected, selection = select_model(summaries)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "manifest_source": manifest.get("source", "unspecified"),
        "participant_data": bool(manifest.get("participant_data")),
        "record_count": len(manifest["records"]),
        "candidate_keys": candidate_keys,
        "selection_predeclared": True,
        "selection": selection,
        "selected_model": selected,
        "models": model_results,
    }
    (output_dir / "asr-model-results.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "asr-model-results.md").write_text(
        render_report(result), encoding="utf-8"
    )
    print(f"Wrote {output_dir / 'asr-model-results.json'}")
    print(f"Wrote {output_dir / 'asr-model-results.md'}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/whisper_evaluation/audio-manifest.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/asr_family_evaluation")
    )
    parser.add_argument("--candidates", nargs="+", default=list(CANDIDATES))
    args = parser.parse_args()
    run(args.manifest.resolve(), args.output.resolve(), args.candidates)


if __name__ == "__main__":
    main()
