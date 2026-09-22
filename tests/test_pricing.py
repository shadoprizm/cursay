from __future__ import annotations

import unittest

from cursay.pricing import estimate_transcription_cost, format_usd, reported_cost_usd


class PricingTests(unittest.TestCase):
    def test_xai_rest_transcription_rate(self) -> None:
        self.assertAlmostEqual(
            estimate_transcription_cost("xai", "grok-voice-transcribe-2.0", 600) or 0,
            1 / 60,
        )

    def test_local_whisper_has_no_provider_cost(self) -> None:
        self.assertEqual(estimate_transcription_cost("cursay-local", "whisper-base.en", 3600), 0.0)

    def test_remote_whisper_model_is_not_assumed_to_be_free(self) -> None:
        self.assertIsNone(estimate_transcription_cost("openai", "whisper-1", 3600))

    def test_unknown_provider_is_not_guessed(self) -> None:
        self.assertIsNone(estimate_transcription_cost("custom", "private-model", 3600))

    def test_reported_cost_supports_usd_and_xai_ticks(self) -> None:
        self.assertEqual(reported_cost_usd({"cost_usd": 0.25}), 0.25)
        self.assertEqual(reported_cost_usd({"usage": {"cost_usd": 0.5}}), 0.5)
        self.assertEqual(reported_cost_usd({"usage": {"cost_in_usd_ticks": 250_000_000}}), 0.025)

    def test_cost_format_preserves_small_amounts(self) -> None:
        self.assertEqual(format_usd(0), "$0.00")
        self.assertEqual(format_usd(0.001666), "$0.0017")
        self.assertEqual(format_usd(0.0179), "$0.018")


if __name__ == "__main__":
    unittest.main()
