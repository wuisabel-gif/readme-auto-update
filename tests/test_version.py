import tomllib
import unittest
from pathlib import Path

import readme_auto_update


class VersionTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self):
        pyproject = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
        )
        self.assertEqual(pyproject["project"]["version"], readme_auto_update.__version__)

    def test_user_agent_is_single_sourced_from_version(self):
        self.assertEqual(
            readme_auto_update.USER_AGENT,
            f"readme-auto-update/{readme_auto_update.__version__}",
        )


if __name__ == "__main__":
    unittest.main()
