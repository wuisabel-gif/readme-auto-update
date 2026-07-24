from __future__ import annotations

import difflib
import os
from pathlib import Path
import sys

from .config import Config
from .generators import ai_summary, rules_summary
from .git import commit_and_push, configure_identity, repository_root
from .markdown import managed_content, read_document, update_document
from .snapshot import build_account_snapshot


def notice(message: str) -> None:
    print(f"::notice::{message}")


def warning(message: str) -> None:
    print(f"::warning::{message}")


def error(message: str) -> None:
    print(f"::error::{message}", file=sys.stderr)


def _generate(config: Config, snapshot, old_document: str) -> tuple[str, str]:
    """Return (generated_markdown, mode_used). The free structural template is the
    safety net: if the AI writer fails and strict is off, fall back to it and keep
    the run green; if no key is set at all, note how to get the narrative upgrade."""
    mode = config.effective_mode
    if mode == "ai":
        api_key = config.openai_api_key or config.anthropic_api_key
        if not api_key:
            raise ValueError("openai_api_key or anthropic_api_key is required when mode is ai")
        try:
            generated = ai_summary(
                snapshot,
                provider=config.ai_provider,
                api_key=api_key,
                model=config.model,
                prior_content=managed_content(old_document, config.section_name),
                extra_prompt=config.prompt,
            )
            return generated, "ai"
        except Exception as exc:
            if config.strict:
                raise
            warning(
                f"Narrative writer failed ({exc}); wrote the free structural template "
                f"'{config.template}' instead. Set strict: true to fail the run instead."
            )
            return rules_summary(snapshot, template=config.template), "rules"

    generated = rules_summary(snapshot, template=config.template)
    if config.mode == "auto":
        notice(
            f"Wrote the free structural README (rules mode, template: {config.template}). "
            "For a narrative 'builder's story', run it in your agent, polish with Cadence "
            "(https://github.com/wuisabel-gif/Cadence), or add an OpenAI/Anthropic key for "
            "the scheduled Action."
        )
    return generated, "rules"


def set_output(name: str, value: str) -> None:
    output_file = os.getenv("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def run(config: Config, root: Path | None = None) -> bool:
    root = root or repository_root()
    target = root / config.output_file
    old_document = read_document(target)
    snapshot = build_account_snapshot(config)
    generated, mode = _generate(config, snapshot, old_document)

    if not old_document.strip():
        title = snapshot.profile.name or snapshot.profile.login
        old_document = f"# {title}\n"
    new_document = update_document(old_document, config.section_name, generated)
    changed = new_document != old_document
    set_output("changed", str(changed).lower())
    set_output("mode_used", mode)
    set_output("output_file", config.output_file)
    set_output("username", snapshot.profile.login)
    set_output("repositories_analyzed", str(len(snapshot.repositories)))
    set_output("private_contributions", str(snapshot.private_contributions))

    if not changed:
        notice(f"{config.output_file} is already current ({mode} mode)")
        return False

    if config.dry_run:
        diff = difflib.unified_diff(
            old_document.splitlines(),
            new_document.splitlines(),
            fromfile=config.output_file,
            tofile=config.output_file,
            lineterm="",
        )
        print("\n".join(diff))
        notice("Dry run complete; no files were written")
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_document, encoding="utf-8")
    notice(
        f"Updated {config.output_file} for @{snapshot.profile.login} using {mode} mode"
    )

    if config.commit:
        configure_identity(root, config.commit_username, config.commit_email)
        commit_and_push(root, config.output_file, config.commit_message)
        notice(f"Committed and pushed {config.output_file}")
    return True


def main() -> int:
    try:
        config = Config.from_env()
        run(config)
        return 0
    except Exception as exc:
        error(str(exc).replace("\n", "%0A"))
        return 1
