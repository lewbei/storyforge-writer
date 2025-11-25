"""
Project folder management tool.
"""

import os
import re
from typing import Optional

# Root of this repo (two levels up from this file if in tools/)
# Root of this repo (three levels up from this file if in storyforge/tools/)
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_OUTPUT_ROOT = os.path.join(_ROOT_DIR, "output")


# Global variable to track the active project folder
_active_project_folder: Optional[str] = None


def get_output_root() -> str:
    """Return the absolute, canonical output root for all projects.

    This is the only allowed parent directory for project folders.
    """
    return os.path.abspath(_OUTPUT_ROOT)


def is_valid_project_path(path: str) -> bool:
    """Check that the given path is strictly under the output root.

    Uses os.path.commonpath to avoid prefix tricks and enforces that
    the project directory is a descendant of the configured output root.
    """
    if not path:
        return False

    try:
        abs_root = os.path.normcase(get_output_root())
        abs_path = os.path.normcase(os.path.abspath(path))
        common = os.path.commonpath([abs_root, abs_path])
    except Exception:
        return False

    # Must be strictly inside or equal to the root
    return abs_path.startswith(abs_root)


def sanitize_folder_name(name: str) -> str:
    """Sanitize project folder name and reject dangerous input.

    Rules:
    - Strip whitespace
    - Replace spaces/path separators with underscore
    - Allow only [A-Za-z0-9_-]
    - Disallow traversal attempts (e.g., '..')
    """
    raw = (name or "").strip()

    # Replace path separators first for robustness
    raw = raw.replace("/", "_").replace("\\", "_")

    # Basic invalid cases
    if not raw:
        raise ValueError("Invalid project name: empty")
    if ".." in raw:
        raise ValueError("Invalid project name: contains '..'")

    # Normalize spaces (already replaced)
    raw = raw.replace(" ", "_")
    sanitized = re.sub(r"[^\w\-]", "", raw)
    sanitized = sanitized.strip("-_")

    # Final validation
    if not sanitized:
        raise ValueError("Invalid project name: no valid characters after sanitization")
    if sanitized in {".", ".."}:
        raise ValueError("Invalid project name: reserved name")

    return sanitized


def get_active_project_folder() -> Optional[str]:
    """
    Returns the currently active project folder path.
    
    Returns:
        Path to active project folder or None if not set
    """
    return _active_project_folder


def _ensure_output_root() -> None:
    """Ensure the global output root directory exists inside the repo.

    Used by project and writer tools; logs plain-text errors only via return values.
    """
    try:
        os.makedirs(_OUTPUT_ROOT, exist_ok=True)
    except Exception:
        # Let callers report a consistent error message
        raise


def set_active_project_folder(folder_path: str) -> None:
    """Set the active project folder if it is under the validated output root."""
    global _active_project_folder

    if not is_valid_project_path(folder_path):
        raise ValueError("Active project folder must be under the output root directory.")

    _active_project_folder = os.path.abspath(folder_path)


def create_project_impl(project_name: str) -> str:
    """Create or activate a project folder under the output root.

    Behavior:
    - If the folder does not exist, create it and mark as CREATED.
    - If the folder exists and has any markdown files, treat as existing project (EXISTS).
    - If the folder exists and is empty or has no markdown yet, mark as CREATED.
    """
    global _active_project_folder

    try:
        sanitized_name = sanitize_folder_name(project_name)
    except ValueError as e:
        return f"STATUS: ERROR | Invalid project name: {e}"

    try:
        _ensure_output_root()
    except Exception as e:
        return f"STATUS: ERROR | Failed to ensure output directory: {e}"

    output_root = get_output_root()
    project_path = os.path.join(output_root, sanitized_name)

    # Validate resulting path to guard against any unexpected behavior
    if not is_valid_project_path(project_path):
        return "STATUS: ERROR | Computed project path is invalid or outside output root."

    exists_before = os.path.isdir(project_path)

    try:
        os.makedirs(project_path, exist_ok=True)
    except Exception as e:
        return f"STATUS: ERROR | Failed to create project folder: {e}"

    # Only set active project folder after successful creation/verification
    try:
        set_active_project_folder(project_path)
    except ValueError as e:
        return f"STATUS: ERROR | {e}"

    # Auto-initialize Git for safety
    git_msg = ""
    if not os.path.exists(os.path.join(project_path, ".git")):
        git_result = git_init_impl()
        if "SUCCESS" in git_result:
            git_msg = " | Git initialized"
        else:
            git_msg = " | Git init failed"

    # Report whether it already existed with meaningful content or is effectively new
    if os.path.isdir(project_path) and _active_project_folder == project_path:
        has_md = any(
            name.endswith(".md") and not name.startswith(".")
            for name in os.listdir(project_path)
            if os.path.isfile(os.path.join(project_path, name))
        )
        if exists_before and has_md:
            return f"STATUS: EXISTS | Active project: '{project_path}'{git_msg}"
        return f"STATUS: CREATED | Active project: '{project_path}'{git_msg}"

    return f"STATUS: CREATED | Active project: '{project_path}'{git_msg}"


import subprocess


def git_status_impl() -> str:
    """Get Git status summary for active project."""
    folder = get_active_project_folder()
    if not folder:
        return "STATUS: No active project."
    git_dir = os.path.join(folder, '.git')
    if not os.path.exists(git_dir):
        return f"STATUS: No Git repo in '{folder}'. Run 'git init' manually."
    try:
        status = subprocess.check_output(['git', 'status', '--short'], cwd=folder, text=True, stderr=subprocess.STDOUT)
        if not status.strip():
            return f"GIT STATUS (clean): {folder}"
        return f"GIT STATUS:\n{status}"
    except subprocess.CalledProcessError as e:
        return f"GIT ERROR: {e.output.decode() if e.output else str(e)}"
    except Exception as e:
        return f"GIT ERROR: {str(e)}"


def git_commit_impl(message: str) -> str:
    """Git add . and commit with message in active project."""
    folder = get_active_project_folder()
    if not folder:
        return "STATUS: No active project."
    git_dir = os.path.join(folder, '.git')
    if not os.path.exists(git_dir):
        return f"STATUS: No Git repo in '{folder}'. Init first."
    try:
        subprocess.run(['git', 'add', '.'], cwd=folder, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', message], cwd=folder, check=True, capture_output=True)
        return f"SUCCESS: Committed '{message}' in {folder}"
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if e.stderr else e.stdout.decode() if e.stdout else str(e)
        return f"COMMIT ERROR: {err}"
    except Exception as e:
        return f"COMMIT ERROR: {str(e)}"


def git_init_impl() -> str:
    """Initialize a Git repository in the active project folder."""
    folder = get_active_project_folder()
    if not folder:
        return "STATUS: No active project."
    
    git_dir = os.path.join(folder, '.git')
    if os.path.exists(git_dir):
        return f"STATUS: Git repo already exists in '{folder}'"
        
    try:
        subprocess.run(['git', 'init'], cwd=folder, check=True, capture_output=True)
        # Create a default .gitignore if it doesn't exist
        gitignore_path = os.path.join(folder, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write("__pycache__/\n*.pyc\n.env\n")
        return f"SUCCESS: Initialized Git repo in {folder}"
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if e.stderr else str(e)
        return f"INIT ERROR: {err}"
    except Exception as e:
        return f"INIT ERROR: {str(e)}"
