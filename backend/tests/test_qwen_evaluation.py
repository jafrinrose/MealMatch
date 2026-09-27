from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


EVALUATION_DIR = Path(__file__).resolve().parents[1] / "vision_evaluation"
sys.path.insert(0, str(EVALUATION_DIR))

from evaluate_qwen_household import (  # noqa: E402
    append_checkpoint,
    bootstrap_metric_intervals,
    load_checkpoint,
    match_predictions,
    normalize_label,
    paired_f1_bootstrap,
    select_model,
    score_counts,
    truth_entries,
)


class QwenEvaluationTests(unittest.TestCase):
    def test_declared_aliases_match_without_fuzzy_false_positives(self):
        truth = truth_entries(
            [
                {"name": "eggs", "aliases": ["egg"]},
                {"name": "whole milk", "aliases": ["milk"]},
            ]
        )
        result = match_predictions(["Egg", "milk", "dish soap"], truth)
        self.assertEqual(result["tp"], 2)
        self.assertEqual(result["fp"], 1)
        self.assertEqual(result["fn"], 0)
        self.assertEqual(result["hallucinated"], ["dish soap"])

    def test_normalization_and_metrics_are_deterministic(self):
        self.assertEqual(normalize_label("  Green-Apple! "), "apple")
        self.assertEqual(normalize_label("Eggs"), "egg")
        self.assertEqual(normalize_label("Almond milk"), "almond milk")
        self.assertEqual(normalize_label("Milk"), "milk")
        metrics = score_counts(tp=3, fp=1, fn=2)
        self.assertAlmostEqual(metrics["precision"], 0.75)
        self.assertAlmostEqual(metrics["recall"], 0.6)
        self.assertAlmostEqual(metrics["f1"], 2 / 3)

    def test_bootstrap_resamples_images_and_paired_difference_is_directional(self):
        left = [
            {"image_id": "one", "tp": 1, "fp": 1, "fn": 1},
            {"image_id": "two", "tp": 1, "fp": 1, "fn": 1},
        ]
        right = [
            {"image_id": "one", "tp": 2, "fp": 0, "fn": 0},
            {"image_id": "two", "tp": 2, "fp": 0, "fn": 0},
        ]

        intervals = bootstrap_metric_intervals(right, samples=50, seed=7)
        difference = paired_f1_bootstrap(left, right, samples=50, seed=7)

        self.assertEqual(intervals["f1"]["lower_95"], 1.0)
        self.assertEqual(intervals["f1"]["upper_95"], 1.0)
        self.assertGreater(difference["right_minus_left_f1"], 0)
        self.assertGreater(difference["lower_95"], 0)

    def test_checkpoint_round_trip_and_signature_guard(self):
        record = {"image_id": "photo-1", "run": 1, "tp": 1, "fp": 0, "fn": 0}
        with tempfile.TemporaryDirectory(prefix="mealmatch-qwen-checkpoint-") as directory:
            path = Path(directory) / "checkpoint.jsonl"
            append_checkpoint(path, "signature-a", "qwen2.5vl:3b", record)

            loaded = load_checkpoint(path, "signature-a")
            self.assertEqual(loaded[("qwen2.5vl:3b", "photo-1", 1)], record)
            with self.assertRaises(SystemExit):
                load_checkpoint(path, "signature-b")

    def test_selection_rejects_higher_f1_model_that_fails_operational_gate(self):
        results = {
            "qwen2.5vl:3b": {
                "summary": {"f1": 0.22, "failure_rate": 0.0, "median_latency_ms": 7200},
                "by_packaging": {"unpackaged": {"recall": 0.25}},
            },
            "qwen2.5vl:7b": {
                "summary": {"f1": 0.25, "failure_rate": 0.067, "median_latency_ms": 44700},
                "by_packaging": {"unpackaged": {"recall": 0.51}},
            },
        }

        selection = select_model(results)

        self.assertEqual(selection["winner"], "qwen2.5vl:3b")
        self.assertTrue(selection["eligible"]["qwen2.5vl:3b"])
        self.assertFalse(selection["eligible"]["qwen2.5vl:7b"])


if __name__ == "__main__":
    unittest.main()
