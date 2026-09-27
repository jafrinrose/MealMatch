"""Expand threshold selection using saved predictions without rerunning models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate import choose_threshold, filtered, load_dataset
from metrics import full_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--model", choices=["yolo_world", "grounding_dino"], required=True)
    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validation = load_dataset(args.dataset, "validation")
    test = load_dataset(args.dataset, "test")
    validation_path = args.artifacts / f"{args.model}_validation_predictions.json"
    validation_metrics_path = args.artifacts / f"{args.model}_validation_metrics.json"
    predictions = json.loads(validation_path.read_text(encoding="utf-8"))
    old_validation = json.loads(validation_metrics_path.read_text(encoding="utf-8"))
    old_threshold = float(old_validation["threshold"])
    threshold, metrics, sweep = choose_threshold(validation, predictions, args.thresholds)
    if threshold < old_threshold:
        raise ValueError(
            f"New threshold {threshold} is below stored test floor {old_threshold}; "
            "rerun inference so lower-scored test predictions are retained."
        )
    validation_metrics_path.write_text(
        json.dumps(
            {
                "threshold": threshold,
                "threshold_sweep": sweep,
                "metrics": metrics,
                "latency": old_validation["latency"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for condition in ("original", "dark", "bright", "blur"):
        stem = f"{args.model}_test_{condition}"
        prediction_path = args.artifacts / f"{stem}_predictions.json"
        if not prediction_path.exists():
            continue
        condition_predictions = json.loads(prediction_path.read_text(encoding="utf-8"))
        accepted = filtered(condition_predictions, threshold)
        prediction_path.write_text(json.dumps(accepted, indent=2), encoding="utf-8")
        condition_metrics = full_metrics(test, accepted)
        (args.artifacts / f"{stem}_metrics.json").write_text(
            json.dumps(condition_metrics, indent=2), encoding="utf-8"
        )
        result_path = args.artifacts / f"{stem}_result.json"
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["threshold"] = threshold
            result["metrics"] = condition_metrics
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"model": args.model, "old_threshold": old_threshold, "new_threshold": threshold, "sweep": sweep}, indent=2))


if __name__ == "__main__":
    main()
