"""Evaluate Qwen vision variants on a frozen household ingredient set.

This is intentionally separate from the historical bounding-box detector
benchmark. It measures the deployed product task: extracting a reviewable set
of ingredient names from fridge, pantry and grocery-table photographs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from model_services import (  # noqa: E402
    VISION_CONTEXT_TOKENS,
    VISION_MAX_IMAGE_SIDE,
    VISION_TIMEOUT_SECONDS,
    build_pantry_vision_prompt,
    identify_foods_with_qwen,
    vision_model_display_name,
)


# Frozen before the model comparison and derived only from human ground-truth
# vocabulary. It prevents spelling, plurality and harmless specificity from
# turning a valid pantry concept into a false negative. Product-distinct items
# such as dairy milk and almond milk deliberately remain separate.
LABEL_CANONICALIZATION = {
    "100 plus juice": "100 plus drink",
    "almond milk vanilla": "vanilla almond milk",
    "vanilla almond milk": "vanilla almond milk",
    "apples": "apple",
    "green apple": "apple",
    "red apple": "apple",
    "avocados": "avocado",
    "baby carrots": "carrot",
    "carrots": "carrot",
    "bagels": "bagel",
    "biscuits": "biscuit",
    "blueberry bleuets": "blueberry",
    "boneless skinless chicken breasts": "chicken breast",
    "chicken breast fillets": "chicken breast",
    "canned mushrooms": "mushroom",
    "mushrooms": "mushroom",
    "cashew nuts": "cashew",
    "cheese heads": "cheese",
    "cheese slices": "cheese",
    "cheerios cereal": "cheerios",
    "cherry tomato": "tomato",
    "cherry tomatoes": "tomato",
    "tomatoes": "tomato",
    "eggs": "egg",
    "granola bars": "granola bar",
    "grapes": "grape",
    "green onions": "green onion",
    "spring onions": "green onion",
    "lemons": "lemon",
    "onions": "onion",
    "oranges": "orange",
    "organic milk": "milk",
    "packaged goods": "packaged food",
    "persian cucumbers": "cucumber",
    "pickles": "pickle",
    "potatoes": "potato",
    "russet potatoes": "potato",
    "raspberries": "raspberry",
    "seasonings": "seasoning",
    "strawberries": "strawberry",
    "protein yogurt": "yogurt",
    "vanilla yogurt": "yogurt",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen2.5vl:3b", "qwen2.5vl:7b"],
        help="Ollama model identifiers evaluated with the identical prompt.",
    )
    parser.add_argument(
        "--split",
        choices=["development", "test"],
        default="test",
        help="Use development while refining prompts; reserve test for the final run.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Repeated runs per image; use 3 for final repeatability evidence.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted run from its signature-checked JSONL checkpoint.",
    )
    return parser.parse_args()


def normalize_label(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = " ".join(value.split())
    return LABEL_CANONICALIZATION.get(value, value)


def truth_entries(raw_items: object) -> list[dict]:
    if not isinstance(raw_items, list):
        raise ValueError("Every manifest image needs an ingredients list.")
    entries: list[dict] = []
    for raw in raw_items:
        if isinstance(raw, str):
            name, aliases = raw, []
        elif isinstance(raw, dict):
            name = str(raw.get("name", "")).strip()
            aliases = raw.get("aliases", [])
        else:
            raise ValueError("Ingredients must be strings or {name, aliases} objects.")
        if not name:
            raise ValueError("Ingredient names cannot be empty.")
        accepted = {normalize_label(name)}
        accepted.update(normalize_label(str(alias)) for alias in aliases if str(alias).strip())
        entries.append({"name": name, "accepted": accepted})
    return entries


def match_predictions(predictions: Iterable[str], truth: list[dict]) -> dict:
    unmatched_truth = set(range(len(truth)))
    true_positive_names: list[str] = []
    false_positive_names: list[str] = []

    for prediction in sorted({normalize_label(value) for value in predictions if value.strip()}):
        matched_index = next(
            (index for index in sorted(unmatched_truth) if prediction in truth[index]["accepted"]),
            None,
        )
        if matched_index is None:
            false_positive_names.append(prediction)
            continue
        unmatched_truth.remove(matched_index)
        true_positive_names.append(truth[matched_index]["name"])

    false_negative_names = [truth[index]["name"] for index in sorted(unmatched_truth)]
    return {
        "tp": len(true_positive_names),
        "fp": len(false_positive_names),
        "fn": len(false_negative_names),
        "matched": true_positive_names,
        "hallucinated": false_positive_names,
        "missed": false_negative_names,
    }


def safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def score_counts(tp: int, fp: int, fn: int) -> dict:
    precision = safe_ratio(tp, tp + fp)
    recall = safe_ratio(tp, tp + fn)
    return {
        "precision": precision,
        "recall": recall,
        "f1": safe_ratio(2 * precision * recall, precision + recall),
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def summarize(records: list[dict]) -> dict:
    tp = sum(record["tp"] for record in records)
    fp = sum(record["fp"] for record in records)
    fn = sum(record["fn"] for record in records)
    latencies = [record["latency_ms"] for record in records]
    image_runs: dict[str, list[set[str]]] = defaultdict(list)
    for record in records:
        image_runs[record["image_id"]].append(set(record["normalized_predictions"]))
    repeatability = [
        jaccard(runs[left], runs[right])
        for runs in image_runs.values()
        for left in range(len(runs))
        for right in range(left + 1, len(runs))
    ]
    return {
        **score_counts(tp, fp, fn),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "mean_hallucinations_per_image_run": safe_ratio(fp, len(records)),
        "mean_misses_per_image_run": safe_ratio(fn, len(records)),
        "empty_response_rate": safe_ratio(
            sum(not record["predictions"] for record in records), len(records)
        ),
        "failure_rate": safe_ratio(sum(bool(record["error"]) for record in records), len(records)),
        "mean_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
        "median_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "p95_latency_ms": percentile(latencies, 0.95),
        "mean_repeatability_jaccard": (
            statistics.fmean(repeatability) if repeatability else None
        ),
        "image_runs": len(records),
    }


def grouped_summaries(records: list[dict], field: str) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[str(record.get(field, "unknown"))].append(record)
    return {name: summarize(group) for name, group in sorted(groups.items())}


def bootstrap_metric_intervals(
    records: list[dict], samples: int = 2000, seed: int = 20260923
) -> dict:
    """Return image-cluster bootstrap intervals without treating repeats as independent."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["image_id"]].append(record)
    image_ids = sorted(grouped)
    if not image_ids:
        return {}
    randomizer = random.Random(seed)
    sampled_metrics = {metric: [] for metric in ("precision", "recall", "f1")}
    for _ in range(samples):
        selected = [randomizer.choice(image_ids) for _ in image_ids]
        tp = sum(record["tp"] for image_id in selected for record in grouped[image_id])
        fp = sum(record["fp"] for image_id in selected for record in grouped[image_id])
        fn = sum(record["fn"] for image_id in selected for record in grouped[image_id])
        metrics = score_counts(tp, fp, fn)
        for metric in sampled_metrics:
            sampled_metrics[metric].append(metrics[metric])
    return {
        metric: {
            "lower_95": percentile(values, 0.025),
            "upper_95": percentile(values, 0.975),
        }
        for metric, values in sampled_metrics.items()
    }


def paired_f1_bootstrap(
    left_records: list[dict],
    right_records: list[dict],
    samples: int = 2000,
    seed: int = 20260923,
) -> dict:
    """Estimate the paired F1 difference by resampling shared image clusters."""
    grouped: list[dict[str, list[dict]]] = []
    for records in (left_records, right_records):
        by_image: dict[str, list[dict]] = defaultdict(list)
        for record in records:
            by_image[record["image_id"]].append(record)
        grouped.append(by_image)
    image_ids = sorted(set(grouped[0]) & set(grouped[1]))
    if not image_ids:
        return {}

    def micro_f1(by_image: dict[str, list[dict]], selected: list[str]) -> float:
        tp = sum(record["tp"] for image_id in selected for record in by_image[image_id])
        fp = sum(record["fp"] for image_id in selected for record in by_image[image_id])
        fn = sum(record["fn"] for image_id in selected for record in by_image[image_id])
        return score_counts(tp, fp, fn)["f1"]

    observed = micro_f1(grouped[1], image_ids) - micro_f1(grouped[0], image_ids)
    randomizer = random.Random(seed)
    differences = []
    for _ in range(samples):
        selected = [randomizer.choice(image_ids) for _ in image_ids]
        differences.append(micro_f1(grouped[1], selected) - micro_f1(grouped[0], selected))
    return {
        "right_minus_left_f1": observed,
        "lower_95": percentile(differences, 0.025),
        "upper_95": percentile(differences, 0.975),
        "image_clusters": len(image_ids),
        "bootstrap_samples": samples,
    }


def evaluation_signature(
    images: list[dict], models: list[str], split: str, runs: int
) -> str:
    """Fingerprint every frozen input that could affect a resumable evaluation."""
    records = [
        {
            "id": record.get("id"),
            "image": record.get("image"),
            "scene_type": record.get("scene_type"),
            "packaging": record.get("packaging"),
            "difficulty": record.get("difficulty"),
            "ingredients": record.get("ingredients"),
            "second_review_status": record.get("second_review_status"),
        }
        for record in images
    ]
    frozen = {
        "records": records,
        "models": models,
        "split": split,
        "runs": runs,
        "prompt": build_pantry_vision_prompt(),
        "label_canonicalization": LABEL_CANONICALIZATION,
        "context_tokens": VISION_CONTEXT_TOKENS,
        "max_image_side": VISION_MAX_IMAGE_SIDE,
        "minimum_confidence": float(os.getenv("MEALMATCH_VLM_MIN_CONFIDENCE", "0.45")),
    }
    encoded = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_checkpoint(path: Path, signature: str) -> dict[tuple[str, str, int], dict]:
    records: dict[tuple[str, str, int], dict] = {}
    if not path.exists():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("signature") != signature:
            raise SystemExit(
                f"Checkpoint signature mismatch at line {line_number}; use a new output directory."
            )
        record = entry["record"]
        key = (str(entry["model"]), str(record["image_id"]), int(record["run"]))
        records[key] = record
    return records


def append_checkpoint(path: Path, signature: str, model: str, record: dict) -> None:
    with path.open("a", encoding="utf-8") as checkpoint:
        checkpoint.write(
            json.dumps({"signature": signature, "model": model, "record": record}) + "\n"
        )
        checkpoint.flush()


def select_model(results_by_model: dict[str, dict]) -> dict:
    """Apply the selection rule declared before the frozen test was inspected."""
    eligibility = {
        model: (
            result["summary"]["failure_rate"] <= 0.05
            and result["summary"]["median_latency_ms"] <= 45_000
        )
        for model, result in results_by_model.items()
    }
    eligible = [model for model, allowed in eligibility.items() if allowed]
    if not eligible:
        return {
            "winner": None,
            "eligible": eligibility,
            "reason": "No candidate met both predeclared operational gates.",
        }
    ranked = sorted(
        eligible,
        key=lambda model: results_by_model[model]["summary"]["f1"],
        reverse=True,
    )
    winner = ranked[0]
    reason = "Highest ingredient F1 among operationally eligible candidates."
    if len(ranked) > 1:
        first, second = ranked[:2]
        first_f1 = results_by_model[first]["summary"]["f1"]
        second_f1 = results_by_model[second]["summary"]["f1"]
        if abs(first_f1 - second_f1) < 0.03:
            unpackaged_recall = {
                model: results_by_model[model]
                .get("by_packaging", {})
                .get("unpackaged", {})
                .get("recall", 0.0)
                for model in (first, second)
            }
            if abs(unpackaged_recall[first] - unpackaged_recall[second]) >= 0.03:
                winner = max(unpackaged_recall, key=unpackaged_recall.get)
                reason = "F1 was practically tied; selected higher unpackaged-scene recall."
            elif {first, second} == {"qwen2.5vl:3b", "qwen2.5vl:7b"}:
                latency_3b = results_by_model["qwen2.5vl:3b"]["summary"]["median_latency_ms"]
                latency_7b = results_by_model["qwen2.5vl:7b"]["summary"]["median_latency_ms"]
                if latency_7b > 1.5 * latency_3b:
                    winner = "qwen2.5vl:3b"
                    reason = "F1 and unpackaged recall were practically tied; 7B was over 1.5 times slower."
    return {"winner": winner, "eligible": eligibility, "reason": reason}


def markdown_report(payload: dict) -> str:
    lines = [
        "# Qwen household-photo evaluation results",
        "",
        f"**Generated:** {payload['generated_at']}",
        f"**Manifest:** `{payload['manifest']}`",
        f"**Split:** `{payload['split']}`",
        f"**Images:** {payload['image_count']}",
        f"**Repeated runs per image:** {payload['runs_per_image']}",
        "",
        "Both variants used the identical production prompt and output validation. Model selection must be based on the frozen test split, not the development split.",
        "",
        "| Model | Precision | Recall | F1 | Hallucinations/image | Misses/image | Empty | Failures | Median latency | Repeatability |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model_name, result in payload["models"].items():
        summary = result["summary"]
        repeatability = summary["mean_repeatability_jaccard"]
        lines.append(
            "| "
            + " | ".join(
                [
                    vision_model_display_name(model_name),
                    f"{summary['precision']:.3f}",
                    f"{summary['recall']:.3f}",
                    f"{summary['f1']:.3f}",
                    f"{summary['mean_hallucinations_per_image_run']:.2f}",
                    f"{summary['mean_misses_per_image_run']:.2f}",
                    f"{summary['empty_response_rate']:.1%}",
                    f"{summary['failure_rate']:.1%}",
                    f"{summary['median_latency_ms']:.0f} ms",
                    "n/a" if repeatability is None else f"{repeatability:.3f}",
                ]
            )
            + " |"
        )
    if payload.get("paired_f1_comparison"):
        comparison = payload["paired_f1_comparison"]
        lines.extend(
            [
                "",
                "## Paired uncertainty estimate",
                "",
                f"The paired image-cluster bootstrap estimates `{comparison['right_model']}` minus `{comparison['left_model']}` F1 as "
                f"{comparison['right_minus_left_f1']:.3f} (95% interval {comparison['lower_95']:.3f} to {comparison['upper_95']:.3f}; "
                f"{comparison['bootstrap_samples']} resamples).",
            ]
        )
    if payload.get("selection", {}).get("winner"):
        selection = payload["selection"]
        lines.extend(
            [
                "",
                "## Final selection",
                "",
                f"**Selected runtime model: {vision_model_display_name(selection['winner'])}.** "
                + selection["reason"],
            ]
        )
    lines.extend(
        [
            "",
            "## Selection rule",
            "",
            "A candidate is operationally eligible when failure rate is at most 5% and median latency is at most 45 seconds on the reference machine. Select the eligible model with the highest ingredient F1. Treat an absolute F1 difference below 0.03 as practically tied; then prefer unpackaged-scene recall, and prefer 3B if recall is also within 0.03 while 7B is more than 1.5 times slower. Do not treat self-reported confidence as calibrated probability.",
            "",
            "Full predictions, misses, hallucinations, subgroup summaries and errors are retained in the adjacent JSON file.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images = manifest.get(args.split, [])
    if not isinstance(images, list) or not images:
        raise SystemExit(f"Manifest split '{args.split}' is missing or empty.")
    unverified = [str(record.get("id", "<missing id>")) for record in images if record.get("annotation_status") != "verified"]
    if unverified:
        raise SystemExit(
            "Evaluation requires human-verified ground truth. Unverified records: "
            + ", ".join(unverified[:10])
        )
    incomplete_metadata = [
        str(record.get("id", "<missing id>"))
        for record in images
        if any(record.get(field, "unknown") == "unknown" for field in ("scene_type", "packaging", "difficulty"))
    ]
    if incomplete_metadata:
        raise SystemExit(
            "Complete scene_type, packaging and difficulty before evaluation. Records: "
            + ", ".join(incomplete_metadata[:10])
        )
    if args.split == "test":
        reviewed = [
            record
            for record in images
            if record.get("second_review_status") in {"agreed", "resolved"}
        ]
        required_reviews = math.ceil(len(images) * 0.20)
        if len(reviewed) < required_reviews:
            raise SystemExit(
                "Frozen-test evaluation requires second-person review of at least "
                f"20% of labels ({required_reviews}/{len(images)}); found {len(reviewed)}."
            )

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    signature = evaluation_signature(images, args.models, args.split, args.runs)
    checkpoint_path = output_dir / f"qwen-household-{args.split}.checkpoint.jsonl"
    if checkpoint_path.exists() and not args.resume:
        raise SystemExit(
            f"Checkpoint already exists: {checkpoint_path}. Pass --resume or use a new output directory."
        )
    checkpoint_records = load_checkpoint(checkpoint_path, signature) if args.resume else {}
    total_calls = len(images) * len(args.models) * args.runs
    completed_calls = len(checkpoint_records)
    if completed_calls:
        print(f"Resuming {completed_calls}/{total_calls} completed image-model runs.", flush=True)
    results_by_model: dict[str, dict] = {}

    for model_name in args.models:
        records: list[dict] = [
            record
            for (saved_model, _, _), record in checkpoint_records.items()
            if saved_model == model_name
        ]
        for image_record in images:
            image_id = str(image_record.get("id", "")).strip()
            relative_path = Path(str(image_record.get("image", "")))
            image_path = relative_path if relative_path.is_absolute() else manifest_path.parent / relative_path
            if not image_id or not image_path.exists():
                raise SystemExit(f"Missing id or image for manifest record: {image_record}")
            truth = truth_entries(image_record.get("ingredients"))
            for run_index in range(1, args.runs + 1):
                key = (model_name, image_id, run_index)
                if key in checkpoint_records:
                    continue
                started = time.perf_counter()
                error = ""
                suggestions: list[dict] = []
                try:
                    suggestions = identify_foods_with_qwen(str(image_path), model_name)
                except Exception as exc:  # retain failures as measurable outcomes
                    error = str(exc)
                latency_ms = (time.perf_counter() - started) * 1000
                predictions = [item["ingredient"] for item in suggestions]
                match = match_predictions(predictions, truth)
                record = {
                        "image_id": image_id,
                        "image": str(relative_path),
                        "run": run_index,
                        "scene_type": image_record.get("scene_type", "unknown"),
                        "packaging": image_record.get("packaging", "unknown"),
                        "difficulty": image_record.get("difficulty", "unknown"),
                        "ground_truth": [item["name"] for item in truth],
                        "predictions": predictions,
                        "normalized_predictions": [normalize_label(value) for value in predictions],
                        "suggestions": suggestions,
                        "latency_ms": round(latency_ms, 2),
                        "error": error,
                        **match,
                    }
                records.append(record)
                append_checkpoint(checkpoint_path, signature, model_name, record)
                completed_calls += 1
                print(
                    f"[{completed_calls}/{total_calls}] {model_name} {image_id} run {run_index}",
                    flush=True,
                )
        records.sort(key=lambda record: (record["image"], record["run"]))
        results_by_model[model_name] = {
            "summary": summarize(records),
            "confidence_intervals": bootstrap_metric_intervals(records),
            "by_scene_type": grouped_summaries(records, "scene_type"),
            "by_packaging": grouped_summaries(records, "packaging"),
            "by_difficulty": grouped_summaries(records, "difficulty"),
            "records": records,
        }

    paired_comparison = {}
    if len(args.models) == 2:
        paired_comparison = {
            "left_model": args.models[0],
            "right_model": args.models[1],
            **paired_f1_bootstrap(
                results_by_model[args.models[0]]["records"],
                results_by_model[args.models[1]]["records"],
            ),
        }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "split": args.split,
        "image_count": len(images),
        "runs_per_image": args.runs,
        "prompt": build_pantry_vision_prompt(),
        "normalization": "case-fold, punctuation-to-space, whitespace collapse, frozen pantry-concept canonicalization, then exact canonical/declared-alias match",
        "label_canonicalization": LABEL_CANONICALIZATION,
        "evaluation_signature": signature,
        "configuration": {
            "context_tokens": VISION_CONTEXT_TOKENS,
            "max_image_side": VISION_MAX_IMAGE_SIDE,
            "timeout_seconds": VISION_TIMEOUT_SECONDS,
            "minimum_confidence": float(os.getenv("MEALMATCH_VLM_MIN_CONFIDENCE", "0.45")),
        },
        "selection": select_model(results_by_model),
        "paired_f1_comparison": paired_comparison,
        "models": results_by_model,
    }
    json_path = output_dir / f"qwen-household-{args.split}.json"
    markdown_path = output_dir / f"qwen-household-{args.split}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(markdown_report(payload), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    main()
