from __future__ import annotations

import os
import sys
import tempfile
import unittest
import base64
import io
from pathlib import Path

from PIL import Image


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from model_services import (  # noqa: E402
    build_pantry_vision_prompt,
    clean_qwen_items,
    encode_vision_image,
    vision_model_display_name,
)


class QwenVisionTests(unittest.TestCase):
    def test_prompt_covers_packaged_and_unpacked_food_and_blocks_household_goods(self):
        prompt = build_pantry_vision_prompt().casefold()
        self.assertIn("packaged or unpackaged", prompt)
        self.assertIn("soap", prompt)
        self.assertIn("do not infer hidden contents", prompt)

    def test_untrusted_items_are_normalized_and_non_food_is_removed(self):
        previous_threshold = os.environ.get("MEALMATCH_VLM_MIN_CONFIDENCE")
        os.environ["MEALMATCH_VLM_MIN_CONFIDENCE"] = "0.45"
        try:
            cleaned = clean_qwen_items(
                [
                    {
                        "ingredient": "Milk",
                        "quantity": 2,
                        "unit": "carton",
                        "category": "dairy",
                        "visible_text": "WHOLE MILK",
                        "confidence": 0.82,
                    },
                    {
                        "ingredient": "dish soap",
                        "quantity": 1,
                        "unit": "bottle",
                        "confidence": 0.99,
                    },
                    {
                        "ingredient": "broccoli",
                        "quantity": 1,
                        "unit": "piece",
                        "confidence": 0.3,
                    },
                ],
                "qwen2.5vl:7b",
            )
        finally:
            if previous_threshold is None:
                os.environ.pop("MEALMATCH_VLM_MIN_CONFIDENCE", None)
            else:
                os.environ["MEALMATCH_VLM_MIN_CONFIDENCE"] = previous_threshold

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["ingredient"], "milk")
        self.assertEqual(cleaned[0]["quantity"], "2 cartons")
        self.assertEqual(cleaned[0]["source"], "Qwen2.5-VL 7B")

    def test_vague_items_are_removed_and_duplicate_food_keeps_best_confidence(self):
        cleaned = clean_qwen_items(
            [
                {"ingredient": "packaged goods", "confidence": 0.99},
                {"ingredient": "Milk", "confidence": 0.62},
                {"ingredient": "milk", "confidence": 0.91, "quantity": 2, "unit": "carton"},
            ],
            "qwen2.5vl:3b",
        )

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["ingredient"], "milk")
        self.assertEqual(cleaned[0]["confidence"], 0.91)
        self.assertEqual(cleaned[0]["quantity"], "2 cartons")

    def test_image_encoding_caps_resolution_and_returns_jpeg(self):
        with tempfile.TemporaryDirectory(prefix="mealmatch-qwen-image-") as directory:
            source_path = Path(directory) / "large.png"
            Image.new("RGB", (2400, 1200), color=(220, 30, 80)).save(source_path)

            encoded = encode_vision_image(str(source_path))
            with Image.open(io.BytesIO(base64.b64decode(encoded))) as result:
                self.assertEqual(result.format, "JPEG")
                self.assertLessEqual(max(result.size), 1600)
                self.assertEqual(result.size, (1600, 800))

    def test_model_display_name_preserves_variant(self):
        self.assertEqual(vision_model_display_name("qwen2.5vl:3b"), "Qwen2.5-VL 3B")
        self.assertEqual(vision_model_display_name("qwen2.5vl:7b"), "Qwen2.5-VL 7B")


if __name__ == "__main__":
    unittest.main()
