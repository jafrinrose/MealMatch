from __future__ import annotations

import sys
import unittest
from pathlib import Path


EVALUATION_DIR = Path(__file__).resolve().parents[1] / "vision_evaluation"
sys.path.insert(0, str(EVALUATION_DIR))

from metrics import full_metrics, iou  # noqa: E402


class VisionMetricTests(unittest.TestCase):
    def test_iou(self):
        self.assertEqual(iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)
        self.assertEqual(iou([0, 0, 5, 5], [10, 10, 5, 5]), 0.0)

    def test_perfect_predictions_score_one(self):
        dataset = {
            "categories": [{"id": 1, "name": "apple"}, {"id": 2, "name": "banana"}],
            "annotations": [
                {"image_id": 1, "category_id": 1, "bbox": [0, 0, 10, 10], "iscrowd": 0},
                {"image_id": 1, "category_id": 2, "bbox": [20, 20, 10, 10], "iscrowd": 0},
            ],
        }
        predictions = [
            {"image_id": 1, "category_id": 1, "bbox": [0, 0, 10, 10], "score": 0.9},
            {"image_id": 1, "category_id": 2, "bbox": [20, 20, 10, 10], "score": 0.8},
        ]
        metrics = full_metrics(dataset, predictions)
        self.assertEqual(metrics["map_50"], 1.0)
        self.assertEqual(metrics["map_50_95"], 1.0)
        self.assertEqual(metrics["precision_50"], 1.0)
        self.assertEqual(metrics["recall_50"], 1.0)
        self.assertEqual(metrics["ndcg_50"], 1.0)

    def test_prediction_inside_group_region_is_not_a_false_positive(self):
        dataset = {
            "categories": [{"id": 1, "name": "apple"}],
            "annotations": [
                {
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [0, 0, 100, 100],
                    "iscrowd": 1,
                },
                {
                    "image_id": 2,
                    "category_id": 1,
                    "bbox": [0, 0, 10, 10],
                    "iscrowd": 0,
                },
            ],
        }
        predictions = [
            {"image_id": 1, "category_id": 1, "bbox": [10, 10, 10, 10], "score": 0.9},
            {"image_id": 2, "category_id": 1, "bbox": [0, 0, 10, 10], "score": 0.8},
        ]
        metrics = full_metrics(dataset, predictions)
        self.assertEqual(metrics["precision_50"], 1.0)
        self.assertEqual(metrics["recall_50"], 1.0)


if __name__ == "__main__":
    unittest.main()
