import os
import re
from typing import List, Optional
from .project import get_active_project_folder
from .bible import read_project_bible

def summarize_chapter(file_path: str, client, model: str) -> str:
    """
    Summarizes a chapter file using the LLM.
    Saves the summary to a .summary file alongside the original.
    """
    if not os.path.exists(file_path):
        return f"Error: File {file_path} not found."
    
    # Check if summary already exists and is newer
    summary_path = file_path.replace(".md", ".summary.md")
    if os.path.exists(summary_path):
        if os.path.getmtime(summary_path) > os.path.getmtime(file_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                return f.read()

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    prompt = f"""TASK: Summarize the following chapter in 200-300 words.
    
    FOCUS ON:
    - Key plot events (what actually happened).
    - Character emotional shifts.
    - New information revealed.
    - Unresolved hooks/cliffhangers. 
    
    TEXT:
    {content[:15000]}  # Truncate to avoid token overflow
    """
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500
        )
        summary = response.choices[0].message.content
        
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
            
        return summary
    except Exception as e:
        return f"Error generating summary: {e}"

def get_rolling_context(client, model: str) -> str:
    """
    Assembles the "Rolling Context" for the AI.
    Includes:
    1. Project Bible (Static)
    2. Character/World Analysis (Static)
    3. Summaries of the last 3 chapters (Dynamic)
    4. Current Plan/Beat Sheet (Immediate)
    """
    project_folder = get_active_project_folder()
    if not project_folder:
        return ""

    context_parts = []

    # 1. Project Bible
    bible = read_project_bible(project_folder)
    if bible:
        context_parts.append(f"## PROJECT BIBLE\n{bible}")

    # 2. Analyses
    for analysis_file in ["character_analysis.md", "world_analysis.md"]:
        path = os.path.join(project_folder, analysis_file)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                # Truncate if too long? For now, assume analyses are concise.
                context_parts.append(f"## {analysis_file.upper()}\n{content[:2000]}...") 

    # 3. Recent Chapter Summaries
    # Find all chapter files
    files = os.listdir(project_folder)
    chapter_files = sorted([f for f in files if f.lower().startswith("chapter") and f.endswith(".md")])
    
    recent_chapters = chapter_files[-3:] # Last 3
    if recent_chapters:
        summaries = []
        for ch_file in recent_chapters:
            full_path = os.path.join(project_folder, ch_file)
            summary = summarize_chapter(full_path, client, model)
            summaries.append(f"**{ch_file}**: {summary}")
        
        context_parts.append("## PREVIOUSLY ON...\n" + "\n\n".join(summaries))

    # 4. Active Plan (Check for most recent beat sheet)
    plans_dir = os.path.join(project_folder, "plans")
    if os.path.exists(plans_dir):
        beat_sheets = sorted([f for f in os.listdir(plans_dir) if f.startswith("beats_")])
        if beat_sheets:
            latest_beat_sheet = beat_sheets[-1]
            with open(os.path.join(plans_dir, latest_beat_sheet), "r", encoding="utf-8") as f:
                beats = f.read()
                context_parts.append(f"## CURRENT BEAT SHEET ({latest_beat_sheet})\n{beats}")

    return "\n\n".join(context_parts)
