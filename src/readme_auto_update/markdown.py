from __future__ import annotations

from pathlib import Path
import re


def markers(section_name: str) -> tuple[str, str]:
    return (
        f"<!-- README-AUTO-UPDATE:START:{section_name} -->",
        f"<!-- README-AUTO-UPDATE:END:{section_name} -->",
    )


def managed_content(document: str, section_name: str) -> str:
    start, end = markers(section_name)
    pattern = re.compile(re.escape(start) + r"\s*(.*?)\s*" + re.escape(end), re.DOTALL)
    match = pattern.search(document)
    return match.group(1).strip() if match else ""


def update_document(document: str, section_name: str, generated: str) -> str:
    start, end = markers(section_name)
    if "<!-- README-AUTO-UPDATE:" in generated:
        raise ValueError("Generated content must not contain README Auto Update markers")
    if document.count(start) > 1 or document.count(end) > 1:
        raise ValueError("Managed section markers must occur at most once")
    if (start in document) != (end in document):
        raise ValueError("Both managed section markers must be present")

    block = f"{start}\n{generated.strip()}\n{end}"
    if start in document:
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
        return pattern.sub(lambda _: block, document, count=1).rstrip() + "\n"

    prefix = document.rstrip()
    if not prefix:
        prefix = "# GitHub Profile"
    return f"{prefix}\n\n{block}\n"


def read_document(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""
