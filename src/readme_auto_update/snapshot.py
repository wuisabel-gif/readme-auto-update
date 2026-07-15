from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json

from .config import Config
from .github import GitHubClient


REPOSITORY_FRAGMENT = """
fragment RepositoryEvidence on Repository {
  nameWithOwner
  description
  url
  isPrivate
  isArchived
  isFork
  stargazerCount
  forkCount
  updatedAt
  owner { login }
  primaryLanguage { name }
  repositoryTopics(first: 10) { nodes { topic { name } } }
}
"""


ACCOUNT_QUERY = REPOSITORY_FRAGMENT + """
query ReadmeAutoUpdateAccount($from: DateTime!, $to: DateTime!) {
  viewer {
    login
    name
    bio
    company
    location
    websiteUrl
    avatarUrl(size: 160)
    organizations(first: 100) { nodes { login name } }
    repositories(
      first: 100
      ownerAffiliations: [OWNER]
      orderBy: { field: UPDATED_AT, direction: DESC }
    ) { nodes { ...RepositoryEvidence } }
    contributionsCollection(from: $from, to: $to) {
      startedAt
      endedAt
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
      restrictedContributionsCount
      hasAnyRestrictedContributions
      commitContributionsByRepository(maxRepositories: 100) {
        repository { ...RepositoryEvidence }
        contributions(first: 1) { totalCount }
      }
      issueContributions(first: 100) {
        nodes { issue { repository { ...RepositoryEvidence } } }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { ...RepositoryEvidence }
        contributions(first: 1) { totalCount }
      }
      pullRequestReviewContributionsByRepository(maxRepositories: 100) {
        repository { ...RepositoryEvidence }
        contributions(first: 1) { totalCount }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class Profile:
    login: str
    name: str
    bio: str
    company: str
    location: str
    website_url: str
    avatar_url: str


@dataclass
class RepositorySummary:
    name_with_owner: str
    description: str
    url: str
    owner: str
    relationship: str
    is_private: bool
    is_archived: bool
    is_fork: bool
    language: str
    topics: tuple[str, ...]
    stars: int
    forks: int
    updated_at: str
    commits: int = 0
    pull_requests: int = 0
    issues: int = 0
    reviews: int = 0
    restricted: int = 0

    @property
    def contributions(self) -> int:
        return self.commits + self.pull_requests + self.issues + self.reviews + self.restricted


@dataclass(frozen=True)
class AccountSnapshot:
    profile: Profile
    started_at: str
    ended_at: str
    organizations: tuple[str, ...]
    repositories: tuple[RepositorySummary, ...]
    total_commits: int
    total_pull_requests: int
    total_issues: int
    total_reviews: int
    total_repositories_created: int
    restricted_contributions: int
    private_contributions: int

    @property
    def total_contributions(self) -> int:
        return self.total_commits + self.total_pull_requests + self.total_issues + self.total_reviews

    def as_prompt_text(self) -> str:
        payload = {
            "profile": asdict(self.profile),
            "period": {"from": self.started_at, "to": self.ended_at},
            "totals": {
                "commits": self.total_commits,
                "pull_requests": self.total_pull_requests,
                "issues": self.total_issues,
                "reviews": self.total_reviews,
                "repositories_created": self.total_repositories_created,
                "private_or_restricted_contributions": self.private_contributions,
            },
            "organizations": list(self.organizations),
            "repository_evidence": [asdict(repository) for repository in self.repositories],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _repository(node: dict, login: str, organizations: set[str]) -> RepositorySummary:
    owner = _text((node.get("owner") or {}).get("login"))
    if owner.lower() == login.lower():
        relationship = "owned"
    elif owner.lower() in {organization.lower() for organization in organizations}:
        relationship = "organization"
    else:
        relationship = "open_source"
    topics = tuple(
        _text(((item or {}).get("topic") or {}).get("name"))
        for item in ((node.get("repositoryTopics") or {}).get("nodes") or [])
    )
    return RepositorySummary(
        name_with_owner=_text(node.get("nameWithOwner")),
        description=_text(node.get("description")),
        url=_text(node.get("url")),
        owner=owner,
        relationship=relationship,
        is_private=bool(node.get("isPrivate")),
        is_archived=bool(node.get("isArchived")),
        is_fork=bool(node.get("isFork")),
        language=_text((node.get("primaryLanguage") or {}).get("name")),
        topics=tuple(topic for topic in topics if topic),
        stars=int(node.get("stargazerCount") or 0),
        forks=int(node.get("forkCount") or 0),
        updated_at=_text(node.get("updatedAt")),
    )


def _get_or_add(
    repositories: dict[str, RepositorySummary],
    node: dict,
    login: str,
    organizations: set[str],
) -> RepositorySummary | None:
    if not node:
        return None
    name = _text(node.get("nameWithOwner"))
    if not name:
        return None
    if name not in repositories:
        repositories[name] = _repository(node, login, organizations)
    return repositories[name]


def _private_aggregate(repositories: list[RepositorySummary], restricted: int) -> RepositorySummary | None:
    private = [repository for repository in repositories if repository.is_private]
    contribution_count = sum(repository.contributions for repository in private) + restricted
    if contribution_count == 0:
        return None
    return RepositorySummary(
        name_with_owner="Private work",
        description="Private repository activity; names and repository content are hidden.",
        url="",
        owner="",
        relationship="private",
        is_private=True,
        is_archived=False,
        is_fork=False,
        language="",
        topics=(),
        stars=0,
        forks=0,
        updated_at="",
        commits=sum(repository.commits for repository in private),
        pull_requests=sum(repository.pull_requests for repository in private),
        issues=sum(repository.issues for repository in private),
        reviews=sum(repository.reviews for repository in private),
        restricted=restricted,
    )


def parse_account(data: dict, config: Config) -> AccountSnapshot:
    viewer = data.get("viewer") or {}
    login = _text(viewer.get("login"))
    if not login:
        raise ValueError(
            "The GitHub token did not resolve to a user account; use a user-authorized token"
        )

    organization_nodes = (viewer.get("organizations") or {}).get("nodes") or []
    organizations = {
        _text(node.get("login")) for node in organization_nodes if _text(node.get("login"))
    }
    repositories: dict[str, RepositorySummary] = {}
    if config.include_owned:
        for node in (viewer.get("repositories") or {}).get("nodes") or []:
            _get_or_add(repositories, node or {}, login, organizations)

    contributions = viewer.get("contributionsCollection") or {}
    for group in contributions.get("commitContributionsByRepository") or []:
        repository = _get_or_add(
            repositories, group.get("repository") or {}, login, organizations
        )
        if repository:
            repository.commits += int((group.get("contributions") or {}).get("totalCount") or 0)

    for node in (contributions.get("issueContributions") or {}).get("nodes") or []:
        repository = _get_or_add(
            repositories,
            ((node or {}).get("issue") or {}).get("repository") or {},
            login,
            organizations,
        )
        if repository:
            repository.issues += 1

    for group in contributions.get("pullRequestContributionsByRepository") or []:
        repository = _get_or_add(
            repositories,
            (group or {}).get("repository") or {},
            login,
            organizations,
        )
        if repository:
            repository.pull_requests += int(
                ((group or {}).get("contributions") or {}).get("totalCount") or 0
            )

    for group in contributions.get("pullRequestReviewContributionsByRepository") or []:
        repository = _get_or_add(
            repositories, (group or {}).get("repository") or {}, login, organizations
        )
        if repository:
            repository.reviews += int(
                ((group or {}).get("contributions") or {}).get("totalCount") or 0
            )

    all_repositories = list(repositories.values())
    restricted = int(contributions.get("restrictedContributionsCount") or 0)
    selected: list[RepositorySummary] = []
    private_pool: list[RepositorySummary] = []
    for repository in all_repositories:
        if repository.is_archived and not config.include_archived:
            continue
        if repository.relationship == "owned" and not config.include_owned:
            continue
        if repository.relationship == "organization" and not config.include_organizations:
            continue
        if repository.relationship == "open_source" and not config.include_open_source:
            continue
        if repository.is_private:
            if not config.include_private:
                continue
            private_pool.append(repository)
            if not config.show_private_names:
                continue
        selected.append(repository)

    if config.include_private and not config.show_private_names:
        aggregate = _private_aggregate(private_pool, restricted)
        if aggregate:
            selected.append(aggregate)
    elif config.include_private and restricted:
        # Even with private names enabled, GitHub can report contributions whose repository
        # identity is unavailable. Keep those explicitly anonymous.
        aggregate = _private_aggregate([], restricted)
        if aggregate:
            selected.append(aggregate)

    accessible_private = sum(repository.contributions for repository in private_pool)

    activity_scope = list(selected)
    selected.sort(
        key=lambda repository: (
            repository.contributions,
            repository.stars,
            repository.updated_at,
        ),
        reverse=True,
    )
    selected = selected[: config.max_repositories]

    all_categories_enabled = (
        config.include_owned
        and config.include_organizations
        and config.include_open_source
        and config.include_private
    )
    if all_categories_enabled:
        total_commits = int(contributions.get("totalCommitContributions") or 0)
        total_pull_requests = int(contributions.get("totalPullRequestContributions") or 0)
        total_issues = int(contributions.get("totalIssueContributions") or 0)
        total_reviews = int(contributions.get("totalPullRequestReviewContributions") or 0)
    else:
        total_commits = sum(repository.commits for repository in activity_scope)
        total_pull_requests = sum(repository.pull_requests for repository in activity_scope)
        total_issues = sum(repository.issues for repository in activity_scope)
        total_reviews = sum(repository.reviews for repository in activity_scope)

    visible_organizations = {
        repository.owner
        for repository in activity_scope
        if repository.relationship == "organization" and repository.owner
    }

    profile = Profile(
        login=login,
        name=_text(viewer.get("name")),
        bio=_text(viewer.get("bio")),
        company=_text(viewer.get("company")),
        location=_text(viewer.get("location")),
        website_url=_text(viewer.get("websiteUrl")),
        avatar_url=_text(viewer.get("avatarUrl")),
    )
    return AccountSnapshot(
        profile=profile,
        started_at=_text(contributions.get("startedAt")),
        ended_at=_text(contributions.get("endedAt")),
        organizations=tuple(sorted(visible_organizations, key=str.lower)),
        repositories=tuple(selected),
        total_commits=total_commits,
        total_pull_requests=total_pull_requests,
        total_issues=total_issues,
        total_reviews=total_reviews,
        total_repositories_created=int(contributions.get("totalRepositoryContributions") or 0),
        restricted_contributions=restricted,
        private_contributions=accessible_private + restricted if config.include_private else 0,
    )


def build_account_snapshot(config: Config) -> AccountSnapshot:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=config.days)
    variables = {
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
    }
    data = GitHubClient(config.github_token).graphql(ACCOUNT_QUERY, variables)
    return parse_account(data, config)
