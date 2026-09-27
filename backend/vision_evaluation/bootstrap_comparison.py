"""Calculate paired bootstrap uncertainty for two detector result sets."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from metrics import evaluate_at_iou, ndcg_by_image


METRIC_NAMES = ("map_50", "map_50_95", "precision_50", "recall_50", "f1_50", "ndcg_50")


def metric_summary(dataset: dict, predictions: list[dict]) -> dict[str, float]:
    category_ids = [category["id"] for category in dataset["categories"]]
    thresholds = [round(0.5 + index * 0.05, 2) for index in range(10)]
    results = [
        evaluate_at_iou(dataset["annotations"], predictions, category_ids, threshold)
        for threshold in thresholds
    ]
    return {
        "map_50": results[0]["map"],
        "map_50_95": sum(result["map"] for result in results) / len(results),
        "precision_50": results[0]["precision"],
        "recall_50": results[0]["recall"],
        "f1_50": results[0]["f1"],
        "ndcg_50": ndcg_by_image(dataset["annotations"], predictions),
    }


def grouped(items: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = defaultdict(list)
    for item in items:
        result[item["image_id"]].append(item)
    return result


def resample(
    dataset: dict,
    predictions: list[dict],
    sampled_ids: list[int],
) -> tuple[dict, list[dict]]:
    images = {item["id"]: item for item in dataset["images"]}
    annotations = grouped(dataset["annotations"])
    predictions_by_image = grouped(predictions)
    sampled_dataset = {**dataset, "images": [], "annotations": []}
    sampled_predictions: list[dict] = []
    annotation_id = 1
    for new_id, original_id in enumerate(sampled_ids, start=1):
        sampled_dataset["images"].append({**images[original_id], "id": new_id})
        for annotation in annotations.get(original_id, []):
            sampled_dataset["annotations"].append(
                {**annotation, "id": annotation_id, "image_id": new_id}
            )
            annotation_id += 1
        sampled_predictions.extend(
            {**prediction, "image_id": new_id}
            for prediction in predictions_by_image.get(original_id, [])
        )
    return sampled_dataset, sampled_predictions


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * proportion
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def interval(values: list[float]) -> dict[str, float]:
    return {
        "lower_95": percentile(values, 0.025),
        "median": percentile(values, 0.5),
        "upper_95": percentile(values, 0.975),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--left-name", default="left")
    parser.add_argument("--right-name", default="right")
    parser.add_argument("--replicates", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    left_predictions = json.loads(args.left.read_text(encoding="utf-8"))
    right_predictions = json.loads(args.right.read_text(encoding="utf-8"))
    image_ids = [image["id"] for image in dataset["images"]]
    rng = random.Random(args.seed)
    distributions = {
        args.left_name: {name: [] for name in METRIC_NAMES},
        args.right_name: {name: [] for name in METRIC_NAMES},
        f"{args.right_name}_minus_{args.left_name}": {name: [] for name in METRIC_NAMES},
    }
    for replicate in range(args.replicates):
        sampled_ids = [rng.choice(image_ids) for _ in image_ids]
        left_dataset, left_sample = resample(dataset, left_predictions, sampled_ids)
        _, right_sample = resample(dataset, right_predictions, sampled_ids)
        left_metrics = metric_summary(left_dataset, left_sample)
        right_metrics = metric_summary(left_dataset, right_sample)
        for name in METRIC_NAMES:
            distributions[args.left_name][name].append(left_metrics[name])
            distributions[args.right_name][name].append(right_metrics[name])
            distributions[f"{args.right_name}_minus_{args.left_name}"][name].append(
                right_metrics[name] - left_metrics[name]
            )
        if (replicate + 1) % 20 == 0:
            print(f"bootstrap {replicate + 1}/{args.replicates}")
    payload = {
        "method": "paired nonparametric bootstrap over test images",
        "replicates": args.replicates,
        "seed": args.seed,
        "images_per_replicate": len(image_ids),
        "intervals": {
            group: {name: interval(values) for name, values in metrics.items()}
            for group, metrics in distributions.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
