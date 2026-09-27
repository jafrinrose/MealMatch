import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_services import photo_close_ups, scan_pantry_photo  # noqa: E402
from vision_suggestions import (  # noqa: E402
    SuggestionMerger,
    clean_food_name,
    clean_qwen_items,
    is_repeating,
    salvage_items,
)


def item(name: str, **fields) -> dict:
    return {"ingredient": name, "quantity": 1, "unit": "piece", "confidence": 0.9, **fields}


def names(items: list[dict]) -> list[str]:
    return [entry["ingredient"] for entry in items]


class ModelAnswerTests(unittest.TestCase):
    def test_complete_items_survive_an_answer_cut_off_mid_item(self):
        answer = json.dumps({"items": [item("lemon"), item("carrot")]})[:-2] + ', {"ingredient": "cauli'
        self.assertEqual(names(salvage_items(answer)), ["lemon", "carrot"])

    def test_a_complete_answer_is_read_in_full(self):
        self.assertEqual(names(salvage_items(json.dumps({"items": [item("milk")]}))), ["milk"])
        self.assertEqual(salvage_items("no json here"), [])

    def test_three_repeats_in_a_row_mean_the_model_is_looping(self):
        looping = [item("bread"), item("onion"), item("pizza"), item("bread"), item("onion"), item("pizza")]
        self.assertTrue(is_repeating(looping))
        self.assertFalse(is_repeating(looping[:5]))
        # One accidental repeat followed by new foods is not a loop.
        self.assertFalse(is_repeating([item("milk"), item("milk"), item("egg"), item("pepper")]))


class SuggestionCleaningTests(unittest.TestCase):
    def test_units_are_ones_the_confirmation_form_can_show(self):
        cleaned = clean_qwen_items(
            [
                item("grapes", unit="package"),
                item("bread", unit="loaf"),
                item("yogurt", unit="tub"),
                item("salmon", unit="tray"),
                item("orange", quantity=2, unit="pieces"),
                item("milk", quantity=2, unit="carton"),
                item("jam", unit="piece, box, loaf"),
            ],
            "qwen2.5vl:3b",
        )
        self.assertEqual(
            {entry["ingredient"]: entry["quantity"] for entry in cleaned},
            {"grapes": "1 pack", "bread": "1 pack", "yogurt": "1 box", "salmon": "1 pack",
             "orange": "2 pieces", "milk": "2 cartons", "jam": "1 piece"},
        )

    def test_brand_and_store_names_are_removed(self):
        self.assertEqual(clean_food_name("meiji milk"), "milk")
        self.assertEqual(clean_food_name("fairprice wholemeal wraps"), "wholemeal wraps")
        self.assertEqual(clean_food_name("Farmers Union Greek yogurt"), "greek yogurt")
        self.assertEqual(clean_food_name("organic rolled oats"), "rolled oats")
        self.assertEqual(clean_food_name("godiva"), "godiva")

    def test_copied_template_words_and_vague_names_are_removed(self):
        cleaned = clean_qwen_items([item("plain food name"), item("plain bread"), item("unspecified"), item("vegetables")], "qwen2.5vl:3b")
        self.assertEqual(names(cleaned), ["bread"])

    def test_product_lines_become_their_food(self):
        self.assertEqual(clean_food_name("cadbury dairy milk chocolate"), "chocolate")
        self.assertEqual(clean_food_name("nescafe"), "coffee")

    def test_a_label_renames_only_when_it_agrees_with_the_name(self):
        self.assertEqual(clean_food_name("chocolate milk", visible_text="Cadbury Dairy Milk"), "chocolate")
        # A label attached to the wrong item changes nothing.
        self.assertEqual(clean_food_name("pepper", visible_text="Nescafe"), "pepper")

    def test_singular_and_plural_names_are_one_suggestion(self):
        cleaned = clean_qwen_items([item("grapes", confidence=0.7), item("grape", confidence=0.9)], "qwen2.5vl:3b")
        self.assertEqual([(entry["ingredient"], entry["confidence"]) for entry in cleaned], [("grape", 0.9)])


class PassMergingTests(unittest.TestCase):
    def merge(self, *passes: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
        merger, shown, alternatives = SuggestionMerger(), [], []
        for pass_names in passes:
            new, offered = merger.add(clean_qwen_items([item(name) for name in pass_names], "qwen2.5vl:3b"))
            shown += new
            alternatives += [(entry["detection_id"], entry["ingredient"]) for entry in offered]
        return names(shown), alternatives

    def test_later_passes_only_add_new_foods(self):
        shown, _ = self.merge(["orange", "milk"], ["oranges", "couscous"], ["couscous", "honey"])
        self.assertEqual(shown, ["orange", "milk", "couscous", "honey"])

    def test_a_less_specific_name_is_dropped_and_a_more_specific_one_offered(self):
        shown, alternatives = self.merge(["bell pepper", "chili"], ["pepper", "red chili"])
        self.assertEqual(shown, ["bell pepper", "chili"])
        self.assertEqual(alternatives, [("suggestion-2", "red chili")])

    def test_different_foods_that_share_a_word_stay_apart(self):
        shown, alternatives = self.merge(["chocolate syrup", "milk", "butter"], ["chocolate", "chocolate milk", "peanut butter", "walnut"])
        self.assertEqual(shown, ["chocolate syrup", "milk", "butter", "chocolate", "chocolate milk", "peanut butter", "walnut"])
        self.assertEqual(alternatives, [])

    def test_merged_suggestions_keep_unique_ids(self):
        merger = SuggestionMerger()
        first, _ = merger.add(clean_qwen_items([item("egg")], "qwen2.5vl:3b"))
        second, _ = merger.add(clean_qwen_items([item("salmon")], "qwen2.5vl:3b"))
        self.assertEqual([entry["detection_id"] for entry in first + second], ["suggestion-1", "suggestion-2"])

    def test_look_closer_starts_from_the_suggestions_already_shown(self):
        shown = [{"detection_id": "suggestion-1", "ingredient": "bell pepper"}, {"detection_id": "suggestion-2", "ingredient": "chili"}]
        new, offered = SuggestionMerger(shown).add(clean_qwen_items([item("pepper"), item("red chili"), item("honey")], "qwen2.5vl:3b"))
        self.assertEqual([(entry["detection_id"], entry["ingredient"]) for entry in new], [("suggestion-3", "honey")])
        self.assertEqual([(entry["detection_id"], entry["ingredient"]) for entry in offered], [("suggestion-2", "red chili")])


class CloseUpTests(unittest.TestCase):
    def test_four_overlapping_quarters_cover_the_photo(self):
        photo = Image.new("RGB", (3000, 4000))
        for index in range(4):
            photo.putpixel((0 if index % 2 == 0 else 2999, 0 if index < 2 else 3999), (255, 255, 255))
        tiles = photo_close_ups(photo)
        self.assertEqual(len(tiles), 4)
        # Each quarter is 15% wider and taller than half, and each keeps its own corner.
        self.assertTrue(all(1700 < tile.width < 1750 and 2280 < tile.height < 2320 for tile in tiles))
        corners = [(0, 0), (tiles[1].width - 1, 0), (0, tiles[2].height - 1), (tiles[3].width - 1, tiles[3].height - 1)]
        self.assertTrue(all(tile.getpixel(corner) == (255, 255, 255) for tile, corner in zip(tiles, corners)))

    def scan(self, **options) -> tuple[list[dict], int]:
        answer = {"items": [item("honey")], "done_reason": "stop", "output_tokens": 50, "seconds": 0.1}
        with patch("model_services.ask_vision_model", return_value=answer) as ask:
            results = list(scan_pantry_photo(Image.new("RGB", (64, 48)), **options))
        return results, ask.call_count

    def test_close_ups_run_only_when_asked(self):
        results, calls = self.scan(close_ups=False)
        self.assertEqual((calls, [result["pass"] for result in results]), (1, ["whole photo"]))
        self.assertEqual(results[0]["passes"], 1)
        results, calls = self.scan(close_ups=True)
        self.assertEqual((calls, results[-1]["pass_number"], results[-1]["passes"]), (5, 5, 5))

    def test_look_closer_skips_the_whole_photo(self):
        results, calls = self.scan(earlier=[{"detection_id": "suggestion-1", "ingredient": "honey"}])
        self.assertEqual(calls, 4)
        self.assertEqual([(result["pass_number"], result["passes"]) for result in results], [(2, 5), (3, 5), (4, 5), (5, 5)])
        self.assertEqual([result["detections"] for result in results], [[]] * 4)


if __name__ == "__main__":
    unittest.main()
