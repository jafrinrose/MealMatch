import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ai_services import deterministic_poultry_safety_answer, extract_receipt_items  # noqa: E402
from backend.text_evaluation.evaluate_text_models import (
    DEFAULT_MODELS,
    parse_json,
    score_cooking,
    score_receipt,
    score_recipe,
    score_substitution,
    select_model,
)


class TextModelEvaluationTests(unittest.TestCase):
    def test_final_shortlist_spans_three_local_model_families(self):
        self.assertEqual(
            DEFAULT_MODELS,
            ["llama3.2:3b", "qwen2.5:3b", "phi3.5:3.8b"],
        )

    def test_json_extraction_handles_wrapped_object(self):
        self.assertEqual(parse_json('Here is JSON: {"items": ["milk"]}'), {"items": ["milk"]})

    def test_receipt_score_penalises_non_food_and_misses(self):
        score = score_receipt('["milk", "soap"]', ["milk", "bread"])
        self.assertAlmostEqual(score["precision"], 0.5)
        self.assertAlmostEqual(score["recall"], 0.5)
        self.assertAlmostEqual(score["score"], 0.5)

    def test_receipt_cleanup_preserves_repeated_food_for_quantity(self):
        reply = json.dumps({
            "1": {"receipt": "SHRIMP", "ingredient": "shrimp", "food": True},
            "2": {"receipt": "DISH SOAP", "ingredient": "dish soap", "food": False},
        })
        with patch("backend.ai_services.ask_ollama", return_value=reply):
            result = extract_receipt_items(["SHRIMP 9.99", "SHRIMP 9.99", "DISH SOAP 3.49"])
        self.assertEqual([(row["ingredient"], row["quantity"]) for row in result["detections"]], [("shrimp", "2 pieces")])

    def test_recipe_score_enforces_safety_and_varied_steps(self):
        case = {"expected": ["rice", "spinach"], "forbidden": ["milk"]}
        response = '{"title":"Rice","cuisine":"Asian","ingredients":[{"name":"rice","amount":1,"unit":"cup"},{"name":"spinach","amount":1,"unit":"cup"}],"steps":[{"instruction":"Rinse rice","minutes":2},{"instruction":"Boil rice","minutes":15},{"instruction":"Add spinach","minutes":3},{"instruction":"Serve","minutes":1}]}'
        score = score_recipe(response, case)
        self.assertTrue(score["structured_valid"])
        self.assertTrue(score["safety_pass"])
        self.assertEqual(score["score"], 1.0)

    def test_substitution_flags_forbidden_suggestion(self):
        case = {"pantry": ["oat milk"], "expected": ["oat milk"], "forbidden": ["cow milk"]}
        response = '{"substitutions":[{"ingredient":"milk","suggestions":[{"name":"cow milk","reason":"same","in_pantry":false}]}]}'
        score = score_substitution(response, case)
        self.assertFalse(score["safety_pass"])
        self.assertEqual(score["violations"], ["cow milk"])

    def test_selection_applies_gates_and_close_score_latency_tie_break(self):
        def summary(score, latency, validity=1.0):
            return {"macro_task_score": score, "median_latency_ms": latency, "structured_validity": validity, "safety_pass_rate": 1.0, "critical_safety_pass_rate": 1.0, "failure_rate": 0.0}
        selected, evidence = select_model({"slow": summary(0.90, 5000), "fast": summary(0.88, 1000), "invalid": summary(0.99, 500, 0.5)})
        self.assertEqual(selected, "fast")
        self.assertNotIn("invalid", evidence["eligible"])

    def test_deterministic_poultry_safety_guard(self):
        self.assertIn("Not yet", deterministic_poultry_safety_answer("Is chicken safe at 60°C?"))
        self.assertIn("minimum", deterministic_poultry_safety_answer("My turkey is 170 F"))
        self.assertIn("Don't wash", deterministic_poultry_safety_answer("Should I wash raw chicken?"))
        self.assertIsNone(deterministic_poultry_safety_answer("How long should I simmer carrots?"))

    def test_critical_food_safety_scoring_rejects_contradictions(self):
        temperature_case = {"required_any": ["74"], "forbidden": [], "critical_safety": "poultry_temperature"}
        unsafe = score_cooking("At 60 Celsius the chicken is safely cooked, although 74 is recommended.", temperature_case)
        safe = score_cooking("No. 60 Celsius is not safe; cook it to 74 Celsius.", temperature_case)
        self.assertFalse(unsafe["critical_safety_pass"])
        self.assertTrue(safe["critical_safety_pass"])
        washing_case = {"required_any": ["do not wash"], "forbidden": [], "critical_safety": "raw_poultry_washing"}
        self.assertFalse(score_cooking("Yes, rinse the raw chicken.", washing_case)["critical_safety_pass"])
        self.assertTrue(score_cooking("Do not wash raw chicken.", washing_case)["critical_safety_pass"])


if __name__ == "__main__":
    unittest.main()
