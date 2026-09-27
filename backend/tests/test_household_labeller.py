from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


EVALUATION_DIR = Path(__file__).resolve().parents[1] / "vision_evaluation"
sys.path.insert(0, str(EVALUATION_DIR))

from label_household_photos import (  # noqa: E402
    entries_to_ingredient_text,
    exclude_records,
    initialize_manifest,
    ingredient_text_to_entries,
    update_record,
)


class HouseholdLabellerTests(unittest.TestCase):
    def test_initialization_adds_supported_images_once(self):
        with tempfile.TemporaryDirectory(prefix="mealmatch-household-labels-") as directory:
            root = Path(directory)
            images = root / "images"
            images.mkdir()
            (images / "fridge.jpg").write_bytes(b"image")
            (images / "pantry.png").write_bytes(b"image")
            (images / "notes.txt").write_text("not an image", encoding="utf-8")
            manifest_path = root / "manifest.json"

            first = initialize_manifest(images, manifest_path, development_fraction=0.5)
            second = initialize_manifest(images, manifest_path, development_fraction=0.5)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(first["images_found"], 2)
            self.assertEqual(first["development_added"] + first["test_added"], 2)
            self.assertEqual(second["development_added"] + second["test_added"], 0)
            self.assertEqual(len(payload["development"]) + len(payload["test"]), 2)

    def test_verified_labels_and_aliases_are_saved_separately_from_drafts(self):
        payload = {
            "development": [
                {
                    "id": "photo-1",
                    "image": "images/one.jpg",
                    "ingredients": [],
                    "draft_predictions": {"qwen2.5vl:3b": {"items": [{"ingredient": "pear"}]}},
                    "draft_revealed": False,
                }
            ],
            "test": [],
        }
        record = update_record(
            payload,
            {
                "id": "photo-1",
                "split": "test",
                "scene_type": "fridge",
                "packaging": "mixed",
                "difficulty": "moderate",
                "annotator": "A1",
                "ingredient_text": "eggs | egg\nmilk\neggs",
                "verified": True,
                "second_review_status": "not_reviewed",
            },
        )

        self.assertEqual(payload["development"], [])
        self.assertEqual(payload["test"][0]["id"], "photo-1")
        self.assertEqual(record["annotation_method"], "independent_human")
        self.assertEqual(
            record["ingredients"],
            [
                {"name": "eggs", "aliases": ["egg"]},
                {"name": "milk", "aliases": []},
            ],
        )
        self.assertIn("qwen2.5vl:3b", record["draft_predictions"])

    def test_ingredient_text_round_trip(self):
        entries = ingredient_text_to_entries("whole milk | milk, milk carton\nbroccoli")
        self.assertEqual(
            entries_to_ingredient_text(entries),
            "whole milk | milk, milk carton\nbroccoli",
        )

    def test_exclusion_preserves_record_and_original_split(self):
        with tempfile.TemporaryDirectory(prefix="mealmatch-household-exclusion-") as directory:
            manifest_path = Path(directory) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "development": [{"id": "duplicate-1", "image": "images/copy.jpg"}],
                        "test": [],
                    }
                ),
                encoding="utf-8",
            )
            excluded = exclude_records(manifest_path, ["duplicate-1"], "exact duplicate")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["development"], [])
            self.assertEqual(excluded[0]["original_split"], "development")
            self.assertEqual(payload["excluded"][0]["exclusion_reason"], "exact duplicate")


if __name__ == "__main__":
    unittest.main()
