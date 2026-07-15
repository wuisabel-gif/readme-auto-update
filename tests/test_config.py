import os
import unittest
from unittest.mock import patch

from readme_auto_update.config import Config


class ConfigTests(unittest.TestCase):
    def test_requires_user_authorized_github_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "github_token is required"):
                Config.from_env()

    def test_auto_uses_rules_without_openai_key(self):
        with patch.dict(os.environ, {"INPUT_GITHUB_TOKEN": "gh-test"}, clear=True):
            config = Config.from_env()
        self.assertEqual(config.effective_mode, "rules")

    def test_auto_uses_ai_with_openai_key(self):
        environment = {"INPUT_GITHUB_TOKEN": "gh-test", "OPENAI_API_KEY": "openai-test"}
        with patch.dict(os.environ, environment, clear=True):
            config = Config.from_env()
        self.assertEqual(config.effective_mode, "ai")

    def test_rejects_path_escape(self):
        environment = {
            "INPUT_GITHUB_TOKEN": "gh-test",
            "INPUT_OUTPUT_FILE": "../README.md",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "relative path"):
                Config.from_env()

    def test_rejects_more_than_one_year(self):
        environment = {"INPUT_GITHUB_TOKEN": "gh-test", "INPUT_DAYS": "366"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "between 1 and 365"):
                Config.from_env()

    def test_private_names_are_hidden_by_default(self):
        with patch.dict(os.environ, {"INPUT_GITHUB_TOKEN": "gh-test"}, clear=True):
            config = Config.from_env()
        self.assertTrue(config.include_private)
        self.assertFalse(config.show_private_names)


if __name__ == "__main__":
    unittest.main()

