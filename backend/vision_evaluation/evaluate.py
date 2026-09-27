"""Compare YOLO-World and Grounding DINO on the prepared food subset."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import statistics
from time import perf_counter
from datetime import datetime, timezone
from pathlib import Path

MODEL_CACHE = Path(__file__).resolve().parents[1] / ".model_cache"
(MODEL_CACHE / "matplotlib").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MODEL_CACHE / "matplotlib"))

from detectors import build_detector, transformed_image
from metrics import full_metrics


def load_dataset(dataset_root: Path, split: str) -> dict:
    path = dataset_root / "annotations" / f"instances_{split}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run prepare_open_images.py before evaluation."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def run_inference(
    detector,
    detector_name: str,
    dataset_root: Path,
    dataset: dict,
    condition: str,
    minimum_score: float,
) -> tuple[list[dict], dict]:
    categories = {category["name"]: category["id"] for category in dataset["categories"]}
    predictions: list[dict] = []
    latency_ms: list[float] = []
    batch_size = max(1, int(getattr(detector, "batch_size", 1)))
    image_records = dataset["images"]
    for start in range(0, len(image_records), batch_size):
        batch_info = image_records[start : start + batch_size]
        images = [
            transformed_image(dataset_root / image_info["file_name"], condition)
            for image_info in batch_info
        ]
        started = perf_counter()
        if hasattr(detector, "predict_batch"):
            batch_results = detector.predict_batch(images, minimum_score)
        else:
            batch_results = [detector.predict(image, minimum_score) for image in images]
        elapsed_per_image = (perf_counter() - started) * 1000 / len(images)
        latency_ms.extend([elapsed_per_image] * len(images))
        for image_info, results in zip(batch_info, batch_results):
            for result in results:
                predictions.append(
                    {
                        "image_id": image_info["id"],
                        "category_id": categories[result["category_name"]],
                        "bbox": result["bbox"],
                        "score": result["score"],
                    }
                )
        completed = start + len(batch_info)
        if completed % 10 < batch_size or completed == len(image_records):
            print(
                f"  {detector_name}/{condition}: "
                f"{completed}/{len(image_records)}"
            )
    ordered_latency = sorted(latency_ms)
    p95_index = max(0, min(len(ordered_latency) - 1, round(0.95 * len(ordered_latency)) - 1))
    return predictions, {
        "mean_latency_ms": round(statistics.fmean(latency_ms), 2) if latency_ms else 0.0,
        "p95_latency_ms": round(ordered_latency[p95_index], 2) if ordered_latency else 0.0,
        "images": len(latency_ms),
    }


def filtered(predictions: list[dict], score: float) -> list[dict]:
    return [prediction for prediction in predictions if prediction["score"] >= score]


def choose_threshold(
    dataset: dict, predictions: list[dict], thresholds: list[float]
) -> tuple[float, dict, list[dict]]:
    candidates = []
    for threshold in thresholds:
        metrics = full_metrics(dataset, filtered(predictions, threshold))
        candidates.append((threshold, metrics))
    best_threshold, best_metrics = max(
        candidates, key=lambda item: (item[1]["f1_50"], item[1]["map_50"])
    )
    sweep = [
        {
            "threshold": threshold,
            "map_50": metrics["map_50"],
            "precision_50": metrics["precision_50"],
            "recall_50": metrics["recall_50"],
            "f1_50": metrics["f1_50"],
            "ndcg_50": metrics["ndcg_50"],
        }
        for threshold, metrics in candidates
    ]
    return best_threshold, best_metrics, sweep


def write_confusion_csv(path: Path, metrics: dict, category_names: dict[int, str]) -> None:
    labels = [category_names.get(int(label), label) if label != "background" else label for label in metrics["confusion_labels"]]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["actual\\predicted", *labels])
        for label, row in zip(labels, metrics["confusion_matrix"]):
            writer.writerow([label, *row])


def report_markdown(results: list[dict], run_metadata: dict) -> str:
    validation = run_metadata["dataset"]["validation"]
    test = run_metadata["dataset"]["test"]
    lines = [
        "# Pantry detector evaluation results",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Run label: {run_metadata['run_label']}",
        (
            f"Dataset: {validation['images']} validation images / "
            f"{validation['annotations']} annotations; {test['images']} test images / "
            f"{test['annotations']} annotations; {run_metadata['dataset']['classes']} classes."
        ),
        "",
        "| Model | Condition | Threshold | mAP@0.50 | mAP@0.50:0.95 | Precision | Recall | NDCG@0.50 | Mean latency (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        metrics = result["metrics"]
        lines.append(
            f"| {result['model']} | {result['condition']} | {result['threshold']:.2f} "
            f"| {metrics['map_50']:.3f} | {metrics['map_50_95']:.3f} "
            f"| {metrics['precision_50']:.3f} | {metrics['recall_50']:.3f} "
            f"| {metrics['ndcg_50']:.3f} | {result['latency']['mean_latency_ms']:.1f} |"
        )
    lines.extend(
        [
            "",
            "Validation selects each model's confidence threshold by F1@IoU 0.50. The untouched test split provides final results. Dark, bright and blur conditions are deterministic robustness tests and do not alter ground-truth boxes.",
            "",
            "Confusion matrices and raw JSON predictions are stored beside this report.",
        ]
    )
    lines.extend(["", "## Reproducibility", "", "```json", json.dumps(run_metadata, indent=2), "```"])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/open_images_food"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/vision_evaluation"))
    parser.add_argument(
        "--models", nargs="+", choices=["yolo_world", "grounding_dino"], default=["yolo_world", "grounding_dino"]
    )
    parser.add_argument(
        "--conditions", nargs="+", choices=["original", "dark", "bright", "blur"], default=["original", "dark", "bright", "blur"]
    )
    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70],
    )
    parser.add_argument("--run-label", default="pretrained-zero-shot")
    return parser.parse_args()


def split_summary(dataset: dict) -> dict[str, int]:
    return {
        "images": len(dataset["images"]),
        "annotations": sum(
            1 for annotation in dataset["annotations"] if not annotation.get("iscrowd", 0)
        ),
        "group_annotations_excluded": sum(
            1 for annotation in dataset["annotations"] if annotation.get("iscrowd", 0)
        ),
    }


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    validation = load_dataset(args.dataset, "validation")
    test = load_dataset(args.dataset, "test")
    category_names = {item["id"]: item["name"] for item in test["categories"]}
    all_results: list[dict] = []
    run_metadata = {
        "run_label": args.run_label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "packages": {
            name: package_version(name)
            for name in ("torch", "ultralytics", "transformers", "Pillow")
        },
        "dataset": {
            "validation": split_summary(validation),
            "test": split_summary(test),
            "classes": len(test["categories"]),
            "selection_seed": test.get("info", {}).get("selection_seed"),
        },
        "threshold_candidates": args.thresholds,
        "threshold_selection": "maximum validation F1@IoU0.50; mAP@0.50 tie-break",
        "conditions": args.conditions,
        "models": {},
    }
    existing_metadata_path = args.output / "run_metadata.json"
    if existing_metadata_path.exists():
        existing_metadata = json.loads(existing_metadata_path.read_text(encoding="utf-8"))
        run_metadata["models"].update(existing_metadata.get("models", {}))

    for model_name in args.models:
        print(f"Loading {model_name}")
        class_names = [category["name"] for category in validation["categories"]]
        detector = build_detector(model_name, class_names)
        run_metadata["models"][model_name] = detector.metadata
        validation_predictions, validation_latency = run_inference(
            detector, model_name, args.dataset, validation, "original", min(args.thresholds)
        )
        best_threshold, validation_metrics, threshold_sweep = choose_threshold(
            validation, validation_predictions, args.thresholds
        )
        (args.output / f"{model_name}_validation_predictions.json").write_text(
            json.dumps(validation_predictions, indent=2), encoding="utf-8"
        )
        (args.output / f"{model_name}_validation_metrics.json").write_text(
            json.dumps(
                {
                    "threshold": best_threshold,
                    "threshold_sweep": threshold_sweep,
                    "metrics": validation_metrics,
                    "latency": validation_latency,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        for condition in args.conditions:
            test_predictions, latency = run_inference(
                detector, model_name, args.dataset, test, condition, min(args.thresholds)
            )
            accepted = filtered(test_predictions, best_threshold)
            metrics = full_metrics(test, accepted)
            result = {
                "model": model_name,
                "condition": condition,
                "threshold": best_threshold,
                "metrics": metrics,
                "latency": latency,
            }
            all_results.append(result)
            stem = f"{model_name}_test_{condition}"
            (args.output / f"{stem}_predictions.json").write_text(
                json.dumps(accepted, indent=2), encoding="utf-8"
            )
            (args.output / f"{stem}_metrics.json").write_text(
                json.dumps(metrics, indent=2), encoding="utf-8"
            )
            (args.output / f"{stem}_result.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            write_confusion_csv(
                args.output / f"{stem}_confusion.csv", metrics, category_names
            )

    stored_results = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.output.glob("*_test_*_result.json"))
    ]
    if stored_results:
        all_results = stored_results
    (args.output / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2), encoding="utf-8"
    )
    (args.output / "all_results.json").write_text(
        json.dumps(all_results, indent=2), encoding="utf-8"
    )
    (args.output / "results.md").write_text(
        report_markdown(all_results, run_metadata), encoding="utf-8"
    )
    print(f"Evaluation artifacts written to {args.output.resolve()}")


if __name__ == "__main__":
    main()
