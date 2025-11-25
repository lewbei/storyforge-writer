#!/usr/bin/env python3
"""
StoryForge AI - An autonomous agent for creative writing tasks.

This agent uses advanced AI models to create novels, books, 
and short story collections based on user prompts.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.table import Table
from rich.live import Live
from rich.progress import Progress
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

from .utils import (
    ascii_only_ui,
    estimate_token_count,
    get_tool_definitions,
    get_tool_map,
    get_system_prompt,
    get_autonomous_system_prompt,
)
from .tools.compression import compress_context_impl
from .tools.run_logger import log_event, log_error, log_summary
from .tools.progress import (
    update_status_on_analysis_impl,
    display_status_summary_impl,
)
from .tools.approval import request_approval_impl
from .tools.project import get_active_project_folder

BASE_BACKOFF = 1.5


def _format_prompt_snippet(prompt: str | None) -> str:
    """Return a sanitized, truncated prompt snippet for logging."""
    snippet = (prompt or "").splitlines()[0]
    snippet = ascii_only_ui(snippet) or ""
    return snippet[:120]


def log_provider_error(exc: Exception, attempt: int, max_attempts: int, prompt: str | None, context: str) -> None:
    """Log provider errors with prompt context for later debugging."""
    prompt_snippet = _format_prompt_snippet(prompt)
    error_snippet = ascii_only_ui(str(exc)) or ""
    log_error(
        f"Provider error (attempt {attempt}/{max_attempts}) | context={context} | prompt='{prompt_snippet}' | error={error_snippet}"
    )


def should_retry_provider_error(exc: Exception) -> bool:
    """Decide whether a provider error should trigger an automatic retry."""
    message = str(exc).lower()
    if "inference server" in message or "model inference" in message:
        return True
    if "unknown" in message and "error" in message:
        return True
    return is_transient_error(exc)


def _safe_log(message: str, *, error: bool = False) -> None:
    """Best-effort wrapper around run_logger helpers.

    Ensures logging never raises and long messages are truncated.
    """
    try:
        if len(message) > 2000:
            message = message[:2000] + "...[truncated]"
        if error:
            log_error(message)
        else:
            log_event(message)
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="StoryForge AI autonomous writing agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'prompt',
        nargs='?',
        help='Your writing request (e.g., "Create a mystery novel")'
    )
    parser.add_argument(
        '--recover',
        type=str,
        help='Path to a context summary file to continue from'
    )
    parser.add_argument(
        '--status',
        metavar='PROJECT_NAME',
        help='Show status summary for the given project (by folder name) and exit.'
    )
    return parser.parse_args()


def load_context_from_file(path: str) -> str:
    """Load conversation context from a previously saved summary."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def get_extra_body(model: str | None) -> dict:
    """Get extra_body for reasoning-enabled models."""
    if model and "grok-4.1-fast" in model:
        return {"reasoning": {"enabled": True}}
    return {}


def get_provider_config() -> Dict[str, Any]:
    """Resolve provider configuration from environment variables with multi-model fallback."""
    retry_attempts = max(1, int(os.getenv("REQUEST_RETRIES", "2")))

    # Priority: OpenRouter (multi-model incl. free/local proxies) -> Moonshot -> Ollama (local)
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    moonshot_key = os.getenv("MOONSHOT_API_KEY")
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    if openrouter_key:
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        model = os.getenv("OPENROUTER_MODEL")  # No default, must be in .env
        headers: Dict[str, str] = {}
        app_url = os.getenv("OPENROUTER_APP_URL")
        app_title = os.getenv("OPENROUTER_APP_TITLE")
        if app_url:
            headers["X-OpenRouter-App-Url"] = app_url
        if app_title:
            headers["X-OpenRouter-App-Title"] = app_title
        return {
            "api_key": openrouter_key,
            "base_url": base_url,
            "model": model,
            "token_limit": 2000000,
            "compression_threshold": int(2000000 * 0.9),
            "headers": headers,
            "retry_attempts": retry_attempts,
        }
    if moonshot_key:
        base_url = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
        return {
            "api_key": moonshot_key,
            "base_url": base_url,
            "model": os.getenv("MOONSHOT_MODEL", "moonshot-v1"),
            "token_limit": 200_000,
            "compression_threshold": int(200_000 * 0.9),
            "headers": {},
            "retry_attempts": retry_attempts,
        }
    # Ollama fallback (no key needed, local)
    print("Using local Ollama (ensure running: ollama serve)")
    return {
        "api_key": "ollama",  # Dummy
        "base_url": ollama_base,
        "model": os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),  # Coding-optimized local
        "token_limit": 131072,  # Typical local limit
        "compression_threshold": int(131072 * 0.9),
        "headers": {},
        "retry_attempts": retry_attempts,
    }


def get_user_input() -> tuple[str, bool]:
    """Gets user input for non-interactive mode only.

    Returns (prompt/context, is_recovery_mode).
    For interactive mode, main will handle.
    """
    args = parse_args()

    # Status-only mode: set active project and print summary
    if args.status:
        from .tools.project import sanitize_folder_name, get_output_root, set_active_project_folder
        sanitized = sanitize_folder_name(args.status)
        project_path = os.path.join(get_output_root(), sanitized)
        if os.path.isdir(project_path):
            set_active_project_folder(project_path)
            print(display_status_summary_impl())
        else:
            print(f"PROJECT STATUS: {sanitized} | not found")
        sys.exit(0)

    # Recovery mode
    if args.recover:
        context = load_context_from_file(args.recover)
        return context, True

    # Prompt via CLI arg
    if args.prompt:
        return args.prompt, False

    # No prompt: for non-interactive, error
    print("Error: No prompt provided for non-interactive mode.")
    print("Use 'python storyforge.py \"your prompt\"' or run without args for interactive mode.")
    sys.exit(1)


def convert_message_for_api(msg: Any) -> Dict[str, Any]:
    """
    Converts a message object to a dictionary suitable for API calls.
    Preserves reasoning_content if present.
    
    Args:
        msg: Message object (can be OpenAI message object or dict)
        
    Returns:
        Dictionary representation of the message
    """
    if isinstance(msg, dict):
        return msg
    
    # Convert OpenAI message object to dict
    msg_dict = {
        "role": msg.role,
    }
    
    if msg.content:
        msg_dict["content"] = msg.content
    
    # Preserve reasoning_content if present
    if hasattr(msg, "reasoning_content"):
        reasoning = getattr(msg, "reasoning_content")
        if reasoning:
            msg_dict["reasoning_content"] = reasoning
    
    # Preserve tool calls if present
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        msg_dict["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            }
            for tc in msg.tool_calls
        ]
    
    # Preserve tool call id for tool response messages
    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
        msg_dict["tool_call_id"] = msg.tool_call_id
    
    if hasattr(msg, "name") and msg.name:
        msg_dict["name"] = msg.name
    
    return msg_dict


def is_transient_error(exc: Exception, status: Optional[int] = None) -> bool:
    """Classify whether an error is transient and worth retrying.

    Transient examples:
    - 408, 429 (without hard rate limit messaging), 500, 502, 503, 504
    - Network timeouts / connection issues from OpenAI/httpx
    """
    # Try to get HTTP status from common client error types
    status_code = status
    if status_code is None:
        for attr in ("status_code", "status", "http_status"):
            if hasattr(exc, attr):
                try:
                    status_code = int(getattr(exc, attr))
                    break
                except (TypeError, ValueError):
                    continue

    message = str(exc).lower()

    # Explicit unrecoverable cues
    if status_code in (400, 401, 403):
        return False
    if status_code == 429:
        # Retry only if it's not clearly a hard rate limit lockout
        if "rate limit" in message and ("exceeded" in message or "too many" in message):
            return False
        return True
    if status_code and 400 <= status_code < 500:
        # Other 4xx (validation / bad request) are unrecoverable
        return False

    # Transient server-side or networky things
    if status_code in (408, 500, 502, 503, 504):
        return True

    network_hints = [
        "timeout", "timed out", "connection reset", "temporarily unavailable",
        "connection aborted", "connection refused", "server disconnected",
    ]
    if any(h in message for h in network_hints):
        return True

    return False


def is_unrecoverable_error(exc: Exception, status: Optional[int] = None) -> bool:
    """Classify unrecoverable errors that should stop the agent.

    Unrecoverable examples:
    - 401/403 auth issues
    - 429 with clear rate-limit exceeded
    - 400-series validation / bad request
    """
    status_code = status
    if status_code is None:
        for attr in ("status_code", "status", "http_status"):
            if hasattr(exc, attr):
                try:
                    status_code = int(getattr(exc, attr))
                    break
                except (TypeError, ValueError):
                    continue

    message = str(exc).lower()

    if status_code in (401, 403):
        return True
    if status_code == 429 and "rate limit" in message and ("exceeded" in message or "too many" in message):
        return True
    if status_code and 400 <= status_code < 500:
        return True

    return False


def _extract_status_from_exception(exc: Exception) -> Optional[int]:
    """Best-effort extraction of HTTP status from various client exceptions."""
    for attr in ("status_code", "status", "http_status"):
        if hasattr(exc, attr):
            try:
                return int(getattr(exc, attr))
            except (TypeError, ValueError):
                continue
    # httpx/OpenAI often embed response on .response
    resp = getattr(exc, "response", None)
    if resp is not None:
        for attr in ("status_code", "status", "http_status"):
            if hasattr(resp, attr):
                try:
                    return int(getattr(resp, attr))
                except (TypeError, ValueError):
                    continue
    return None


def _sleep_backoff(attempt: int) -> None:
    """Simple exponential backoff sleep. Kept tiny/quiet."""
    import time

    delay = BASE_BACKOFF ** attempt
    # Cap delay to keep runtime reasonable
    if delay > 10:
        delay = 10
    print(f"Retrying in {delay:.1f}s...")
    time.sleep(delay)


def get_rich_console():
    """Get a Rich console instance with safe defaults."""
    # Force a minimum width to prevent layout errors in small/headless terminals
    try:
        console = Console()
        if hasattr(console, "size") and console.size.width < 80:
            return Console(width=80)
        return console
    except Exception:
        return Console(width=80)


def display_chat_message(console, role, content, is_stream=False):
    """Display a message in a Rich panel for GUI-like chat."""
    from .utils import sanitize_text
    content = sanitize_text(content)
    if role == "user":
        panel = Panel(Text(content, style="bold cyan"), title="[User]", border_style="cyan")
    elif role == "assistant":
        panel = Panel(Text(content, style="bold green"), title="[Agent]", border_style="green")
    else:
        panel = Panel(Text(content, style="bold yellow"), title="[System/Tool]", border_style="yellow")
    
    console.print(panel)
    if is_stream:
        console.print("[dim]Streaming complete.[/]")


def show_status_table(console, project_name=None):
    """Display enhanced project status dashboard with progress bars and detailed stats."""
    from .tools.project import get_active_project_folder
    from rich.progress import BarColumn, Progress, TextColumn
    import glob
    
    active_folder = get_active_project_folder() or "None"
    
    if active_folder == "None" or not os.path.exists(active_folder):
        console.print("[yellow]No active project.[/]")
        return
    
    # Gather statistics
    files = [f for f in os.listdir(active_folder) if os.path.isfile(os.path.join(active_folder, f))]
    chapters = [f for f in files if f.startswith("Chapter") and f.endswith(".md")]
    
    # Word counts
    total_words = 0
    chapter_words = {}
    for chapter in chapters:
        try:
            with open(os.path.join(active_folder, chapter), 'r', encoding='utf-8') as f:
                words = len(f.read().split())
                chapter_words[chapter] = words
                total_words += words
        except:
            pass
    
    # Analysis files
    has_plot = os.path.exists(os.path.join(active_folder, "plot_analysis.md"))
    has_character = os.path.exists(os.path.join(active_folder, "character_analysis.md"))
    has_world = os.path.exists(os.path.join(active_folder, "world_analysis.md"))
    has_outline = os.path.exists(os.path.join(active_folder, "continuation_outline.md"))
    
    # Create dashboard
    console.print("\n")
    project_label = ascii_only_ui(project_name or os.path.basename(active_folder)) or ""
    console.print(Panel(f"[bold cyan]Project: {project_label}[/]", border_style="cyan"))
    
    # Main stats table
    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="bold green")
    
    stats_table.add_row("Total Files", str(len(files)))
    stats_table.add_row("Chapters", str(len(chapters)))
    stats_table.add_row("Total Words", f"{total_words:,}")
    if chapters:
        avg_words = total_words // len(chapters)
        stats_table.add_row("Avg Words/Chapter", f"{avg_words:,}")
    
    console.print(stats_table)
    
    # Analysis checklist
    console.print("\n[bold]Analysis Completion:[/]")
    analysis_table = Table(show_header=False, box=None)
    analysis_table.add_column("Item", style="dim")
    analysis_table.add_column("Status")
    
    analysis_table.add_row("Plot Analysis", "[green]Complete[/]" if has_plot else "[dim]Pending[/]")
    analysis_table.add_row("Character Analysis", "[green]Complete[/]" if has_character else "[dim]Pending[/]")
    analysis_table.add_row("World Building", "[green]Complete[/]" if has_world else "[dim]Pending[/]")
    analysis_table.add_row("Continuation Outline", "[green]Complete[/]" if has_outline else "[dim]Pending[/]")
    
    console.print(analysis_table)
    
    # Chapter progress (if chapters exist)
    if chapters:
        console.print("\n[bold]Chapter Word Counts:[/]")
        # Show top 5 longest chapters
        sorted_chapters = sorted(chapter_words.items(), key=lambda x: x[1], reverse=True)[:5]
        for chapter, words in sorted_chapters:
            # Create simple progress bar representation
            max_words = sorted_chapters[0][1] if sorted_chapters else 1
            bar_width = 20
            filled = int((words / max_words) * bar_width)
            # Use ASCII only for compatibility
            bar = "#" * filled + "." * (bar_width - filled)
            console.print(f"  {chapter[:30]:<30} {bar} {words:>6,} words")
    
    console.print("")


def chat_mode_gui(client, config, tools, tool_map, initial_messages=None, project_name=None):
    """
    GUI-like chat mode using Rich for panels, colors, and tables.
    """
    console = get_rich_console()
    from .tools.ui_input import process_user_input
    from .tools.ui_helpers import CHAT_HELP_COMMANDS, list_all_projects, display_projects_table
    from .tools.project import set_active_project_folder, get_output_root, sanitize_folder_name
    import json
    import glob
    
    if project_name:
        sanitized = sanitize_folder_name(project_name)
        project_path = os.path.join(get_output_root(), sanitized)
        set_active_project_folder(project_path)
        console.print(f"[bold green]Active project: {ascii_only_ui(sanitized)}[/]")
    
    # Initialize messages
    if initial_messages:
        messages = initial_messages
    else:
        base_system = get_system_prompt()
        
        # If we have an active project, assemble robust rolling context
        if project_name:
            from .tools.summarizer import get_rolling_context
            console.print("[cyan]Assembling rolling context (checking summaries)...[/]")
            try:
                rolling_context = get_rolling_context(client, config["model"])
                full_system = f"{base_system}\n\n{rolling_context}"
                console.print("[green]Context loaded.[/]")
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load rolling context: {e}[/]")
                full_system = base_system
        else:
            full_system = base_system

        messages = [{"role": "system", "content": full_system}]

    if console.size.width >= 60:
        console.print(Panel(
            "Chat Mode - Type your message or /command. Type /help for available commands.\nExample: 'Plan Chapter 1 using the Fantasy template'",
            title="StoryForge AI - Chat Mode", border_style="blue"
        ))
    else:
        print("\n--- StoryForge AI: Chat Mode ---")
        print("Type /help for commands. Example: 'Plan Chapter 1'")

    # Track consecutive chapter writes for autonomous batch generation
    consecutive_chapter_writes = {"count": 0, "in_batch": False}
    
    from .tools.persona import generate_dynamic_system_prompt

    def get_system_prompt() -> str:
        return generate_dynamic_system_prompt("writer")

    def _print_tool_result_summary(func_name: str, result: str) -> None:
        """Print a concise tool result summary to the console without dumping entire file contents.

        - For read_project_files: show status line, list of filenames, totals, cache stats
        - For other tools: print up to a safe limit of characters/lines
        """
        from .utils import ascii_only_ui
        import re

        safe_result = result or ""
        if func_name == "read_project_files":
            lines = safe_result.splitlines()
            status_line = next((l for l in lines if l.startswith("STATUS:")), None)
            total_line = next((l for l in lines if l.startswith("Total characters read:")), None)
            cache_line = next((l for l in lines if l.startswith("Cache ") or l.startswith("Cache Stats:")), None)
            file_names = []
            file_re = re.compile(r"^--- FILE: (.+?)(?: \\[CACHED\\])? ---$")
            for l in lines:
                m = file_re.match(l.strip())
                if m:
                    file_names.append(ascii_only_ui(m.group(1)) or "")
            # Build summary
            console.print("\n[blue][TOOL RESULT - read_project_files][/blue]")
            if status_line:
                console.print(f"[blue]{ascii_only_ui(status_line)}[/blue]")
            if file_names:
                max_show = 10
                shown = ", ".join(file_names[:max_show])
                extra = len(file_names) - max_show
                if extra > 0:
                    shown += f" ... (+{extra} more)"
                console.print(f"[blue]Files: {shown}[/blue]")
            if total_line:
                console.print(f"[blue]{ascii_only_ui(total_line)}[/blue]")
            if cache_line:
                console.print(f"[blue]{ascii_only_ui(cache_line)}[/blue]")
            console.print("")
            return

        # Generic truncation for other tools
        MAX_CHARS = 1000
        MAX_LINES = 30
        out = safe_result
        lines = out.splitlines()
        truncated = False
        if len(lines) > MAX_LINES:
            out = "\n".join(lines[:MAX_LINES])
            truncated = True
        if len(out) > MAX_CHARS:
            out = out[:MAX_CHARS]
            truncated = True
        suffix = "\n... [truncated]" if truncated else ""
        console.print(f"\n[blue][TOOL RESULT - {func_name}]:\n{ascii_only_ui(out)}{suffix}[/blue]\n")

    last_user_prompt = None
    while True:
        user_input = Prompt.ask("[bold cyan]You[/]", console=console).strip()
        if not user_input:
            continue

        # Process input via helper
        action, normalized_input, skip_append, warning = process_user_input(messages, user_input)

        # Command / meta handling
        if action == "noop":
            if warning:
                console.print(f"[yellow]{ascii_only_ui(warning)}[/]")
            continue
        if action == "exit":
            console.print("[bold red]Exiting chat mode.[/]")
            break
        if action == "help":
            help_text = Text()
            help_text.append("Available Commands:\n\n", style="bold cyan")
            for command, description in CHAT_HELP_COMMANDS:
                help_text.append(command, style="yellow")
                help_text.append(f" - {description}\n")

            console.print(Panel(help_text, title="Help", border_style="cyan"))
            continue
        if action == "resume":
            if not project_name:
                console.print("[yellow]No active project. Use /projects to select one first.[/]")
                continue
            from .tools.project import get_active_project_folder
            folder = get_active_project_folder()
            if not folder or not os.path.isdir(folder):
                console.print("[red]Active project folder not found.[/]")
                continue
            summary_pattern = os.path.join(folder, ".context_summary_*.md")
            summary_files = glob.glob(summary_pattern)
            if not summary_files:
                console.print("[yellow]No saved conversation summaries found to resume.[/]")
                continue
            latest_summary = max(summary_files, key=os.path.getmtime)
            try:
                with open(latest_summary, 'r', encoding='utf-8') as f:
                    context = f.read()
                messages.append({"role": "user", "content": f"[RECOVERED CONTEXT]\n\n{context}\n\n[END RECOVERED CONTEXT]"})
                console.print(f"[green]Resumed conversation from: {ascii_only_ui(os.path.basename(latest_summary))}[/]")
            except Exception as e:
                console.print(f"[yellow]Failed to load resume context: {ascii_only_ui(str(e))}[/]")
            continue
        if action == "status":
            show_status_table(console, project_name)
            continue
        if action == "projects":
            projects = list_all_projects(get_output_root())
            if projects:
                display_projects_table(console, projects)
            else:
                console.print("[yellow]No projects found.[/]")
            continue
        if action == "files":
            if project_name:
                from .tools.project import get_active_project_folder
                folder = get_active_project_folder()
                if folder and os.path.exists(folder):
                    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and not f.startswith('.')]
                    table = Table(title=f"Files in {project_name}")
                    table.add_column("#", style="cyan", width=4)
                    table.add_column("Filename", style="green")
                    table.add_column("Size", justify="right")
                    for idx, f in enumerate(sorted(files), 1):
                        size = os.path.getsize(os.path.join(folder, f))
                        size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
                        table.add_row(str(idx), f, size_str)
                    console.print(table)
                else:
                    console.print("[red]Project folder not found.[/]")
            else:
                console.print("[yellow]No active project. Use /projects to select one.[/]")
            continue
        if action == "switch":
            parts = (normalized_input or "").split(maxsplit=1)
            if len(parts) == 2:
                new_project = parts[1].strip()
                from .tools.project import get_output_root, sanitize_folder_name, set_active_project_folder
                sanitized = sanitize_folder_name(new_project)
                project_path2 = os.path.join(get_output_root(), sanitized)
                if os.path.isdir(project_path2):
                    set_active_project_folder(project_path2)
                    project_name = sanitized
                    
                    # Show dashboard on switch
                    try:
                        display_dashboard_impl(console, project_path2)
                    except Exception:
                        pass

                    summary_pattern = os.path.join(project_path2, ".context_summary_*.md")
                    summary_files = glob.glob(summary_pattern)
                    if summary_files:
                        latest_summary = max(summary_files, key=os.path.getmtime)
                        try:
                            with open(latest_summary, 'r', encoding='utf-8') as f:
                                context = f.read()
                            messages = [
                                {"role": "system", "content": get_system_prompt()},
                                {"role": "user", "content": f"[RECOVERED CONTEXT]\n\n{context}\n\n[END RECOVERED CONTEXT]"}
                            ]
                            console.print(f"[green]Switched to {ascii_only_ui(sanitized)} and loaded context[/]")
                        except Exception as e:
                            console.print(f"[yellow]Switched to {ascii_only_ui(sanitized)} but failed to load context: {ascii_only_ui(str(e))}[/]")
                    else:
                        messages = [{"role": "system", "content": get_system_prompt()}]
                        console.print(f"[green]Switched to {ascii_only_ui(sanitized)}[/]")
                else:
                    console.print(f"[red]Project '{ascii_only_ui(sanitized)}' not found. Use /projects to see available projects.[/]")
            else:
                console.print("[yellow]Usage: /switch <project_name>[/]")
            continue
        if action == "troubleshoot":
            from .tools.error_handler import get_troubleshooting_tips
            console.print(Panel(get_troubleshooting_tips(), title="Troubleshooting", border_style="yellow"))
            continue
        if action == "save":
            with Progress() as progress:
                task = progress.add_task("[green]Saving context...[/]", total=None)
                compression_result = compress_context_impl(
                    messages=messages,
                    client=client,
                    model=config["model"],
                    keep_recent=len(messages)
                )
                progress.remove_task(task)
            summary_file = compression_result.get("summary_file")
            if summary_file:
                console.print(f"[green]Context saved to: {ascii_only_ui(summary_file)}[/]")
            else:
                console.print("[red]Save failed.[/]")
            continue
        if action == "new":
            messages = [{"role": "system", "content": get_system_prompt()}]
            console.print("[yellow]New conversation started.[/]")
            continue

        # Send action
        prepared_input = normalized_input or ""
        if not skip_append:
            display_chat_message(console, "user", prepared_input)
            messages.append({"role": "user", "content": prepared_input})
            last_user_prompt = prepared_input
        
        # Agent response with streaming simulation using Rich Live and retries
        try:
            max_attempts = max(1, config.get("retry_attempts", 2))
            for attempt in range(1, max_attempts + 1):
                try:
                    # Token check
                    from .utils import estimate_token_count, sanitize_messages
                    token_count = estimate_token_count(
                        config["base_url"],
                        config["api_key"],
                        config["model"],
                        sanitize_messages(messages),
                        headers=config.get("headers")
                    )
                    console.print(f"[dim]Tokens: {token_count:,}/{config['token_limit']:,} ({(token_count / config['token_limit'] * 100):.1f}%)[/]")
                    
                    if token_count >= config["compression_threshold"]:
                        console.print("[yellow]Compressing context...[/]")
                        compression_result = compress_context_impl(
                            messages=messages,
                            client=client,
                            model=config["model"],
                            keep_recent=10
                        )
                        if "compressed_messages" in compression_result:
                            messages = compression_result["compressed_messages"]
                            console.print("[green]Context compressed.[/]")
                    
                    # Call model
                    from .utils import sanitize_messages, sanitize_text
                    full_content = ""
                    tool_calls_acc = []
                    current_tool = None
                    stream_text = Text()
                    console.print("[bold green]Agent:[/]", end="")
                    try:
                        extra_body = get_extra_body(config["model"])
                        response = client.chat.completions.create(
                            model=config["model"],
                            messages=sanitize_messages(messages),
                            max_tokens=4096,
                            tools=tools,
                            temperature=0.7,
                            stream=True,
                            tool_choice="auto",  # encourage model-directed tool use
                            extra_body=extra_body
                        )
                        for chunk in response:
                            delta = chunk.choices[0].delta
                            # Stream regular content tokens
                            if getattr(delta, "content", None):
                                safe = sanitize_text(delta.content)
                                stream_text.append(safe)
                                full_content += safe
                                console.print(safe, end="", style="green", highlight=False)
                            # Stream tool call deltas (support multiple tool calls and incremental args)
                            tc_list = getattr(delta, "tool_calls", None)
                            if tc_list:
                                for tc_delta in tc_list:
                                    idx = getattr(tc_delta, "index", 0) or 0
                                    # Ensure list large enough
                                    while len(tool_calls_acc) <= idx:
                                        tool_calls_acc.append({
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""}
                                        })
                                    current_tool = tool_calls_acc[idx]
                                    # Capture id if available
                                    if getattr(tc_delta, "id", None):
                                        current_tool["id"] = tc_delta.id
                                    # Function object may be partial across deltas
                                    fn = getattr(tc_delta, "function", None)
                                    if fn and getattr(fn, "name", None):
                                        # Only announce when name first appears
                                        if current_tool["function"]["name"] != fn.name:
                                            console.print(f"\n[yellow][TOOL {idx+1}: {fn.name}][/yellow]", end="")
                                        current_tool["function"]["name"] = fn.name
                                    if fn and getattr(fn, "arguments", None):
                                        safe_args = sanitize_text(fn.arguments)
                                        current_tool["function"]["arguments"] += safe_args
                                        console.print(safe_args, end="", style="yellow")
                    except Exception as se:
                        # Fallback to non-streaming
                        console.print("\n[yellow]Streaming failed, retrying without streaming...[/]")
                        extra_body = get_extra_body(config["model"])
                        resp = client.chat.completions.create(
                            model=config["model"],
                            messages=sanitize_messages(messages),
                            max_tokens=4096,
                            tools=tools,
                            temperature=0.7,
                            stream=False,
                            tool_choice="auto",
                            extra_body=extra_body
                        )
                        content = resp.choices[0].message.content if resp.choices else ""
                        content = sanitize_text(content or "")
                        full_content += content
                        console.print(content, end="", style="green", highlight=False)
                    
                    console.print("\n")
                    
                    # Execute tools if any
                    if tool_calls_acc:
                        # Add assistant message with tool call metadata
                        messages.append({
                            "role": "assistant",
                            "content": full_content or None,
                            "tool_calls": tool_calls_acc,
                        })

                        # Execute each tool call in order
                        for i, tc in enumerate(tool_calls_acc, start=1):
                            func_name = tc["function"].get("name")
                            args_str = tc["function"].get("arguments", "")
                            if not func_name:
                                console.print(f"[red]Skipping tool #{i}: missing function name[/red]")
                                continue
                            try:
                                # Empty args -> treat as {}
                                json_args = args_str.strip() or "{}"
                                args = json.loads(json_args)
                            except Exception:
                                # Attempt to repair trailing JSON fragments (simple heuristic)
                                repaired = args_str.rstrip().rstrip(",")
                                try:
                                    args = json.loads(repaired)
                                except Exception as e:
                                    console.print(f"[red][TOOL ARG PARSE ERROR {func_name}: {e}][/red]")
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc.get("id") or func_name,
                                        "name": func_name,
                                        "content": f"STATUS: ERROR | argument parse failed: {e}"
                                    })
                                    continue
                            tool_func = tool_map.get(func_name)
                            if not tool_func:
                                console.print(f"[red][ERROR: Unknown tool {func_name}][/red]")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.get("id") or func_name,
                                    "name": func_name,
                                    "content": f"STATUS: ERROR | Unknown tool '{func_name}'"
                                })
                                continue
                            try:
                                with Progress() as progress:
                                    task = progress.add_task(f"[blue]Executing {func_name}...[/]", total=None)
                                    result = tool_func(**args)
                                    progress.remove_task(task)
                                
                                # Track chapter writes for batch mode
                                if func_name == "write_file" and "filename" in args:
                                    filename = args.get("filename", "")
                                    if "chapter" in filename.lower():
                                        consecutive_chapter_writes["count"] += 1
                                        if consecutive_chapter_writes["count"] >= 2:
                                            consecutive_chapter_writes["in_batch"] = True
                                            console.print("[dim]-> Batch chapter generation active[/]")
                                else:
                                    # Reset if non-chapter tool called
                                    if func_name != "format_chapter" and func_name != "quality_check" and func_name != "validate_chapter_content":
                                        if consecutive_chapter_writes["in_batch"]:
                                            console.print("[dim]<- Batch chapter generation complete[/]")
                                        consecutive_chapter_writes["count"] = 0
                                        consecutive_chapter_writes["in_batch"] = False
                            except Exception as e:
                                console.print(f"[red][TOOL EXEC ERROR {func_name}: {e}][/red]")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.get("id") or func_name,
                                    "name": func_name,
                                    "content": f"STATUS: ERROR | {e}"
                                })
                            else:
                                _print_tool_result_summary(func_name, str(result))
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.get("id") or func_name,
                                    "name": func_name,
                                    "content": str(result)
                                })

                        # Final assistant response after all tool outputs
                        console.print("[bold green]Agent (final):[/]", end="")
                        final_content = ""
                        try:
                            extra_body = get_extra_body(config["model"])
                            final_response = client.chat.completions.create(
                                model=config["model"],
                                messages=sanitize_messages(messages),
                                max_tokens=4096,  # Increased from 2048 for longer responses
                                stream=True,
                                tool_choice="auto",  # Allow continuation if more tools needed
                                extra_body=extra_body
                            )
                            for chunk in final_response:
                                delta2 = chunk.choices[0].delta
                                if getattr(delta2, "content", None):
                                    safe_final = sanitize_text(delta2.content)
                                    console.print(safe_final, end="", style="green")
                                    final_content += safe_final
                        except Exception:
                            console.print("\n[yellow]Final streaming failed, retrying without streaming...[/]")
                            extra_body = get_extra_body(config["model"])
                            resp2 = client.chat.completions.create(
                                model=config["model"],
                                messages=sanitize_messages(messages),
                                max_tokens=4096,
                                stream=False,
                                tool_choice="auto",
                                extra_body=extra_body
                            )
                            content2 = resp2.choices[0].message.content if resp2.choices else ""
                            content2 = sanitize_text(content2 or "")
                            console.print(content2, end="", style="green")
                            final_content += content2
                        console.print("\n")
                        messages.append({"role": "assistant", "content": final_content})
                    else:
                        messages.append({"role": "assistant", "content": full_content})
                    
                    # Check if agent wants to continue (don't break immediately)
                    # Allow the loop to continue if tools were called or continuation is needed
                    if not tool_calls_acc:
                        # No tools in this turn, check if we should wait or continue
                        if consecutive_chapter_writes["in_batch"]:
                            # In batch mode, allow agent to continue planning next chapter
                            console.print("[dim]-> Continuing batch generation...[/]")
                            # Don't break - let the loop continue with tool_choice="auto"
                            pass
                        else:
                            # Normal mode - wait for user input
                            break
                    # If tools were called, loop will continue automatically
                except Exception as request_error:
                    log_provider_error(
                        request_error,
                        attempt,
                        max_attempts,
                        prepared_input,
                        "during AI response generation"
                    )
                    if attempt == max_attempts or not should_retry_provider_error(request_error):
                        raise
                    _sleep_backoff(attempt)
        except Exception as e:
            from .tools.error_handler import display_error
            display_error(console, e, context="during AI response generation")
            _safe_log(f"chat_error | {e}", error=True)
            # Don't append error to messages, let user retry
    
    # Save on exit (always preserve context)
    if project_name and len(messages) > 2:  # Only save if there was actual conversation
        try:
            compression_result = compress_context_impl(
                messages=messages,
                client=client,
                model=config["model"],
                keep_recent=len(messages)
            )
            summary_file = compression_result.get("summary_file")
            if summary_file:
                console.print(f"[green]Chat session saved: {ascii_only_ui(summary_file)}[/]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save session: {ascii_only_ui(str(e))}[/]")

def chat_mode_gui(client, config, tools, tool_map, initial_messages=None, project_name=None):
    """
    Rich-based GUI for chat mode.
    """
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text
    from .tools.ui_input import process_user_input
    from .tools.ui_helpers import CHAT_HELP_COMMANDS, display_dashboard_impl
    from .tools.project import get_active_project_folder
    from .tools.bible import read_project_bible, generate_bible_template
    
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.completion import WordCompleter
    
    console = Console()

    # Autocompletion setup
    commands = [
        '/help', '/status', '/projects', '/files', '/switch', 
        '/save', '/resume', '/new', '/brainstorm', '/critique', 
        '/dashboard', '/context', '/bible', '/exit'
    ]
    command_completer = WordCompleter(commands, ignore_case=True)

    def _print_tool_result_summary(func_name: str, result: str) -> None:
        """Print a concise tool result summary to the console without dumping entire file contents."""
        from .utils import ascii_only_ui
        
        safe_result = result or ""
        if func_name == "read_project_files":
            lines = safe_result.splitlines()
            status_line = next((l for l in lines if l.startswith("STATUS:")), None)
            files_line = next((l for l in lines if l.startswith("FILES:")), None)
            total_line = next((l for l in lines if l.startswith("TOTAL:")), None)
            cache_line = next((l for l in lines if l.startswith("CACHE:")), None)
            
            if status_line:
                console.print(f"[blue]{ascii_only_ui(status_line)}[/blue]")
            if files_line:
                console.print(f"[blue]{ascii_only_ui(files_line)}[/blue]")
            if total_line:
                console.print(f"[blue]{ascii_only_ui(total_line)}[/blue]")
            if cache_line:
                console.print(f"[blue]{ascii_only_ui(cache_line)}[/blue]")
            console.print("")
            return

        # Generic truncation for other tools
        MAX_CHARS = 1000
        MAX_LINES = 30
        out = safe_result
        lines = out.splitlines()
        truncated = False
        if len(lines) > MAX_LINES:
            out = "\n".join(lines[:MAX_LINES])
            truncated = True
        if len(out) > MAX_CHARS:
            out = out[:MAX_CHARS]
            truncated = True
        suffix = "\n... [truncated]" if truncated else ""
        console.print(f"\n[blue][TOOL RESULT - {func_name}]:\n{ascii_only_ui(out)}{suffix}[/blue]\n")

    
    # Load Project Bible if available
    project_bible_content = ""
    if project_name:
        # We need the full path. get_active_project_folder might rely on global state or we need to find it.
        # Since we passed project_name, let's assume it's active or we can find it.
        # Actually, get_active_project_folder() should work if set_active_project_folder was called.
        project_folder = get_active_project_folder()
        if project_folder:
            bible_content = read_project_bible(project_folder)
            if bible_content:
                project_bible_content = f"\n\n[PROJECT BIBLE]\n{bible_content}\n[/PROJECT BIBLE]"
                console.print(f"[dim]Loaded Project Bible context.[/]")

    # Header
    console.print(Panel(f"[bold cyan]StoryForge AI[/] - Project: [bold green]{project_name or 'New Session'}[/]", style="blue"))
    console.print("[dim]Type /help for commands, /dashboard for stats, /exit to quit.[/]")
    console.print("[dim]Input: Enter to send, Alt+Enter to add newline.[/]\n")
    
    base_system_prompt = get_system_prompt()
    full_system_prompt = base_system_prompt + project_bible_content
    
    messages = initial_messages or [{"role": "system", "content": full_system_prompt}]
    
    # Ensure system prompt is up to date if resuming (unless it was custom)
    if messages and messages[0]["role"] == "system" and project_bible_content:
        if "[PROJECT BIBLE]" not in messages[0]["content"]:
             messages[0]["content"] += project_bible_content

    # If resuming, show last few messages
    if initial_messages and len(initial_messages) > 1:
        for msg in initial_messages[-2:]:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                console.print(Panel(content, title="You", style="green", title_align="left"))
            elif role == "assistant":
                model_name = config.get("model", "StoryForge")
                console.print(Panel(Markdown(content), title=model_name, style="blue", title_align="right"))
    
    # Setup PromptSession with keybindings
    bindings = KeyBindings()

    @bindings.add('escape', 'enter')
    @bindings.add('c-j') # Alt+Enter often sends this or similar, let's try standard way
    def _(event):
        event.current_buffer.insert_text('\n')
        
    session = PromptSession(key_bindings=bindings)

    while True:
        try:
            # Dynamic prompt with active project name
            from .tools.project import get_active_project_folder
            active_path = get_active_project_folder()
            proj_label = os.path.basename(active_path) if active_path else "No Project"
            
            # User Input with prompt_toolkit
            user_input = session.prompt(
                HTML(f"<b><green>[{proj_label}] You</green></b>: "),
                completer=command_completer
            )
            user_input = user_input.strip()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting...[/]")
            break
            
        if not user_input:
            continue

        # Process Input
        action, normalized_input, skip_append, warning = process_user_input(messages, user_input)

        if warning:
            console.print(f"[yellow]{warning}[/]")

        if action == "exit":
            break
            
        if action == "help":
            console.print("\n[bold]Available Commands:[/]")
            for cmd, desc in CHAT_HELP_COMMANDS:
                console.print(f"  [cyan]{cmd}[/] - {desc}")
            console.print(f"  [cyan]/dashboard[/] - Show project dashboard")
            console.print(f"  [cyan]/brainstorm[/] - Enter brainstorming mode")
            console.print(f"  [cyan]/critique <file>[/] - Critique a chapter")
            console.print(f"  [cyan]/context[/] - Show current context and system prompt")
            console.print(f"  [cyan]/bible[/] - Manage Project Bible (Context)")
            console.print(f"  [dim]Tip: End a line with \\ to type multiple lines.[/]")
            continue
            
        if action == "dashboard":
            project_folder = get_active_project_folder()
            if project_folder:
                display_dashboard_impl(console, project_folder)
            else:
                console.print("[yellow]No active project.[/]")
            continue
            
        if action == "bible":
            project_folder = get_active_project_folder()
            if not project_folder:
                console.print("[yellow]No active project.[/]")
                continue
                
            bible_content = read_project_bible(project_folder)
            if bible_content:
                console.print(Panel(bible_content, title="Project Bible", style="green"))
                console.print("[dim]Edit 'bible.md' in your project folder to update.[/]")
            else:
                console.print("[yellow]No Project Bible found.[/]")
                # Use session.prompt for consistency
                confirm = session.prompt(HTML("<yellow>Generate template? (Y/n): </yellow>")).strip().upper()
                if confirm == 'Y' or confirm == '':
                    path = generate_bible_template(project_folder)
                    if path:
                        console.print(f"[green]Template created at: {path}[/]")
                        console.print("[dim]Please edit this file with your story details.[/]")
                        # Reload context
                        new_content = read_project_bible(project_folder)
                        if new_content:
                            project_bible_content = f"\n\n[PROJECT BIBLE]\n{new_content}\n[/PROJECT BIBLE]"
                            if messages and messages[0]["role"] == "system":
                                messages[0]["content"] += project_bible_content
                            console.print("[cyan]Bible loaded into context.[/]")
            continue

        if action == "context":
            console.print(Panel(f"[bold]Active Project:[/] {project_name or 'None'}", title="Context Info", style="cyan"))
            if messages and messages[0]["role"] == "system":
                sys_prompt = messages[0]["content"]
                # Check if bible is in it
                has_bible = "[PROJECT BIBLE]" in sys_prompt
                bible_indicator = "[green]Active[/]" if has_bible else "[dim]Inactive[/]"
                console.print(f"Project Bible: {bible_indicator}")
                
                preview = sys_prompt[:500] + "..." if len(sys_prompt) > 500 else sys_prompt
                console.print(Panel(preview, title="System Prompt", style="dim"))
            console.print(f"[dim]Total Messages: {len(messages)}[/]")
            continue

        if action == "brainstorm":
            # Switch system prompt
            brainstorm_prompt = generate_dynamic_system_prompt("brainstorm")
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] = brainstorm_prompt
            else:
                messages.insert(0, {"role": "system", "content": brainstorm_prompt})
            console.print(Panel("[bold magenta]Entered Writers' Room (Brainstorm Mode)[/]\nI am now your Story Consultant.", style="magenta"))
            continue
            
        if action == "critique":
            parts = normalized_input.split(" ", 1)
            if len(parts) > 1:
                filename = parts[1].strip()
                user_msg = f"Please critique {filename}."
                action = "send"
                normalized_input = user_msg
                console.print(f"[dim]Requesting critique for {filename}...[/]")
            else:
                console.print("[red]Usage: /critique <filename>[/]")
                continue

        if action == "noop":
            continue

        # Send to Model
        if action == "send":
            if not skip_append:
                messages.append({"role": "user", "content": normalized_input})
            
            # Show spinner while thinking
            try:
                with Live(Spinner("dots", text="Thinking...", style="cyan"), refresh_per_second=10, transient=True) as live:
                    try:
                        # Call API
                        response = client.chat.completions.create(
                            model=config["model"],
                            messages=messages,
                            tools=tools,
                            tool_choice="auto",
                            temperature=0.7,
                            max_tokens=4000
                        )
                        
                        response_message = response.choices[0].message
                        tool_calls = response_message.tool_calls
                        
                        if tool_calls:
                            # Handle Tool Calls
                            messages.append(response_message)
                            
                            for tool_call in tool_calls:
                                func_name = tool_call.function.name
                                func_args = json.loads(tool_call.function.arguments)
                                
                                # console.print(f"[dim]Executing {func_name}...[/]")
                                
                                if func_name in tool_map:
                                    try:
                                        func_result = tool_map[func_name](**func_args)
                                    except Exception as e:
                                        func_result = f"Error: {str(e)}"
                                else:
                                    func_result = f"Error: Tool {func_name} not found"
                                    
                                messages.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": func_name,
                                    "content": str(func_result)
                                })
                                
                                # Show tool result summary
                                # We need to print this outside the Live context or update the Live context?
                                # Printing outside might break the spinner visual if not careful, 
                                # but transient=True means spinner disappears.
                                # Actually, we should pause live or just print.
                                live.stop()
                                _print_tool_result_summary(func_name, str(func_result))
                                live.start()

                            # Follow-up response
                            live.update(Spinner("dots", text="Finalizing...", style="cyan"))
                            second_response = client.chat.completions.create(
                                model=config["model"],
                                messages=messages
                            )
                            final_content = second_response.choices[0].message.content
                            messages.append({"role": "assistant", "content": final_content})
                            live.stop()
                            model_name = config.get("model", "StoryForge")
                            console.print(Panel(Markdown(final_content), title=model_name, style="blue", title_align="right"))
                            
                        else:
                            # Normal response
                            content = response_message.content
                            messages.append({"role": "assistant", "content": content})
                            live.stop()
                            model_name = config.get("model", "StoryForge")
                            console.print(Panel(Markdown(content), title=model_name, style="blue", title_align="right"))
                            
                    except Exception as e:
                        live.stop()
                        raise e # Re-raise to be caught by outer try/except
                        
            except KeyboardInterrupt:
                console.print("\n[yellow]Generation cancelled by user.[/]")
                # Remove the last user message if it wasn't processed? 
                # Actually, if we interrupted, we might want to keep it or remove it.
                # Let's keep it but maybe mark it? For simplicity, just return to prompt.
                continue
            except Exception as e:
                console.print(f"[bold red]Error:[/ {e}")
                _safe_log(f"chat_error | {e}", error=True)

    # Save on exit
    if project_name and len(messages) > 2:
        try:
            console.print("[dim]Saving session...[/]")
            compress_context_impl(messages, client, config["model"], len(messages))
            console.print("[green]Session saved.[/]")
        except Exception as e:
            console.print(f"[red]Failed to save: {e}[/]")
def chat_mode(client, config, tools, tool_map, initial_messages=None, project_name=None):
    """
    Wrapper for chat mode, handles GUI or plain.
    """
    try:
        # Try GUI
        chat_mode_gui(client, config, tools, tool_map, initial_messages, project_name)
    except Exception as e:
        # If gui fails (e.g. window too small, missing lib), fallback
        print(f"GUI mode unavailable ({e}), using plain chat.")
        plain_chat_loop(client, config, tools, tool_map, initial_messages, project_name)


def interactive_cli(client, config, tools, tool_map) -> None:
    """
    Enhanced project selection menu with browsing and preview.
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt, IntPrompt
        from rich.text import Text
        from .tools.ui_helpers import list_all_projects, display_projects_table, display_project_preview, get_project_tips
        from .tools.project import get_output_root, sanitize_folder_name, set_active_project_folder
        import random
        import glob
        
        console = Console()
        
        # Welcome banner
        welcome = Text()
        welcome.append("=" * 50 + "\n", style="bold blue")
        welcome.append("  StoryForge AI", style="bold cyan")
        welcome.append(" - Creative Writing Studio\n", style="bold blue")
        welcome.append("=" * 50 + "\n", style="bold blue")
        welcome.append("\n" + random.choice(get_project_tips()), style="dim italic")
        console.print(Panel(welcome, border_style="blue"))
        
        # List projects
        output_root = get_output_root()
        projects = list_all_projects(output_root)
        
        initial_messages = None
        project_name = None
        
        if projects:
            display_projects_table(console, projects)
            console.print("\n[bold]Quick Actions:[/]")
            console.print("  [cyan]1-9[/] -> Load project by number")
            console.print("  [cyan]R[/] -> Resume latest  |  [cyan]N [name][/] -> New project (optional name)  |  [cyan]P[/] -> Preview  |  [cyan]X[/] -> Exit")
            
            while True:
                choice = Prompt.ask("\nYour choice", default="R", console=console).strip()
                if not choice:
                    continue
                    
                upper_choice = choice.upper()
                
                if upper_choice == 'X':
                    console.print("[red]Goodbye![/]")
                    sys.exit(0)
                    
                elif upper_choice.startswith('N'):
                    # Handle N or N <name>
                    parts = choice.split(maxsplit=1)
                    if len(parts) > 1:
                        project_name = parts[1]
                        console.print(f"[cyan]Starting new project: {project_name}[/]")
                    else:
                        console.print("[cyan]Starting new unnamed session...[/]")
                        project_name = None
                    break
                    
                elif upper_choice == 'R':
                    # Resume latest
                    project_name = projects[0]["name"]
                    console.print(f"[cyan]Resuming: {ascii_only_ui(project_name)}[/]")
                    break
                    
                elif upper_choice == 'P':
                    # Preview mode
                    proj_num = IntPrompt.ask("Preview project #", console=console)
                    if 1 <= proj_num <= len(projects):
                        display_project_preview(console, projects[proj_num - 1])
                        if Prompt.ask("\nLoad this project? (Y/n)", default="Y", console=console).upper() == 'Y':
                            project_name = projects[proj_num - 1]["name"]
                            break
                    else:
                        console.print("[red]Invalid project number.[/]")
                    continue
                    
                elif choice.isdigit():
                    proj_num = int(choice)
                    if 1 <= proj_num <= len(projects):
                        project_name = projects[proj_num - 1]["name"]
                        console.print(f"[cyan]Loading: {ascii_only_ui(project_name)}[/]")
                        break
                    else:
                        console.print(f"[red]Invalid number {proj_num}. Range is 1-{len(projects)}.[/]")
                        console.print("[yellow]Please try again or use 'N' for a new project.[/]")
                        continue
                else:
                    # Treat as project name
                    project_name = choice
                    console.print(f"[cyan]Loading/Creating: {ascii_only_ui(project_name)}[/]")
                    break
        else:
            console.print("\n[yellow]No existing projects found.[/]")
            if Prompt.ask("Start a new project? (Y/n)", default="Y", console=console).upper() == 'Y':
                project_name = None
            else:
                console.print("[red]Goodbye![/]")
                sys.exit(0)
        
        # Load project context if we have a project name
        if project_name:
            sanitized = sanitize_folder_name(project_name)
            project_path = os.path.join(output_root, sanitized)
            if os.path.isdir(project_path):
                set_active_project_folder(project_path)
                
                # Show dashboard immediately upon loading
                from .tools.ui_helpers import display_dashboard_impl
                try:
                    display_dashboard_impl(console, project_path)
                except Exception:
                    pass # Fallback silently if dashboard fails, chat will still work

                summary_pattern = os.path.join(project_path, ".context_summary_*.md")
                summary_files = glob.glob(summary_pattern)
                if summary_files:
                    latest_summary = max(summary_files, key=os.path.getmtime)
                    try:
                        with open(latest_summary, 'r', encoding='utf-8') as f:
                            context = f.read()
                        initial_messages = [
                            {"role": "system", "content": get_system_prompt()},
                            {"role": "user", "content": f"[RECOVERED CONTEXT]\n\n{context}\n\n[END RECOVERED CONTEXT]"}
                        ]
                        console.print(f"[green]Loaded context from {os.path.basename(latest_summary)}[/green]")
                    except Exception as e:
                        console.print(f"[red]Failed to load context: {e}[/red]")
                console.print(f"[bold green]Active project: {ascii_only_ui(sanitized)}[/]\n")
            else:
                console.print(f"[yellow]Project '{ascii_only_ui(sanitized)}' not found. Will create on first write.[/]\n")
        
        chat_mode(client, config, tools, tool_map, initial_messages=initial_messages, project_name=project_name or None)
    except ImportError:
        print("Rich not installed. Falling back to plain CLI.")
        print("Install with 'pip install rich' for GUI-like interface.")
        # Fallback plain interactive
        print("\n=== StoryForge AI - Plain Interactive Mode ===")
        project_name = input("Enter project name (optional): ").strip()
        # Simple loop
        while True:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ['/exit', 'quit', 'q']:
                break
            print(f"Agent: (Simulated response - full implementation needs Rich or loop)")
            print("Type /exit to quit.")


def plain_chat_loop(client, config, tools, tool_map, initial_messages=None, project_name=None):
    """
    Plain text fallback chat loop.
    """
    from .tools.ui_input import process_user_input
    from .tools.ui_helpers import CHAT_HELP_COMMANDS

    messages = initial_messages or [{"role": "system", "content": get_system_prompt()}]
    print("\n=== Plain Chat Mode ===")
    print("Type your message or /help for commands.")
    print("Type your message or /help for commands.")
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except KeyboardInterrupt:
            print("\nExiting...")
            break
            
        if not user_input:
            continue

        action, normalized_input, skip_append, warning = process_user_input(messages, user_input)

        if action == "noop":
            if warning:
                print(ascii_only_ui(warning))
            continue
        if action == "exit":
            break
        if action == "help":
            print("\nAvailable Commands:")
            for command, description in CHAT_HELP_COMMANDS:
                print(f"  {command} - {description}")
            continue
        if action == "resume":
            print("Command '/resume' is only available in the GUI mode.")
            continue
        if action == "status":
            print(display_status_summary_impl())
            continue
        if action == "save":
            compression_result = compress_context_impl(
                messages=messages,
                client=client,
                model=config["model"],
                keep_recent=len(messages),
            )
            summary_file = compression_result.get("summary_file")
            if summary_file:
                print(f"Context saved to: {ascii_only_ui(summary_file)}")
            else:
                print("Context saved.")
            continue
        if action == "new":
            messages = [{"role": "system", "content": get_system_prompt()}]
            print("Started a new conversation.")
            continue
        if action == "brainstorm":
            # Switch system prompt to brainstorm mode
            brainstorm_prompt = generate_dynamic_system_prompt("brainstorm")
            # Update system message
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] = brainstorm_prompt
            else:
                messages.insert(0, {"role": "system", "content": brainstorm_prompt})
            print("\n=== Entered Writers' Room (Brainstorm Mode) ===")
            print("I am now your Story Consultant. Let's discuss ideas!")
            continue
        if action == "critique":
            # Parse filename from input (e.g., "/critique Chapter 1.md")
            parts = normalized_input.split(" ", 1)
            if len(parts) > 1:
                filename = parts[1].strip()
                # Inject a user message requesting critique
                user_msg = f"Please critique {filename}."
                messages.append({"role": "user", "content": user_msg})
                # The loop will continue and send this to the model, which will call the tool
                print(f"Requesting critique for {filename}...")
                # We don't 'continue' here because we want to fall through to 'send' logic
                # But wait, 'action' is 'critique', not 'send'. 
                # We need to manually trigger the send or change action to 'send'.
                # Simpler: Just print instruction and let user type? 
                # No, better to automate.
                # Let's set action to 'send' and prepared_input to the request.
                action = "send" # Override action to ensure message is sent
                prepared_input = user_msg # Override prepared_input with the critique request
            else:
                print("Usage: /critique <filename>")
                continue
        if action == "dashboard":
            try:
                from .tools.ui_helpers import display_dashboard_impl
                from .tools.project import get_active_project_folder
                project_folder = get_active_project_folder()
                if project_folder:
                    from rich.console import Console
                    console = Console()
                    display_dashboard_impl(console, project_folder)
                else:
                    print("No active project to show dashboard for.")
            except ImportError:
                print("Rich is not installed or dashboard failed.")
            continue
        if action in {"projects", "files", "switch", "troubleshoot"}:
            print(f"Command '{action}' is only available in the GUI mode.")
            continue
        if action == "clear":
            os.system('cls' if os.name == 'nt' else 'clear')
            continue

        prepared_input = normalized_input or ""
        if not skip_append:
            messages.append({"role": "user", "content": prepared_input})

        # Stream response
        print("Agent: ", end="", flush=True)
        response = ""
        max_attempts = max(1, config.get("retry_attempts", 2))
        for attempt in range(1, max_attempts + 1):
            try:
                stream = client.chat.completions.create(
                    model=config["model"],
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    stream=True,
                )
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        print(content, end="", flush=True)
                        response += content
                    if chunk.choices[0].delta.tool_calls:
                        # Handle tool calls in stream (simplified)
                        pass
                print()
                break
            except Exception as e:
                log_provider_error(
                    e,
                    attempt,
                    max_attempts,
                    user_input,
                    "plain chat response"
                )
                if attempt == max_attempts or not should_retry_provider_error(e):
                    print(f"\nError: {ascii_only_ui(str(e))}")
                    break
                _sleep_backoff(attempt)
        messages.append({"role": "assistant", "content": response})

        # Execute tools if any (simplified, sequential)
        # Full tool handling would be here


def main():
    """Main entry point."""
    # Parse args first
    args = parse_args()
    
    # If status, already handled in get_user_input, but since we moved, handle here if needed
    # But status is handled in get_user_input, but to avoid call, check
    if args.status:
        # Status handled in get_user_input, but since we changed, insert handling
        from .tools.project import sanitize_folder_name, get_output_root, set_active_project_folder
        sanitized = sanitize_folder_name(args.status)
        project_path = os.path.join(get_output_root(), sanitized)
        if os.path.isdir(project_path):
            set_active_project_folder(project_path)
            print(display_status_summary_impl())
        else:
            print(f"PROJECT STATUS: {sanitized} | not found")
        sys.exit(0)
    
    # Load config
    try:
        config = get_provider_config()
        if args.prompt or args.recover:
            print("Configuration loaded.")
    except Exception as e:
        print(f"Config error: {e}")
        print("Check .env for API keys.")
        sys.exit(1)
    
    # Setup client
    api_key = config["api_key"]
    base_url = config["base_url"]
    model_name = config["model"]
    default_headers = config.get("headers")
    
    client_kwargs = {"api_key": api_key, "base_url": base_url}
    if default_headers:
        client_kwargs["default_headers"] = default_headers
    client = OpenAI(**client_kwargs)
    
    # Load tools
    tools = get_tool_definitions()
    tool_map = get_tool_map()

    # Check if non-interactive (autonomous mode with multi-agent pipeline)
    if args.prompt or args.recover:
        user_prompt, is_recovery = get_user_input()

        console = get_rich_console()

        if is_recovery:
            # TODO: Recovery mode not yet supported in orchestrator
            print("[WARNING] Recovery mode not yet supported in multi-agent pipeline.")
            print("Falling back to regular generation...")
            print(f"Task: {user_prompt}")

        # ========================================
        # NEW: Multi-Agent Pipeline
        # ========================================
        from .orchestrator import run_autonomous_pipeline

        print(f"\n{'=' * 60}")
        print(f"  Task: {user_prompt}")
        print(f"{'=' * 60}\n")

        # Run the multi-agent orchestrator
        pipeline_results = run_autonomous_pipeline(user_prompt, console=console)

        # Check if pipeline succeeded
        if not pipeline_results["success"]:
            console.print("[red]Story generation failed. Check logs for details.[/]")
            sys.exit(1)

        # Extract project info for interactive mode
        planning_result = pipeline_results.get("planning", {})
        project_path = planning_result.get("project_path")

        if project_path:
            # Load context for interactive mode
            import glob
            summary_pattern = os.path.join(project_path, ".context_summary_*.md")
            summary_files = glob.glob(summary_pattern)

            messages = [{"role": "system", "content": get_system_prompt()}]

            if summary_files:
                latest_summary = max(summary_files, key=os.path.getmtime)
                try:
                    with open(latest_summary, 'r', encoding='utf-8') as f:
                        context = f.read()
                    messages.append({
                        "role": "user",
                        "content": f"[PROJECT CONTEXT]\n\n{context}\n\n[END CONTEXT]"
                    })
                    console.print(f"[green]Loaded context for interactive mode[/]")
                except Exception as e:
                    console.print(f"[yellow]Could not load context: {e}[/]")

        # Fall through to original autonomous loop section (will be removed)
        # For now, jump directly to interactive mode
        console.print("\n[bold green]Story generation complete! Entering interactive mode...[/]")
        console.print("[dim]You can now refine, edit, or continue the story.[/]\n")

        # Get project name from path
        project_name = os.path.basename(project_path) if project_path else None

        # Enter interactive chat mode
        chat_mode(client, config, tools, tool_map, initial_messages=messages, project_name=project_name)

    else:
        # Interactive mode (normal startup when no args provided)
        interactive_cli(client, config, tools, tool_map)

if __name__ == "__main__":
    main()
