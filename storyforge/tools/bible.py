import os
from typing import Optional

def generate_bible_template(project_path: str) -> str:
    """
    Generates a bible.md file in the project directory with a detailed checklist template.
    Returns the path to the created file.
    """
    bible_path = os.path.join(project_path, "bible.md")
    
    if os.path.exists(bible_path):
        return bible_path

    template = """# Project Bible

## Core Creative Inputs
**Genre**: [e.g., Historical Mystery with light fantasy]
**Mood/Tone**: [e.g., Moody, suspenseful, wry humor]
**Target Audience**: [e.g., YA, Adult, specific fans]

## Fractal Outline (Structure)
**Global Synopsis**:
[1-2 paragraph summary of the entire book]

**Act Breakdown**:
- **Act I (Setup)**: [Inciting Incident to Plot Point 1]
- **Act II (Confrontation)**: [Rising Action to All Hope Is Lost]
- **Act III (Resolution)**: [Climax to Resolution]

**Chapter Budget**:
- **Target Word Count**: [e.g., 90,000 words total]
- **Average Chapter Length**: [e.g., 3,000 words]
- **Total Chapters**: [e.g., 30]

## Character Elements
**Protagonist**: [Name, Role, Goal, Motivation, Flaw]
**Antagonist**: [Name, Role, Goal, Why they oppose the hero]
**Key Side Characters**: [Names, Roles, Relationship to Hero]

## Plot Expectations
**Core Themes**: [e.g., Justice vs. Revenge, Found Family]
**Tropes to Include**: [e.g., Enemies to lovers, Unlikely allies]
**Tropes to Avoid**: [e.g., Dream endings, Love triangles]
**Desired Ending**: [e.g., Bittersweet, Happy, Cliffhanger]

## Style Guide (Voice & Prose)
**Narrative Voice**: [e.g., Witty, formal, gritty, lyrical]
**POV**: [e.g., First-person past tense, Third-person limited (Deep POV)]
**Reading Level**: [e.g., High-school, Adult literary]
**Sentence Structure**: [e.g., Varied lengths, avoid repetitive openers]
**Negative Constraints**:
- Do not use: [e.g., "shivers down spine", "let out a breath she didn't know she was holding"]
- Avoid: [e.g., Excessive adverbs, filtering words like "he saw", "she felt"]

## Self-Publishing Goals
**Format**: [e.g., eBook, Print, Audio]
**Timeline**: [e.g., Launch in 6 months]
"""
    try:
        with open(bible_path, "w", encoding="utf-8") as f:
            f.write(template)
        return bible_path
    except Exception as e:
        print(f"Error creating bible template: {e}")
        return None

def read_project_bible(project_path: str) -> Optional[str]:
    """
    Reads the content of bible.md if it exists.
    """
    bible_path = os.path.join(project_path, "bible.md")
    if os.path.exists(bible_path):
        try:
            with open(bible_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading bible: {e}")
            return None
    return None
