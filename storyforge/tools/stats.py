import os
from pathlib import Path

from . import project


def _get_active_project_dir() -> Path | None:
    try:
        return Path(project.get_active_project_dir())
    except Exception:
        return None


def _count_words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def project_stats_impl() -> str:
    project_dir = _get_active_project_dir()
    if not project_dir or not project_dir.is_dir():
        return "STATUS: WARN | no active project"

    md_files = sorted(project_dir.glob("*.md"))
    if not md_files:
        return "STATUS: WARN | no markdown files"

    file_count = 0
    word_count = 0

    for p in md_files:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        file_count += 1
        word_count += _count_words(text)

    return f"STATUS: OK | files={file_count} | words={word_count}"
