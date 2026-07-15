from __future__ import annotations

import json
import urllib.error
import urllib.request


class GitHubAPIError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str, *, timeout: int = 120):
        if not token:
            raise ValueError("A GitHub token is required")
        self._token = token
        self._timeout = timeout

    def graphql(self, query: str, variables: dict) -> dict:
        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "readme-auto-update/0.2",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise GitHubAPIError(
                f"GitHub API request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GitHubAPIError(f"GitHub API request failed: {exc.reason}") from exc

        errors = result.get("errors") or []
        if errors:
            messages = "; ".join(str(item.get("message", "Unknown GraphQL error")) for item in errors)
            raise GitHubAPIError(f"GitHub GraphQL error: {messages[:1000]}")
        data = result.get("data")
        if not isinstance(data, dict):
            raise GitHubAPIError("GitHub GraphQL response did not contain data")
        return data
