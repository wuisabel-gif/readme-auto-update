from __future__ import annotations

from dataclasses import dataclass
import os


def _input(name: str, default: str = "") -> str:
    return os.getenv(f"INPUT_{name.upper()}", default).strip()


def _bool(value: str, *, name: str) -> bool:
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false, got {value!r}")


def _integer(value: str, *, name: str, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


@dataclass(frozen=True)
class Config:
    github_token: str
    openai_api_key: str
    mode: str
    output_file: str
    section_name: str
    model: str
    days: int
    max_repositories: int
    include_owned: bool
    include_organizations: bool
    include_open_source: bool
    include_private: bool
    show_private_names: bool
    include_archived: bool
    prompt: str
    commit: bool
    commit_message: str
    commit_username: str
    commit_email: str
    dry_run: bool
    anthropic_api_key: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        mode = _input("mode", "auto").lower()
        if mode not in {"auto", "ai", "rules"}:
            raise ValueError("mode must be one of: auto, ai, rules")

        github_token = _input("github_token") or os.getenv("GH_TOKEN", "")
        if not github_token:
            raise ValueError(
                "github_token is required for account-wide repository and contribution discovery"
            )

        output_file = _input("output_file", "README.md")
        if not output_file or output_file.startswith("/") or ".." in output_file.split("/"):
            raise ValueError("output_file must be a relative path inside the repository")

        section_name = _input("section_name", "readme-auto-update")
        if not section_name or "--" in section_name or any(c in section_name for c in "<>"):
            raise ValueError("section_name contains unsupported characters")

        return cls(
            github_token=github_token,
            openai_api_key=_input("openai_api_key") or os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=_input("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY", ""),
            mode=mode,
            output_file=output_file,
            section_name=section_name,
            model=_input("model"),
            days=_integer(_input("days", "365"), name="days", minimum=1, maximum=365),
            max_repositories=_integer(
                _input("max_repositories", "30"),
                name="max_repositories",
                minimum=1,
                maximum=100,
            ),
            include_owned=_bool(_input("include_owned", "true"), name="include_owned"),
            include_organizations=_bool(
                _input("include_organizations", "true"), name="include_organizations"
            ),
            include_open_source=_bool(
                _input("include_open_source", "true"), name="include_open_source"
            ),
            include_private=_bool(
                _input("include_private", "true"), name="include_private"
            ),
            show_private_names=_bool(
                _input("show_private_names", "false"), name="show_private_names"
            ),
            include_archived=_bool(
                _input("include_archived", "false"), name="include_archived"
            ),
            prompt=_input("prompt"),
            commit=_bool(_input("commit", "true"), name="commit"),
            commit_message=_input(
                "commit_message", "docs: update README with README Auto Update"
            ),
            commit_username=_input("commit_username", "readme-auto-update[bot]"),
            commit_email=_input(
                "commit_email",
                "readme-auto-update-bot@example.invalid",
            ),
            dry_run=_bool(_input("dry_run", "false"), name="dry_run"),
        )

    @property
    def effective_mode(self) -> str:
        if self.mode == "auto":
            return "ai" if self.openai_api_key or self.anthropic_api_key else "rules"
        return self.mode

    @property
    def ai_provider(self) -> str:
        # ponytail: openai wins when both keys are set, preserving pre-anthropic behavior
        return "openai" if self.openai_api_key else "anthropic"
