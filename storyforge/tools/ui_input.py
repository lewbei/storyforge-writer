"""
Command/input processing helper for chat mode.
Pure function to support unit testing of command parsing and retry behavior.
"""
from typing import Dict, Any, List, Optional, Tuple


def process_user_input(messages: List[Dict[str, Any]], user_input: str) -> Tuple[str, Optional[str], bool, Optional[str]]:
    """
    Process a single user input and decide the action.

    Returns a tuple: (action, normalized_input, skip_append, warning)
    - action: one of {"exit", "help", "status", "projects", "files", "switch", "troubleshoot", "save", "resume", "new", "send"}
    - normalized_input: for "send" action, the text to send to the model. For retry, it's the last user message.
    - skip_append: if True, the caller must NOT append a new user message (used for retry behavior)
    - warning: optional warning string (e.g., retry without previous user message)
    """
    text = (user_input or "").strip()
    if not text:
        return ("noop", None, True, None)

    low = text.lower()

    # Exit
    if low in ("/exit", "/quit", "q"):
        return ("exit", None, True, None)

    # Retry: reuse the last user message
    if low in ("retry", "/retry"):
        last_user = None
        for m in reversed(messages or []):
            if m.get("role") == "user":
                last_user = m.get("content")
                break
        if not last_user:
            return ("noop", None, True, "No previous user request to retry.")
        return ("send", last_user, True, None)

    # Help and other commands
    if low == "/help":
        return ("help", None, True, None)
    if low == "/status":
        return ("status", None, True, None)
    if low == "/projects":
        return ("projects", None, True, None)
    if low == "/files":
        return ("files", None, True, None)
    if low.startswith("/switch"):
        return ("switch", text, True, None)
    if low == "/troubleshoot":
        return ("troubleshoot", None, True, None)
    if low == "/save":
        return ("save", None, True, None)
    if low == "/resume":
        return ("resume", None, True, None)
    if low == "/new":
        return ("new", None, True, None)
    if low == "/brainstorm":
        return ("brainstorm", None, True, None)
    if low.startswith("/critique"):
        return ("critique", text, True, None)
    if low == "/dashboard":
        return ("dashboard", None, True, None)
    if low == "/context":
        return ("context", None, True, None)
    if low == "/bible":
        return ("bible", None, True, None)

    # Default: send to model
    return ("send", text, False, None)
