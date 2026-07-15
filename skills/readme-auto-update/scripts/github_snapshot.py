#!/usr/bin/env python3
"""Collect privacy-filtered GitHub profile evidence for README writing."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request


REPOSITORY_FIELDS = """
fragment ReadmeRepository on Repository {
  nameWithOwner description url isPrivate isArchived isFork
  stargazerCount forkCount updatedAt
  owner { login }
  primaryLanguage { name }
  repositoryTopics(first: 10) { nodes { topic { name } } }
}
"""

QUERY = REPOSITORY_FIELDS + """
query ReadmeAutoUpdateSnapshot($from: DateTime!, $to: DateTime!) {
  viewer {
    login name bio company location websiteUrl avatarUrl(size: 160)
    organizations(first: 100) { nodes { login } }
    repositories(
      first: 100
      ownerAffiliations: [OWNER]
      orderBy: { field: UPDATED_AT, direction: DESC }
    ) { nodes { ...ReadmeRepository } }
    contributionsCollection(from: $from, to: $to) {
      startedAt endedAt
      totalCommitContributions totalIssueContributions
      totalPullRequestContributions totalPullRequestReviewContributions
      totalRepositoryContributions restrictedContributionsCount
      commitContributionsByRepository(maxRepositories: 100) {
        repository { ...ReadmeRepository }
        contributions(first: 1) { totalCount }
      }
      issueContributions(first: 100) {
        nodes { issue { repository { ...ReadmeRepository } } }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { ...ReadmeRepository }
        contributions(first: 1) { totalCount }
      }
      pullRequestReviewContributionsByRepository(maxRepositories: 100) {
        repository { ...ReadmeRepository }
        contributions(first: 1) { totalCount }
      }
    }
  }
}
"""


def find_token() -> str:
    for name in ("README_AUTO_UPDATE_GITHUB_TOKEN", "GH_TOKEN"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    if shutil.which("gh"):
        result = subprocess.run(
            ["gh", "auth", "token"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise RuntimeError(
        "No user-authorized GitHub credential found. Set "
        "README_AUTO_UPDATE_GITHUB_TOKEN or GH_TOKEN, or authenticate gh."
    )


def graphql(token: str, variables: dict) -> dict:
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "readme-auto-update-skill/1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise RuntimeError(f"GitHub API failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API failed: {exc.reason}") from exc
    if result.get("errors"):
        messages = "; ".join(item.get("message", "GraphQL error") for item in result["errors"])
        raise RuntimeError(f"GitHub GraphQL error: {messages[:1000]}")
    if not isinstance(result.get("data"), dict):
        raise RuntimeError("GitHub response did not contain data")
    return result["data"]


def text(value) -> str:
    return value if isinstance(value, str) else ""


def make_repository(node: dict, login: str, organizations: set[str]) -> dict:
    owner = text((node.get("owner") or {}).get("login"))
    if owner.lower() == login.lower():
        relationship = "owned"
    elif owner.lower() in {item.lower() for item in organizations}:
        relationship = "organization"
    else:
        relationship = "open_source"
    topics = [
        text(((item or {}).get("topic") or {}).get("name"))
        for item in ((node.get("repositoryTopics") or {}).get("nodes") or [])
    ]
    return {
        "name_with_owner": text(node.get("nameWithOwner")),
        "description": text(node.get("description")),
        "url": text(node.get("url")),
        "owner": owner,
        "relationship": relationship,
        "is_private": bool(node.get("isPrivate")),
        "is_archived": bool(node.get("isArchived")),
        "is_fork": bool(node.get("isFork")),
        "language": text((node.get("primaryLanguage") or {}).get("name")),
        "topics": [topic for topic in topics if topic],
        "stars": int(node.get("stargazerCount") or 0),
        "forks": int(node.get("forkCount") or 0),
        "updated_at": text(node.get("updatedAt")),
        "commits": 0,
        "pull_requests": 0,
        "issues": 0,
        "reviews": 0,
        "restricted": 0,
    }


def activity(repository: dict) -> int:
    return sum(
        int(repository.get(key) or 0)
        for key in ("commits", "pull_requests", "issues", "reviews", "restricted")
    )


def private_aggregate(repositories: list[dict], restricted: int) -> dict | None:
    total = sum(activity(repository) for repository in repositories) + restricted
    if not total:
        return None
    return {
        "name_with_owner": "Private work",
        "description": "Private repository activity; names and repository content are hidden.",
        "url": "",
        "owner": "",
        "relationship": "private",
        "is_private": True,
        "is_archived": False,
        "is_fork": False,
        "language": "",
        "topics": [],
        "stars": 0,
        "forks": 0,
        "updated_at": "",
        "commits": sum(item["commits"] for item in repositories),
        "pull_requests": sum(item["pull_requests"] for item in repositories),
        "issues": sum(item["issues"] for item in repositories),
        "reviews": sum(item["reviews"] for item in repositories),
        "restricted": restricted,
    }


def parse_account(data: dict, options: argparse.Namespace) -> dict:
    viewer = data.get("viewer") or {}
    login = text(viewer.get("login"))
    if not login:
        raise RuntimeError("The credential did not resolve to a GitHub user account")
    organizations = {
        text(node.get("login"))
        for node in ((viewer.get("organizations") or {}).get("nodes") or [])
        if text(node.get("login"))
    }
    repositories: dict[str, dict] = {}

    def get_repository(node: dict) -> dict | None:
        name = text(node.get("nameWithOwner"))
        if not name:
            return None
        repositories.setdefault(name, make_repository(node, login, organizations))
        return repositories[name]

    if options.include_owned:
        for node in (viewer.get("repositories") or {}).get("nodes") or []:
            get_repository(node or {})

    contributions = viewer.get("contributionsCollection") or {}
    grouped = (
        ("commitContributionsByRepository", "commits"),
        ("pullRequestContributionsByRepository", "pull_requests"),
        ("pullRequestReviewContributionsByRepository", "reviews"),
    )
    for group_name, counter in grouped:
        for group in contributions.get(group_name) or []:
            repository = get_repository((group or {}).get("repository") or {})
            if repository:
                repository[counter] += int(
                    ((group or {}).get("contributions") or {}).get("totalCount") or 0
                )
    for node in (contributions.get("issueContributions") or {}).get("nodes") or []:
        repository = get_repository(
            ((node or {}).get("issue") or {}).get("repository") or {}
        )
        if repository:
            repository["issues"] += 1

    restricted = int(contributions.get("restrictedContributionsCount") or 0)
    selected: list[dict] = []
    private_pool: list[dict] = []
    for repository in repositories.values():
        if repository["is_archived"] and not options.include_archived:
            continue
        relationship = repository["relationship"]
        if relationship == "owned" and not options.include_owned:
            continue
        if relationship == "organization" and not options.include_organizations:
            continue
        if relationship == "open_source" and not options.include_open_source:
            continue
        if repository["is_private"]:
            if not options.include_private:
                continue
            private_pool.append(repository)
            if not options.show_private_names:
                continue
        selected.append(repository)

    if options.include_private and not options.show_private_names:
        aggregate = private_aggregate(private_pool, restricted)
        if aggregate:
            selected.append(aggregate)
    elif options.include_private and restricted:
        selected.append(private_aggregate([], restricted))

    selected.sort(
        key=lambda item: (activity(item), item["stars"], item["updated_at"]), reverse=True
    )
    activity_scope = list(selected)
    selected = selected[: options.max_repositories]
    all_categories = (
        options.include_owned
        and options.include_organizations
        and options.include_open_source
        and options.include_private
    )
    if all_categories:
        totals = {
            "commits": int(contributions.get("totalCommitContributions") or 0),
            "pull_requests": int(contributions.get("totalPullRequestContributions") or 0),
            "issues": int(contributions.get("totalIssueContributions") or 0),
            "reviews": int(contributions.get("totalPullRequestReviewContributions") or 0),
        }
    else:
        totals = {
            key: sum(int(repository.get(key) or 0) for repository in activity_scope)
            for key in ("commits", "pull_requests", "issues", "reviews")
        }
    visible_organizations = sorted(
        {
            repository["owner"]
            for repository in activity_scope
            if repository["relationship"] == "organization" and repository["owner"]
        },
        key=str.lower,
    )
    totals.update(
        {
            "repositories_created": int(contributions.get("totalRepositoryContributions") or 0),
            "private_or_restricted_contributions": (
                sum(activity(repository) for repository in private_pool) + restricted
                if options.include_private
                else 0
            ),
        }
    )
    return {
        "profile": {
            "login": login,
            "name": text(viewer.get("name")),
            "bio": text(viewer.get("bio")),
            "company": text(viewer.get("company")),
            "location": text(viewer.get("location")),
            "website_url": text(viewer.get("websiteUrl")),
            "avatar_url": text(viewer.get("avatarUrl")),
        },
        "period": {
            "from": text(contributions.get("startedAt")),
            "to": text(contributions.get("endedAt")),
        },
        "totals": totals,
        "organizations": visible_organizations,
        "repository_evidence": selected,
    }


def bounded_integer(name: str, minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"{name} must be between {minimum} and {maximum}"
            )
        return number

    return parse


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=bounded_integer("days", 1, 365), default=365)
    parser.add_argument(
        "--max-repositories",
        type=bounded_integer("max repositories", 1, 100),
        default=30,
    )
    parser.add_argument("--output", default="-", help="JSON path, or - for stdout")
    parser.add_argument("--show-private-names", action="store_true")
    parser.add_argument("--exclude-private", dest="include_private", action="store_false")
    parser.add_argument("--exclude-owned", dest="include_owned", action="store_false")
    parser.add_argument(
        "--exclude-organizations", dest="include_organizations", action="store_false"
    )
    parser.add_argument("--exclude-open-source", dest="include_open_source", action="store_false")
    parser.add_argument("--include-archived", action="store_true")
    parser.set_defaults(
        include_private=True,
        include_owned=True,
        include_organizations=True,
        include_open_source=True,
    )
    return parser.parse_args()


def main() -> int:
    options = arguments()
    now = datetime.now(timezone.utc)
    variables = {
        "from": (now - timedelta(days=options.days)).isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
    }
    try:
        result = parse_account(graphql(find_token(), variables), options)
        rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if options.output == "-":
            sys.stdout.write(rendered)
        else:
            output = Path(options.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        return 0
    except Exception as exc:
        print(f"github_snapshot: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
