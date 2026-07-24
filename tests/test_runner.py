import unittest
from unittest.mock import patch

from readme_auto_update.runner import _generate
from test_generators import sample_snapshot
from test_snapshot import config


class GenerateTests(unittest.TestCase):
    def test_ai_success_returns_ai_mode(self):
        cfg = config(mode="ai", openai_api_key="k")
        with patch("readme_auto_update.runner.ai_summary", return_value="## Story"):
            text, mode = _generate(cfg, sample_snapshot(), "")
        self.assertEqual((text, mode), ("## Story", "ai"))

    def test_ai_failure_falls_back_to_the_chosen_template(self):
        cfg = config(mode="ai", openai_api_key="k", template="badges")
        with patch("readme_auto_update.runner.ai_summary", side_effect=RuntimeError("boom")):
            text, mode = _generate(cfg, sample_snapshot(), "")
        self.assertEqual(mode, "rules")
        self.assertIn("img.shields.io", text)  # the badges template rendered

    def test_strict_reraises_ai_failure(self):
        cfg = config(mode="ai", openai_api_key="k", strict=True)
        with patch("readme_auto_update.runner.ai_summary", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                _generate(cfg, sample_snapshot(), "")

    def test_auto_without_a_key_uses_rules(self):
        cfg = config(mode="auto", openai_api_key="", anthropic_api_key="")
        text, mode = _generate(cfg, sample_snapshot(), "")
        self.assertEqual(mode, "rules")
        self.assertIn("skillicons", text)  # default icons template


if __name__ == "__main__":
    unittest.main()
