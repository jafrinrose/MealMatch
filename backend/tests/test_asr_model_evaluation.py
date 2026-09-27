import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from backend.audio_evaluation.evaluate_asr_models import CANDIDATES, read_pcm16


class AsrModelEvaluationTests(unittest.TestCase):
    def test_final_shortlist_spans_three_families(self):
        self.assertEqual(len(CANDIDATES), 3)
        self.assertEqual(
            {candidate["family"] for candidate in CANDIDATES.values()},
            {"Whisper", "Distil-Whisper", "wav2vec 2.0"},
        )

    def test_pcm_reader_normalizes_16_bit_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.wav"
            with wave.open(str(path), "wb") as target:
                target.setparams((1, 2, 16000, 2, "NONE", "not compressed"))
                target.writeframes(
                    int(-32768).to_bytes(2, "little", signed=True)
                    + int(16384).to_bytes(2, "little", signed=True)
                )
            audio, rate = read_pcm16(path)
            self.assertEqual(rate, 16000)
            np.testing.assert_allclose(audio, [-1.0, 0.5])


if __name__ == "__main__":
    unittest.main()
