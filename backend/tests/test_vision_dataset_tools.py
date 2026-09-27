from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


EVALUATION_DIR = Path(__file__).resolve().parents[1] / "vision_evaluation"
sys.path.insert(0, str(EVALUATION_DIR))

from prepare_yolo_finetuning import convert_split, write_dataset_yaml  # noqa: E402


class VisionDatasetToolTests(unittest.TestCase):
    def test_coco_boxes_convert_to_normalized_yolo_and_groups_are_skipped(self):
        with tempfile.TemporaryDirectory(prefix="mealmatch-yolo-conversion-") as directory:
            root = Path(directory)
            annotations = root / "annotations"
            annotations.mkdir()
            payload = {
                "images": [
                    {
                        "id": 7,
                        "file_name": "images/train/example.jpg",
                        "width": 200,
                        "height": 100,
                    }
                ],
                "categories": [{"id": 4, "name": "Apple"}],
                "annotations": [
                    {
                        "id": 1,
                        "image_id": 7,
                        "category_id": 4,
                        "bbox": [20, 10, 40, 20],
                        "iscrowd": 0,
                    },
                    {
                        "id": 2,
                        "image_id": 7,
                        "category_id": 4,
                        "bbox": [0, 0, 200, 100],
                        "iscrowd": 1,
                    },
                ],
            }
            (annotations / "instances_train.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

            summary = convert_split(root, "train")

            self.assertEqual(summary["images"], 1)
            self.assertEqual(summary["objects"], 1)
            self.assertEqual(summary["skipped_group_annotations"], 1)
            self.assertEqual(
                (root / "labels" / "train" / "example.txt").read_text().strip(),
                "0 0.20000000 0.20000000 0.20000000 0.20000000",
            )

    def test_dataset_yaml_preserves_category_order(self):
        with tempfile.TemporaryDirectory(prefix="mealmatch-yolo-yaml-") as directory:
            root = Path(directory)
            yaml_path = write_dataset_yaml(
                root, [{"id": 9, "name": "Apple"}, {"id": 2, "name": "Fish"}]
            )
            content = yaml_path.read_text(encoding="utf-8")
            self.assertIn('0: "Apple"', content)
            self.assertIn('1: "Fish"', content)
            self.assertLess(content.index('0: "Apple"'), content.index('1: "Fish"'))


if __name__ == "__main__":
    unittest.main()
