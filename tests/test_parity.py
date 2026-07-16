"""Keep the Action and skill snapshot parsers in agreement.

The privacy-filtering logic exists twice: src/readme_auto_update/snapshot.py
(the Action) and skills/readme-auto-update/scripts/github_snapshot.py (the
skill). These tests feed identical GraphQL data through both and fail if the
filtered output — especially private-name redaction — diverges.
"""

import json
import unittest

from readme_auto_update.snapshot import parse_account as action_parse
from test_skill_scripts import github_snapshot
from test_snapshot import config, response_data


class ParityTests(unittest.TestCase):
    def assert_parity(self, **overrides):
        cfg = config(**overrides)
        expected = json.loads(action_parse(response_data(), cfg).as_prompt_text())
        actual = github_snapshot.parse_account(response_data(), cfg)
        self.assertEqual(actual, expected)

    def test_default_privacy_filtering_matches(self):
        self.assert_parity()

    def test_show_private_names_matches(self):
        self.assert_parity(show_private_names=True)

    def test_exclude_private_matches(self):
        self.assert_parity(include_private=False)

    def test_exclude_organizations_matches(self):
        self.assert_parity(include_organizations=False)

    def test_exclude_open_source_matches(self):
        self.assert_parity(include_open_source=False)

    def test_exclude_owned_matches(self):
        self.assert_parity(include_owned=False)

    def test_repository_cap_matches(self):
        self.assert_parity(max_repositories=1)


if __name__ == "__main__":
    unittest.main()
