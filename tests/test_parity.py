"""Keep the Action and skill snapshot parsers in agreement.

The privacy-filtering logic exists twice: src/readme_auto_update/snapshot.py
(the Action) and skills/readme-auto-update/scripts/github_snapshot.py (the
skill). These tests feed identical GraphQL data through both and fail if the
filtered output — especially private-name redaction — diverges.
"""

import copy
import json
import unittest
from unittest.mock import patch

from readme_auto_update.snapshot import _paged_account, parse_account as action_parse
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

    def test_paginated_fixtures_have_action_skill_parity(self):
        initial = response_data()
        initial["viewer"]["organizations"]["pageInfo"] = {"hasNextPage": True, "endCursor": "org-2"}
        initial["viewer"]["repositories"]["pageInfo"] = {"hasNextPage": True, "endCursor": "repo-2"}
        initial["viewer"]["contributionsCollection"]["issueContributions"]["pageInfo"] = {
            "hasNextPage": True, "endCursor": "issue-2"
        }
        pages = []
        for cursor, field in (("org-2", "organizations"), ("repo-2", "repositories"), ("issue-2", "issueContributions")):
            page = copy.deepcopy(initial)
            viewer = page["viewer"]
            viewer["organizations"]["nodes"] = []
            viewer["repositories"]["nodes"] = []
            viewer["contributionsCollection"]["issueContributions"]["nodes"] = []
            viewer["organizations"]["pageInfo"] = {"hasNextPage": False, "endCursor": None}
            viewer["repositories"]["pageInfo"] = {"hasNextPage": False, "endCursor": None}
            viewer["contributionsCollection"]["issueContributions"]["pageInfo"] = {
                "hasNextPage": False, "endCursor": None
            }
            pages.append(page)

        action_fixture = copy.deepcopy(initial)
        skill_fixture = copy.deepcopy(initial)
        action_pages = copy.deepcopy(pages)
        skill_pages = copy.deepcopy(pages)
        cfg = config(github_token="token")
        with patch("readme_auto_update.snapshot.GitHubClient.graphql", side_effect=[action_fixture] + action_pages):
            action_data = _paged_account(cfg, {})
        with patch.object(github_snapshot, "graphql", side_effect=[skill_fixture] + skill_pages):
            skill_data = github_snapshot.paginated_account("token", {})
        self.assertEqual(json.loads(action_parse(action_data, cfg).as_prompt_text()),
                         github_snapshot.parse_account(skill_data, cfg))


if __name__ == "__main__":
    unittest.main()
