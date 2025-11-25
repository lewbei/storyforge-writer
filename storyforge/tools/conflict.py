import os
from pathlib import Path

from . import project


def _get_active_project_path() -> Path:
    active = project.get_active_project_folder()
    return Path(active) if active else None


def detect_manual_edits_impl() -> str:
    """Minimal heuristic for manual edit detection.

    For Phase 9, this is intentionally conservative and non-intrusive.
    """

    project_path = _get_active_project_path()
    if not project_path or not project_path.exists():
        return "STATUS: SKIP | no_story_bible"

    bible_path = project_path / "story_bible.json"
    if not bible_path.exists():
        return "STATUS: SKIP | no_story_bible"

    return "STATUS: OK | tracking not implemented yet"


def resolve_conflicts_impl() -> str:
    """Placeholder: conflict resolution not yet implemented.

    Exposed for API completeness only.
    """

    return "STATUS: SKIP | not_implemented"