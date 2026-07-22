from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request


class GitHubAPIError(RuntimeError):
    pass


# 429 (rate limit) and 5xx (upstream) are transient; auth/permission errors are not.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class GitHubClient:
    def __init__(self, token: str, *, timeout: int = 120, max_retries: int = 2):
        if not token:
            raise ValueError("A GitHub token is required")
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries

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
        for attempt in range(self._max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                # Never include the upstream body: it can contain private repository names.
                if exc.code in _RETRYABLE_STATUS and attempt < self._max_retries:
                    self._backoff(attempt, exc.headers.get("Retry-After"))
                    continue
                raise GitHubAPIError(
                    f"GitHub API request failed with HTTP {exc.code}"
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < self._max_retries:
                    self._backoff(attempt, None)
                    continue
                raise GitHubAPIError("GitHub API request failed (network error)") from exc

        errors = result.get("errors") or []
        if errors:
            # GraphQL messages can include private resource names or query details.
            raise GitHubAPIError("GitHub GraphQL request failed (upstream error)")
        data = result.get("data")
        if not isinstance(data, dict):
            raise GitHubAPIError("GitHub GraphQL response did not contain data")
        return data

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        if retry_after and retry_after.strip().isdigit():
            delay = min(float(retry_after), 30.0)
        else:
            delay = min(2.0**attempt + random.uniform(0.0, 0.5), 30.0)
        time.sleep(delay)
