import json
import unittest
from unittest.mock import patch

from readme_auto_update.generators import ai_summary, rules_summary
from readme_auto_update.snapshot import AccountSnapshot, Profile, RepositorySummary


def sample_snapshot() -> AccountSnapshot:
    return AccountSnapshot(
        profile=Profile(
            login="example-user",
            name="Example User",
            bio="I build tools for AI agents.",
            company="",
            location="Example City",
            website_url="https://example.invalid",
            avatar_url="https://example.invalid/avatar.png",
        ),
        started_at="2025-07-15T00:00:00Z",
        ended_at="2026-07-15T00:00:00Z",
        organizations=("example-org",),
        repositories=(
            RepositorySummary(
                name_with_owner="example-user/sample-project",
                description="Local memory for terminal agents.",
                url="https://github.com/example-user/sample-project",
                owner="example-user",
                relationship="owned",
                is_private=False,
                is_archived=False,
                is_fork=False,
                language="Rust",
                topics=("ai",),
                stars=12,
                forks=2,
                updated_at="2026-07-14T00:00:00Z",
                commits=20,
            ),
            RepositorySummary(
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
                commits=5,
                restricted=2,
            ),
        ),
        total_commits=25,
        total_pull_requests=4,
        total_issues=2,
        total_reviews=6,
        total_repositories_created=3,
        restricted_contributions=2,
        private_contributions=7,
    )


class FakeResponse:
    def __init__(self, body: dict):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.body).encode()


class GeneratorTests(unittest.TestCase):
    def test_rules_writer_separates_projects_and_private_work(self):
        output = rules_summary(sample_snapshot())
        self.assertIn("## Projects", output)
        self.assertIn("sample-project", output)
        self.assertIn("## Private work", output)
        self.assertNotIn("example-org/private-project", output)

    @patch("readme_auto_update.generators.urllib.request.urlopen")
    def test_ai_writer_receives_structured_evidence(self, urlopen):
        urlopen.return_value = FakeResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "```markdown\n## Projects\nUseful.\n```"}
                        ],
                    }
                ]
            }
        )
        output = ai_summary(
            sample_snapshot(),
            api_key="not-a-real-key",
            model="test-model",
            prior_content="",
            extra_prompt="Be direct.",
        )
        self.assertEqual(output, "## Projects\nUseful.")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "test-model")
        self.assertIn("Private work", payload["input"])
        self.assertIn("intentionally anonymized", payload["instructions"])

    @patch("readme_auto_update.generators.urllib.request.urlopen")
    def test_anthropic_writer_receives_structured_evidence(self, urlopen):
        urlopen.return_value = FakeResponse(
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "## Projects\nUseful."}],
            }
        )
        output = ai_summary(
            sample_snapshot(),
            provider="anthropic",
            api_key="not-a-real-key",
            model="",
            prior_content="",
            extra_prompt="",
        )
        self.assertEqual(output, "## Projects\nUseful.")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.get_header("X-api-key"), "not-a-real-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "claude-opus-4-8")
        self.assertIn("intentionally anonymized", payload["system"])
        self.assertIn("Private work", payload["messages"][0]["content"])

    @patch("readme_auto_update.generators.urllib.request.urlopen")
    def test_anthropic_writer_raises_on_refusal(self, urlopen):
        urlopen.return_value = FakeResponse({"stop_reason": "refusal", "content": []})
        with self.assertRaisesRegex(RuntimeError, "refusal"):
            ai_summary(
                sample_snapshot(),
                provider="anthropic",
                api_key="not-a-real-key",
                model="",
                prior_content="",
                extra_prompt="",
            )


if __name__ == "__main__":
    unittest.main()
