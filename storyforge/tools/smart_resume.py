"""
Smart resume functionality for StoryForge AI.

Provides context-aware project resumption with suggestions.
"""

import os
import json
import glob
from datetime import datetime
from typing import Dict, List, Optional, Tuple


def get_last_actions(project_path: str, count: int = 3) -> List[str]:
    """
    Get the last N actions from run.log.
    
    Args:
        project_path: Path to project folder
        count: Number of recent actions to retrieve
        
    Returns:
        List of recent action strings
    """
    log_file = os.path.join(project_path, "run.log")
    actions = []
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Get last N non-empty lines
                for line in reversed(lines):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        actions.append(line)
                        if len(actions) >= count:
                            break
                actions.reverse()
        except:
            pass
    
    return actions


def get_project_completion_status(project_path: str) -> Dict:
    """
    Analyze project completion status.
    
    Args:
        project_path: Path to project folder
        
    Returns:
        Dictionary with completion metrics
    """
    status = {
        "has_plot": False,
        "has_characters": False,
        "has_world": False,
        "has_outline": False,
        "chapters_count": 0,
        "completion_percent": 0,
        "next_suggested_action": None,
    }
    
    try:
        # Check analysis files
        status["has_plot"] = os.path.exists(os.path.join(project_path, "plot_analysis.md"))
        status["has_characters"] = os.path.exists(os.path.join(project_path, "character_analysis.md"))
        status["has_world"] = os.path.exists(os.path.join(project_path, "world_analysis.md"))
        status["has_outline"] = os.path.exists(os.path.join(project_path, "continuation_outline.md"))
        
        # Count chapters
        files = os.listdir(project_path)
        chapters = [f for f in files if f.startswith("Chapter") and f.endswith(".md")]
        status["chapters_count"] = len(chapters)
        
        # Calculate completion
        analysis_complete = sum([status["has_plot"], status["has_characters"], status["has_world"], status["has_outline"]])
        status["completion_percent"] = int((analysis_complete / 4) * 50 + (min(status["chapters_count"], 10) / 10) * 50)
        
        # Suggest next action
        if not status["has_plot"]:
            status["next_suggested_action"] = "Analyze the plot structure and themes"
        elif not status["has_characters"]:
            status["next_suggested_action"] = "Develop character profiles and arcs"
        elif not status["has_world"]:
            status["next_suggested_action"] = "Build the world setting and rules"
        elif status["chapters_count"] == 0:
            status["next_suggested_action"] = "Start writing Chapter 1"
        elif not status["has_outline"]:
            status["next_suggested_action"] = "Create continuation outline for remaining chapters"
        else:
            # Find next chapter to write
            chapter_nums = []
            for ch in chapters:
                try:
                    # Extract chapter number
                    num_part = ch.split(".")[0].replace("Chapter", "").strip()
                    if num_part.isdigit():
                        chapter_nums.append(int(num_part))
                except:
                    pass
            if chapter_nums:
                next_chapter = max(chapter_nums) + 1
                status["next_suggested_action"] = f"Continue with Chapter {next_chapter}"
            else:
                status["next_suggested_action"] = "Review and revise existing chapters"
    
    except Exception as e:
        print(f"Warning: Could not analyze completion status: {e}")
    
    return status


def get_resume_summary(project_path: str) -> str:
    """
    Generate a resume summary for display.
    
    Args:
        project_path: Path to project folder
        
    Returns:
        Formatted summary string
    """
    summary = []
    
    # Get last actions
    actions = get_last_actions(project_path, 3)
    if actions:
        summary.append("Recent Activity:")
        for action in actions:
            summary.append(f"  - {action[:80]}")
    
    # Get completion status
    status = get_project_completion_status(project_path)
    summary.append(f"\nProgress: {status['completion_percent']}%")
    summary.append(f"Chapters: {status['chapters_count']}")
    
    # Analysis checklist
    analysis = []
    if status["has_plot"]:
        analysis.append("[x] Plot")
    if status["has_characters"]:
        analysis.append("[x] Characters")
    if status["has_world"]:
        analysis.append("[x] World")
    if status["has_outline"]:
        analysis.append("[x] Outline")
    
    if analysis:
        summary.append(f"\nAnalysis: {', '.join(analysis)}")
    
    # Next suggestion
    if status["next_suggested_action"]:
        summary.append(f"\nSuggested: {status['next_suggested_action']}")
    
    return "\n".join(summary)


def should_auto_resume(project_path: str) -> bool:
    """
    Determine if project should auto-resume (has context less than 1 hour old).
    
    Args:
        project_path: Path to project folder
        
    Returns:
        True if should auto-resume
    """
    try:
        context_files = glob.glob(os.path.join(project_path, ".context_summary_*.md"))
        if context_files:
            latest = max(context_files, key=os.path.getmtime)
            mtime = os.path.getmtime(latest)
            age_hours = (datetime.now().timestamp() - mtime) / 3600
            return age_hours < 1.0  # Less than 1 hour old
    except:
        pass
    return False
