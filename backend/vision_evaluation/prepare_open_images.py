"""Download a class-balanced Open Images V7 food subset in COCO format.

The script uses only official Open Images annotation files and image storage. It
does not depend on any MealMatch-created labels. The original Open Images split
is retained so that validation decisions cannot leak into final test results.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image


CLASS_DESCRIPTION_URL = (
    "https://storage.googleapis.com/openimages/v7/"
    "oidv7-class-descriptions-boxable.csv"
)
ANNOTATION_URLS = {
    "train": "https://storage.googleapis.com/openimages/v6/oidv6-train-annotations-bbox.csv",
    "validation": "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv",
    "test": "https://storage.googleapis.com/openimages/v5/test-annotations-bbox.csv",
}
IMAGE_METADATA_URLS = {
    "train": "https://storage.googleapis.com/openimages/2018_04/train/train-images-boxable-with-rotation.csv",
    "validation": "https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv",
    "test": "https://storage.googleapis.com/openimages/2018_04/test/test-images-with-rotation.csv",
}
IMAGE_URL = "https://open-images-dataset.s3.amazonaws.com/{split}/{image_id}.jpg"

# These are generic, visually identifiable foods that are useful in a fridge,
# pantry, or grocery-on-table scene. The script validates every requested name
# against the official boxable-class file before downloading images.
DEFAULT_CLASSES = [
    "Apple",
    "Banana",
    "Orange (fruit)",
    "Strawberry",
    "Tomato",
    "Potato",
    "Carrot",
    "Cucumber",
    "Broccoli",
    "Cabbage",
    "Bell pepper",
    "Lemon (plant)",
    "Mango",
    "Pear",
    "Grape",
    "Peach",
    "Pineapple",
    "Pumpkin",
    "Watermelon",
    "Egg",
    "Milk",
    "Cheese",
    "Bread",
    "Pasta",
    "Chicken",
    "Fish",
    "Shrimp",
]


def download(url: str, destination: Path) -> None:
    """Stream a file once and retain it for repeatable reruns."""
    if destination.exists() and destination.stat().st_size:
        print(f"Using cached {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    print(f"Downloading {url}")
    with requests.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    partial.replace(destination)


def load_class_map(path: Path, requested_names: list[str]) -> dict[str, str]:
    available: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for mid, display_name in csv.reader(handle):
            available[display_name.casefold()] = mid

    missing = [name for name in requested_names if name.casefold() not in available]
    if missing:
        raise ValueError(
            "These names are not Open Images boxable classes: "
            + ", ".join(missing)
            + ". Pass --classes with names from oidv7-class-descriptions-boxable.csv."
        )
    return {available[name.casefold()]: name for name in requested_names}


def class_balanced_image_sample(
    annotation_path: Path,
    class_map: dict[str, str],
    per_class: int,
    seed: int,
) -> set[str]:
    """Reservoir-sample image IDs independently for each target class."""
    rng = random.Random(seed)
    reservoirs: dict[str, list[str]] = {mid: [] for mid in class_map}
    seen_images: dict[str, int] = defaultdict(int)
    previous_pair: tuple[str, str] | None = None

    with annotation_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            mid = row["LabelName"]
            if mid not in class_map or row.get("IsDepiction", "0") == "1":
                continue
            pair = (mid, row["ImageID"])
            if pair == previous_pair:
                continue
            previous_pair = pair
            seen_images[mid] += 1
            reservoir = reservoirs[mid]
            if len(reservoir) < per_class:
                reservoir.append(row["ImageID"])
            else:
                replacement = rng.randrange(seen_images[mid])
                if replacement < per_class:
                    reservoir[replacement] = row["ImageID"]

    for mid, image_ids in reservoirs.items():
        print(f"  {class_map[mid]}: selected {len(image_ids)} images")
    return {image_id for image_ids in reservoirs.values() for image_id in image_ids}


def selected_annotations(
    annotation_path: Path,
    image_ids: set[str],
    class_map: dict[str, str],
) -> dict[str, list[dict[str, str]]]:
    rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    with annotation_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (
                row["ImageID"] in image_ids
                and row["LabelName"] in class_map
                and row.get("IsDepiction", "0") != "1"
            ):
                rows[row["ImageID"]].append(row)
    return rows


def selected_image_metadata(metadata_path: Path, image_ids: set[str]) -> dict[str, dict[str, str]]:
    selected: dict[str, dict[str, str]] = {}
    with metadata_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("ImageID") in image_ids:
                selected[row["ImageID"]] = row
    return selected


def download_image(split: str, image_id: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = IMAGE_URL.format(split=split, image_id=image_id)
    partial = destination.with_suffix(".jpg.part")
    with requests.get(url, stream=True, timeout=(30, 180)) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            shutil.copyfileobj(response.raw, handle)
    partial.replace(destination)


def build_coco_split(
    split: str,
    output_root: Path,
    annotation_path: Path,
    metadata_path: Path,
    class_map: dict[str, str],
    per_class: int,
    seed: int,
    workers: int,
) -> dict[str, int]:
    print(f"Selecting {split} images")
    image_ids = class_balanced_image_sample(annotation_path, class_map, per_class, seed)
    rows_by_image = selected_annotations(annotation_path, image_ids, class_map)
    metadata_by_image = selected_image_metadata(metadata_path, image_ids)
    category_id_by_mid = {mid: index + 1 for index, mid in enumerate(class_map)}
    categories = [
        {"id": category_id_by_mid[mid], "name": name, "open_images_mid": mid}
        for mid, name in class_map.items()
    ]
    images: list[dict] = []
    annotations: list[dict] = []
    image_dir = output_root / "images" / split
    annotation_id = 1

    def fetch_and_measure(image_id: str) -> tuple[str, int, int]:
        path = image_dir / f"{image_id}.jpg"
        download_image(split, image_id, path)
        with Image.open(path) as image:
            width, height = image.size
        return image_id, width, height

    dimensions: dict[str, tuple[int, int]] = {}
    selected_ids = sorted(rows_by_image)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_and_measure, image_id): image_id
            for image_id in selected_ids
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            image_id = futures[future]
            try:
                _, width, height = future.result()
                dimensions[image_id] = (width, height)
            except Exception as error:
                print(f"Skipping {image_id}: {error}")
                (image_dir / f"{image_id}.jpg").unlink(missing_ok=True)
            if completed % 25 == 0 or completed == len(futures):
                print(f"  downloaded or checked {completed}/{len(futures)} images")

    for image_number, image_id in enumerate(sorted(dimensions), start=1):
        width, height = dimensions[image_id]

        metadata = metadata_by_image.get(image_id, {})
        images.append(
            {
                "id": image_number,
                "file_name": f"images/{split}/{image_id}.jpg",
                "width": width,
                "height": height,
                "open_images_id": image_id,
                "original_url": metadata.get("OriginalURL", ""),
                "original_landing_url": metadata.get("OriginalLandingURL", ""),
                "license_url": metadata.get("License", ""),
                "author": metadata.get("Author", ""),
                "title": metadata.get("Title", ""),
            }
        )
        for row in rows_by_image[image_id]:
            x_min = float(row["XMin"]) * width
            x_max = float(row["XMax"]) * width
            y_min = float(row["YMin"]) * height
            y_max = float(row["YMax"]) * height
            box_width = max(0.0, x_max - x_min)
            box_height = max(0.0, y_max - y_min)
            if not box_width or not box_height:
                continue
            annotations.append(
                {
                    "id": annotation_id,
                    "image_id": image_number,
                    "category_id": category_id_by_mid[row["LabelName"]],
                    "bbox": [x_min, y_min, box_width, box_height],
                    "area": box_width * box_height,
                    "iscrowd": int(row.get("IsGroupOf", "0") == "1"),
                    "attributes": {
                        "is_occluded": int(row.get("IsOccluded", "0") == "1"),
                        "is_truncated": int(row.get("IsTruncated", "0") == "1"),
                        "is_group_of": int(row.get("IsGroupOf", "0") == "1"),
                    },
                }
            )
            annotation_id += 1

    payload = {
        "info": {
            "description": "MealMatch Open Images V7 food-object benchmark subset",
            "source": "https://storage.googleapis.com/openimages/web/download_v7.html",
            "split": split,
            "selection_seed": seed,
            "requested_images_per_class": per_class,
        },
        "licenses": [
            {
                "id": 1,
                "name": "See original Open Images per-image metadata and licence",
                "url": "https://storage.googleapis.com/openimages/web/download_v7.html",
            }
        ],
        "images": images,
        "annotations": annotations,
        "categories": categories,
    }
    annotation_dir = output_root / "annotations"
    annotation_dir.mkdir(parents=True, exist_ok=True)
    with (annotation_dir / f"instances_{split}.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    attribution_dir = output_root / "attribution"
    attribution_dir.mkdir(parents=True, exist_ok=True)
    attribution_fields = [
        "ImageID", "OriginalURL", "OriginalLandingURL", "License", "AuthorProfileURL",
        "Author", "Title",
    ]
    with (attribution_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=attribution_fields)
        writer.writeheader()
        for image in images:
            metadata = metadata_by_image.get(image["open_images_id"], {})
            writer.writerow({field: metadata.get(field, "") for field in attribution_fields})
    return {"images": len(images), "annotations": len(annotations)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/open_images_food"),
        help="Dataset output directory (default: data/open_images_food)",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        choices=sorted(ANNOTATION_URLS),
        default=["train", "validation", "test"],
    )
    parser.add_argument("--train-per-class", type=int, default=80)
    parser.add_argument("--validation-per-class", type=int, default=20)
    parser.add_argument("--test-per-class", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Concurrent image downloads (default: 8)",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        default=DEFAULT_CLASSES,
        help="Exact Open Images display names to include",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_dir = args.output / "raw"
    class_path = raw_dir / "oidv7-class-descriptions-boxable.csv"
    download(CLASS_DESCRIPTION_URL, class_path)
    class_map = load_class_map(class_path, args.classes)
    quotas = {
        "train": args.train_per_class,
        "validation": args.validation_per_class,
        "test": args.test_per_class,
    }
    manifest = {
        "source": "Open Images V7",
        "classes": list(class_map.values()),
        "seed": args.seed,
        "splits": {},
    }

    for split in args.splits:
        annotation_path = raw_dir / f"{split}-annotations-bbox.csv"
        metadata_path = raw_dir / f"{split}-images-with-rotation.csv"
        download(ANNOTATION_URLS[split], annotation_path)
        download(IMAGE_METADATA_URLS[split], metadata_path)
        manifest["splits"][split] = build_coco_split(
            split,
            args.output,
            annotation_path,
            metadata_path,
            class_map,
            quotas[split],
            args.seed,
            max(1, args.workers),
        )

    with (args.output / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    print(f"Dataset ready at {args.output.resolve()}")


if __name__ == "__main__":
    main()
