import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from impact import RESCUE_WINDOW_DAYS, cooking_impact, estimate_grams
from recipe_relevance import choose_pantry_for_request, unrelated_pantry_ingredients


def session(session_id, started, items):
    return SimpleNamespace(id=session_id, recipe_id=1, status="completed", started_at=started.isoformat(), pantry_snapshot=json.dumps(items))


class ImpactTests(unittest.TestCase):
    def test_counts_foods_used_in_the_use_soon_window_even_when_units_differ(self):
        now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
        started = now - timedelta(days=1)
        expiring = (started + timedelta(days=2)).date().isoformat()
        later = (started + timedelta(days=RESCUE_WINDOW_DAYS + 3)).date().isoformat()
        items = [
            {"ingredient": "spinach", "expiry_date": expiring, "deducted": False, "amount_used": None, "quantity_used": "120 g"},
            {"ingredient": "rice", "expiry_date": later, "deducted": True, "amount_used": 1, "quantity_used": "1 cup"},
        ]
        result = cooking_impact([session(1, started, items)], {1: "Test meal"}, now=now)
        self.assertEqual(result["ingredients_used"], 2)
        self.assertEqual(result["rescued_items"], 1)
        self.assertEqual(result["estimated_grams_saved"], 120)
        self.assertEqual(result["weekly_rescues"][-1]["count"], 1)

    def test_weight_estimates_use_units_then_typical_portions(self):
        self.assertEqual(estimate_grams({"ingredient": "milk", "quantity_used": "0.5 l"}), 500)
        self.assertEqual(estimate_grams({"ingredient": "eggs", "quantity_used": "2 pieces", "recipe_amount": 2, "recipe_unit": "pieces"}), 110)

    def test_at_risk_items_come_from_the_pantry(self):
        now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
        pantry = [SimpleNamespace(ingredient="basil", expiry_date="2026-09-28"), SimpleNamespace(ingredient="rice", expiry_date="2027-01-01")]
        result = cooking_impact([], {}, now=now, pantry_items=pantry)
        self.assertEqual(result["at_risk_items"], [{"ingredient": "basil", "days_left": 1}])


class RelevanceTests(unittest.TestCase):
    pantry = [SimpleNamespace(ingredient=name, category=category, expiry_date="") for name, category in [
        ("chicken breast", "meat"), ("strawberry", "fruit"), ("blueberries", "fruit"), ("kalamata olives", "vegetables"),
        ("onion", "vegetables"), ("mini fruit bars", "snacks"), ("grape tomato", "fruit"),
    ]]

    def test_named_foods_and_categories_are_offered(self):
        chosen, _ = choose_pantry_for_request("a quick chicken dinner", self.pantry, [])
        self.assertIn("chicken breast", chosen)
        self.assertNotIn("strawberry", chosen)
        chosen, _ = choose_pantry_for_request("a fruit smoothie", self.pantry, [])
        self.assertIn("strawberry", chosen)
        self.assertNotIn("grape tomato", chosen)   # botanically fruit, cooked as a vegetable

    def test_unrelated_pantry_foods_are_flagged_but_staples_are_not(self):
        offered = ["chicken breast"]
        scores = {"chicken breast": 1.0}
        names = [item.ingredient for item in self.pantry]
        unrelated = unrelated_pantry_ingredients(["chicken", "strawberries", "onion"], offered, scores, names)
        self.assertEqual(unrelated, ["strawberry"])


if __name__ == "__main__":
    unittest.main()
