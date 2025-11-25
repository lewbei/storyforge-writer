"""
Critique tool for providing deep editorial feedback on chapters.
"""
import os
from typing import Optional
from .project import get_active_project_folder

def critique_chapter_impl(chapter_filename: str, focus: Optional[str] = None) -> str:
    """
    Analyzes a chapter and provides a structured editorial critique.
    
    Args:
        chapter_filename: The filename of the chapter to critique (e.g., "Chapter 1.md").
        focus: Optional specific focus area (e.g., "pacing", "dialogue", "tone").
        
    Returns:
        A structured critique prompt to be sent to the AI model.
    """
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project."
        
    file_path = os.path.join(project_folder, chapter_filename)
    if not os.path.exists(file_path):
        return f"STATUS: ERROR | File '{chapter_filename}' not found."
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"STATUS: ERROR | Could not read file: {e}"
        
    # Construct the critique prompt
    focus_instruction = ""
    if focus:
        focus_instruction = f"Pay special attention to: {focus}."
        
    prompt = f"""STATUS: OK | CRITIQUE_REQUEST
    
INSTRUCTIONS FOR AI MODEL:
You are a harsh but fair Senior Editor at a top publishing house. Your job is to critique the following chapter.
Do NOT rewrite the chapter. Provide actionable feedback in the following format:

## Overall Impression
(A brief summary of what works and what doesn't)

## Strengths
- (Bullet points of what is effective)

## Weaknesses & Improvements
- **Show, Don't Tell**: (Identify specific instances where the author tells instead of showing)
- **Pacing**: (Is it too slow? Too fast?)
- **Dialogue**: (Is it natural? Does it have subtext?)
- **Plot Holes/Inconsistencies**: (Any logic gaps?)

## Specific Recommendations
(Concrete steps to improve the chapter)

{focus_instruction}

---
CHAPTER CONTENT:
{content}
"""
    return prompt
