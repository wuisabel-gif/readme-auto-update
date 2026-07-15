from __future__ import annotations

from pathlib import Path
import os
import subprocess


class GitError(RuntimeError):
    pass


def run_git(root: Path, *args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise GitError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout


def repository_root(start: Path | None = None) -> Path:
    root = Path(start or os.getenv("GITHUB_WORKSPACE") or Path.cwd()).resolve()
    # Docker actions commonly run as root against a runner-owned workspace.
    run_git(root, "config", "--global", "--add", "safe.directory", str(root), check=False)
    discovered = run_git(root, "rev-parse", "--show-toplevel").strip()
    return Path(discovered)


def configure_identity(root: Path, username: str, email: str) -> None:
    run_git(root, "config", "user.name", username)
    run_git(root, "config", "user.email", email)


def commit_and_push(root: Path, path: str, message: str) -> None:
    run_git(root, "add", "--", path)
    run_git(root, "commit", "-m", message, "--", path)
    branch = os.getenv("GITHUB_REF_NAME", "").strip()
    if not branch:
        branch = run_git(root, "branch", "--show-current").strip()
    if not branch:
        raise GitError("Cannot determine the branch to push; set GITHUB_REF_NAME")
    run_git(root, "push", "origin", f"HEAD:{branch}")

