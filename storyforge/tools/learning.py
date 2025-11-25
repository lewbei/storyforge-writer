import json
import os
from pathlib import Path
from typing import Any, Dict


def _preferences_path() -> Path:
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or str(Path.home())
    base = Path(home) / ".storyforge"
    base.mkdir(parents=True, exist_ok=True)
    return base / "user_preferences.json"


def load_preferences_impl() -> Dict[str, Any]:
    path = _preferences_path()
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_preferences_impl(prefs: Dict[str, Any]) -> str:
    path = _preferences_path()
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
        return "STATUS: OK | preferences_saved"
    except Exception as exc:
        return f"STATUS: ERROR | {exc}"


def track_revision_patterns_impl(feedback_type: str) -> str:
    prefs = load_preferences_impl()
    rev = prefs.setdefault("revision_patterns", {})
    current = rev.get(feedback_type, 0)
    try:
        current = int(current)
    except Exception:
        current = 0
    rev[feedback_type] = current + 1

    status = save_preferences_impl(prefs)
    if status.startswith("STATUS: OK"):
        return "STATUS: OK | tracked"
    return status
