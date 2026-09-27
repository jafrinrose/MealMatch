#!/usr/bin/env python3
"""Evaluate Whisper sizes on MealMatch hands-free cooking utterances.

The built-in fixture generator uses macOS voices to create a quick controlled
benchmark. It is deliberately described as synthetic speech and must not be
reported as participant testing. The evaluator also accepts the same manifest
format with real consented recordings for the later user study.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import random
import re
import shutil
import statistics
import subprocess
import time
import wave
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MODELS = ["tiny.en", "base.en", "small.en"]
DEFAULT_VOICES = ["Samantha", "Daniel", "Rishi"]
NOISY_SNR_DB = 10.0
SEED = 20260924

# These phrases exercise every deterministic route in the cooking screen plus
# open questions that should be passed to the text assistant.
UTTERANCES = [
    ("stop-listening", "stop listening", "stop_listening"),
    ("disable-hands-free", "turn off hands free", "stop_listening"),
    ("cancel-cooking", "cancel cooking", "cancel_cooking"),
    ("changed-mind", "I changed my mind", "cancel_cooking"),
    ("finish-cooking", "finish cooking", "finish_cooking"),
    ("meal-ready", "the meal is ready", "finish_cooking"),
    ("peek-next", "what should I do next", "peek_next"),
    ("next-step", "next step", "next_step"),
    ("move-on", "I am done with this step", "next_step"),
    ("previous-step", "previous step", "previous_step"),
    ("go-back", "go back", "previous_step"),
    ("repeat-step", "repeat the current step", "repeat_step"),
    ("time-left", "how much time is left", "time_remaining"),
    ("current-step", "which step am I on", "current_step"),
    ("voice-help", "what can I say", "help"),
    ("confirm-finish", "confirm finish", "confirm"),
    ("never-mind", "never mind", "decline"),
    ("food-safety-question", "is the chicken cooked through", "question"),
]


def normalize_text(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9'\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def route_cooking_intent(value: str) -> str:
    """Mirror the deterministic command order used by the cooking UI."""
    command = normalize_text(value)
    if re.match(r"^(yes|confirm|confirmed|do it|please do|go ahead)", command) or "confirm cancel" in command or "confirm finish" in command:
        return "confirm"
    if re.match(r"^(no|don't|do not|never mind|nevermind|keep cooking)", command):
        return "decline"
    if re.search(r"stop listening|turn off (voice|hands free)|disable (voice|hands free)|pause listening", command):
        return "stop_listening"
    if re.search(r"cancel cooking|changed my mind|restore (my )?pantry", command):
        return "cancel_cooking"
    if re.search(r"finish cooking|meal is ready|complete (the )?(recipe|cooking)|i am finished cooking", command):
        return "finish_cooking"
    if re.search(r"what('s| is) (the )?next|what should i do (next|after)|read (the )?next", command):
        return "peek_next"
    if re.search(r"next step|continue|move on|go forward|done with (this|the) step|finished (this|the) step", command):
        return "next_step"
    if re.search(r"previous step|go back|step back|last step", command):
        return "previous_step"
    if re.search(r"repeat|say that again|read (this|the current) step|what am i doing", command):
        return "repeat_step"
    if re.search(r"how much time|time (is )?left|when (will|is) (it|the food) (be )?ready|check (the )?timer", command):
        return "time_remaining"
    if re.search(r"what step|which step|where am i", command):
        return "current_step"
    if re.search(r"what can i say|voice help|help me use", command):
        return "help"
    return "question"


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for ref_token in reference:
        current = [previous[0] + 1]
        for index, hyp_token in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index] + 1,
                    previous[index - 1] + (ref_token != hyp_token),
                )
            )
        previous = current
    return previous[-1]


def word_error_counts(reference: str, hypothesis: str) -> tuple[int, int]:
    reference_words = normalize_text(reference).split()
    hypothesis_words = normalize_text(hypothesis).split()
    return edit_distance(reference_words, hypothesis_words), len(reference_words)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as source:
        return source.getnframes() / source.getframerate()


def add_white_noise(source_path: Path, output_path: Path, snr_db: float, seed: int) -> None:
    """Add deterministic Gaussian noise to mono 16-bit PCM without dependencies."""
    with wave.open(str(source_path), "rb") as source:
        parameters = source.getparams()
        frames = source.readframes(source.getnframes())
    if parameters.nchannels != 1 or parameters.sampwidth != 2:
        raise ValueError("Fixture audio must be mono 16-bit PCM")
    samples = [int.from_bytes(frames[i : i + 2], "little", signed=True) for i in range(0, len(frames), 2)]
    active = [sample for sample in samples if abs(sample) > 32]
    signal_rms = math.sqrt(sum(sample * sample for sample in active) / max(len(active), 1))
    noise_rms = signal_rms / (10 ** (snr_db / 20))
    generator = random.Random(seed)
    noisy = bytearray()
    for sample in samples:
        mixed = round(sample + generator.gauss(0, noise_rms))
        mixed = max(-32768, min(32767, mixed))
        noisy.extend(int(mixed).to_bytes(2, "little", signed=True))
    with wave.open(str(output_path), "wb") as target:
        target.setparams(parameters)
        target.writeframes(bytes(noisy))


def generate_macos_fixtures(output_dir: Path, voices: list[str]) -> Path:
    if not shutil.which("say") or not shutil.which("ffmpeg"):
        raise RuntimeError("Fixture generation requires macOS 'say' and ffmpeg")
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for voice in voices:
        voice_slug = re.sub(r"[^a-z0-9]+", "-", voice.casefold()).strip("-")
        for utterance_id, text, intent in UTTERANCES:
            clean_path = audio_dir / f"{voice_slug}-{utterance_id}-clean.wav"
            noisy_path = audio_dir / f"{voice_slug}-{utterance_id}-noise10.wav"
            if not clean_path.exists():
                aiff_path = audio_dir / f"{voice_slug}-{utterance_id}.aiff"
                subprocess.run(["say", "-v", voice, "-r", "175", "-o", str(aiff_path), text], check=True)
                subprocess.run(
                    ["ffmpeg", "-loglevel", "error", "-y", "-i", str(aiff_path), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(clean_path)],
                    check=True,
                )
                aiff_path.unlink(missing_ok=True)
            if not noisy_path.exists():
                noise_seed = int(hashlib.sha256(f"{voice}:{utterance_id}:{SEED}".encode()).hexdigest()[:8], 16)
                add_white_noise(clean_path, noisy_path, NOISY_SNR_DB, noise_seed)
            for condition, path in (("clean", clean_path), ("noise_10db", noisy_path)):
                records.append(
                    {
                        "id": f"{voice_slug}-{utterance_id}-{condition}",
                        "path": str(path.relative_to(output_dir)),
                        "reference": text,
                        "intent": intent,
                        "speaker": voice,
                        "condition": condition,
                        "duration_seconds": round(wav_duration(path), 3),
                    }
                )
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "controlled synthetic speech generated with macOS voices",
        "participant_data": False,
        "voices": voices,
        "noise_condition": f"deterministic white noise at {NOISY_SNR_DB:g} dB SNR",
        "records": records,
    }
    manifest_path = output_dir / "audio-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("records"), list) or not payload["records"]:
        raise ValueError("Audio manifest must contain at least one record")
    required = {"id", "path", "reference", "intent", "speaker", "condition"}
    for record in payload["records"]:
        missing = required - set(record)
        if missing:
            raise ValueError(f"Record {record.get('id', '<unknown>')} is missing {sorted(missing)}")
        audio_path = path.parent / record["path"]
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)
    return payload


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def summarize(records: list[dict]) -> dict:
    valid = [record for record in records if not record["error"]]
    errors = sum(record["word_errors"] for record in valid)
    words = sum(record["reference_words"] for record in valid)
    by_condition = {}
    for condition in sorted({record["condition"] for record in records}):
        group = [record for record in records if record["condition"] == condition]
        usable = [record for record in group if not record["error"]]
        group_errors = sum(record["word_errors"] for record in usable)
        group_words = sum(record["reference_words"] for record in usable)
        by_condition[condition] = {
            "wer": group_errors / group_words if group_words else 1.0,
            "intent_accuracy": sum(record["intent_correct"] for record in usable) / len(group) if group else 0.0,
            "failure_rate": (len(group) - len(usable)) / len(group) if group else 0.0,
        }
    latencies = [record["latency_ms"] for record in valid]
    rtfs = [record["real_time_factor"] for record in valid]
    return {
        "wer": errors / words if words else 1.0,
        "intent_accuracy": sum(record["intent_correct"] for record in valid) / len(records),
        "failure_rate": (len(records) - len(valid)) / len(records),
        "median_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "p95_latency_ms": percentile(latencies, 0.95),
        "median_real_time_factor": statistics.median(rtfs) if rtfs else 0.0,
        "records": len(records),
        "by_condition": by_condition,
    }


def select_model(summaries: dict[str, dict]) -> tuple[str | None, dict]:
    """Apply the rule frozen before the first benchmark run."""
    eligible = {}
    for model, summary in summaries.items():
        clean = summary["by_condition"].get("clean", {})
        noisy = summary["by_condition"].get("noise_10db", {})
        if (
            summary["failure_rate"] <= 0.05
            and clean.get("intent_accuracy", 0) >= 0.95
            and noisy.get("intent_accuracy", 0) >= 0.85
        ):
            eligible[model] = summary
    if not eligible:
        return None, {"eligible": [], "reason": "No candidate met every operational gate."}
    ordered = sorted(
        eligible,
        key=lambda model: (
            -eligible[model]["by_condition"]["noise_10db"]["intent_accuracy"],
            eligible[model]["by_condition"]["noise_10db"]["wer"],
            eligible[model]["median_latency_ms"],
        ),
    )
    return ordered[0], {
        "eligible": ordered,
        "rule": "failure <=5%, clean intent >=95%, noisy intent >=85%; then noisy intent, noisy WER, median latency",
    }


def render_report(result: dict) -> str:
    lines = [
        "# Whisper cooking-command evaluation",
        "",
        f"**Generated:** {result['generated_at']}",
        f"**Audio:** {result['manifest_source']}",
        f"**Utterances:** {result['record_count']}",
        "",
        "| Model | WER | Intent accuracy | Clean intent | Noisy intent | Failures | Median latency | Median RTF |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model, details in result["models"].items():
        summary = details["summary"]
        clean = summary["by_condition"]["clean"]
        noisy = summary["by_condition"]["noise_10db"]
        lines.append(
            f"| Whisper {model} | {summary['wer']:.3f} | {summary['intent_accuracy']:.1%} | "
            f"{clean['intent_accuracy']:.1%} | {noisy['intent_accuracy']:.1%} | "
            f"{summary['failure_rate']:.1%} | {summary['median_latency_ms']:.0f} ms | "
            f"{summary['median_real_time_factor']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Selection",
            "",
            f"**Selected:** {result['selected_model'] or 'none'}",
            "",
            result["selection"]["rule"] if "rule" in result["selection"] else result["selection"]["reason"],
            "",
            "## Interpretation boundary",
            "",
            "This is a controlled task-specific benchmark generated with computer voices. It tests model size, noise robustness and downstream command routing reproducibly, but it does not represent accents, hesitations, microphone distance or kitchen noise from real participants. The selected model must therefore remain subject to the planned hands-free user study.",
            "",
            "Raw transcripts, expected/predicted intents, per-file latency and model-load time are retained in the adjacent JSON file.",
            "",
        ]
    )
    return "\n".join(lines)


def run_evaluation(manifest_path: Path, output_dir: Path, models: list[str]) -> dict:
    from faster_whisper import WhisperModel

    manifest = load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_results = {}
    for model_name in models:
        load_started = time.perf_counter()
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            download_root=str(Path(__file__).resolve().parents[1] / ".model_cache" / "whisper"),
        )
        load_seconds = time.perf_counter() - load_started
        # Warm-up is excluded from reported latency.
        first_path = manifest_path.parent / manifest["records"][0]["path"]
        list(model.transcribe(str(first_path), language="en", beam_size=5, vad_filter=True)[0])
        records = []
        for index, fixture in enumerate(manifest["records"], start=1):
            audio_path = manifest_path.parent / fixture["path"]
            started = time.perf_counter()
            error = ""
            transcript = ""
            language_probability = 0.0
            try:
                segments, info = model.transcribe(str(audio_path), language="en", beam_size=5, vad_filter=True)
                transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
                language_probability = float(info.language_probability)
            except Exception as exc:  # retained in raw evidence
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = (time.perf_counter() - started) * 1000
            word_errors, reference_words = word_error_counts(fixture["reference"], transcript)
            predicted_intent = route_cooking_intent(transcript)
            duration = float(fixture.get("duration_seconds") or wav_duration(audio_path))
            records.append(
                {
                    **fixture,
                    "transcript": transcript,
                    "predicted_intent": predicted_intent,
                    "intent_correct": not error and predicted_intent == fixture["intent"],
                    "word_errors": word_errors,
                    "reference_words": reference_words,
                    "latency_ms": round(latency_ms, 2),
                    "real_time_factor": round((latency_ms / 1000) / duration, 4),
                    "language_probability": round(language_probability, 4),
                    "error": error,
                }
            )
            print(f"[{model_name} {index}/{len(manifest['records'])}] {fixture['id']}", flush=True)
        model_results[model_name] = {
            "load_seconds": round(load_seconds, 3),
            "summary": summarize(records),
            "records": records,
        }
        del model
        gc.collect()
    summaries = {model: details["summary"] for model, details in model_results.items()}
    selected, selection = select_model(summaries)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "manifest_source": manifest.get("source", "unspecified"),
        "participant_data": bool(manifest.get("participant_data")),
        "record_count": len(manifest["records"]),
        "configuration": {"device": "cpu", "compute_type": "int8", "beam_size": 5, "vad_filter": True},
        "selection_predeclared": True,
        "selection": selection,
        "selected_model": selected,
        "models": model_results,
    }
    json_path = output_dir / "whisper-results.json"
    report_path = output_dir / "whisper-results.md"
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {report_path}")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/whisper_evaluation"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--generate-macos", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--voices", nargs="+", default=DEFAULT_VOICES)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output.resolve()
    manifest_path = args.manifest.resolve() if args.manifest else output_dir / "audio-manifest.json"
    if args.generate_macos:
        manifest_path = generate_macos_fixtures(output_dir, args.voices)
        print(f"Wrote {manifest_path}")
    if args.prepare_only:
        load_manifest(manifest_path)
        print(f"Validated {manifest_path}")
        return
    run_evaluation(manifest_path, output_dir, args.models)


if __name__ == "__main__":
    main()
