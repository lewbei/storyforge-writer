import json
import os
import re
from pathlib import Path

from . import project
from . import reader


CAPITALIZED_TOKEN_RE = re.compile(r"\b([A-Z][a-zA-Z]+)\b")


def _get_active_project_path() -> Path:
    active = project.get_active_project_folder()
    return Path(active) if active else None


def _iter_markdown_files(base: Path):
    for path in base.rglob("*.md"):
        if path.is_file():
            yield path


def build_story_bible_impl() -> str:
    """Build a very simple story bible for the active project.

    - Scans markdown files for chapter headings and capitalized tokens.
    - Writes JSON to story_bible.json in the active project root.
    """

    project_path = _get_active_project_path()
    if not project_path or not project_path.exists():
        return "STATUS: ERROR | active project not set"

    characters = set()
    chapters = []

    try:
        for md_file in _iter_markdown_files(project_path):
            text = md_file.read_text(encoding="utf-8", errors="ignore")

            # naive chapter heading detection: lines starting with "#" or "Chapter"
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or stripped.lower().startswith("chapter "):
                    chapters.append({"file": str(md_file.name), "heading": stripped})

            # collect capitalized tokens as character-like names
            # Filter out common stopwords
            STOPWORDS = {
                "The", "A", "An", "It", "He", "She", "They", "We", "You", "I",
                "In", "On", "At", "To", "For", "Of", "With", "By", "From",
                "And", "But", "Or", "So", "Yet", "Nor",
                "Chapter", "Section", "Part", "Prologue", "Epilogue",
                "Mr", "Mrs", "Ms", "Dr", "St",
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
                "Yes", "No", "Oh", "Ah", "Well", "Now", "Then", "Here", "There"
            }
            
            for match in CAPITALIZED_TOKEN_RE.findall(text):
                if len(match) > 2 and match not in STOPWORDS:  # avoid very short tokens and stopwords
                    characters.add(match)

        bible = {
            "characters": sorted(characters),
            "chapters": chapters,
        }

        bible_path = project_path / "story_bible.json"
        bible_path.write_text(json.dumps(bible, indent=2), encoding="utf-8")

        return "STATUS: OK | story_bible.json updated"
    except Exception as exc:  # pragma: no cover - defensive
        return f"STATUS: ERROR | {exc}"


def validate_chapter_consistency_impl(chapter_content: str) -> str:
    """Validate a chapter against the existing story bible.

    Conservative behavior:
    - If no bible, skip.
    - If bible has known characters and none appear in chapter, warn.
    - New names are allowed and not treated as errors.
    """

    project_path = _get_active_project_path()
    if not project_path or not project_path.exists():
        return "STATUS: SKIP | story_bible.json not found"

    bible_path = project_path / "story_bible.json"
    if not bible_path.exists():
        return "STATUS: SKIP | story_bible.json not found"

    try:
        bible = json.loads(bible_path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - malformed bible
        return "STATUS: SKIP | story_bible.json not found"

    known_chars = bible.get("characters") or []
    if not known_chars:
        return "STATUS: OK | no_known_characters_in_bible"

    content_lower = chapter_content
    found = False
    for name in known_chars:
        if name and name in content_lower:
            found = True
            break

    if not found:
        return "STATUS: WARN | no_known_characters"

    return "STATUS: OK | contains_known_character"