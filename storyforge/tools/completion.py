import json
import os
from pathlib import Path

from . import project


def _get_project_status_path() -> Path | None:
    """Return path to project_status.json for the active project if available."""
    try:
        project_dir = project.get_active_project_dir()
    except Exception:
        project_dir = None

    if not project_dir:
        return None

    status_path = Path(project_dir) / "project_status.json"
    if not status_path.is_file():
        return None
    return status_path


def detect_completion_impl() -> str:
    """Detect whether the novel is complete based on project_status.json.

    Rules (conservative):
    - If chapters_total and chapters_written exist, equal, and > 0: novel_complete=true.
    - Otherwise: novel_complete=false.
    - Always return a clear STATUS line; never raise for missing data.
    """

    status_path = _get_project_status_path()
    if not status_path:
        return "STATUS: OK | novel_complete=false"

    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return "STATUS: OK | novel_complete=false"

    chapters_total = data.get("chapters_total")
    chapters_written = data.get("chapters_written")

    if (
        isinstance(chapters_total, int)
        and isinstance(chapters_written, int)
        and chapters_total > 0
        and chapters_total == chapters_written
    ):
        return f"STATUS: OK | novel_complete=true | chapters={chapters_total}"

    return "STATUS: OK | novel_complete=false"


def generate_epilogue_impl() -> str:
    """Stub for suggesting epilogue generation.

    No heavy logic here; just a structured hint for orchestration layers.
    """

    return "STATUS: OK | EPILOGUE_SUGGESTION_REQUEST"


def create_blurb_impl() -> str:
    """Stub for suggesting blurb creation.

    No heavy logic here; just a structured hint for orchestration layers.
    """

    return "STATUS: OK | BLURB_REQUEST"
