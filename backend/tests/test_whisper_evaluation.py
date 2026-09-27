import tempfile
import unittest
import wave
from pathlib import Path

from backend.audio_evaluation.evaluate_whisper import (
    add_white_noise,
    normalize_text,
    route_cooking_intent,
    select_model,
    word_error_counts,
)


class WhisperEvaluationTests(unittest.TestCase):
    def test_normalization_and_word_errors(self):
        self.assertEqual(normalize_text("  Next, STEP! "), "next step")
        self.assertEqual(word_error_counts("next step", "next steps"), (1, 2))

    def test_command_router_matches_cooking_intents(self):
        cases = {
            "Turn off hands-free": "stop_listening",
            "I changed my mind": "cancel_cooking",
            "the meal is ready": "finish_cooking",
            "what should I do next": "peek_next",
            "done with this step": "next_step",
            "go back": "previous_step",
            "repeat that": "repeat_step",
            "how much time is left": "time_remaining",
            "which step am I on": "current_step",
            "what can I say": "help",
            "confirm finish": "confirm",
            "never mind": "decline",
            "is the chicken cooked through": "question",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(route_cooking_intent(phrase), expected)

    def test_noise_generation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clean = root / "clean.wav"
            first = root / "first.wav"
            second = root / "second.wav"
            with wave.open(str(clean), "wb") as target:
                target.setparams((1, 2, 16000, 1600, "NONE", "not compressed"))
                frames = b"".join(int(1000).to_bytes(2, "little", signed=True) for _ in range(1600))
                target.writeframes(frames)
            add_white_noise(clean, first, 10, 42)
            add_white_noise(clean, second, 10, 42)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertNotEqual(clean.read_bytes(), first.read_bytes())

    def test_predeclared_selection_prefers_noisy_accuracy_then_wer(self):
        def summary(noisy_accuracy, noisy_wer, latency):
            return {
                "failure_rate": 0,
                "median_latency_ms": latency,
                "by_condition": {
                    "clean": {"intent_accuracy": 1, "wer": 0},
                    "noise_10db": {"intent_accuracy": noisy_accuracy, "wer": noisy_wer},
                },
            }

        selected, evidence = select_model(
            {
                "tiny.en": summary(0.90, 0.1, 100),
                "base.en": summary(0.95, 0.05, 200),
                "small.en": summary(0.95, 0.02, 400),
            }
        )
        self.assertEqual(selected, "small.en")
        self.assertEqual(evidence["eligible"], ["small.en", "base.en", "tiny.en"])


if __name__ == "__main__":
    unittest.main()
