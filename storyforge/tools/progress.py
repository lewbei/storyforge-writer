"""Progress tracking helpers for StoryForge AI.

Stores lightweight status in project_status.json inside the active project.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .project import get_active_project_folder


_STATUS_FILENAME = "project_status.json"


def _get_status_path() -> str | None:
    folder = get_active_project_folder()
    if not folder:
        return None
    return os.path.join(folder, _STATUS_FILENAME)


def load_project_status_impl() -> Dict[str, Any]:
    """Load current project status JSON or default if missing/invalid."""
    path = _get_status_path()
    if not path or not os.path.exists(path):
        return {
            "project_name": None,
            "has_analysis_plan": False,
            "analysis_plan_approved": False,
            "chapters_total": 0,
            "chapters_written": 0,
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("status not an object")
        return data
    except Exception:
        return {
            "project_name": None,
            "has_analysis_plan": False,
            "analysis_plan_approved": False,
            "chapters_total": 0,
            "chapters_written": 0,
        }


def save_project_status_impl(status: Dict[str, Any]) -> str:
    """Persist status dictionary to project_status.json.

    Returns a STATUS line for logs.
    """
    path = _get_status_path()
    if not path:
        return "STATUS: ERROR | No active project for saving status."

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
        return "STATUS: OK | project_status.json saved"
    except Exception as e:
        return f"STATUS: ERROR | Failed to save project_status.json: {e}"


def update_status_on_analysis_impl(approved: bool = False) -> str:
    """Mark that analysis/outline exists and optionally approved."""
    status = load_project_status_impl()
    status["has_analysis_plan"] = True
    if approved:
        status["analysis_plan_approved"] = True
    result = save_project_status_impl(status)
    return result


def display_status_summary_impl() -> str:
    """Return human-readable status summary for CLI printing."""
    status = load_project_status_impl()
    name = status.get("project_name") or "(unknown project)"
    has_plan = status.get("has_analysis_plan", False)
    approved = status.get("analysis_plan_approved", False)
    total = status.get("chapters_total", 0) or 0
    written = status.get("chapters_written", 0) or 0

    parts = [f"PROJECT STATUS: {name}"]
    if has_plan:
        parts.append(f"Analysis/outline: {'approved' if approved else 'present'}")
    else:
        parts.append("Analysis/outline: not created yet")

    if total or written:
        parts.append(f"Chapters: {written}/{total}")

    return " | ".join(parts)