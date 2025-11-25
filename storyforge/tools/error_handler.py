"""
Error handling utilities for StoryForge AI.

Provides user-friendly error messages and formatting.
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typing import Optional


def format_error_message(error: Exception, context: str = "") -> str:
    """
    Format an error message in a user-friendly way.
    
    Args:
        error: The exception that occurred
        context: Additional context about what was being done
        
    Returns:
        Formatted error message
    """
    error_str = str(error).lower()
    
    # API Key errors
    if "api" in error_str and ("key" in error_str or "auth" in error_str or "401" in error_str):
            return (
                "API Authentication Error\n\n"
                "Your API key appears to be invalid or missing.\n\n"
                "Fix steps:\n"
                "1. Check your .env file in the project root\n"
                "2. Ensure OPENROUTER_API_KEY or MOONSHOT_API_KEY is set\n"
                "3. Verify the key has no extra spaces or quotes\n"
                "4. Get a key from: https://openrouter.ai or https://moonshot.ai\n\n"
                "Example .env entry:\nOPENROUTER_API_KEY=sk-or-v1-xxxxx\n"
            )
    
    # Rate limit errors
    elif "rate limit" in error_str or "429" in error_str:
            return (
                "Rate Limit Exceeded\n\n"
                "Too many requests in a short time.\n\n"
                "Fix steps:\n"
                "1. Wait a few minutes before retrying\n"
                "2. Reduce rapid consecutive requests\n"
                "3. Use /save to preserve your progress\n"
            )
    
    # Network errors
    elif any(word in error_str for word in ["timeout", "connection", "network"]):
            return (
                "Network Connection Error\n\n"
                "Unable to reach the AI service.\n\n"
                "Fix steps:\n"
                "1. Check your internet connection\n"
                "2. Try again in a few moments\n"
                "3. Verify BASE_URL in your .env is correct\n"
            )
    
    # File/Path errors
    elif "path separator" in error_str or "invalid" in error_str and "name" in error_str:
            return (
                "Invalid Project Name\n\n"
                "Project names cannot contain special characters like / or \\ or reserved patterns.\n\n"
                "Allowed: letters, numbers, hyphen, underscore.\n"
                "Examples: my-novel, scifi_story, project1\n"
            )
    
    # Default error
    else:
        msg = f"Error Occurred\n\n{str(error)}\n"
        if context:
            msg += f"Context: {context}\n"
        msg += (
            "Try:\n"
            "- Use /help to see available commands\n"
            "- Use /save to preserve progress\n"
            "- Check logs in output/project_name/run.log\n"
        )
        return msg


def display_error(console: Console, error: Exception, context: str = "", show_retry: bool = True):
    """
    Display a formatted error message to the console.
    
    Args:
        console: Rich Console instance
        error: The exception
        context: Additional context
        show_retry: Whether to show retry option
    """
    from ..utils import sanitize_text
    error_msg = sanitize_text(format_error_message(error, context))
    error_text = Text(error_msg, style="yellow")
    
    console.print(Panel(error_text, title="[!] Error", border_style="red"))
    
    if show_retry:
        console.print("[dim]Type 'retry' to try again, or continue with your next request.[/]")


def validate_project_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate a project name and return helpful error if invalid.
    
    Args:
        name: Project name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Project name cannot be empty"
    
    if "/" in name or "\\" in name:
        return False, "Project name cannot contain path separators (/ or \\\\). Try: my-project"
    
    if ".." in name:
        return False, "Project name cannot contain '..'  for security reasons"
    
    if name.startswith("."):
        return False, "Project name cannot start with a dot"
    
    # Check for invalid characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
    if any(char in name for char in invalid_chars):
        return False, f"Project name cannot contain: {' '.join(invalid_chars)}"
    
    if len(name) > 100:
        return False, "Project name too long (max 100 characters)"
    
    return True, None


def get_troubleshooting_tips() -> str:
    """Get general troubleshooting tips."""
    return (
        "Troubleshooting Tips\n\n"
        "Common Issues:\n\n"
        "1. API Key Not Working\n"
        "   - Check .env file exists in project root\n"
        "   - Verify key format: OPENROUTER_API_KEY=sk-or-v1-xxxxx\n"
        "   - No quotes or extra spaces around the key\n\n"
        "2. Agent Not Responding\n"
        "   - Check internet connection\n"
        "   - Verify API service status\n"
        "   - Try /save and restart\n\n"
        "3. Files Not Saving\n"
        "   - Check output/ folder permissions\n"
        "   - Ensure disk space available\n"
        "   - Verify project name is valid\n\n"
        "4. Context Not Loading\n"
        "   - Use /projects to list projects\n"
        "   - Check for .context_summary_*.md files\n"
        "   - Use /switch to change projects\n\n"
        "5. Token Limit Exceeded\n"
        "   - Context auto-compresses near limit\n"
        "   - Use /save to create checkpoints\n"
        "   - Start /new conversation for fresh start\n\n"
        "See README.md or run.log for more details.\n"
    )
