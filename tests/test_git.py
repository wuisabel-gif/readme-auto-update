import os
import unittest
from pathlib import Path
from unittest.mock import patch

from readme_auto_update.git import GitError, commit_and_push


class CommitAndPushTests(unittest.TestCase):
    def _run(self, push_failures: int):
        """Drive commit_and_push against a fake git that fails the first
        `push_failures` push attempts with a non-fast-forward error."""
        calls = []

        def fake_run_git(root, *args, check=True):
            calls.append(args)
            if args == ("branch", "--show-current"):
                return "main\n"
            if args[0] == "push":
                pushes = sum(1 for c in calls if c and c[0] == "push")
                if pushes <= push_failures:
                    raise GitError("! [rejected] (non-fast-forward)")
            return ""

        with patch("readme_auto_update.git.run_git", side_effect=fake_run_git), patch.dict(
            os.environ, {}, clear=True
        ):
            commit_and_push(Path("/repo"), "README.md", "msg")
        return calls

    def test_rebases_and_retries_once_on_non_fast_forward(self):
        calls = self._run(push_failures=1)
        self.assertIn(("pull", "--rebase", "origin", "main"), calls)
        self.assertEqual(sum(1 for c in calls if c[0] == "push"), 2)

    def test_reraises_when_push_still_rejected_after_rebase(self):
        with self.assertRaises(GitError):
            self._run(push_failures=2)


if __name__ == "__main__":
    unittest.main()
