import re


def _normalize_blank_lines(text: str) -> str:
    # Replace 3+ consecutive newlines with exactly two
    return re.sub(r"\n{3,}", "\n\n", text)


def format_chapter_impl(content: str) -> str:
    """Apply light auto-formatting to chapter content.

    - If leading line starts with '# Chapter', keep as-is.
    - If missing, leave content unchanged (Phase 8 keeps behavior minimal).
    - Normalize multiple blank lines to at most two.
    """
    if not isinstance(content, str):
        return content

    stripped = content.lstrip()
    lines = stripped.splitlines()
    if lines:
        first = lines[0].strip()
        if first.startswith("# Chapter"):
            # Only normalize blank lines for now
            return _normalize_blank_lines(content)

    # No chapter header at top: return unchanged
    return content


def quality_check_impl(content: str) -> str:
    """Return a simple quality report based on word count.

    - STATUS: WARN if word count < 1500 or > 10000
    - STATUS: OK otherwise
    - Always include 'word_count=<n>' and a short summary
    """
    if not isinstance(content, str):
        return "STATUS: ERROR | message=content must be string"

    # Simple whitespace-based split for robustness
    words = [w for w in content.split() if w]
    count = len(words)

    if count < 1500 or count > 10000:
        status = "WARN"
    else:
        status = "OK"

    return (
        f"STATUS: {status} | word_count={count} | "
        f"summary=Chapter length {'too short' if count < 1500 else ('too long' if count > 10000 else 'within target range')}"
    )
