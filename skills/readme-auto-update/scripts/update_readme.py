#!/usr/bin/env python3
"""Safely replace one generated section of a Markdown README."""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path
import re
import sys


def markers(section: str) -> tuple[str, str]:
    return (
        f"<!-- README-AUTO-UPDATE:START:{section} -->",
        f"<!-- README-AUTO-UPDATE:END:{section} -->",
    )


def update(document: str, generated: str, section: str) -> str:
    start, end = markers(section)
    if "<!-- README-AUTO-UPDATE:" in generated:
        raise ValueError("generated content must not contain managed markers")
    if document.count(start) > 1 or document.count(end) > 1:
        raise ValueError("managed markers must occur at most once")
    if (start in document) != (end in document):
        raise ValueError("both managed markers must be present")
    block = f"{start}\n{generated.strip()}\n{end}"
    if start in document:
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
        return pattern.sub(lambda _: block, document, count=1).rstrip() + "\n"
    prefix = document.rstrip() or "# README"
    return f"{prefix}\n\n{block}\n"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="README.md")
    parser.add_argument("--section", default="readme-auto-update")
    parser.add_argument("--content-file", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    options = arguments()
    path = Path(options.file)
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    generated = Path(options.content_file).read_text(encoding="utf-8")
    try:
        after = update(before, generated, options.section)
    except ValueError as exc:
        print(f"update_readme: {exc}", file=sys.stderr)
        return 1
    if options.dry_run:
        print(
            "\n".join(
                difflib.unified_diff(
                    before.splitlines(),
                    after.splitlines(),
                    fromfile=str(path),
                    tofile=str(path),
                    lineterm="",
                )
            )
        )
    elif after != before:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(after, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

