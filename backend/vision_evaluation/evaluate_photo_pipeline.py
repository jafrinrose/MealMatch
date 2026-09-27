"""Score the production photo pipeline on the household set.

evaluate_qwen_household.py compares models on a single whole-photo pass. This
script runs the app's photo pipeline with close-ups always on (whole photo,
then four close-ups, as in iteration 1 and as after "Look closer") and scores
every image twice: after the whole-photo pass, which is what the user sees
first, and after all close-ups. It reuses the frozen labels, label
canonicalization and matching of the model comparison, so its numbers can be
set beside the recorded 3B results. One run per image.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluate_qwen_household import (  # noqa: E402
    grouped_summaries,
    match_predictions,
    normalize_label,
    summarize,
    truth_entries,
)
from model_services import (  # noqa: E402
    VISION_LANGUAGE_MODEL_NAME,
    VISION_MAX_OUTPUT_TOKENS,
    open_photo,
    scan_pantry_photo,
)

STAGES = ("whole_photo", "with_close_ups")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/household_vision/manifest.json"))
    parser.add_argument("--split", choices=("development", "test"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Skip images already in the checkpoint.")
    return parser.parse_args()


def scan_record(image_record: dict, image_path: Path) -> dict:
    """Both stages of one image, with each pass's done_reason and timing."""
    truth = truth_entries(image_record["ingredients"])
    base = {
        "image_id": image_record["id"],
        "image": image_record["image"],
        "run": 1,
        "scene_type": image_record.get("scene_type", "unknown"),
        "packaging": image_record.get("packaging", "unknown"),
        "difficulty": image_record.get("difficulty", "unknown"),
        "ground_truth": [entry["name"] for entry in truth],
    }
    predictions: dict[str, list[str]] = {stage: [] for stage in STAGES}
    latency: dict[str, float] = {stage: 0.0 for stage in STAGES}
    passes: list[dict] = []
    error = ""
    started = time.perf_counter()
    try:
        for result in scan_pantry_photo(open_photo(str(image_path)), close_ups=True):
            names = [item["ingredient"] for item in result["detections"]]
            elapsed_ms = (time.perf_counter() - started) * 1000
            if result["pass_number"] == 1:
                predictions["whole_photo"] = list(names)
                latency["whole_photo"] = elapsed_ms
            predictions["with_close_ups"] += names
            latency["with_close_ups"] = elapsed_ms
            passes.append({key: value for key, value in result.items() if key != "detections"} | {"new": names})
    except Exception as exc:  # a failed scan is a measurable outcome
        error = str(exc)
    stages = {}
    for stage in STAGES:
        stages[stage] = {
            **base,
            "predictions": predictions[stage],
            "normalized_predictions": [normalize_label(name) for name in predictions[stage]],
            "latency_ms": round(latency[stage] or (time.perf_counter() - started) * 1000, 2),
            "error": error,
            **match_predictions(predictions[stage], truth),
        }
    return {"image_id": image_record["id"], "stages": stages, "passes": passes}


def markdown_report(payload: dict) -> str:
    lines = [
        f"# Photo pipeline evaluation: {payload['split']} split",
        "",
        f"Model `{payload['configuration']['model']}`, one run per image, "
        f"{payload['images']} images. Output limit {payload['configuration']['max_output_tokens']} tokens.",
        "",
        "| Stage | Scene | Precision | Recall | F1 | TP | FP | FN | Empty | Median s |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for stage in STAGES:
        groups = {"all": payload[stage]["summary"], **payload[stage]["by_scene_type"]}
        for scene, summary in groups.items():
            lines.append(
                f"| {stage.replace('_', ' ')} | {scene} | {summary['precision']:.3f} | {summary['recall']:.3f} | "
                f"{summary['f1']:.3f} | {summary['true_positives']} | {summary['false_positives']} | "
                f"{summary['false_negatives']} | {summary['empty_response_rate']:.0%} | "
                f"{summary['median_latency_ms'] / 1000:.1f} |"
            )
    reasons: dict[str, int] = {}
    for record in payload["records"]:
        for entry in record["passes"]:
            reasons[str(entry.get("done_reason", "error"))] = reasons.get(str(entry.get("done_reason", "error")), 0) + 1
    lines += ["", "Pass endings: " + ", ".join(f"{reason} {count}" for reason, count in sorted(reasons.items())), ""]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    images = json.loads(manifest_path.read_text(encoding="utf-8"))[args.split]
    unverified = [record["id"] for record in images if record.get("annotation_status") != "verified"]
    if unverified:
        raise SystemExit("Evaluation requires human-verified ground truth: " + ", ".join(unverified[:10]))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / f"photo-pipeline-{args.split}.checkpoint.jsonl"
    if checkpoint.exists() and not args.resume:
        raise SystemExit(f"Checkpoint already exists: {checkpoint}. Pass --resume or use a new output directory.")
    done = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            done[record["image_id"]] = record

    for number, image_record in enumerate(images, start=1):
        if image_record["id"] in done:
            continue
        image_path = manifest_path.parent / image_record["image"]
        record = scan_record(image_record, image_path)
        done[record["image_id"]] = record
        with checkpoint.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        full = record["stages"]["with_close_ups"]
        print(
            f"[{number}/{len(images)}] {image_record['id']}: whole photo tp={record['stages']['whole_photo']['tp']} "
            f"-> with close-ups tp={full['tp']} fp={full['fp']} fn={full['fn']} in {full['latency_ms'] / 1000:.1f}s",
            flush=True,
        )

    records = [done[record["id"]] for record in images]
    payload = {
        "split": args.split,
        "images": len(records),
        "configuration": {
            "model": VISION_LANGUAGE_MODEL_NAME,
            "close_ups": True,
            "max_output_tokens": VISION_MAX_OUTPUT_TOKENS,
        },
        "records": records,
    }
    for stage in STAGES:
        stage_records = [record["stages"][stage] for record in records]
        payload[stage] = {
            "summary": summarize(stage_records),
            "by_scene_type": grouped_summaries(stage_records, "scene_type"),
        }
    (output / f"photo-pipeline-{args.split}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report = markdown_report(payload)
    (output / f"photo-pipeline-{args.split}.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
