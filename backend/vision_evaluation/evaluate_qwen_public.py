"""Fast external-validity benchmark for Qwen on public Open Images food data.

This is a post-selection check, not a replacement for the household benchmark.
It converts the existing COCO boxes to image-level class presence and gives both
Qwen variants the same closed 27-class vocabulary. A deterministic, visibility-
favoured class-balanced subset keeps the local experiment practical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from model_services import (  # noqa: E402
    OLLAMA_CHAT_URL,
    VISION_CONTEXT_TOKENS,
    VISION_MAX_IMAGE_SIDE,
    VISION_TIMEOUT_SECONDS,
    _json_object,
    encode_vision_image,
    vision_model_display_name,
)
from evaluate_qwen_household import (  # noqa: E402
    bootstrap_metric_intervals,
    paired_f1_bootstrap,
    percentile,
    score_counts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/open_images_food"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen2.5vl:3b", "qwen2.5vl:7b"],
    )
    parser.add_argument(
        "--examples-per-class",
        type=int,
        default=2,
        help="Minimum selected public images containing each class.",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--select-only",
        action="store_true",
        help="Write the deterministic subset manifest without running inference.",
    )
    return parser.parse_args()


def canonical_label(value: str) -> str:
    aliases = {
        "orange (fruit)": "orange",
        "lemon (plant)": "lemon",
    }
    normalized = " ".join(value.casefold().replace("_", " ").split())
    return aliases.get(normalized, normalized)


def dataset_records(dataset: dict) -> tuple[list[str], list[dict]]:
    category_by_id = {
        int(category["id"]): canonical_label(str(category["name"]))
        for category in dataset["categories"]
    }
    annotations_by_image: dict[int, list[dict]] = defaultdict(list)
    for annotation in dataset["annotations"]:
        annotations_by_image[int(annotation["image_id"])].append(annotation)

    records = []
    for image in dataset["images"]:
        image_id = int(image["id"])
        image_area = max(1.0, float(image["width"]) * float(image["height"]))
        truth: set[str] = set()
        quality: dict[str, float] = defaultdict(float)
        for annotation in annotations_by_image.get(image_id, []):
            label = category_by_id[int(annotation["category_id"])]
            truth.add(label)
            attributes = annotation.get("attributes", {})
            relative_area = min(1.0, float(annotation.get("area", 0.0)) / image_area)
            score = relative_area
            score += 0.20 if not attributes.get("is_group_of") else 0.0
            score += 0.10 if not attributes.get("is_occluded") else 0.0
            score += 0.05 if not attributes.get("is_truncated") else 0.0
            quality[label] = max(quality[label], score)
        if truth:
            records.append(
                {
                    "image_id": image_id,
                    "file_name": str(image["file_name"]),
                    "open_images_id": str(image.get("open_images_id", image_id)),
                    "truth": sorted(truth),
                    "quality": dict(quality),
                }
            )
    return sorted(set(category_by_id.values())), records


def select_balanced_subset(
    records: list[dict], classes: list[str], examples_per_class: int
) -> list[dict]:
    if examples_per_class < 1:
        raise ValueError("examples_per_class must be at least 1")
    selected: dict[int, dict] = {}
    counts: Counter[str] = Counter()
    for label in classes:
        while counts[label] < examples_per_class:
            candidates = [
                record
                for record in records
                if record["image_id"] not in selected and label in record["truth"]
            ]
            if not candidates:
                raise ValueError(f"Not enough public examples for class: {label}")

            def rank(record: dict) -> tuple[float, int, str]:
                remaining_gain = sum(
                    counts[item] < examples_per_class for item in record["truth"]
                )
                return (
                    -float(record["quality"].get(label, 0.0)),
                    -remaining_gain,
                    record["file_name"],
                )

            chosen = sorted(candidates, key=rank)[0]
            selected[chosen["image_id"]] = chosen
            counts.update(chosen["truth"])
    return sorted(selected.values(), key=lambda record: record["file_name"])


def build_public_prompt(classes: list[str]) -> str:
    vocabulary = ", ".join(classes)
    return (
        "Inspect the complete image and identify visible foods only from this closed "
        f"vocabulary: {vocabulary}. Return each present class once using exactly the "
        "spelling in the vocabulary. Do not infer hidden food and do not output any "
        "class outside the vocabulary. Return JSON only as {\"classes\": [\"class\"]}. "
        "Return an empty classes array when none is reliably visible."
    )


def parse_class_predictions(raw: object, classes: list[str]) -> tuple[list[str], list[str]]:
    allowed = set(classes)
    predictions: set[str] = set()
    invalid: set[str] = set()
    if not isinstance(raw, list):
        return [], []
    for value in raw:
        label = canonical_label(str(value))
        if label in allowed:
            predictions.add(label)
        elif label:
            invalid.add(label)
    return sorted(predictions), sorted(invalid)


def infer_classes(image_path: Path, model: str, classes: list[str]) -> dict:
    response = requests.post(
        OLLAMA_CHAT_URL,
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": build_public_prompt(classes),
                    "images": [encode_vision_image(str(image_path))],
                }
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_ctx": VISION_CONTEXT_TOKENS,
                "num_predict": 256,
            },
        },
        timeout=VISION_TIMEOUT_SECONDS,
    )
    if not response.ok:
        detail = response.text.strip()[:1000] or response.reason
        raise RuntimeError(f"Ollama returned HTTP {response.status_code}: {detail}")
    payload = _json_object(response.json().get("message", {}).get("content", ""))
    predictions, invalid = parse_class_predictions(payload.get("classes", []), classes)
    return {"predictions": predictions, "invalid_outputs": invalid}


def match_sets(predictions: list[str], truth: list[str]) -> dict:
    predicted_set, truth_set = set(predictions), set(truth)
    return {
        "tp": len(predicted_set & truth_set),
        "fp": len(predicted_set - truth_set),
        "fn": len(truth_set - predicted_set),
        "matched": sorted(predicted_set & truth_set),
        "hallucinated": sorted(predicted_set - truth_set),
        "missed": sorted(truth_set - predicted_set),
    }


def summarize(records: list[dict], classes: list[str]) -> dict:
    tp = sum(record["tp"] for record in records)
    fp = sum(record["fp"] for record in records)
    fn = sum(record["fn"] for record in records)
    latencies = [record["latency_ms"] for record in records]
    per_class = {}
    for label in classes:
        label_tp = sum(label in record["truth"] and label in record["predictions"] for record in records)
        label_fp = sum(label not in record["truth"] and label in record["predictions"] for record in records)
        label_fn = sum(label in record["truth"] and label not in record["predictions"] for record in records)
        per_class[label] = {
            **score_counts(label_tp, label_fp, label_fn),
            "support": label_tp + label_fn,
            "true_positives": label_tp,
            "false_positives": label_fp,
            "false_negatives": label_fn,
        }
    macro_f1 = statistics.fmean(item["f1"] for item in per_class.values())
    return {
        **score_counts(tp, fp, fn),
        "macro_f1": macro_f1,
        "exact_set_accuracy": sum(
            set(record["truth"]) == set(record["predictions"]) for record in records
        )
        / len(records),
        "failure_rate": sum(bool(record["error"]) for record in records) / len(records),
        "mean_latency_ms": statistics.fmean(latencies),
        "median_latency_ms": statistics.median(latencies),
        "p95_latency_ms": percentile(latencies, 0.95),
        "mean_invalid_outputs": statistics.fmean(
            len(record["invalid_outputs"]) for record in records
        ),
        "image_runs": len(records),
        "per_class": per_class,
    }


def evaluation_signature(
    annotation_bytes: bytes,
    selected: list[dict],
    models: list[str],
    classes: list[str],
) -> str:
    frozen = {
        "annotation_sha256": hashlib.sha256(annotation_bytes).hexdigest(),
        "selected": [
            {"image_id": record["image_id"], "file_name": record["file_name"], "truth": record["truth"]}
            for record in selected
        ],
        "models": models,
        "classes": classes,
        "prompt": build_public_prompt(classes),
        "context_tokens": VISION_CONTEXT_TOKENS,
        "max_image_side": VISION_MAX_IMAGE_SIDE,
        "timeout_seconds": VISION_TIMEOUT_SECONDS,
    }
    encoded = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_checkpoint(path: Path, signature: str) -> dict[tuple[str, int], dict]:
    completed = {}
    if not path.exists():
        return completed
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("signature") != signature:
            raise SystemExit(f"Checkpoint signature mismatch at line {line_number}.")
        record = entry["record"]
        completed[(str(entry["model"]), int(record["image_id"]))] = record
    return completed


def append_checkpoint(path: Path, signature: str, model: str, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"signature": signature, "model": model, "record": record}) + "\n")
        handle.flush()


def markdown_report(payload: dict) -> str:
    lines = [
        "# Qwen public-dataset external-validity results",
        "",
        f"**Generated:** {payload['generated_at']}",
        "**Dataset:** Open Images V7 food subset (official test split)",
        f"**Selected images:** {payload['image_count']}",
        f"**Classes:** {len(payload['classes'])}",
        f"**Minimum examples per class:** {payload['examples_per_class']}",
        "",
        "This post-selection benchmark tests external validity. It did not influence the previously frozen household-model selection.",
        "",
        "| Model | Micro precision | Micro recall | Micro F1 | Macro F1 | Exact sets | Failures | Median latency | p95 latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model, result in payload["models"].items():
        summary = result["summary"]
        lines.append(
            f"| {vision_model_display_name(model)} | {summary['precision']:.3f} | "
            f"{summary['recall']:.3f} | {summary['f1']:.3f} | {summary['macro_f1']:.3f} | "
            f"{summary['exact_set_accuracy']:.1%} | {summary['failure_rate']:.1%} | "
            f"{summary['median_latency_ms']:.0f} ms | {summary['p95_latency_ms']:.0f} ms |"
        )
    comparison = payload.get("paired_f1_comparison", {})
    if comparison:
        lines.extend(
            [
                "",
                "## Paired comparison",
                "",
                f"The paired image-cluster bootstrap estimates `{comparison['right_model']}` minus "
                f"`{comparison['left_model']}` micro F1 as {comparison['right_minus_left_f1']:.3f} "
                f"(95% interval {comparison['lower_95']:.3f} to {comparison['upper_95']:.3f}; "
                f"{comparison['bootstrap_samples']} resamples).",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Open Images supplies reproducible public labels but is not a household-fridge dataset. The fixed vocabulary avoids penalising unrelated visible foods that the 27-class annotation set does not cover. This result complements rather than replaces the household benchmark and user study.",
            "",
            "Full subset selection, raw predictions, class metrics, failures and configuration are retained in the adjacent JSON file.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    annotation_path = args.dataset.resolve() / "annotations" / "instances_test.json"
    annotation_bytes = annotation_path.read_bytes()
    dataset = json.loads(annotation_bytes)
    classes, all_records = dataset_records(dataset)
    selected = select_balanced_subset(all_records, classes, args.examples_per_class)

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    subset_path = output_dir / "public-subset.json"
    subset_path.write_text(
        json.dumps(
            {
                "source": "Open Images V7 official test split",
                "examples_per_class": args.examples_per_class,
                "classes": classes,
                "images": selected,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Selected {len(selected)} images covering {len(classes)} classes.", flush=True)
    if args.select_only:
        print(f"Wrote {subset_path}")
        return

    signature = evaluation_signature(annotation_bytes, selected, args.models, classes)
    checkpoint_path = output_dir / "qwen-public.checkpoint.jsonl"
    if checkpoint_path.exists() and not args.resume:
        raise SystemExit(f"Checkpoint exists: {checkpoint_path}. Pass --resume or use a new output directory.")
    completed = load_checkpoint(checkpoint_path, signature) if args.resume else {}
    total = len(selected) * len(args.models)
    completed_count = len(completed)
    results_by_model = {}

    for model in args.models:
        records = [record for (saved_model, _), record in completed.items() if saved_model == model]
        for selected_record in selected:
            key = (model, selected_record["image_id"])
            if key in completed:
                continue
            image_path = args.dataset.resolve() / selected_record["file_name"]
            started = time.perf_counter()
            error = ""
            inference = {"predictions": [], "invalid_outputs": []}
            try:
                inference = infer_classes(image_path, model, classes)
            except Exception as exc:
                error = str(exc)
            latency_ms = (time.perf_counter() - started) * 1000
            match = match_sets(inference["predictions"], selected_record["truth"])
            record = {
                "image_id": selected_record["image_id"],
                "file_name": selected_record["file_name"],
                "open_images_id": selected_record["open_images_id"],
                "truth": selected_record["truth"],
                "predictions": inference["predictions"],
                "normalized_predictions": inference["predictions"],
                "invalid_outputs": inference["invalid_outputs"],
                "latency_ms": round(latency_ms, 2),
                "error": error,
                **match,
            }
            records.append(record)
            append_checkpoint(checkpoint_path, signature, model, record)
            completed_count += 1
            print(
                f"[{completed_count}/{total}] {model} {selected_record['open_images_id']}",
                flush=True,
            )
        records.sort(key=lambda record: record["file_name"])
        results_by_model[model] = {
            "summary": summarize(records, classes),
            "confidence_intervals": bootstrap_metric_intervals(records),
            "records": records,
        }

    paired = {}
    if len(args.models) == 2:
        paired = {
            "left_model": args.models[0],
            "right_model": args.models[1],
            **paired_f1_bootstrap(
                results_by_model[args.models[0]]["records"],
                results_by_model[args.models[1]]["records"],
            ),
        }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset.resolve()),
        "annotation_sha256": hashlib.sha256(annotation_bytes).hexdigest(),
        "evaluation_signature": signature,
        "post_selection_external_validity": True,
        "examples_per_class": args.examples_per_class,
        "image_count": len(selected),
        "classes": classes,
        "prompt": build_public_prompt(classes),
        "configuration": {
            "context_tokens": VISION_CONTEXT_TOKENS,
            "max_image_side": VISION_MAX_IMAGE_SIDE,
            "timeout_seconds": VISION_TIMEOUT_SECONDS,
            "num_predict": 256,
        },
        "selected_images": selected,
        "paired_f1_comparison": paired,
        "models": results_by_model,
    }
    json_path = output_dir / "qwen-public-results.json"
    markdown_path = output_dir / "qwen-public-results.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(markdown_report(payload), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    main()
