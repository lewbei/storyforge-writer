import os

from .project import get_active_project_folder, is_valid_project_path


def request_revision_impl(chapter_file: str, feedback_type: str, note: str = "") -> str:
    """Return a structured revision request message.

    - Ensures the chapter file is inside the active project folder.
    - Does not modify files; orchestrator/LLM will handle actual edits.
    """
    active_root = get_active_project_folder()
    if not active_root:
        return "STATUS: ERROR | message=no active project"

    chapter_path = os.path.abspath(chapter_file)
    root_path = os.path.abspath(active_root)

    # Ensure chapter is inside active project folder; rely on configured active root
    if not chapter_path.startswith(root_path + os.sep):
        return "STATUS: ERROR | message=chapter_file is outside active project"

    # Basic normalization
    feedback_type = (feedback_type or "").strip()
    note = (note or "").strip()

    if not feedback_type:
        return "STATUS: ERROR | message=feedback_type is required"

    return (
        "STATUS: OK | REVISION_REQUEST | "
        f"chapter={chapter_path} | feedback_type={feedback_type} | note={note}"
    )
