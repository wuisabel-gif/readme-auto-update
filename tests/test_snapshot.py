from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from readme_auto_update.config import Config
from readme_auto_update.github import GitHubClient
from readme_auto_update.snapshot import parse_account


def config(**overrides) -> Config:
    base = Config(
        github_token="gh-test",
        openai_api_key="",
        mode="rules",
        output_file="README.md",
        section_name="readme-auto-update",
        model="unused",
        days=365,
        max_repositories=30,
        include_owned=True,
        include_organizations=True,
        include_open_source=True,
        include_private=True,
        show_private_names=False,
        include_archived=False,
        prompt="",
        commit=False,
        commit_message="docs: update README with README Auto Update",
        commit_username="readme-auto-update[bot]",
        commit_email="bot@example.invalid",
        dry_run=False,
    )
    return replace(base, **overrides)


def repo(name, owner, *, private=False, archived=False):
    return {
        "nameWithOwner": name,
        "description": f"Description for {name}",
        "url": f"https://github.com/{name}",
        "isPrivate": private,
        "isArchived": archived,
        "isFork": False,
        "stargazerCount": 3,
        "forkCount": 1,
        "updatedAt": "2026-07-10T00:00:00Z",
        "owner": {"login": owner},
        "primaryLanguage": {"name": "Python"},
        "repositoryTopics": {"nodes": [{"topic": {"name": "tools"}}]},
    }


def response_data():
    owned = repo("example-user/owned-project", "example-user")
    organization = repo("example-org/private-project", "example-org", private=True)
    external = repo("community/library", "community")
    return {
        "viewer": {
            "login": "example-user",
            "name": "Example User",
            "bio": "Builder",
            "company": "",
            "location": "Example City",
            "websiteUrl": "https://example.invalid",
            "avatarUrl": "https://example.invalid/avatar.png",
            "organizations": {"nodes": [{"login": "example-org", "name": "Example Organization"}]},
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
                "hasAnyRestrictedContributions": True,
                "commitContributionsByRepository": [
                    {"repository": owned, "contributions": {"totalCount": 4}},
                    {"repository": organization, "contributions": {"totalCount": 3}},
                    {"repository": external, "contributions": {"totalCount": 2}},
                ],
                "issueContributions": {"nodes": [{"issue": {"repository": organization}}]},
                "pullRequestContributionsByRepository": [
                    {"repository": external, "contributions": {"totalCount": 1}}
                ],
                "pullRequestReviewContributionsByRepository": [
                    {"repository": external, "contributions": {"totalCount": 1}}
                ],
            },
        }
    }


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.body).encode()


class SnapshotTests(unittest.TestCase):
    def test_classifies_owned_open_source_and_anonymous_private_work(self):
        snapshot = parse_account(response_data(), config())
        relationships = {repository.relationship for repository in snapshot.repositories}
        names = {repository.name_with_owner for repository in snapshot.repositories}
        self.assertEqual(relationships, {"owned", "open_source", "private"})
        self.assertNotIn("example-org/private-project", names)
        self.assertIn("Private work", names)
        self.assertNotIn("example-org", snapshot.organizations)
        self.assertNotIn("example-org", snapshot.as_prompt_text())
        self.assertEqual(snapshot.private_contributions, 9)
        private = next(repository for repository in snapshot.repositories if repository.relationship == "private")
        self.assertEqual(private.contributions, 9)

    def test_can_explicitly_include_private_names(self):
        snapshot = parse_account(response_data(), config(show_private_names=True))
        private = next(
            repository
            for repository in snapshot.repositories
            if repository.name_with_owner == "example-org/private-project"
        )
        self.assertEqual(private.relationship, "organization")
        self.assertEqual(private.commits, 3)
        anonymous = next(
            repository
            for repository in snapshot.repositories
            if repository.name_with_owner == "Private work"
        )
        self.assertEqual(anonymous.restricted, 5)

    def test_filters_open_source(self):
        snapshot = parse_account(response_data(), config(include_open_source=False))
        names = {repository.name_with_owner for repository in snapshot.repositories}
        self.assertNotIn("community/library", names)
        self.assertEqual(snapshot.total_commits, 7)
        self.assertEqual(snapshot.total_pull_requests, 0)

    def test_excluding_private_removes_private_activity_from_totals(self):
        snapshot = parse_account(response_data(), config(include_private=False))
        self.assertEqual(snapshot.private_contributions, 0)
        self.assertEqual(snapshot.total_commits, 6)
        self.assertEqual(snapshot.total_issues, 0)

    def test_organization_filter_applies_before_private_aggregation(self):
        snapshot = parse_account(response_data(), config(include_organizations=False))
        private = next(repository for repository in snapshot.repositories if repository.relationship == "private")
        self.assertEqual(private.contributions, 5)
        self.assertEqual(snapshot.private_contributions, 5)

    @patch("readme_auto_update.github.urllib.request.urlopen")
    def test_github_client_posts_graphql_with_bearer_token(self, urlopen):
        urlopen.return_value = FakeResponse({"data": {"viewer": {"login": "example-user"}}})
        data = GitHubClient("gh-secret").graphql("query { viewer { login } }", {})
        self.assertEqual(data["viewer"]["login"], "example-user")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer gh-secret")


if __name__ == "__main__":
    unittest.main()
