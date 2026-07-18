import argparse
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "skills" / "readme-auto-update" / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


github_snapshot = load_script("github_snapshot.py")
update_readme = load_script("update_readme.py")


def repository(name, owner, *, private=False):
    return {
        "nameWithOwner": name,
        "description": f"Description for {name}",
        "url": f"https://github.com/{name}",
        "isPrivate": private,
        "isArchived": False,
        "isFork": False,
        "stargazerCount": 3,
        "forkCount": 1,
        "updatedAt": "2026-07-10T00:00:00Z",
        "owner": {"login": owner},
        "primaryLanguage": {"name": "Python"},
        "repositoryTopics": {"nodes": [{"topic": {"name": "tools"}}]},
    }


def account_data():
    owned = repository("example-user/owned-project", "example-user")
    private_org = repository("example-org/private-project", "example-org", private=True)
    external = repository("community/library", "community")
    return {
        "viewer": {
            "login": "example-user",
            "name": "Example User",
            "bio": "Builder",
            "company": "",
            "location": "Example City",
            "websiteUrl": "https://example.invalid",
            "avatarUrl": "https://example.invalid/avatar.png",
            "organizations": {"nodes": [{"login": "example-org"}]},
            "repositories": {"nodes": [owned]},
            "contributionsCollection": {
                "startedAt": "2025-07-15T00:00:00Z",
                "endedAt": "2026-07-15T00:00:00Z",
                "totalCommitContributions": 9,
                "totalIssueContributions": 1,
                "totalPullRequestContributions": 1,
                "totalPullRequestReviewContributions": 1,
                "totalRepositoryContributions": 2,
                "restrictedContributionsCount": 5,
                "commitContributionsByRepository": [
                    {"repository": owned, "contributions": {"totalCount": 4}},
                    {"repository": private_org, "contributions": {"totalCount": 3}},
                    {"repository": external, "contributions": {"totalCount": 2}},
                ],
                "issueContributions": {
                    "nodes": [{"issue": {"repository": private_org}}]
                },
                "pullRequestContributionsByRepository": [
                    {"repository": external, "contributions": {"totalCount": 1}}
                ],
                "pullRequestReviewContributionsByRepository": [
                    {"repository": external, "contributions": {"totalCount": 1}}
                ],
            },
        }
    }


def options(**overrides):
    values = {
        "include_owned": True,
        "include_organizations": True,
        "include_open_source": True,
        "include_private": True,
        "show_private_names": False,
        "include_archived": False,
        "max_repositories": 30,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class SkillSnapshotTests(unittest.TestCase):
    def test_graphql_errors_redact_upstream_content(self):
        http_error = urllib.error.HTTPError(
            "https://api.github.com/graphql", 500, "error", {},
            io.BytesIO(b"private-repository-sentinel"),
        )
        with patch.object(github_snapshot.urllib.request, "urlopen", side_effect=http_error):
            with self.assertRaisesRegex(Exception, "HTTP 500") as raised:
                github_snapshot.graphql("token", {})
        self.assertNotIn("private-repository-sentinel", str(raised.exception))
        response = type("Response", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: False,
            "read": lambda self: b'{"errors":[{"message":"private-repository-sentinel"}]}',
        })()
        with patch.object(github_snapshot.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(Exception) as raised:
                github_snapshot.graphql("token", {})
        self.assertNotIn("private-repository-sentinel", str(raised.exception))

    def test_private_repository_identity_is_redacted_by_default(self):
        snapshot = github_snapshot.parse_account(account_data(), options())
        rendered = github_snapshot.json.dumps(snapshot)
        names = {item["name_with_owner"] for item in snapshot["repository_evidence"]}
        self.assertIn("Private work", names)
        self.assertNotIn("example-org/private-project", rendered)
        self.assertNotIn("example-org", snapshot["organizations"])
        self.assertEqual(snapshot["totals"]["private_or_restricted_contributions"], 9)

    def test_private_names_require_explicit_option(self):
        snapshot = github_snapshot.parse_account(
            account_data(), options(show_private_names=True)
        )
        names = {item["name_with_owner"] for item in snapshot["repository_evidence"]}
        self.assertIn("example-org/private-project", names)
        self.assertIn("example-org", snapshot["organizations"])

    def test_organization_filter_applies_before_private_aggregation(self):
        snapshot = github_snapshot.parse_account(
            account_data(), options(include_organizations=False)
        )
        private = next(
            item
            for item in snapshot["repository_evidence"]
            if item["relationship"] == "private"
        )
        self.assertEqual(private["restricted"], 5)
        self.assertEqual(private["commits"], 0)


class SkillReadmeUpdaterTests(unittest.TestCase):
    def test_preserves_manual_content_while_replacing_managed_section(self):
        source = """# Example User

Manual introduction.

<!-- README-AUTO-UPDATE:START:readme-auto-update -->
Old generated content.
<!-- README-AUTO-UPDATE:END:readme-auto-update -->

Manual footer.
"""
        result = update_readme.update(source, "## Current work\n\nNew content.", "readme-auto-update")
        self.assertIn("Manual introduction.", result)
        self.assertIn("Manual footer.", result)
        self.assertIn("New content.", result)
        self.assertNotIn("Old generated content.", result)

    def test_appends_managed_section_when_markers_are_absent(self):
        result = update_readme.update("# Project\n", "Useful summary.", "summary")
        self.assertTrue(result.startswith("# Project\n"))
        self.assertIn("README-AUTO-UPDATE:START:summary", result)

    def test_rejects_marker_injection(self):
        with self.assertRaisesRegex(ValueError, "must not contain managed markers"):
            update_readme.update(
                "# Project\n",
                "<!-- README-AUTO-UPDATE:END:summary -->",
                "summary",
            )


if __name__ == "__main__":
    unittest.main()
