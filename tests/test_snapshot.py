from dataclasses import replace
import json
import io
import unittest
from unittest.mock import patch
import urllib.error

from readme_auto_update.config import Config
from readme_auto_update.github import GitHubClient
from readme_auto_update.snapshot import _next_page, _paged_account, parse_account


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


def repo(name, owner, *, private=False, archived=False, fork=False, parent=None):
    node = {
        "nameWithOwner": name,
        "description": f"Description for {name}",
        "url": f"https://github.com/{name}",
        "isPrivate": private,
        "isArchived": archived,
        "isFork": fork,
        "stargazerCount": 3,
        "forkCount": 1,
        "updatedAt": "2026-07-10T00:00:00Z",
        "owner": {"login": owner},
        "primaryLanguage": {"name": "Python"},
        "repositoryTopics": {"nodes": [{"topic": {"name": "tools"}}]},
    }
    if parent:
        node["parent"] = {"nameWithOwner": parent, "url": f"https://github.com/{parent}"}
    return node


def fork_response_data():
    active = repo("example-user/awesome-fork", "example-user", fork=True, parent="upstream-org/awesome")
    dead = repo("example-user/dead-fork", "example-user", fork=True, parent="someone/dead")
    return {
        "viewer": {
            "login": "example-user",
            "name": "Example User",
            "bio": "",
            "company": "",
            "location": "",
            "websiteUrl": "",
            "avatarUrl": "",
            "organizations": {"nodes": []},
            "repositories": {"nodes": [active, dead]},
            "contributionsCollection": {
                "startedAt": "2025-07-15T00:00:00Z",
                "endedAt": "2026-07-15T00:00:00Z",
                "totalCommitContributions": 6,
                "totalIssueContributions": 0,
                "totalPullRequestContributions": 0,
                "totalPullRequestReviewContributions": 0,
                "totalRepositoryContributions": 0,
                "restrictedContributionsCount": 0,
                "hasAnyRestrictedContributions": False,
                "commitContributionsByRepository": [
                    {"repository": active, "contributions": {"totalCount": 6}},
                ],
                "issueContributions": {"nodes": []},
                "pullRequestContributionsByRepository": [],
                "pullRequestReviewContributionsByRepository": [],
            },
        }
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

    def test_active_owned_fork_becomes_open_source_contribution(self):
        snapshot = parse_account(fork_response_data(), config())
        forks = [
            repository
            for repository in snapshot.repositories
            if repository.parent_name_with_owner == "upstream-org/awesome"
        ]
        self.assertEqual(len(forks), 1)
        self.assertEqual(forks[0].relationship, "open_source")
        self.assertEqual(forks[0].commits, 6)
        self.assertEqual(forks[0].parent_url, "https://github.com/upstream-org/awesome")

    def test_inactive_owned_fork_is_dropped(self):
        snapshot = parse_account(fork_response_data(), config())
        names = {repository.name_with_owner for repository in snapshot.repositories}
        self.assertNotIn("example-user/dead-fork", names)

    def test_fork_contribution_follows_open_source_toggle(self):
        snapshot = parse_account(fork_response_data(), config(include_open_source=False))
        self.assertFalse(
            any(r.parent_name_with_owner == "upstream-org/awesome" for r in snapshot.repositories)
        )

    def test_pagination_rejects_missing_and_repeated_cursors(self):
        with self.assertRaisesRegex(ValueError, "without a cursor"):
            _next_page({"pageInfo": {"hasNextPage": True, "endCursor": ""}}, "organizations", set())
        with self.assertRaisesRegex(ValueError, "repeated cursor"):
            _next_page({"pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"}}, "issues", {"cursor-1"})

    @patch("readme_auto_update.snapshot.GitHubClient.graphql")
    def test_paged_account_merges_all_connections_without_leaking_private_names(self, graphql):
        def repository(name, owner, private=False):
            return {
                "nameWithOwner": f"{owner}/{name}", "description": "", "url": "",
                "isPrivate": private, "isArchived": False, "isFork": False,
                "stargazerCount": 0, "forkCount": 0, "updatedAt": "",
                "owner": {"login": owner}, "primaryLanguage": None,
                "repositoryTopics": {"nodes": []},
            }

        def page(orgs, repos, issues, org_info, repo_info, issue_info):
            return {"viewer": {
                "login": "example-user", "organizations": {"nodes": orgs, "pageInfo": org_info},
                "repositories": {"nodes": repos, "pageInfo": repo_info},
                "contributionsCollection": {
                    "startedAt": "", "endedAt": "", "issueContributions": {
                        "nodes": issues, "pageInfo": issue_info,
                    },
                    "commitContributionsByRepository": [],
                    "pullRequestContributionsByRepository": [],
                    "pullRequestReviewContributionsByRepository": [],
                },
            }}

        org_repo = repository("project", "later-org")
        private_repo = repository("secret", "example-user", private=True)
        responses = {
            None: page([{"login": "first-org"}], [],
                       [{"issue": {"id": "issue-1", "repository": org_repo}}],
                       {"hasNextPage": True, "endCursor": "org-2"},
                       {"hasNextPage": True, "endCursor": "repo-2"},
                       {"hasNextPage": True, "endCursor": "issue-2"}),
            "org-2": page([{"login": "later-org"}], [], [],
                          {"hasNextPage": False, "endCursor": None},
                          {"hasNextPage": False, "endCursor": None},
                          {"hasNextPage": False, "endCursor": None}),
            "repo-2": page([], [private_repo], [],
                           {"hasNextPage": False, "endCursor": None},
                           {"hasNextPage": False, "endCursor": None},
                           {"hasNextPage": False, "endCursor": None}),
            "issue-2": page([], [],
                             [{"issue": {"id": "issue-1", "repository": org_repo}}],
                             {"hasNextPage": False, "endCursor": None},
                             {"hasNextPage": False, "endCursor": None},
                             {"hasNextPage": False, "endCursor": None}),
        }
        graphql.side_effect = lambda query, variables: responses[variables.get("organizationsCursor") or variables.get("repositoriesCursor") or variables.get("issuesCursor")]
        snapshot = parse_account(_paged_account(config(github_token="token"), {}), config(github_token="token"))
        self.assertEqual([item.owner for item in snapshot.repositories if item.relationship == "organization"], ["later-org"])
        self.assertEqual(sum(item.issues for item in snapshot.repositories), 1)
        self.assertNotIn("example-user/secret", snapshot.as_prompt_text())
        self.assertEqual(graphql.call_count, 4)

    @patch("readme_auto_update.snapshot.GitHubClient.graphql")
    def test_paged_account_skips_owned_repositories_when_disabled(self, graphql):
        first_page = {"viewer": {
            "login": "example-user",
            "organizations": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}},
            "repositories": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "repo-2"}},
            "contributionsCollection": {
                "issueContributions": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}},
            },
        }}
        graphql.return_value = first_page
        _paged_account(config(github_token="token", include_owned=False), {})
        self.assertEqual(graphql.call_count, 1)

    def test_issue_contributions_without_ids_are_counted_individually(self):
        def repo(name):
            return {"nameWithOwner": name, "owner": {"login": name.split("/")[0]}}

        data = {"viewer": {
            "login": "example-user",
            "organizations": {"nodes": []},
            "repositories": {"nodes": []},
            "contributionsCollection": {"issueContributions": {"nodes": [
                {"issue": {"repository": repo("example-user/app")}},
                {"issue": {"repository": repo("example-user/app")}},
            ]}},
        }}
        snapshot = parse_account(data, config())
        self.assertEqual(sum(item.issues for item in snapshot.repositories), 2)

    @patch("readme_auto_update.snapshot.GitHubClient.graphql")
    def test_pagination_fails_when_pages_never_terminate(self, graphql):
        def endless(query, variables):
            token = variables.get("organizationsCursor") or "seed"
            return {"viewer": {
                "login": "example-user",
                "organizations": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": f"{token}-next"}},
            }}

        graphql.side_effect = endless
        with self.assertRaises(ValueError):
            _paged_account(config(github_token="token"), {})

    def test_github_http_and_graphql_errors_redact_upstream_content(self):
        http_error = urllib.error.HTTPError(
            "https://api.github.com/graphql", 500, "error", {},
            io.BytesIO(b"private-repository-sentinel"),
        )
        with patch("readme_auto_update.github.urllib.request.urlopen", side_effect=http_error):
            with self.assertRaisesRegex(Exception, "HTTP 500") as raised:
                GitHubClient("token", max_retries=0).graphql("query", {})
        self.assertNotIn("private-repository-sentinel", str(raised.exception))
        with patch("readme_auto_update.github.urllib.request.urlopen",
                   return_value=FakeResponse({"errors": [{"message": "private-repository-sentinel"}]})):
            with self.assertRaises(Exception) as raised:
                GitHubClient("token", max_retries=0).graphql("query", {})
        self.assertNotIn("private-repository-sentinel", str(raised.exception))

    @patch("readme_auto_update.github.time.sleep", return_value=None)
    @patch("readme_auto_update.github.urllib.request.urlopen")
    def test_retries_transient_5xx_then_succeeds(self, urlopen, sleep):
        transient = urllib.error.HTTPError("https://api.github.com/graphql", 502, "bad", {}, None)
        urlopen.side_effect = [transient, FakeResponse({"data": {"viewer": {"login": "ok"}}})]
        data = GitHubClient("token", max_retries=2).graphql("query", {})
        self.assertEqual(data["viewer"]["login"], "ok")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()

    @patch("readme_auto_update.github.time.sleep", return_value=None)
    @patch("readme_auto_update.github.urllib.request.urlopen")
    def test_does_not_retry_auth_errors(self, urlopen, sleep):
        forbidden = urllib.error.HTTPError("https://api.github.com/graphql", 403, "no", {}, None)
        urlopen.side_effect = forbidden
        with self.assertRaisesRegex(Exception, "HTTP 403"):
            GitHubClient("token", max_retries=2).graphql("query", {})
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    @patch("readme_auto_update.github.urllib.request.urlopen")
    def test_github_client_posts_graphql_with_bearer_token(self, urlopen):
        urlopen.return_value = FakeResponse({"data": {"viewer": {"login": "example-user"}}})
        data = GitHubClient("gh-secret").graphql("query { viewer { login } }", {})
        self.assertEqual(data["viewer"]["login"], "example-user")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer gh-secret")


if __name__ == "__main__":
    unittest.main()
