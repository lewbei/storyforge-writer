"""
UI helper functions for StoryForge AI interactive CLI.

Provides project browsing, metadata collection, and Rich UI components.
"""

import os
import json
import glob
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

CHAT_HELP_COMMANDS: List[Tuple[str, str]] = [
    ("/status", "Show project statistics and progress"),
    ("/save", "Manually save conversation context"),
    ("/resume", "Load last saved conversation context for current project"),
    ("/new", "Start a fresh conversation (clears context)"),
    ("/projects", "List all available projects"),
    ("/switch", "Switch to a different project"),
    ("/files", "List files in the current project"),
    ("/troubleshoot", "Show troubleshooting tips and common fixes"),
    ("/exit", "Exit chat mode"),
]


def get_project_metadata(project_path: str) -> Dict:
    """
    Extract metadata from a project folder.
    
    Args:
        project_path: Absolute path to project folder
        
    Returns:
        Dictionary with project metadata
    """
    metadata = {
        "name": os.path.basename(project_path),
        "path": project_path,
        "chapter_count": 0,
        "total_files": 0,
        "word_count": 0,
        "last_modified": None,
        "status": "Unknown",
        "has_context": False,
    }
    
    try:
        # Count files
        all_files = [f for f in os.listdir(project_path) if os.path.isfile(os.path.join(project_path, f))]
        metadata["total_files"] = len(all_files)
        
        # Count chapters (files starting with "Chapter")
        chapters = [f for f in all_files if f.startswith("Chapter") and f.endswith(".md")]
        metadata["chapter_count"] = len(chapters)
        
        # Calculate total word count from markdown files
        total_words = 0
        for file in all_files:
            if file.endswith(".md") and not file.startswith("."):
                file_path = os.path.join(project_path, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        words = len(content.split())
                        total_words += words
                except:
                    pass
        metadata["word_count"] = total_words
        
        # Get last modified time
        mtime = os.path.getmtime(project_path)
        metadata["last_modified"] = datetime.fromtimestamp(mtime)
        
        # Check for context summaries
        context_files = glob.glob(os.path.join(project_path, ".context_summary_*.md"))
        metadata["has_context"] = len(context_files) > 0
        
        # Load status from project_status.json if exists
        status_file = os.path.join(project_path, "project_status.json")
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                    metadata["status"] = status_data.get("status", "In Progress")
            except:
                metadata["status"] = "In Progress"
        else:
            metadata["status"] = "Active" if metadata["has_context"] else "New"
            
        metadata["settings"] = get_bible_settings(project_path)
    
    except Exception as e:
        print(f"Warning: Could not read metadata for {project_path}: {e}")
    
    return metadata


def get_bible_settings(project_path: str) -> Dict[str, str]:
    """
    Extracts Genre, Tone, and Theme from the project's bible.md or analysis_plan.md.
    """
    settings = {"Genre": "Unknown", "Tone": "Unknown", "Theme": "Unknown"}
    
    # Helper to parse content
    def parse_content(text: str, current_settings: Dict[str, str]):
        import re
        # Genre
        if current_settings["Genre"] == "Unknown":
            m = re.search(r"(?:\*\*|# |^)?Genre(?:\*\*|:)?\s*:?\s*\[?([^\]\n]+)", text, re.IGNORECASE | re.MULTILINE)
            if m: current_settings["Genre"] = m.group(1).strip()
            
        # Tone
        if current_settings["Tone"] == "Unknown":
            m = re.search(r"(?:\*\*|# |^)?(?:Mood/)?Tone(?:\*\*|:)?\s*:?\s*\[?([^\]\n]+)", text, re.IGNORECASE | re.MULTILINE)
            if m: current_settings["Tone"] = m.group(1).strip()
            
        # Theme
        if current_settings["Theme"] == "Unknown":
            m = re.search(r"(?:\*\*|# |^)?(?:Core )?Themes?(?:\*\*|:)?\s*:?\s*\[?([^\]\n]+)", text, re.IGNORECASE | re.MULTILINE)
            if m: current_settings["Theme"] = m.group(1).strip()

    # Try bible.md first
    bible_path = os.path.join(project_path, "bible.md")
    if os.path.exists(bible_path):
        try:
            with open(bible_path, 'r', encoding='utf-8') as f:
                parse_content(f.read(), settings)
        except Exception:
            pass

    # Fallback to analysis_plan.md
    plan_path = os.path.join(project_path, "analysis_plan.md")
    if os.path.exists(plan_path):
        try:
            with open(plan_path, 'r', encoding='utf-8') as f:
                parse_content(f.read(), settings)
        except Exception:
            pass
            
    return settings


def list_all_projects(output_root: str) -> List[Dict]:
    """
    List all projects with their metadata.
    
    Args:
        output_root: Path to output directory
        
    Returns:
        List of project metadata dictionaries, sorted by last modified (newest first)
    """
    projects = []
    
    if not os.path.exists(output_root):
        return projects
    
    try:
        for item in os.listdir(output_root):
            item_path = os.path.join(output_root, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                metadata = get_project_metadata(item_path)
                projects.append(metadata)
    except Exception as e:
        print(f"Error listing projects: {e}")
    
    # Sort by last modified (newest first), then name (alphabetical)
    projects.sort(key=lambda p: (p["last_modified"] or datetime.min, p["name"]), reverse=True)
    
    return projects


def display_projects_table(console: Console, projects: List[Dict]) -> None:
    """
    Display projects in a Rich table.
    
    Args:
        console: Rich Console instance
        projects: List of project metadata
    """
    table = Table(title="Your Projects", show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", width=4, justify="right")
    table.add_column("Name", style="bold green", width=20)
    table.add_column("Chapters", justify="right", width=10)
    table.add_column("Words", justify="right", width=10)
    table.add_column("Last Modified", width=18)
    table.add_column("Status", width=12)
    
    for idx, proj in enumerate(projects, 1):
        # Format last modified
        if proj["last_modified"]:
            now = datetime.now()
            diff = now - proj["last_modified"]
            if diff.days == 0:
                if diff.seconds < 3600:
                    time_str = f"{diff.seconds // 60}m ago"
                else:
                    time_str = f"{diff.seconds // 3600}h ago"
            elif diff.days == 1:
                time_str = "Yesterday"
            elif diff.days < 7:
                time_str = f"{diff.days}d ago"
            else:
                time_str = proj["last_modified"].strftime("%Y-%m-%d")
        else:
            time_str = "Unknown"
        
        # Format word count
        word_count = proj["word_count"]
        if word_count >= 1000:
            words_str = f"{word_count / 1000:.1f}K"
        else:
            words_str = str(word_count)
        
        # Status with emoji
        status = proj["status"]
        if status == "Active":
            status_display = "Active"
        elif status == "New":
            status_display = "New"
        elif status == "Complete":
            status_display = "Complete"
        else:
            status_display = f"{status}"
        
        table.add_row(
            str(idx),
            proj["name"],
            str(proj["chapter_count"]),
            words_str,
            time_str,
            status_display
        )
    
    console.print(table)


def get_project_preview(project_path: str, max_lines: int = 10) -> str:
    """
    Get a preview of the project (first few lines of first chapter or README).
    
    Args:
        project_path: Path to project
        max_lines: Maximum lines to show
        
    Returns:
        Preview text
    """
    preview = ""
    
    # Try to find first chapter
    try:
        files = os.listdir(project_path)
        chapters = sorted([f for f in files if f.startswith("Chapter") and f.endswith(".md")])
        
        preview_file = None
        if chapters:
            preview_file = os.path.join(project_path, chapters[0])
        elif "README.md" in files:
            preview_file = os.path.join(project_path, "README.md")
        elif any(f.endswith(".md") for f in files):
            md_files = [f for f in files if f.endswith(".md") and not f.startswith(".")]
            if md_files:
                preview_file = os.path.join(project_path, md_files[0])
        
        if preview_file:
            with open(preview_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:max_lines]
                preview = "".join(lines)
                if len(f.readlines()) > max_lines:
                    preview += "\n... (more content available)"
    except Exception as e:
        preview = f"Unable to load preview: {e}"

    if not preview:
        preview = "Unable to load preview: no markdown chapter or README files found"
    
    return preview


def display_project_preview(console: Console, project: Dict) -> None:
    """
    Display detailed preview of a project.
    
    Args:
        console: Rich Console instance
        project: Project metadata dict
    """
    preview_text = get_project_preview(project["path"])
    
    info_text = Text()
    info_text.append(f"Project: {project['name']}\n", style="bold cyan")
    info_text.append(f"Progress: Chapters: {project['chapter_count']} | ", style="dim")
    info_text.append(f"Files: {project['total_files']} | ", style="dim")
    info_text.append(f"Words: {project['word_count']:,}\n", style="dim")
    info_text.append(f"Modified: {project['last_modified'].strftime('%Y-%m-%d %H:%M') if project['last_modified'] else 'Unknown'}\n", style="dim")
    info_text.append(f"\n{preview_text[:500]}", style="green")
    
    panel = Panel(info_text, title="Project Preview", border_style="blue")
    console.print(panel)


def format_time_ago(dt: datetime) -> str:
    """Format datetime as 'X time ago' string."""
    now = datetime.now()
    diff = now - dt
    
    if diff.days == 0:
        if diff.seconds < 60:
            return "Just now"
        elif diff.seconds < 3600:
            return f"{diff.seconds // 60} minutes ago"
        else:
            return f"{diff.seconds // 3600} hours ago"
    elif diff.days == 1:
        return "Yesterday"
    elif diff.days < 7:
        return f"{diff.days} days ago"
    elif diff.days < 30:
        return f"{diff.days // 7} weeks ago"
    else:
        return dt.strftime("%B %d, %Y")


def get_project_tips() -> List[str]:
    """Get random tips for users."""
    return [
        "Tip: Use /help in chat to see all available commands",
        "Tip: Press Ctrl+C to interrupt long-running operations",
        "Tip: Context is automatically saved every 50 iterations",
        "Tip: Use /save to manually save your progress",
        "Tip: Chapter files support full markdown formatting",
        "Tip: Use /status to see project statistics anytime",
        "Tip: Projects are stored in the 'output/' folder",
        "Tip: Use /export to save conversation history",
    ]


def display_dashboard_impl(console: Console, project_path: str) -> None:
    """
    Display a rich dashboard for the active project.
    """
    from rich.layout import Layout
    
    metadata = get_project_metadata(project_path)
    
    # Check for small terminal size and fallback to simple view
    # Height < 15 is critical because split layout needs at least ~10 lines to render cleanly
    if console.size.width < 60 or console.size.height < 15:
        console.print(Panel(Text(f"Dashboard: {metadata['name']}", style="bold white"), style="blue"))
        
        stats_text = Text()
        stats_text.append(f"Chapters: {metadata['chapter_count']} | Files: {metadata['total_files']}\n", style="cyan")
        word_fmt = f"{metadata['word_count']:,}"
        stats_text.append(f"Words: {word_fmt}\n", style="green")
        stats_text.append(f"Status: {metadata['status']}\n\n", style="yellow")
        
        settings = metadata.get("settings", {})
        stats_text.append("Settings:\n", style="bold white")
        stats_text.append(f"Genre: {settings.get('Genre', 'Unknown')}\n", style="blue")
        stats_text.append(f"Tone: {settings.get('Tone', 'Unknown')}\n", style="magenta")
        stats_text.append(f"Theme: {settings.get('Theme', 'Unknown')}\n", style="dim")
        
        console.print(Panel(stats_text, title="Statistics", border_style="green"))
        
        activity_text = Text()
        last_mod = metadata.get('last_modified')
        mod_str = format_time_ago(last_mod) if last_mod else "Unknown"
        activity_text.append(f"Last Modified: {mod_str}\n", style="dim")
        console.print(Panel(activity_text, title="Activity", border_style="magenta"))
        return

    try:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="stats"),
            Layout(name="activity")
        )
        
        # Header
        layout["header"].update(Panel(Text(f"Dashboard: {metadata['name']}", style="bold white"), style="blue"))
        
        # Stats
        stats_text = Text()
        stats_text.append(f"Chapters: {metadata['chapter_count']}\n", style="cyan")
        stats_text.append(f"Files: {metadata['total_files']}\n", style="cyan")
        word_fmt = f"{metadata['word_count']:,}"
        stats_text.append(f"Words: {word_fmt}\n", style="green")
        stats_text.append(f"Status: {metadata['status']}\n\n", style="yellow")
        
        settings = metadata.get("settings", {})
        stats_text.append("Settings:\n", style="bold white")
        stats_text.append(f"Genre: {settings.get('Genre', 'Unknown')}\n", style="blue")
        stats_text.append(f"Tone: {settings.get('Tone', 'Unknown')}\n", style="magenta")
        stats_text.append(f"Theme: {settings.get('Theme', 'Unknown')}\n", style="dim")
        
        layout["stats"].update(Panel(stats_text, title="Statistics", border_style="green"))
        
        # Activity
        activity_text = Text()
        last_mod = metadata.get('last_modified')
        if last_mod:
            activity_text.append(f"Last Modified: {format_time_ago(last_mod)}\n\n", style="dim")
        else:
            activity_text.append("Last Modified: Unknown\n\n", style="dim")
        
        # Try to read recent scene cards
        scene_cards_dir = os.path.join(project_path, "scene_cards")
        if os.path.exists(scene_cards_dir):
            cards = [f for f in os.listdir(scene_cards_dir) if f.endswith(".md")]
            activity_text.append(f"Scene Cards: {len(cards)} prepared\n", style="magenta")
        else:
            activity_text.append("No scene cards found. Use /prepare to start.\n", style="dim italic")
            
        layout["activity"].update(Panel(activity_text, title="Recent Activity", border_style="magenta"))
        
        # Footer
        tips = get_project_tips()
        import random
        layout["footer"].update(Panel(Text(random.choice(tips), justify="center", style="italic"), style="dim"))
        
        console.print(layout)
    except Exception as e:
        # Ultimate fallback if layout calculation fails (e.g. height too small for constraints)
        console.print(f"[yellow]Dashboard layout failed (screen too small): {e}[/]")
        console.print(f"Project: {metadata['name']} | Chapters: {metadata['chapter_count']} | Words: {metadata['word_count']:,}")

