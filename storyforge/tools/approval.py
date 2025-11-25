"""Interactive approval tool for StoryForge AI.

Provides a simple stdin-based approval prompt.
"""

from typing import Dict, List


def request_approval_impl(prompt: str, options: Dict[str, str], context_file: str | None = None) -> str:
    """Prompt the user for approval with simple single-line input.

    Args:
        prompt: Main message to display.
        options: Mapping of short keys (e.g. "A") to human labels (e.g. "Approve").
        context_file: Optional filename to mention for user reference.

    Returns:
        Plain-text status line including normalized choice and label.
    """
    if not options:
        options = {"A": "Approve"}

    # Build concise prompt line
    parts: List[str] = []
    for key, label in options.items():
        key = str(key).strip()[:1].upper()
        label = str(label).strip() or key
        parts.append(f"[{key}] {label}")

    options_line = " | ".join(parts)
    ctx_note = f" (see {context_file})" if context_file else ""

    print(f"{prompt}{ctx_note}")
    print(options_line)
    raw = input("> ").strip()

    if not raw:
        choice_key = ""
    else:
        choice_key = raw[:1].upper()

    # Resolve label
    label = options.get(choice_key)
    if not label:
        # Unknown choice: treat as cancel-style fallback
        return f"STATUS: UNKNOWN | choice={choice_key or 'EMPTY'}"

    return f"STATUS: OK | choice={choice_key} | label={label}"