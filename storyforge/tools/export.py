import os
from pathlib import Path

from . import project


SUPPORTED_FORMATS = {"markdown", "single-md"}


def _get_active_project_dir() -> Path | None:
    try:
        return Path(project.get_active_project_dir())
    except Exception:
        return None


def _collect_markdown_files(project_dir: Path) -> list[Path]:
    return sorted(project_dir.glob("*.md"))


def export_to_format_impl(format: str, include_toc: bool, metadata: dict | None = None) -> str:
    """Export project to a combined markdown file.

    - Supports only "markdown" and "single-md".
    - Writes exports/combined.md inside the active project directory.
    - Optionally includes a very simple TOC (filenames only).
    - For unsupported formats, returns WARN, no side effects.
    """

    fmt = (format or "").lower().strip()

    if fmt not in SUPPORTED_FORMATS:
        return "STATUS: WARN | format not supported in this build"

    project_dir = _get_active_project_dir()
    if not project_dir or not project_dir.is_dir():
        return "STATUS: WARN | no active project"

    md_files = _collect_markdown_files(project_dir)
    if not md_files:
        return "STATUS: WARN | no markdown files to export"

    exports_dir = project_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    combined_path = exports_dir / "combined.md"

    parts: list[str] = []

    if include_toc:
        parts.append("# Table of Contents")
        for p in md_files:
            parts.append(f"- {p.name}")
        parts.append("")

    for p in md_files:
        text = p.read_text(encoding="utf-8")
        parts.append(text)
        if not text.endswith("\n"):
            parts.append("")

    combined_path.write_text("\n".join(parts), encoding="utf-8")

    return f"STATUS: OK | exported={combined_path} | files={len(md_files)}"
