import os
from typing import Optional
from .templates import get_genre_structure
from .project import get_active_project_folder

def get_beat_sheet_template(genre: str) -> str:
    """
    Retrieves the beat sheet model for a specific genre.
    """
    structure = get_genre_structure(genre)
    if not structure:
        return f"STATUS: ERROR | Genre '{genre}' not found. Available: romance, fantasy, mystery, thriller."
    
    beats = structure.get("beat_sheet_model", [])
    return "\n".join(beats)

def save_beat_sheet(chapter_title: str, content: str) -> str:
    """
    Saves a beat sheet to the 'plans' directory in the active project.
    """
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project."
    
    # Create plans directory
    plans_dir = os.path.join(project_folder, "plans")
    if not os.path.exists(plans_dir):
        os.makedirs(plans_dir)
    
    # Sanitize filename
    safe_title = "".join(c for c in chapter_title if c.isalnum() or c in (' ', '-', '_')).strip()
    filename = f"beats_{safe_title}.md"
    file_path = os.path.join(plans_dir, filename)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"STATUS: OK | Beat sheet saved to {file_path}"
    except Exception as e:
        return f"STATUS: ERROR | Failed to save beat sheet: {e}"

def generate_chapter_plan_prompt(chapter_title: str, summary: str, genre: str) -> str:
    """
    Generates a prompt for the Agent to use when creating beats.
    This doesn't call the LLM, but returns the text the Agent should 'think' about.
    """
    structure = get_genre_structure(genre)
    if not structure:
        return f"STATUS: ERROR | Genre '{genre}' not found."
        
    beats_template = "\n".join(structure.get("beat_sheet_model", []))
    
    prompt = f"""TASK: Create a detailed Beat Sheet for '{chapter_title}'.

CONTEXT:
Genre: {genre}
Chapter Summary: {summary}

TEMPLATE ({genre}):
{beats_template}

INSTRUCTIONS:
1. Break the summary down into specific scenes or moments corresponding to the beat template.
2. Ensure each beat advances the plot or character arc.
3. Output the result as a structured Markdown list.
4. Use 'save_beat_sheet' to save the result.
"""
    return prompt
