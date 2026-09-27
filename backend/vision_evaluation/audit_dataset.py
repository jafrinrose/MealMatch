"""Audit split integrity and annotation coverage for the frozen benchmark."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * proportion
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def split_audit(path: Path) -> tuple[dict, set[str]]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    categories = {item["id"]: item["name"] for item in dataset["categories"]}
    images = {item["id"]: item for item in dataset["images"]}
    class_counts: Counter[str] = Counter()
    relative_areas: list[float] = []
    occluded = truncated = groups = 0
    for annotation in dataset["annotations"]:
        class_counts[categories[annotation["category_id"]]] += 1
        image = images[annotation["image_id"]]
        relative_areas.append(
            annotation["area"] / max(1, image["width"] * image["height"])
        )
        attributes = annotation.get("attributes", {})
        occluded += int(bool(attributes.get("is_occluded", 0)))
        truncated += int(bool(attributes.get("is_truncated", 0)))
        groups += int(bool(annotation.get("iscrowd", 0)))
    image_ids = {item["open_images_id"] for item in dataset["images"]}
    return (
        {
            "images": len(images),
            "annotations": len(dataset["annotations"]),
            "non_group_annotations": len(dataset["annotations"]) - groups,
            "group_annotations": groups,
            "occluded_annotations": occluded,
            "truncated_annotations": truncated,
            "annotations_per_class": dict(sorted(class_counts.items())),
            "relative_box_area": {
                "p10": percentile(relative_areas, 0.10),
                "median": percentile(relative_areas, 0.50),
                "p90": percentile(relative_areas, 0.90),
            },
        },
        image_ids,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/open_images_food"))
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summaries: dict[str, dict] = {}
    ids: dict[str, set[str]] = {}
    for split in ("train", "validation", "test"):
        summaries[split], ids[split] = split_audit(
            args.dataset / "annotations" / f"instances_{split}.json"
        )
    overlap = {
        "train_validation": len(ids["train"] & ids["validation"]),
        "train_test": len(ids["train"] & ids["test"]),
        "validation_test": len(ids["validation"] & ids["test"]),
    }
    payload = {
        "dataset": str(args.dataset.resolve()),
        "splits": summaries,
        "cross_split_image_overlap": overlap,
        "integrity_passed": all(value == 0 for value in overlap.values()),
    }
    output = args.output or args.dataset / "dataset_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
