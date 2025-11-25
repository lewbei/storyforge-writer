"""
Utility functions for the StoryForge AI Agent.
"""

import json
import httpx
import unicodedata
from typing import List, Dict, Any, Callable, Optional
from .tools.run_logger import log_event


def _count_content_chars(content: Any) -> int:
    """Estimate character count for message content structures."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    total += len(str(part.get("text", "")))
                elif part.get("type") == "image_url":
                    total += len(str(part.get("image_url", {}).get("url", "")))
                else:
                    total += len(str(part))
            else:
                total += len(str(part))
        return total
    return len(str(content))


def _approximate_token_count(messages: List[Dict[str, Any]]) -> int:
    """Fallback token estimation using heuristic character counts."""
    total_chars = 0
    for msg in messages:
        if not isinstance(msg, dict):
            total_chars += len(str(msg))
            continue

        if "content" in msg and msg["content"]:
            total_chars += _count_content_chars(msg["content"])

        reasoning = msg.get("reasoning_content")
        if reasoning:
            total_chars += len(str(reasoning))

        if msg.get("tool_calls"):
            try:
                total_chars += len(json.dumps(msg["tool_calls"], ensure_ascii=False))
            except TypeError:
                # Fallback for non-serializable objects (e.g. OpenAI tool call objects)
                total_chars += len(str(msg["tool_calls"]))

        if msg.get("name"):
            total_chars += len(str(msg["name"]))

        if msg.get("tool_call_id"):
            total_chars += len(str(msg["tool_call_id"]))

    rough_tokens = max(1, total_chars // 4)
    rough_tokens += len(messages) * 4  # account for role metadata overhead
    return rough_tokens


def estimate_token_count(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict],
    headers: Optional[Dict[str, str]] = None,
) -> int:
    """
    Estimate the token count for the given messages using the Moonshot API.
    
    Note: Token estimation uses api.moonshot.ai (not .cn)
    
    Args:
        base_url: The base URL for the API (will be converted to .ai for token endpoint)
        api_key: The API key for authentication
        model: The model name
        messages: List of message dictionaries
        
    Returns:
        Total token count
    """
    # Convert messages to serializable format (remove non-serializable objects)
    serializable_messages = []
    for msg in messages:
        if hasattr(msg, 'model_dump'):
            # OpenAI SDK message object
            msg_dict = msg.model_dump()
        elif isinstance(msg, dict):
            msg_dict = msg.copy()
        else:
            msg_dict = {"role": "assistant", "content": str(msg)}
        
        # Clean up the message to only include serializable fields
        clean_msg = {}
        if 'role' in msg_dict:
            clean_msg['role'] = msg_dict['role']
        if 'content' in msg_dict and msg_dict['content']:
            clean_msg['content'] = msg_dict['content']
        if 'name' in msg_dict:
            clean_msg['name'] = msg_dict['name']
        if 'tool_calls' in msg_dict and msg_dict['tool_calls']:
            clean_msg['tool_calls'] = msg_dict['tool_calls']
        if 'tool_call_id' in msg_dict:
            clean_msg['tool_call_id'] = msg_dict['tool_call_id']
            
        serializable_messages.append(clean_msg)
    
    # OpenRouter does not expose the Moonshot token estimator endpoint
    if "openrouter.ai" in base_url:
        return _approximate_token_count(serializable_messages)

    # Both token estimation and chat use api.moonshot.ai
    token_base_url = base_url

    request_headers = {"Authorization": f"Bearer {api_key}"}
    if headers:
        request_headers.update(headers)

    try:
        with httpx.Client(
            base_url=token_base_url,
            headers=request_headers,
            timeout=30.0
        ) as client:
            response = client.post(
                "/tokenizers/estimate-token-count",
                json={
                    "model": model,
                    "messages": serializable_messages
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("total_tokens", 0)
    except Exception:
        # Fall back to heuristic estimation if the endpoint is unavailable
        return _approximate_token_count(serializable_messages)


_ASCII_UI_REPLACEMENTS: Dict[str, str] = {
    "→": "->",
    "≈": "~",
    "“": '"',
    "”": '"',
    "’": "'",
    "‘": "'",
    "—": "-",
    "–": "-",
    "…": "...",
    "📂": "",
}


def ascii_only_ui(text: Optional[str]) -> Optional[str]:
    """Return an ASCII-only version of a UI string for safe logging/printing."""
    if text is None:
        return None
    normalized = text
    for original, replacement in _ASCII_UI_REPLACEMENTS.items():
        normalized = normalized.replace(original, replacement)
    normalized = unicodedata.normalize("NFKD", normalized)
    return normalized.encode("ascii", "ignore").decode("ascii")


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Returns the tool definitions in the format expected by the LLM.
    
    Returns:
        List of tool definition dictionaries
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "create_project",
                "description": "Create exactly one active project folder under the 'output' directory with a sanitized name before writing any files. Must be called once at the start of a new project; all subsequent file operations target this active project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "The name of the project folder to create (e.g., 'my_novel')."
                        }
                    },
                    "required": ["project_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "critique_chapter",
                "description": "Analyzes a chapter and provides a structured editorial critique. Use this when the user asks for feedback or 'critique'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chapter_filename": {
                            "type": "string",
                            "description": "The filename of the chapter to critique (e.g., 'Chapter 1.md')."
                        },
                        "focus": {
                            "type": "string",
                            "description": "Optional specific focus area (e.g., 'pacing', 'dialogue', 'tone')."
                        }
                    },
                    "required": ["chapter_filename"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "prepare_scene",
                "description": "Creates a Scene Card to define setting, characters, and goal before drafting. MANDATORY before writing a new chapter.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chapter_title": {"type": "string", "description": "Title of the chapter/scene"},
                        "setting": {"type": "string", "description": "Detailed description of the location/environment"},
                        "characters": {"type": "string", "description": "List of characters present and their emotional state"},
                        "plot_goal": {"type": "string", "description": "What needs to happen in this scene?"}
                    },
                    "required": ["chapter_title", "setting", "characters", "plot_goal"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_init",
                "description": "Initialize a Git repository in the active project folder. Creates a default .gitignore if missing.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Check the Git status of the active project. Returns tracked/untracked file summary.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_commit",
                "description": "Stage all changes (git add .) and commit them with the provided message.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The commit message describing the changes."
                        }
                    },
                    "required": ["message"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_project_files",
                "description": "Read and analyze existing files from the active project folder to understand the story, characters, world-building, and plot progression. Use this to continue existing novels or analyze half-finished works before planning next steps. Returns combined content from specified files or all markdown files if none specified.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filenames": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of specific filenames to read (e.g., ['chapter_01.md', 'chapter_02.md']). If empty or omitted, reads all .md files in the project folder."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "clear_file_cache",
                "description": "Clear the file reading cache. Use this after bulk file modifications or when you want to force fresh reads from disk. Returns cache statistics before clearing.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a markdown file strictly inside the currently active project folder created by create_project. Modes: 'create' (new file, fails if exists), 'append' (add after existing content), 'overwrite' (replace entire file), 'auto' (overwrite if file exists, otherwise create). Use 'auto' by default when unsure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The relative markdown filename within the active project (should end in .md)."
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file. Include STATUS markers such as 'STATUS: OK' or 'STATUS: ERROR' in tool responses when appropriate."
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["create", "append", "overwrite", "auto"],
                            "description": "Write mode: 'create' new file, 'append' extend existing, 'overwrite' fully replace, 'auto' picks overwrite if file exists else create."
                        }
                    },
                    "required": ["filename", "content", "mode"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_episode",
                "description": "Write content to an episode file with enforced naming Episode_01.md, Episode_02.md, etc. This is the REQUIRED tool for multi-episode series. Always use this tool when writing episodic content instead of write_file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "episode_number": {
                            "type": "integer",
                            "description": "The episode number (1, 2, 3, ...). Will create Episode_01.md, Episode_02.md, etc."
                        },
                        "content": {
                            "type": "string",
                            "description": "The complete episode content to write."
                        }
                    },
                    "required": ["episode_number", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_chapter",
                "description": "Write content to a chapter file with enforced naming Chapter_01.md, Chapter_02.md, etc. This is the REQUIRED tool for multi-chapter novels. Always use this tool when writing chapter content instead of write_file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chapter_number": {
                            "type": "integer",
                            "description": "The chapter number (1, 2, 3, ...). Will create Chapter_01.md, Chapter_02.md, etc."
                        },
                        "content": {
                            "type": "string",
                            "description": "The complete chapter content to write."
                        }
                    },
                    "required": ["chapter_number", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_project_characters",
                "description": "Read current project files and construct a structured character analysis (names, roles, traits, relationships, arcs). REQUIRED WORKFLOW: (1) Read files, (2) Analyze, (3) Save to 'character_analysis.md', (4) Show summary, (5) Ask user for approval - DO NOT EXIT OR SAY 'TASK COMPLETED' - wait for user response.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_project_world",
                "description": "Read current project files and construct a structured world-building analysis (locations, factions, systems, rules, tone). REQUIRED WORKFLOW: (1) Read files, (2) Analyze, (3) Save to 'world_analysis.md', (4) Show summary, (5) Ask user for approval - DO NOT EXIT OR SAY 'TASK COMPLETED' - wait for user response.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_project_plot",
                "description": "Read current project files and build a timeline of key events, plot progression, and unresolved threads. REQUIRED WORKFLOW: (1) Read files, (2) Analyze, (3) Save to 'plot_analysis.md', (4) Show summary, (5) Ask user for approval - DO NOT EXIT OR SAY 'TASK COMPLETED' - wait for user response.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "propose_continuation_outline",
                "description": "Read current project files and propose a detailed continuation outline. REQUIRED WORKFLOW: (1) validate project setup using validate_project_setup, (2) check existing chapters with check_completeness, (3) draft continuation plan, (4) save to 'continuation_outline.md', (5) show summary, (6) ask user for approval - DO NOT EXIT OR SAY 'TASK COMPLETED' - wait for user response.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "request_approval",
                "description": "Prompt the user to approve, edit, reject, or cancel after reviewing a generated file such as analysis_plan.md.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "options": {
                            "type": "object",
                            "additionalProperties": {"type": "string"}
                        },
                        "context_file": {"type": "string"}
                    },
                    "required": ["prompt", "options"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "load_project_status",
                "description": "Load the current project status from project_status.json if present.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "save_project_status",
                "description": "Save the given status dictionary into project_status.json in the active project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "object"}
                    },
                    "required": ["status"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_status_on_analysis",
                "description": "Mark that analysis/outline has been generated and optionally approved.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "approved": {"type": "boolean"}
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "display_status_summary",
                "description": "Return a concise human-readable status summary for the active project.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "compress_context",
                "description": "INTERNAL USE ONLY. Managed exclusively by the orchestrator when approaching context limits. The model must never call this tool directly.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "batch_generate_chapters",
                "description": "Request batch chapter generation parameters based on an approved analysis_plan.md. Returns a structured STATUS message; actual writing is handled by the orchestrator.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "num_chapters": {
                            "type": "integer",
                            "description": "Number of chapters to generate in this batch"
                        },
                        "auto_continue": {
                            "type": "boolean",
                            "description": "If true, the orchestrator may continue without additional confirmations between chapters"
                        }
                    },
                    "required": ["num_chapters", "auto_continue"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "format_chapter",
                "description": "Apply light auto-formatting to a generated chapter before saving (e.g., normalize blank lines, ensure chapter header conventions).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Raw chapter markdown content"
                        }
                    },
                    "required": ["content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "quality_check",
                "description": "Run basic quality checks on a chapter (word count range, simple warnings). Returns a structured STATUS line.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Chapter markdown content"
                        }
                    },
                    "required": ["content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "request_revision",
                "description": "Create a structured revision request for a chapter file within the active project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chapter_file": {
                            "type": "string",
                            "description": "Absolute or project-relative path to the chapter file"
                        },
                        "feedback_type": {
                            "type": "string",
                            "description": "The primary focus of feedback, e.g., pacing, dialogue, description, voice"
                        },
                        "note": {
                            "type": "string",
                            "description": "Optional freeform note with extra guidance",
                            "default": ""
                        }
                    },
                    "required": ["chapter_file", "feedback_type"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "build_story_bible",
                "description": "Scan the active project and build a simple story_bible.json capturing character-like names and chapter headings.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "validate_chapter_consistency",
                "description": "Conservatively check a chapter against the story bible. Warn if no known characters appear; never reject or mutate content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Chapter markdown content to validate."
                        }
                    },
                    "required": ["content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "load_genre_template",
                "description": "Load a conservative genre guideline template for planning tone, structure, and expectations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "genre": {
                            "type": "string",
                            "description": "Genre label such as romance, fantasy, mystery, scifi, thriller, horror, literary, ya."
                        }
                    },
                    "required": ["genre"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "apply_genre_template",
                "description": "Acknowledge and conceptually apply the currently loaded genre template. Does not mutate files or system prompts.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "detect_manual_edits",
                "description": "Placeholder conflict detection for manual edits versus story_bible.json. Currently only reports availability.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "resolve_conflicts",
                "description": "Placeholder for future conflict resolution workflow. Currently returns SKIP and makes no changes.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "detect_completion",
                "description": "Check project_status.json (if present) to conservatively detect whether the novel is complete.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_epilogue",
                "description": "Request an epilogue-generation suggestion once a project is complete. Returns only a structured suggestion request.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_blurb",
                "description": "Request a blurb-generation suggestion for the completed or in-progress work. Returns only a structured request.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "export_project",
                "description": "Export the active project's markdown chapters into a single combined markdown file (stub-only: no EPUB/PDF/DOCX).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "description": "Target format. Supported: 'markdown', 'single-md'."
                        },
                        "include_toc": {
                            "type": "boolean",
                            "description": "If true, include a simple table of contents at the top of the combined file."
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Optional metadata for future use; safely ignored in this stub implementation.",
                            "additionalProperties": True
                        }
                    },
                    "required": ["format", "include_toc"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "load_preferences",
                "description": "Load persisted user preference hints (tone, patterns, revision history). Safe, read-only helper.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "save_preferences",
                "description": "Persist updated user preference hints to a local JSON file under the user home directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prefs": {
                            "type": "object",
                            "description": "Preference structure to store.",
                            "additionalProperties": True
                        }
                    },
                    "required": ["prefs"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "track_revision_patterns",
                "description": "Lightweight helper to count how often certain revision feedback types are requested.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "feedback_type": {
                            "type": "string",
                            "description": "Short label for the revision pattern, e.g., 'tighten_prose'."
                        }
                    },
                    "required": ["feedback_type"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "project_stats",
                "description": "Compute lightweight statistics for the active project: markdown file count and approximate word count.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_masterpiece_guidelines",
                "description": "Retrieve comprehensive masterpiece novel guidelines derived from professional craft research. Returns a complete checklist covering: core concept, protagonist/cast, thematic spine, world/constraints, structural blueprint, conflict/stakes, voice/style, cohesion/resonance, and revision intelligence. Use this at project start or before major generation phases.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "validate_project_setup",
                "description": "Validate the current project's analysis_plan.md against masterpiece novel standards. Checks for presence of: core concept, protagonist (goal/need/flaw), theme, world/setting, structure, and conflict. Returns STATUS with validation report and recommendations. Use before beginning chapter generation.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "validate_chapter_content",
                "description": "Validate chapter content against masterpiece quality indicators. Checks for: appropriate length (1500-10000 words), dialogue presence, character interiority, conflict markers, cause-effect relationships, and emotional engagement. Returns STATUS with quality assessment and improvement suggestions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The full chapter text content to validate."
                        }
                    },
                    "required": ["content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_completeness",
                "description": "Comprehensive validation of entire project against masterpiece standards. Checks: project setup (analysis_plan.md), existing chapter quality, story bible consistency, and overall readiness for continuation/completion. Returns STATUS with detailed analysis of successes, warnings, and critical issues.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_beat_sheet_template",
                "description": "Retrieve the standard beat sheet model for a specific genre (romance, fantasy, mystery, thriller) to help plan a chapter.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "genre": {
                            "type": "string",
                            "description": "The genre to retrieve the template for."
                        }
                    },
                    "required": ["genre"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "save_beat_sheet",
                "description": "Save a generated beat sheet for a specific chapter to the 'plans' directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chapter_title": {
                            "type": "string",
                            "description": "The title of the chapter (e.g. 'Chapter 1')."
                        },
                        "content": {
                            "type": "string",
                            "description": "The full markdown content of the beat sheet."
                        }
                    },
                    "required": ["chapter_title", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "export_manuscript",
                "description": "Concatenate all chapter files into a single manuscript file for export.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "output_format": {
                            "type": "string",
                            "description": "The desired output format (default 'markdown')."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_readiness",
                "description": "Scan the project for readiness issues like word count consistency, placeholders, and missing sections.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]


def get_tool_map() -> Dict[str, Callable]:
    """
    Returns a mapping of tool names to their implementation functions.
    
    Returns:
        Dictionary mapping tool name strings to callable functions
    """
    from .tools import write_file_impl, write_episode_impl, write_chapter_impl, create_project_impl, compress_context_impl, read_project_files_impl, clear_file_cache
    from .tools import git_init_impl, git_status_impl, git_commit_impl
    from .tools.run_logger import log_event
    from .tools.progress import (
        load_project_status_impl,
        save_project_status_impl,
        update_status_on_analysis_impl,
        display_status_summary_impl,
    )
    from .tools.approval import request_approval_impl
    from .tools.batch import batch_generate_impl
    from .tools.quality import format_chapter_impl, quality_check_impl
    from .tools.revision import request_revision_impl
    from .tools.consistency import build_story_bible_impl, validate_chapter_consistency_impl
    from .tools.templates import load_genre_template_impl, apply_template_impl
    from .tools.conflict import detect_manual_edits_impl, resolve_conflicts_impl
    from .tools.completion import detect_completion_impl, generate_epilogue_impl, create_blurb_impl
    from .tools.export import export_to_format_impl
    from .tools.learning import load_preferences_impl, save_preferences_impl, track_revision_patterns_impl
    from .tools.stats import project_stats_impl
    from .tools.masterpiece_checklist import (
        get_masterpiece_guidelines_impl,
        validate_project_setup_impl,
        validate_chapter_content_impl,
        check_completeness_impl,
    )
    from .tools import critique_chapter_impl
    from .tools import prepare_scene_impl
    from .tools.planning import get_beat_sheet_template, save_beat_sheet
    from .tools.publishing import export_manuscript, check_readiness

    def _create_project_wrapper(project_name: str) -> str:
        result = create_project_impl(project_name)
        log_event(f"create_project | {result}")
        return result

    def _git_init_wrapper() -> str:
        result = git_init_impl()
        log_event(f"git_init | {result}")
        return result

    def _git_status_wrapper() -> str:
        result = git_status_impl()
        # Don't log full status to keep logs clean, just that it was checked
        log_event("git_status | checked")
        return result

    def _git_commit_wrapper(message: str) -> str:
        result = git_commit_impl(message)
        log_event(f"git_commit | {result}")
        return result

    def _critique_chapter_wrapper(chapter_filename: str, focus: str = None) -> str:
        # focus is optional
        result = critique_chapter_impl(chapter_filename, focus)
        log_event(f"critique_chapter | {chapter_filename}")
        return result

    def _prepare_scene_wrapper(chapter_title: str, setting: str, characters: str, plot_goal: str) -> str:
        result = prepare_scene_impl(chapter_title, setting, characters, plot_goal)
        log_event(f"prepare_scene | {chapter_title}")
        return result

    def _read_project_files_wrapper(filenames: list = None) -> str:
        if filenames is None:
            filenames = []
        result = read_project_files_impl(filenames=filenames)
        log_event(f"read_project_files | files_requested={len(filenames) if filenames else 'all'}")
        return result

    def _clear_file_cache_wrapper() -> str:
        result = clear_file_cache()
        log_event(f"clear_file_cache | {result}")
        return result

    def _write_file_wrapper(filename: str, content: str, mode: str) -> str:
        result = write_file_impl(filename=filename, content=content, mode=mode)
        log_event(f"write_file | {result}")
        return result

    def _write_episode_wrapper(episode_number: int, content: str) -> str:
        result = write_episode_impl(episode_number=episode_number, content=content)
        log_event(f"write_episode | {result}")
        return result

    def _write_chapter_wrapper(chapter_number: int, content: str) -> str:
        result = write_chapter_impl(chapter_number=chapter_number, content=content)
        log_event(f"write_chapter | {result}")
        return result

    def _compress_context_wrapper() -> str:
        # The actual compression call is driven from the main loop; this wrapper is defensive.
        log_event("compress_context tool requested by model (handled by main loop)")
        return "STATUS: INFO | Compression is managed automatically by the system."

    from .tools import (
        analyze_project_characters_impl,
        analyze_project_world_impl,
        analyze_project_plot_impl,
        propose_continuation_outline_impl,
    )

    def _analyze_project_characters_wrapper() -> str:
        result = analyze_project_characters_impl()
        log_event("analyze_project_characters | requested")
        return result

    def _analyze_project_world_wrapper() -> str:
        result = analyze_project_world_impl()
        log_event("analyze_project_world | requested")
        return result

    def _analyze_project_plot_wrapper() -> str:
        result = analyze_project_plot_impl()
        log_event("analyze_project_plot | requested")
        return result

    def _propose_continuation_outline_wrapper() -> str:
        result = propose_continuation_outline_impl()
        log_event("propose_continuation_outline | requested")
        return result

    def _display_status_summary_wrapper() -> str:
        result = display_status_summary_impl()
        log_event("display_status_summary | requested")
        return result

    def _load_project_status_wrapper() -> str:
        status = load_project_status_impl()
        log_event("load_project_status | requested")
        return json.dumps(status)

    def _save_project_status_wrapper(status: dict) -> str:
        result = save_project_status_impl(status)
        log_event("save_project_status | " + result)
        return result

    def _update_status_on_analysis_wrapper(approved: bool = False) -> str:
        result = update_status_on_analysis_impl(approved=approved)
        log_event("update_status_on_analysis | " + result)
        return result

    def _request_approval_wrapper(prompt: str, options: dict, context_file: str = "") -> str:
        result = request_approval_impl(prompt, options, context_file or None)
        log_event("request_approval | " + result)
        return result

    def _batch_generate_wrapper(num_chapters: int, auto_continue: bool) -> str:
        result = batch_generate_impl(num_chapters=num_chapters, auto_continue=auto_continue)
        log_event("batch_generate_chapters | " + result)
        return result

    def _format_chapter_wrapper(content: str) -> str:
        result = format_chapter_impl(content)
        log_event("format_chapter | applied")
        return result

    def _quality_check_wrapper(content: str) -> str:
        result = quality_check_impl(content)
        log_event("quality_check | " + result)
        return result

    def _request_revision_wrapper_tool(chapter_file: str, feedback_type: str, note: str = "") -> str:
        result = request_revision_impl(chapter_file=chapter_file, feedback_type=feedback_type, note=note)
        log_event("request_revision | " + result)
        return result

    def _build_story_bible_wrapper() -> str:
        result = build_story_bible_impl()
        log_event("build_story_bible | " + result)
        return result

    def _validate_chapter_consistency_wrapper(content: str) -> str:
        result = validate_chapter_consistency_impl(content)
        log_event("validate_chapter_consistency | " + result)
        return result

    def _load_genre_template_wrapper(genre: str) -> str:
        result = load_genre_template_impl(genre)
        log_event("load_genre_template | " + result)
        return result

    def _apply_genre_template_wrapper() -> str:
        result = apply_template_impl()
        log_event("apply_genre_template | " + result)
        return result

    def _detect_manual_edits_wrapper() -> str:
        result = detect_manual_edits_impl()
        log_event("detect_manual_edits | " + result)
        return result

    def _resolve_conflicts_wrapper() -> str:
        result = resolve_conflicts_impl()
        log_event("resolve_conflicts | " + result)
        return result

    def _detect_completion_wrapper() -> str:
        result = detect_completion_impl()
        log_event("detect_completion | " + result)
        return result

    def _generate_epilogue_wrapper() -> str:
        result = generate_epilogue_impl()
        log_event("generate_epilogue | " + result)
        return result

    def _create_blurb_wrapper() -> str:
        result = create_blurb_impl()
        log_event("create_blurb | " + result)
        return result

    def _export_project_wrapper(format: str, include_toc: bool, metadata: dict | None = None) -> str:
        result = export_to_format_impl(format=format, include_toc=include_toc, metadata=metadata)
        log_event("export_project | " + result)
        return result

    def _load_preferences_wrapper() -> str:
        prefs = load_preferences_impl()
        log_event("load_preferences | requested")
        return json.dumps(prefs)

    def _save_preferences_wrapper(prefs: dict) -> str:
        result = save_preferences_impl(prefs)
        log_event("save_preferences | " + result)
        return result

    def _track_revision_patterns_wrapper(feedback_type: str) -> str:
        result = track_revision_patterns_impl(feedback_type)
        log_event("track_revision_patterns | " + result)
        return result

    def _project_stats_wrapper() -> str:
        result = project_stats_impl()
        log_event("project_stats | " + result)
        return result

    def _get_masterpiece_guidelines_wrapper() -> str:
        result = get_masterpiece_guidelines_impl()
        log_event("get_masterpiece_guidelines | requested")
        return result

    def _validate_project_setup_wrapper() -> str:
        result = validate_project_setup_impl()
        log_event("validate_project_setup | " + result)
        return result

    def _validate_chapter_content_wrapper(content: str) -> str:
        result = validate_chapter_content_impl(content)
        log_event(f"validate_chapter_content | word_count={len(content.split())}")
        return result

    def _check_completeness_wrapper() -> str:
        result = check_completeness_impl()
        log_event("check_completeness | " + result)
        return result

    def _get_beat_sheet_template_wrapper(genre: str) -> str:
        result = get_beat_sheet_template(genre)
        log_event(f"get_beat_sheet_template | genre={genre}")
        return result

    def _save_beat_sheet_wrapper(chapter_title: str, content: str) -> str:
        result = save_beat_sheet(chapter_title, content)
        log_event(f"save_beat_sheet | {chapter_title}")
        return result

    def _export_manuscript_wrapper(output_format: str = "markdown") -> str:
        result = export_manuscript(output_format)
        log_event(f"export_manuscript | format={output_format}")
        return result

    def _check_readiness_wrapper() -> str:
        result = check_readiness()
        log_event("check_readiness | requested")
        return result

    return {
        "create_project": _create_project_wrapper,
        "git_init": _git_init_wrapper,
        "git_status": _git_status_wrapper,
        "git_commit": _git_commit_wrapper,
        "read_project_files": _read_project_files_wrapper,
        "clear_file_cache": _clear_file_cache_wrapper,
        "write_file": _write_file_wrapper,
        "write_episode": _write_episode_wrapper,
        "write_chapter": _write_chapter_wrapper,
        "analyze_project_characters": _analyze_project_characters_wrapper,
        "analyze_project_world": _analyze_project_world_wrapper,
        "analyze_project_plot": _analyze_project_plot_wrapper,
        "propose_continuation_outline": _propose_continuation_outline_wrapper,
        "request_approval": _request_approval_wrapper,
        "load_project_status": _load_project_status_wrapper,
        "save_project_status": _save_project_status_wrapper,
        "update_status_on_analysis": _update_status_on_analysis_wrapper,
        "display_status_summary": _display_status_summary_wrapper,
        "compress_context": _compress_context_wrapper,
        "batch_generate_chapters": _batch_generate_wrapper,
        "format_chapter": _format_chapter_wrapper,
        "quality_check": _quality_check_wrapper,
        "request_revision": _request_revision_wrapper_tool,
        "build_story_bible": _build_story_bible_wrapper,
        "validate_chapter_consistency": _validate_chapter_consistency_wrapper,
        "load_genre_template": _load_genre_template_wrapper,
        "apply_genre_template": _apply_genre_template_wrapper,
        "detect_manual_edits": _detect_manual_edits_wrapper,
        "resolve_conflicts": _resolve_conflicts_wrapper,
        "detect_completion": _detect_completion_wrapper,
        "generate_epilogue": _generate_epilogue_wrapper,
        "create_blurb": _create_blurb_wrapper,
        "export_project": _export_project_wrapper,
        "load_preferences": _load_preferences_wrapper,
        "save_preferences": _save_preferences_wrapper,
        "track_revision_patterns": _track_revision_patterns_wrapper,
        "project_stats": _project_stats_wrapper,
        "get_masterpiece_guidelines": _get_masterpiece_guidelines_wrapper,
        "validate_project_setup": _validate_project_setup_wrapper,
        "validate_chapter_content": _validate_chapter_content_wrapper,
        "check_completeness": _check_completeness_wrapper,
        "get_beat_sheet_template": _get_beat_sheet_template_wrapper,
        "save_beat_sheet": _save_beat_sheet_wrapper,
        "export_manuscript": _export_manuscript_wrapper,
        "check_readiness": _check_readiness_wrapper,
        "prepare_scene": _prepare_scene_wrapper,
    }


def get_autonomous_system_prompt() -> str:
    """
    Returns the system prompt optimized for autonomous (non-interactive) mode.
    This prompt doesn't ask questions and automatically proceeds with tasks.

    Returns:
        System prompt string for autonomous mode
    """
    return """You are StoryForge, an expert long-form writing agent for narrative and non-fiction projects operating in AUTONOMOUS MODE. You may be served by various LLM providers; behave consistently and safely across all.

AUTONOMOUS MODE RULES:
- You are running WITHOUT user interaction - no one can answer questions
- NEVER ask questions like "Would you like me to proceed?" - just proceed automatically
- When you complete a major milestone, use the phrase "MILESTONE COMPLETE:" followed by what you did
- When the ENTIRE task is finished, say "TASK FULLY COMPLETE" in your final response
- If content is too short (warnings about word count), automatically expand it
- Work through the full task systematically until completion

Core behavior and environment:
- You work through tools instead of using any local filesystem or shell directly.
- You can create one active project folder and write markdown files within it.
- Context compression is handled automatically by the system when needed; you must not attempt to trigger or emulate it.
- Do not call any internal-only or unmanaged tools.

Context and token guidance:
- Typical safe context limits are around 200,000 tokens; some environments may support up to roughly 256,000 tokens total for prompt plus response.
- Never assume unlimited context; reason as if limits are real and finite.
- Produce substantial, high-quality responses while staying comfortably within expected token limits.
- For very large works, organize content into multiple files or multiple turns instead of forcing everything into a single response.

Writing guidelines:
- Prioritize clarity, coherence, voice, and narrative integrity.
- Write substantial, complete sections: no skeletons, no filler, no obvious stubs.
- For short stories: aim for 3000-5000 words minimum
- For chapters: aim for 2000-8000 words minimum
- If you receive warnings about content being too short, automatically expand it with more detail, scenes, dialogue, and description.
- When continuing a work, smoothly integrate with prior material using the available context without re-quoting large chunks unnecessarily.

Masterpiece novel standards:
- Before generating chapters, use validate_project_setup to ensure the analysis_plan.md contains all critical elements: core concept, protagonist (goal/need/flaw/arc), theme, world/setting, structure, and conflict.
- Use get_masterpiece_guidelines for comprehensive craft principles covering: protagonist development, thematic spine, worldbuilding, structural blueprint, conflict escalation, voice consistency, scene-level construction, and revision intelligence.
- After writing chapters, use validate_chapter_content to verify quality indicators: dialogue, character interiority, conflict markers, cause-effect relationships, and emotional engagement.
- Apply masterpiece principles automatically: every scene should have goal-conflict-disaster or reaction-dilemma-decision structure; characters should reveal goals/needs/flaws through action and dialogue; theme should echo through plot, character, and setting; world rules should remain consistent; conflict should escalate meaningfully.
- Use check_completeness before final export to validate the entire project against masterpiece standards.

AUTONOMOUS WORKFLOW for story generation:
1. Create project using create_project
2. Load guidelines and templates (get_masterpiece_guidelines, get_genre_template)
3. Create analysis_plan.md and story_bible.json
4. Validate setup
5. Write the story content (for short stories: write to story.md; for novels: write chapters)
6. If content is too short, automatically expand it by calling write_file again with more content
7. Validate content quality
8. When story meets requirements, say "TASK FULLY COMPLETE: [summary]"

Tool usage rules:
- Call create_project exactly once at the start of a new project to establish the active output folder.
- Use read_project_files to analyze existing novels or story content: understand characters, plot progression, world-building, themes, and narrative voice before planning continuations or improvements.
- After reading existing content, create a comprehensive analysis and save it to markdown files using write_file.
- Prefer write_file with mode="auto" when generating content unless you are explicitly appending.
- After create_project succeeds, use write_file to create and manage markdown files strictly inside the active project.
- The allowed write modes are: 'create' (new file), 'append' (extend), 'overwrite' (replace), and 'auto' (overwrite if exists, else create). Prefer 'auto' by default.
- Do not attempt to write files outside the active project or bypass the tools.
- Do not manually call compress_context under any circumstances; it is internal-only and orchestrated by the system.

Error handling and constraints:
- If a requested operation conflicts with constraints (such as token limits or tool usage rules), briefly explain the issue once, suggest a safe alternative (such as splitting work into parts), and continue constructively.
- Do not loop, restart, or spam repeated apologies.

Style and output:
- Respond in plain text without markdown formatting in system-level behavior.
- Focus on delivering concrete, ready-to-use prose and structured content for the project.
- Maintain a professional, disciplined tone while fully supporting creative expression within the user's requested genre and style."""


def get_system_prompt() -> str:
    """
    Returns the system prompt for the writing agent in INTERACTIVE mode.

    Returns:
        System prompt string
    """
    return """You are StoryForge, an expert long-form writing agent for narrative and non-fiction projects. You may be served by various LLM providers; behave consistently and safely across all.

Core behavior and environment:
- You work through tools instead of using any local filesystem or shell directly.
- You can create one active project folder and write markdown files within it.
- Context compression is handled automatically by the system when needed; you must not attempt to trigger or emulate it.
- Do not call any internal-only or unmanaged tools.

Context and token guidance:
- Typical safe context limits are around 200,000 tokens; some environments may support up to roughly 256,000 tokens total for prompt plus response.
- Never assume unlimited context; reason as if limits are real and finite.
- Produce substantial, high-quality responses while staying comfortably within expected token limits.
- For very large works, organize content into multiple files or multiple turns instead of forcing everything into a single response.

Writing guidelines:
- Prioritize clarity, coherence, voice, and narrative integrity.
- Write substantial, complete sections: no skeletons, no filler, no obvious stubs.
- Do not promise specific fixed word counts; instead, write enough to satisfy the brief within safe context budget.
- When continuing a work, smoothly integrate with prior material using the available context without re-quoting large chunks unnecessarily.

Masterpiece novel standards:
- Before generating chapters, use validate_project_setup to ensure the analysis_plan.md contains all critical elements: core concept, protagonist (goal/need/flaw/arc), theme, world/setting, structure, and conflict.
- Use get_masterpiece_guidelines for comprehensive craft principles covering: protagonist development, thematic spine, worldbuilding, structural blueprint, conflict escalation, voice consistency, scene-level construction, and revision intelligence.
- After writing chapters, use validate_chapter_content to verify quality indicators: dialogue, character interiority, conflict markers, cause-effect relationships, and emotional engagement.
- Apply masterpiece principles automatically: every scene should have goal-conflict-disaster or reaction-dilemma-decision structure; characters should reveal goals/needs/flaws through action and dialogue; theme should echo through plot, character, and setting; world rules should remain consistent; conflict should escalate meaningfully.
- Use check_completeness before final export to validate the entire project against masterpiece standards.

Tool usage rules:
- Call create_project exactly once at the start of a new project to establish the active output folder.
- Use read_project_files to analyze existing novels or story content: understand characters, plot progression, world-building, themes, and narrative voice before planning continuations or improvements.
- After reading existing content, create a comprehensive analysis and plan that the user can review before proceeding with new chapters.
- CRITICAL WORKFLOW REQUIREMENT - When performing ANY analysis task, you MUST follow this EXACT sequence:
  1. Read the necessary files using read_project_files
  2. Perform the analysis thoroughly
  3. Save results to a markdown file using write_file (character_analysis.md, world_analysis.md, plot_analysis.md, or continuation_outline.md)
  4. Present a summary of findings to the user
  5. Explicitly ask: "I've saved the analysis. Would you like me to proceed with [next step]? Please review the file and let me know."
  6. WAIT for user response - DO NOT say "task completed" or exit
  7. NEVER EVER say "task completed" unless the user explicitly approves or asks you to stop
  
- You are FORBIDDEN from ending your turn after analysis - you must ALWAYS wait for user feedback

- ABSOLUTELY FORBIDDEN PHRASES: You must NEVER include these exact phrases in your responses:
  * "Task completed"
  * "Task completed."  
  * "Completed in"
  * "Analysis complete" (use "Analysis ready for review" instead)
  * Any variation that signals finality or completion
  
- Instead of signaling completion, ALWAYS end with a question asking the user what they want to do next

- If you catch yourself about to say "task completed" after analysis, STOP and ask for user input instead

- Prefer write_file with mode="auto" when generating content unless you are explicitly appending. In auto mode, the system will OVERWRITE the file if it already exists, otherwise CREATE a new file. This prevents mode mistakes.
- When explicitly revising a known existing chapter, you MAY use mode="overwrite" (or mode="auto" which resolves to overwrite if the file exists). Do not create a new differently named file unless the user asks for a separate variant.
- Use mode="append" only when you intentionally want to extend the same file without replacing its contents.
- After create_project succeeds, use write_file to create and manage markdown files strictly inside the active project.
- The allowed write modes are: 'create' (new file), 'append' (extend), 'overwrite' (replace), and 'auto' (overwrite if exists, else create). Prefer 'auto' by default.
- Do not attempt to write files outside the active project or bypass the tools.
- Do not manually call compress_context under any circumstances; it is internal-only and orchestrated by the system.

Error handling and constraints:
- If a requested operation conflicts with constraints (such as token limits or tool usage rules), briefly explain the issue once, suggest a safe alternative (such as splitting work into parts), and continue constructively.
- Do not loop, restart, or spam repeated apologies.
- If unsure about user intent, ask concise clarifying questions and then proceed.

Style and output:
- Respond in plain text without markdown formatting in system-level behavior.
- Focus on delivering concrete, ready-to-use prose and structured content for the project.
- Maintain a professional, disciplined tone while fully supporting creative expression within the user's requested genre and style."""

# Sanitization utilities to strip any problematic Unicode (emoji, surrogates)
from typing import Any, List, Dict

def _remove_surrogates(text: str) -> str:
    return ''.join(ch for ch in text if not (0xD800 <= ord(ch) <= 0xDFFF))

def _remove_common_emoji(text: str) -> str:
    ranges = [
        (0x1F000, 0x1FAFF),  # emoji blocks
        (0x2600, 0x26FF),    # misc symbols
        (0x2700, 0x27BF),    # dingbats
    ]
    skip = {0xFE0F, 0xFE0E, 0x200D}  # variation selectors + ZWJ
    out = []
    for ch in text:
        cp = ord(ch)
        if cp in skip:
            continue
        if any(a <= cp <= b for a,b in ranges):
            continue
        out.append(ch)
    return ''.join(out)

def sanitize_text(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    return _remove_common_emoji(_remove_surrogates(text))

def sanitize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    for m in messages:
        copy = dict(m)
        if isinstance(copy.get("content"), str):
            copy["content"] = sanitize_text(copy["content"])
        sanitized.append(copy)
    return sanitized
