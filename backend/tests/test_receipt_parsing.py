import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_services  # noqa: E402
from ai_services import extract_receipt_items, final_receipt_name, is_non_food  # noqa: E402
from receipt_parsing import ReceiptLine, expand_abbreviations, parse_receipt_lines  # noqa: E402

# Tesseract's reading of a real wholesale receipt, including its OCR mistakes.
WHOLESALE_OCR = [
    "=—WHOLEsarce =",
    "1127 Sumas Way",
    "TH Member 111800000000",
    "55506 B/S THIGHS 33.43",
    "27363 16/20 SHRIMP 30.57 :",
    "27363 16/20 SHRIMP 289.",
    "275713 KALAMATA OLY g'gg.",
    "776059 ARTISAN BGT 5.99",
    "776059 ARTISAN BGT 5.99",
    "76059 ARTISAN BGT 5.99",
    "0000351 /776059 1.00-",
    "1436 WHIP CREAMIL = 5.39",
    "SUBTOTAL 194.81",
    "AMOUNT: $194.81",
    "TOTAL NUMBER OF ITEMS SOLD = 7",
]


def model_reply(answers: dict[str, tuple[str, bool]]) -> str:
    return json.dumps({number: {"receipt": "", "ingredient": name, "food": food} for number, (name, food) in answers.items()})


def rows(result: dict) -> dict[str, str]:
    return {row["ingredient"]: row["quantity"] for row in result["detections"]}


class ReceiptLineParsingTests(unittest.TestCase):
    def test_keeps_product_lines_and_counts_repeats(self):
        lines = parse_receipt_lines(WHOLESALE_OCR)
        self.assertEqual(
            [(line.text, line.count) for line in lines],
            [("B/S THIGHS", 1), ("16/20 SHRIMP", 2), ("KALAMATA OLY", 1), ("ARTISAN BGT", 3), ("WHIP CREAMIL", 1)],
        )

    def test_reads_quantities_stated_on_the_receipt(self):
        lines = parse_receipt_lines([
            "GRK YGT PLAIN 750G 5.49",
            "GRK YGT PLAIN 750G 5.49",
            "EGGS LRG 12CT 4.79",
            "WHL MLK 4L 6.29",
            "BANANAS",
            "@.512 kg @ £1.52/kg 0.78",
            "AVOCADO",
            "3 @ 1.29 3.87",
            "LEMONS x3 0.90",
            "RUSSET POTATO 10LB 7.49",
        ])
        stated = {line.text: (line.count, line.size, line.weight and round(line.weight, 3)) for line in lines}
        self.assertEqual(stated["GRK YGT PLAIN"], (2, (750.0, "g"), None))
        self.assertEqual(stated["EGGS LRG"], (1, (12.0, "piece"), None))
        self.assertEqual(stated["WHL MLK"], (1, (4.0, "l"), None))
        self.assertEqual(stated["BANANAS"], (1, None, 0.512))
        self.assertEqual(stated["AVOCADO"][0], 3)
        self.assertEqual(stated["LEMONS"][0], 3)
        self.assertAlmostEqual(stated["RUSSET POTATO"][1][0], 4.536)

    def test_expands_listed_ocr_swapped_and_vowelless_abbreviations(self):
        self.assertEqual(expand_abbreviations("B/S THIGHS"), "boneless skinless thighs")
        self.assertEqual(expand_abbreviations("ARTISAN BGT"), "artisan baguette")
        self.assertEqual(expand_abbreviations("KALAMATA OLY"), "kalamata olives")  # OCR read V as Y
        self.assertEqual(expand_abbreviations("BRKFST SAUSAGE"), "breakfast sausage")
        self.assertEqual(expand_abbreviations("CHDR CHS"), "cheddar cheese")
        self.assertEqual(expand_abbreviations("CAT FOOD POUCHES"), "cat food pouches")
        self.assertEqual(expand_abbreviations("BIN BAGS"), "bin bags")


class ReceiptNamingTests(unittest.TestCase):
    def test_words_dropped_by_the_model_are_restored(self):
        self.assertEqual(final_receipt_name("milk", ReceiptLine(1, "WHL MLK")), "whole milk")
        self.assertEqual(final_receipt_name("onion", ReceiptLine(1, "RED ONION")), "red onion")
        self.assertEqual(final_receipt_name("romain lettuce", ReceiptLine(1, "ROM LETTUCE")), "romaine lettuce")

    def test_model_corrections_are_kept(self):
        self.assertEqual(final_receipt_name("whipping cream", ReceiptLine(1, "WHIP CREAMIL")), "whipping cream")
        self.assertEqual(final_receipt_name("feta cheese", ReceiptLine(1, "FETA CRMBL")), "feta cheese")

    def test_cut_only_means_chicken_and_brands_are_dropped(self):
        self.assertEqual(final_receipt_name("boneless skinless thighs", ReceiptLine(1, "B/S THIGHS")), "chicken thigh")
        self.assertEqual(final_receipt_name("president", ReceiptLine(1, "PRSDNT BRIE")), "brie")

    def test_non_food_matches_whole_words_only(self):
        self.assertTrue(is_non_food("paper towels"))
        self.assertFalse(is_non_food("bagel"))
        self.assertFalse(is_non_food("cabbage"))


class ReceiptExtractionTests(unittest.TestCase):
    def extract(self, ocr_lines, reply):
        with patch.object(ai_services, "ask_ollama", return_value=reply):
            return extract_receipt_items(ocr_lines)

    def test_repeated_lines_raise_quantity_and_different_foods_stay_separate(self):
        reply = model_reply({
            "1": ("whole milk", True), "2": ("skim milk", True), "3": ("baguette", True), "4": ("water", True),
        })
        result = self.extract(["WHL MLK 4L 6.29", "SKM MLK 2L 3.99", "ARTISAN BGT 5.99", "ARTISAN BGT 5.99", "ARTISAN BGT 5.99"], reply)
        self.assertEqual(rows(result), {"whole milk": "4 l", "skim milk": "2 l", "baguette": "3 pieces"})
        baguette = next(row for row in result["detections"] if row["ingredient"] == "baguette")
        self.assertEqual(baguette["visible_text"], "ARTISAN BGT ×3")

    def test_model_cannot_add_food_that_is_not_on_the_receipt(self):
        reply = model_reply({"1": ("shrimp", True), "9": ("water", True)})
        self.assertEqual(rows(self.extract(["16/20 SHRIMP 30.57", "16/20 SHRIMP 28.24"], reply)), {"shrimp": "2 pieces"})

    def test_non_food_is_removed_even_when_the_model_calls_it_food(self):
        reply = model_reply({"1": ("avocado", True), "2": ("dish soap", True), "3": ("paper towel", False)})
        result = self.extract(["AVOCADO 3 @ 1.29 3.87", "DAWN DISH SOAP 3.99", "PAPER TWL 6PK 8.99"], reply)
        self.assertEqual(rows(result), {"avocado": "3 pieces"})

    def test_missing_items_and_unavailable_model_are_reported(self):
        result = self.extract(WHOLESALE_OCR, "Ollama is not running.")
        self.assertIn("chicken thigh", rows(result))
        self.assertTrue(any("did not answer" in warning for warning in result["warnings"]))
        short = self.extract(WHOLESALE_OCR[:6] + ["SUBTOTAL 1.00", "TOTAL NUMBER OF ITEMS SOLD = 7"], "{}")
        self.assertTrue(any("7 items were sold but 3 were read" in warning for warning in short["warnings"]))


if __name__ == "__main__":
    unittest.main()
