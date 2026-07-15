from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from readme_auto_update.config import Config
from readme_auto_update.runner import run
from readme_auto_update.snapshot import AccountSnapshot, Profile, RepositorySummary


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


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


def snapshot() -> AccountSnapshot:
    repository = RepositorySummary(
        name_with_owner="example-user/sample-project",
        description="A useful tool.",
        url="https://github.com/example-user/sample-project",
        owner="example-user",
        relationship="owned",
        is_private=False,
        is_archived=False,
        is_fork=False,
        language="Python",
        topics=("tools",),
        stars=2,
        forks=0,
        updated_at="2026-07-15T00:00:00Z",
        commits=10,
    )
    return AccountSnapshot(
        profile=Profile(
            "example-user", "Example User", "Builder", "", "Example City", "", ""
        ),
        started_at="2025-07-15T00:00:00Z",
        ended_at="2026-07-15T00:00:00Z",
        organizations=(),
        repositories=(repository,),
        total_commits=10,
        total_pull_requests=2,
        total_issues=1,
        total_reviews=3,
        total_repositories_created=1,
        restricted_contributions=0,
        private_contributions=0,
    )


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "README.md").write_text(
            "# Example User\n\nManual intro.\n", encoding="utf-8"
        )
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-m", "Initial profile")

    def tearDown(self):
        self.temp.cleanup()

    @patch("readme_auto_update.runner.build_account_snapshot", return_value=snapshot())
    def test_runner_updates_readme_without_overwriting_manual_content(self, _build):
        with patch.dict(os.environ, {}, clear=True):
            changed = run(config(), self.root)
        output = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertTrue(changed)
        self.assertIn("Manual intro.", output)
        self.assertIn("<!-- README-AUTO-UPDATE:START:readme-auto-update -->", output)
        self.assertIn("example-user/sample-project", output)

    @patch("readme_auto_update.runner.build_account_snapshot", return_value=snapshot())
    def test_dry_run_does_not_write(self, _build):
        before = (self.root / "README.md").read_text(encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            changed = run(config(dry_run=True), self.root)
        self.assertTrue(changed)
        self.assertEqual((self.root / "README.md").read_text(encoding="utf-8"), before)

    @patch("readme_auto_update.runner.build_account_snapshot", return_value=snapshot())
    def test_runner_commits_and_pushes_to_trigger_branch(self, _build):
        remote = Path(self.temp.name) / "remote.git"
        remote.mkdir()
        git(remote, "init", "--bare")
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "push", "-u", "origin", "main")
        with patch.dict(os.environ, {"GITHUB_REF_NAME": "main"}, clear=True):
            changed = run(config(commit=True), self.root)
        self.assertTrue(changed)
        self.assertEqual(
            git(self.root, "log", "-1", "--pretty=%s").strip(),
            "docs: update README with README Auto Update",
        )
        remote_document = git(remote, "show", "main:README.md")
        self.assertIn("<!-- README-AUTO-UPDATE:START:readme-auto-update -->", remote_document)


if __name__ == "__main__":
    unittest.main()
