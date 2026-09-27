"""Convert the frozen COCO subset into Ultralytics YOLO training labels.

The Open Images-derived COCO files remain the annotation source of truth. This
script only creates the normalized text labels and dataset YAML required by the
Ultralytics trainer; it never changes the official train/validation/test split.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def convert_split(dataset_root: Path, split: str) -> dict[str, int]:
    annotation_path = dataset_root / "annotations" / f"instances_{split}.json"
    if not annotation_path.exists():
        raise FileNotFoundError(f"Missing {annotation_path}")

    dataset = json.loads(annotation_path.read_text(encoding="utf-8"))
    images = {image["id"]: image for image in dataset["images"]}
    category_index = {
        category["id"]: index
        for index, category in enumerate(dataset["categories"])
    }
    labels_by_image: dict[int, list[str]] = {image_id: [] for image_id in images}
    skipped_groups = 0

    for annotation in dataset["annotations"]:
        if annotation.get("iscrowd", 0):
            skipped_groups += 1
            continue
        image = images[annotation["image_id"]]
        x, y, width, height = annotation["bbox"]
        x_center = (x + width / 2) / image["width"]
        y_center = (y + height / 2) / image["height"]
        normalized_width = width / image["width"]
        normalized_height = height / image["height"]
        values = (x_center, y_center, normalized_width, normalized_height)
        if any(value < 0 or value > 1 for value in values):
            raise ValueError(
                f"Out-of-range normalized box for annotation {annotation['id']}"
            )
        labels_by_image[annotation["image_id"]].append(
            f"{category_index[annotation['category_id']]} "
            f"{x_center:.8f} {y_center:.8f} "
            f"{normalized_width:.8f} {normalized_height:.8f}"
        )

    labels_dir = dataset_root / "labels" / split
    labels_dir.mkdir(parents=True, exist_ok=True)
    object_count = 0
    for image_id, image in images.items():
        label_path = labels_dir / f"{Path(image['file_name']).stem}.txt"
        labels = labels_by_image[image_id]
        label_path.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
        object_count += len(labels)

    return {
        "images": len(images),
        "objects": object_count,
        "skipped_group_annotations": skipped_groups,
    }


def write_dataset_yaml(dataset_root: Path, categories: list[dict]) -> Path:
    names = "\n".join(
        f"  {index}: {json.dumps(category['name'])}"
        for index, category in enumerate(categories)
    )
    yaml_path = dataset_root / "yolo_dataset.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                f"path: {dataset_root.resolve()}",
                "train: images/train",
                "val: images/validation",
                "test: images/test",
                "names:",
                names,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return yaml_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/open_images_food"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summaries = {
        split: convert_split(args.dataset, split)
        for split in ("train", "validation", "test")
    }
    train_data = json.loads(
        (args.dataset / "annotations" / "instances_train.json").read_text(
            encoding="utf-8"
        )
    )
    yaml_path = write_dataset_yaml(args.dataset, train_data["categories"])
    print(json.dumps({"yaml": str(yaml_path.resolve()), "splits": summaries}, indent=2))


if __name__ == "__main__":
    main()
