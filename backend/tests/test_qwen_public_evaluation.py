from __future__ import annotations

import sys
import unittest
from pathlib import Path


EVALUATION_DIR = Path(__file__).resolve().parents[1] / "vision_evaluation"
sys.path.insert(0, str(EVALUATION_DIR))

from evaluate_qwen_public import (  # noqa: E402
    canonical_label,
    match_sets,
    parse_class_predictions,
    select_balanced_subset,
)


class QwenPublicEvaluationTests(unittest.TestCase):
    def test_public_label_normalization_and_closed_vocabulary(self):
        self.assertEqual(canonical_label("Orange (fruit)"), "orange")
        predictions, invalid = parse_class_predictions(
            ["Apple", "orange (fruit)", "apple", "dish soap"],
            ["apple", "orange"],
        )
        self.assertEqual(predictions, ["apple", "orange"])
        self.assertEqual(invalid, ["dish soap"])

    def test_balanced_selection_is_deterministic_and_covers_each_class(self):
        records = [
            {"image_id": 1, "file_name": "one.jpg", "truth": ["apple", "banana"], "quality": {"apple": 0.8, "banana": 0.7}},
            {"image_id": 2, "file_name": "two.jpg", "truth": ["apple"], "quality": {"apple": 0.9}},
            {"image_id": 3, "file_name": "three.jpg", "truth": ["banana"], "quality": {"banana": 0.9}},
        ]
        selected = select_balanced_subset(records, ["apple", "banana"], 2)
        counts = {label: sum(label in item["truth"] for item in selected) for label in ("apple", "banana")}
        self.assertEqual([item["image_id"] for item in selected], [1, 3, 2])
        self.assertEqual(counts, {"apple": 2, "banana": 2})

    def test_set_matching_counts_tp_fp_and_fn(self):
        result = match_sets(["apple", "banana"], ["apple", "pear"])
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
