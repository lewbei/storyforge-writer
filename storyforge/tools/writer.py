"""
File writing tool for creating and managing markdown files.
"""

import os
from typing import Literal
from .project import get_active_project_folder, get_output_root, is_valid_project_path
from .reader import read_project_files_impl


def write_file_impl(filename: str, content: str, mode: Literal["create", "append", "overwrite", "auto"]) -> str:
    """
    Writes content to a markdown file in the active project folder.
    
    Args:
        filename: The name of the file to write
        content: The content to write
        mode: The write mode - 'create', 'append', or 'overwrite'
        
    Returns:
        Success message or error message
    """
    # Enforce active project invariant
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project. Call create_project first."

    # Enforce project is inside validated output root using helper
    abs_project = os.path.abspath(project_folder)
    if not is_valid_project_path(abs_project):
        return "STATUS: ERROR | Active project folder is invalid or outside output/."

    # Normalize extension early for existence checks
    raw_name = (filename or "").strip()
    if raw_name and not raw_name.endswith(".md"):
        raw_name_check = raw_name + ".md"
    else:
        raw_name_check = raw_name

    target_path_check = os.path.join(abs_project, raw_name_check) if raw_name_check else None

    # Smart behavior:
    # - If mode is 'auto': overwrite if file exists, otherwise create
    # - If mode is 'create' but file already exists: upgrade to overwrite (revision-friendly)
    if mode == "auto":
        if target_path_check and os.path.exists(target_path_check):
            mode = "overwrite"
        else:
            mode = "create"
    elif mode == "create" and target_path_check and os.path.exists(target_path_check):
        mode = "overwrite"
        print(f"INFO: Switching to overwrite mode for existing file: {raw_name_check}")

    # Validate filename
    raw = (filename or "").strip()
    if not raw:
        return "STATUS: ERROR | Invalid filename: empty"
    if os.path.isabs(raw):
        return "STATUS: ERROR | Invalid filename: absolute paths are not allowed"
    # Check for path traversal sequences specifically (allow dots in filenames like "Chapter 1..md")
    if raw.startswith("..") or "/.." in raw or "\\.." in raw:
        return "STATUS: ERROR | Invalid filename: path traversal is not allowed"
    if raw in {".", ".."}:
        return "STATUS: ERROR | Invalid filename: reserved name"

    # Normalize extension
    if not raw.endswith(".md"):
        raw = raw + ".md"

    file_path = os.path.join(abs_project, raw)

    try:
        # Ensure parent directory exists
        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        if mode == "create":
            if os.path.exists(file_path):
                return "STATUS: ERROR | File exists; use append or overwrite."
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"STATUS: CREATED | File: '{raw}' | Chars: {len(content)}"

        if mode == "append":
            if not os.path.exists(file_path):
                return "STATUS: ERROR | Cannot append; file does not exist."
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content)
            return f"STATUS: APPENDED | File: '{raw}' | Chars: {len(content)}"

        if mode == "overwrite":
            if not os.path.exists(file_path):
                return "STATUS: ERROR | Cannot overwrite; file does not exist."
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"STATUS: OVERWRITTEN | File: '{raw}' | Chars: {len(content)}"

        return "STATUS: ERROR | Invalid mode. Use create, append, overwrite, or auto."

    except Exception as e:
        return f"STATUS: ERROR | Failed writing '{raw}': {e}"


def write_episode_impl(episode_number: int, content: str) -> str:
    """
    Writes content to an episode file with enforced naming: Episode_01.md, Episode_02.md, etc.

    Args:
        episode_number: The episode number (1, 2, 3, ...)
        content: The episode content to write

    Returns:
        Success message or error message
    """
    # Validate episode number
    if not isinstance(episode_number, int) or episode_number < 1:
        return "STATUS: ERROR | Invalid episode_number: must be a positive integer"

    # Format filename with zero-padding: Episode_01.md, Episode_02.md, etc.
    filename = f"Episode_{episode_number:02d}.md"

    # Use write_file_impl with auto mode (create or overwrite)
    result = write_file_impl(filename, content, mode="auto")

    # Enhance the result message to indicate this was an episode
    if "CREATED" in result or "OVERWRITTEN" in result:
        return result.replace("File:", f"Episode {episode_number}:")
    return result


def write_chapter_impl(chapter_number: int, content: str) -> str:
    """
    Writes content to a chapter file with enforced naming: Chapter_01.md, Chapter_02.md, etc.

    Args:
        chapter_number: The chapter number (1, 2, 3, ...)
        content: The chapter content to write

    Returns:
        Success message or error message
    """
    # Validate chapter number
    if not isinstance(chapter_number, int) or chapter_number < 1:
        return "STATUS: ERROR | Invalid chapter_number: must be a positive integer"

    # Format filename with zero-padding: Chapter_01.md, Chapter_02.md, etc.
    filename = f"Chapter_{chapter_number:02d}.md"

    # Use write_file_impl with auto mode (create or overwrite)
    result = write_file_impl(filename, content, mode="auto")

    # Enhance the result message to indicate this was a chapter
    if "CREATED" in result or "OVERWRITTEN" in result:
        return result.replace("File:", f"Chapter {chapter_number}:")
    return result


def analyze_project_characters_impl() -> str:
    """Analyze existing project files and extract a structured character index."""
    # Check if project exists but don't load all content (too large)
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project. Call create_project first."
    
    # Count files to give context
    import os
    md_files = [f for f in os.listdir(project_folder) if f.endswith('.md')]
    
    instruction = f"""STATUS: OK | ANALYZE_CHARACTERS | Project has {len(md_files)} markdown files.

INSTRUCTIONS:
1. Use read_project_files with empty list to load ALL files (or specify key files like analysis_plan.md, story_bible.md, and 2-3 sample chapters)
2. Analyze characters: names, roles, traits, relationships, character arcs
3. Save the complete character analysis to 'character_analysis.md' using write_file
4. Present a brief summary to the user (do NOT repeat full analysis in response)
5. Ask: "I've saved the character analysis. Would you like me to continue with world analysis, or would you like to review this first?"

CRITICAL WARNING: DO NOT say "task completed" or "completed in" or exit. WAIT for user response.
FORBIDDEN: Never write "Task completed" - the system will exit if you do!

Note: Keep your analysis response concise. The full details are in the saved file.
"""
    return instruction


def analyze_project_world_impl() -> str:
    """Analyze existing project files and extract a structured world-building summary."""
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project. Call create_project first."
    
    import os
    md_files = [f for f in os.listdir(project_folder) if f.endswith('.md')]
    
    instruction = f"""STATUS: OK | ANALYZE_WORLD | Project has {len(md_files)} markdown files.

INSTRUCTIONS:
1. Use read_project_files with specific files (analysis_plan.md, story_bible.md, and 2-3 sample chapters)
2. Analyze world-building: locations, cultures, factions, magic/tech systems, rules, tone, constraints
3. Save the complete world analysis to 'world_analysis.md' using write_file
4. Present a brief summary to the user (do NOT repeat full analysis in response)
5. Ask: "I've saved the world analysis. Would you like me to continue with plot analysis, or would you like to review this first?"

CRITICAL WARNING: DO NOT say "task completed" or "completed in" or exit. WAIT for user response.
FORBIDDEN: Never write "Task completed" - the system will exit if you do!

Note: Keep your analysis response concise. The full details are in the saved file.
"""
    return instruction


def analyze_project_plot_impl() -> str:
    """Analyze existing project files and extract plot timeline and open threads."""
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project. Call create_project first."
    
    import os
    md_files = [f for f in os.listdir(project_folder) if f.endswith('.md')]
    chapter_files = [f for f in md_files if f.lower().startswith('chapter')]
    
    instruction = f"""STATUS: OK | ANALYZE_PLOT | Project has {len(md_files)} files, including {len(chapter_files)} chapter files.

INSTRUCTIONS:
1. Use read_project_files to load key files in batches (don't load all at once if there are many chapters)
2. Build a chapter-by-chapter timeline with key events, stakes, and unresolved threads
3. Save the complete plot analysis to 'plot_analysis.md' using write_file
4. Present a brief summary to the user (do NOT repeat full timeline in response)
5. Ask: "I've saved the plot analysis. Would you like me to create a continuation outline, or would you like to review the analyses first?"

CRITICAL WARNING: DO NOT say "task completed" or "completed in" or exit. WAIT for user response.
FORBIDDEN: Never write "Task completed" - the system will exit if you do!

Note: Keep your analysis response concise. The full details are in the saved file.
"""
    return instruction


def propose_continuation_outline_impl() -> str:
    """Prepare the agent to propose a continuation outline based on existing content."""
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project. Call create_project first."
    
    import os
    md_files = [f for f in os.listdir(project_folder) if f.endswith('.md')]
    chapter_files = [f for f in md_files if f.lower().startswith('chapter')]
    
    instruction = f"""STATUS: OK | PROPOSE_CONTINUATION_OUTLINE | Project has {len(md_files)} files, {len(chapter_files)} chapters.

INSTRUCTIONS:
1. First use validate_project_setup to check if analysis_plan.md has proper foundation
2. Read the most recent 3-5 chapters to understand current narrative state (use read_project_files with specific filenames)
3. Use check_completeness to validate existing chapters against masterpiece standards
4. Draft a detailed continuation plan addressing any quality gaps or missing elements
5. Save the continuation outline to 'continuation_outline.md' using write_file
6. Present a summary with key recommendations (do NOT repeat full outline in response)
7. Ask: "I've saved the continuation outline. Would you like me to start writing the next chapter, or do you want to review/revise the plan first?"

CRITICAL WARNING: DO NOT say "task completed" or "completed in" or exit. WAIT for user response.
FORBIDDEN: Never write "Task completed" - the system will exit if you do!

Note: Work in batches to avoid token limits. Keep your response concise.
"""
    return instruction

    return instruction


def prepare_scene_impl(chapter_title: str, setting: str, characters: str, plot_goal: str) -> str:
    """
    Creates a Scene Card to ensure context awareness before drafting.
    """
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project."
        
    # Create scene_cards directory
    cards_dir = os.path.join(project_folder, "scene_cards")
    if not os.path.exists(cards_dir):
        os.makedirs(cards_dir)
        
    # Sanitize filename
    safe_title = "".join(c for c in chapter_title if c.isalnum() or c in (' ', '-', '_')).strip()
    filename = f"scene_{safe_title}.md"
    file_path = os.path.join(cards_dir, filename)
    
    content = f"""# Scene Card: {chapter_title}

## Setting
{setting}

## Characters
{characters}

## Plot Goal
{plot_goal}

## Status
Prepared
"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"STATUS: OK | Scene Card saved to {filename}. You may now proceed to draft."
    except Exception as e:
        return f"STATUS: ERROR | Failed to save scene card: {e}"
