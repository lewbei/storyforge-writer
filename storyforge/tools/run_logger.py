"""Run logging utilities for the StoryForge AI Agent.

Plain-text, per-project logging with concise single-line or short multi-line entries.
"""

import os
import time
from typing import Optional
from .project import get_active_project_folder


_LOG_FILE_NAME = "run.log"


def _get_log_path() -> Optional[str]:
    """Return the current project's run.log path, or None if no active project.

    Logging silently no-ops when no active project folder is set yet.
    """
    project = get_active_project_folder()
    if not project:
        return None
    return os.path.join(project, _LOG_FILE_NAME)


_MAX_LOG_SIZE = 1024 * 1024  # 1MB
_BACKUP_COUNT = 3

def _rotate_log_if_needed(path: str) -> None:
    """Rotate log file if it exceeds max size."""
    try:
        if not os.path.exists(path):
            return
            
        if os.path.getsize(path) < _MAX_LOG_SIZE:
            return
            
        # Rotate
        for i in range(_BACKUP_COUNT - 1, 0, -1):
            sfn = f"{path}.{i}"
            dfn = f"{path}.{i+1}"
            if os.path.exists(sfn):
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(sfn, dfn)
        
        dfn = f"{path}.1"
        if os.path.exists(dfn):
            os.remove(dfn)
        os.rename(path, dfn)
        
    except Exception:
        # Fail silently on rotation errors to avoid crashing app
        pass

def log_event(message: str) -> None:
    """Append a single log line to the current project's run.log.

    Format: "YYYY-MM-DD HH:MM:SS | LEVEL | message"
    The caller is responsible for keeping `message` concise and plain text.
    """
    path = _get_log_path()
    if not path:
        return

    _rotate_log_if_needed(path)

    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    line = f"{ts} | INFO | {message.strip()}".rstrip() + "\n"

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # Logging must never break the agent.
        return


def log_error(message: str) -> None:
    """Append an error line to run.log using the same format with LEVEL=ERROR."""
    path = _get_log_path()
    if not path:
        return

    _rotate_log_if_needed(path)

    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    line = f"{ts} | ERROR | {message.strip()}".rstrip() + "\n"

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        return


def log_summary(status: str, iterations: int, details: str = "") -> None:
    """Append a final run summary line.

    status: short code like "COMPLETED", "INTERRUPTED", "MAX_ITERATIONS", "ERROR".
    details: short plain-text explanation.
    """
    message = f"Run summary | status={status} | iterations={iterations}"
    if details:
        message += f" | {details.strip()}"
    log_event(message)
