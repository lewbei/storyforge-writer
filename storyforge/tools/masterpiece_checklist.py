"""
Masterpiece Novel Checklist - Validation Tools

This module provides automatic validation of project setup and chapter content
against masterpiece novel principles derived from professional craft research.

The checklist ensures:
1. Core Concept: Clear premise, hook, thematic question
2. Protagonist & Cast: Goals, needs, flaws, arcs, supporting cast
3. Thematic Spine: Central message, thematic echoes, exploration depth
4. World & Constraints: Rules, boundaries, worldbuilding depth
5. Structural Blueprint: Plot framework, beats, turning points
6. Conflict & Stakes: External/internal conflict, escalation, consequences
7. Voice & Style: POV, tense, narrative voice, tone consistency
8. Cohesion & Resonance: Scene-to-scene flow, cause-effect, emotional resonance
9. Revision Intelligence: Consistency, polish, reader experience optimization
"""

import os
import re
from typing import Dict, List, Optional
from .project import get_active_project_folder


# ============================================================================
# MASTERPIECE NOVEL GUIDELINES (Research-Based)
# ============================================================================

MASTERPIECE_GUIDELINES = """
# Masterpiece Novel Guidelines

Based on research synthesis from professional novel craft sources, these
guidelines represent the core elements found in masterpiece long-form fiction.

## 1. Core Concept
- **Clear Premise**: What is the story fundamentally about?
- **Strong Hook**: What makes this story compelling and unique?
- **Thematic Question**: What deep question does the narrative explore?
- **Genre Clarity**: What reader expectations must be met?

## 2. Protagonist & Cast
- **Protagonist Goal**: What does the main character want? (external)
- **Protagonist Need**: What do they actually need? (internal, often unknown to them)
- **Fatal Flaw**: What weakness threatens to destroy them?
- **Character Arc**: How will they transform from beginning to end?
- **Supporting Cast**: Allies, mentors, antagonists with their own goals/arcs
- **Relationships**: How do characters challenge and change each other?

## 3. Thematic Spine
- **Central Theme**: The story's message or exploration (justice, identity, love, power)
- **Thematic Echoes**: How theme appears in plot, character, setting, symbols
- **Multiple Layers**: Interacting themes that create depth
- **Resonance**: Does the theme touch universal human experience?

## 4. World & Constraints
- **Setting Rules**: Physical, social, magical/technological laws that govern the world
- **Boundaries**: What can/cannot happen within this world's logic?
- **Sensory Detail**: Vivid, specific details that make the world tangible
- **Cultural Context**: History, politics, social structures that shape characters

## 5. Structural Blueprint
- **Framework**: Three-act, Hero's Journey, seven-point, or other tested structure
- **Major Beats**: Inciting incident, turning points, midpoint, climax, resolution
- **Scene Structure**: Goal-Conflict-Disaster / Reaction-Dilemma-Decision cycles
- **Pacing**: Rhythm of action/reflection, tension/release
- **Subplots**: Secondary storylines that enrich and complicate the main plot

## 6. Conflict & Stakes
- **External Conflict**: Physical obstacles, antagonistic forces
- **Internal Conflict**: Emotional/psychological struggles
- **Escalation**: Rising tension, increasing difficulty, compounding problems
- **Consequences**: Clear, meaningful stakes (what happens if protagonist fails?)
- **Ticking Clock**: Time pressure or escalating urgency

## 7. Voice & Style
- **POV Choice**: First/third person, single/multiple, deep/distant
- **Tense**: Past/present and why it serves the story
- **Narrative Voice**: Distinct personality in prose
- **Tone Consistency**: Emotional atmosphere maintained throughout
- **Prose Rhythm**: Sentence variety, cadence, flow

## 8. Cohesion & Resonance
- **Scene Flow**: Each scene connects logically to the next (cause-effect chain)
- **Continuity**: Character knowledge, physical objects, timeline consistency
- **Emotional Arc**: Reader's emotional journey through the story
- **Foreshadowing**: Setup and payoff across the narrative
- **Thematic Unity**: All elements serve the central thematic exploration

## 9. Revision Intelligence
- **Character Consistency**: Names, traits, knowledge remain coherent
- **Plot Holes**: No unexplained contradictions or abandoned threads
- **Pacing Issues**: No saggy middles or rushed endings
- **Show vs. Tell**: Active scenes over passive exposition
- **Reader Experience**: Is the story clear, engaging, emotionally satisfying?

---

**Usage**: Before generating chapters, validate project setup against these guidelines.
During chapter generation, check content for presence of key elements.
After completion, use for comprehensive revision analysis.
"""


# ============================================================================
# VALIDATION CRITERIA (Specific Checks)
# ============================================================================

# Core project elements that should be present in analysis_plan.md
PROJECT_CHECKLIST = {
    "Core Concept": ["premise", "concept", "idea", "story about", "hook"],
    "Protagonist": ["protagonist", "main character", "hero", "detective", "goal", "want", "need", "flaw"],
    "Theme": ["theme", "message", "explores", "about", "question"],
    "World": ["setting", "world", "place", "time period", "location"],
    "Structure": ["structure", "act", "chapter", "outline", "plot"],
    "Conflict": ["conflict", "antagonist", "problem", "obstacle", "stakes"],
}

# Chapter content quality indicators
CHAPTER_QUALITY_INDICATORS = {
    "positive": [
        "dialogue", "said", "asked", "replied",  # Character interaction
        "felt", "thought", "wondered", "realized",  # Interiority
        "but", "however", "although", "despite",  # Conflict markers
        "because", "so", "therefore", "thus",  # Causality
        "could", "would", "should", "must",  # Stakes/choices
        "?", "!",  # Emotional punctuation
    ],
    "negative": [
        "very", "really", "just", "that",  # Weak modifiers (in excess)
        "was", "were", "had been",  # Passive voice (in excess)
    ],
}


# ============================================================================
# IMPLEMENTATION
# ============================================================================

def get_masterpiece_guidelines_impl() -> str:
    """
    Returns the complete masterpiece novel guidelines.
    
    Returns:
        String containing the full guidelines document
    """
    return f"STATUS: OK | Masterpiece Novel Guidelines\n\n{MASTERPIECE_GUIDELINES}"


def validate_project_setup_impl() -> str:
    """
    Validates the project's analysis_plan.md against masterpiece checklist.
    
    Checks for presence of:
    - Core concept/premise
    - Protagonist with goal/need/flaw
    - Thematic spine
    - World/setting details
    - Structural blueprint
    - Conflict and stakes
    
    Returns:
        STATUS message with validation results
    """
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project. Use create_project or set_active_project first."
    
    analysis_path = os.path.join(project_folder, "analysis_plan.md")
    if not os.path.exists(analysis_path):
        return (
            "STATUS: WARN | No analysis_plan.md found. Create a detailed analysis plan "
            "covering: core concept, protagonist, theme, world, structure, and conflict."
        )
    
    # Read and analyze content
    with open(analysis_path, "r", encoding="utf-8") as f:
        content = f.read().lower()
    
    # Check each element
    results = {}
    for element, keywords in PROJECT_CHECKLIST.items():
        found = any(kw in content for kw in keywords)
        results[element] = found
    
    # Build report
    present = [k for k, v in results.items() if v]
    missing = [k for k, v in results.items() if not v]
    
    if len(present) >= 5:  # Most elements present
        status = "OK"
        msg = f"STATUS: {status} | Project setup validation complete\n\n"
        msg += f"FOUND {len(present)}/6 core elements: {', '.join(present)}\n"
        if missing:
            msg += f"WARNING: Consider adding: {', '.join(missing)}\n"
        msg += "\nProject appears ready for masterpiece-level chapter generation."
    elif len(present) >= 3:  # Some elements present
        status = "WARN"
        msg = f"STATUS: {status} | Project setup incomplete\n\n"
        msg += f"FOUND {len(present)}/6 core elements: {', '.join(present)}\n"
        msg += f"MISSING critical elements: {', '.join(missing)}\n"
        msg += "\nRecommendation: Expand analysis_plan.md to include all masterpiece elements."
    else:  # Minimal setup
        status = "WARN"
        msg = f"STATUS: {status} | Project setup insufficient\n\n"
        msg += f"ONLY {len(present)}/6 core elements found: {', '.join(present) if present else 'none'}\n"
        msg += f"MISSING: {', '.join(missing)}\n"
        msg += "\nAction required: Create comprehensive analysis_plan.md using get_masterpiece_guidelines."
    
    return msg


def validate_chapter_content_impl(content: str) -> str:
    """
    Validates chapter content against masterpiece quality indicators.
    
    Checks for:
    - Sufficient length (1500-10000 words)
    - Dialogue presence (character interaction)
    - Interiority (character thoughts/feelings)
    - Conflict markers
    - Cause-effect relationships
    - Emotional engagement
    
    Args:
        content: Chapter text content
    
    Returns:
        STATUS message with content validation results
    """
    if not content or not content.strip():
        return "STATUS: ERROR | Chapter content is empty."
    
    # Word count
    words = content.split()
    word_count = len(words)
    
    if word_count < 1500:
        return (
            f"STATUS: WARN | Chapter too short ({word_count} words)\n"
            "Masterpiece chapters typically range 2000-8000 words for proper scene development."
        )
    
    if word_count > 10000:
        return (
            f"STATUS: WARN | Chapter very long ({word_count} words)\n"
            "Consider splitting into multiple chapters or tightening prose."
        )
    
    # Quality indicators
    content_lower = content.lower()
    
    # Check for dialogue (quotes indicating character speech)
    has_dialogue = '"' in content and content.count('"') >= 4
    
    # Check for interiority (character thoughts/feelings)
    interiority_words = ["felt", "thought", "wondered", "realized", "knew", "understood"]
    has_interiority = any(word in content_lower for word in interiority_words)
    
    # Check for conflict markers
    conflict_words = ["but", "however", "although", "despite", "yet", "still"]
    has_conflict = any(word in content_lower for word in conflict_words)
    
    # Check for causality (plot progression)
    causality_words = ["because", "so", "therefore", "thus", "then", "after"]
    has_causality = any(word in content_lower for word in causality_words)
    
    # Count quality indicators
    indicators_present = sum([has_dialogue, has_interiority, has_conflict, has_causality])
    
    # Build report
    if indicators_present >= 3:
        status = "OK"
        msg = f"STATUS: {status} | Chapter content validation passed\n\n"
        msg += f"Word count: {word_count} words\n"
        msg += f"Quality indicators: {indicators_present}/4 present\n"
        if has_dialogue:
            msg += "DIALOGUE: Character interaction detected\n"
        if has_interiority:
            msg += "INTERIORITY: Character thoughts/feelings present\n"
        if has_conflict:
            msg += "CONFLICT: Tension and obstacles evident\n"
        if has_causality:
            msg += "CAUSALITY: Cause-effect plot progression\n"
        msg += "\nChapter demonstrates masterpiece-level craft elements."
    else:
        status = "WARN"
        msg = f"STATUS: {status} | Chapter content needs improvement\n\n"
        msg += f"Word count: {word_count} words\n"
        msg += f"Quality indicators: {indicators_present}/4 present\n"
        
        missing = []
        if not has_dialogue:
            missing.append("dialogue (character interaction)")
        if not has_interiority:
            missing.append("interiority (character thoughts/feelings)")
        if not has_conflict:
            missing.append("conflict markers (tension, obstacles)")
        if not has_causality:
            missing.append("causality (cause-effect progression)")
        
        msg += f"Missing elements: {', '.join(missing)}\n"
        msg += "\nRecommendation: Enhance chapter with missing craft elements for masterpiece quality."
    
    return msg


def check_completeness_impl() -> str:
    """
    Comprehensive check of project completeness against masterpiece standards.
    
    Validates:
    - Project setup (analysis_plan.md)
    - Existing chapter content quality
    - Story bible consistency (if present)
    - Overall readiness for continuation/completion
    
    Returns:
        STATUS message with comprehensive analysis
    """
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project to check."
    
    issues = []
    warnings = []
    successes = []
    
    # Check analysis_plan.md
    analysis_path = os.path.join(project_folder, "analysis_plan.md")
    if not os.path.exists(analysis_path):
        issues.append("Missing analysis_plan.md")
    else:
        setup_result = validate_project_setup_impl()
        if "STATUS: OK" in setup_result:
            successes.append("Project setup complete and comprehensive")
        elif "STATUS: WARN" in setup_result:
            warnings.append("Project setup incomplete (see validate_project_setup)")
        else:
            issues.append("Project setup has errors (see validate_project_setup)")
    
    # Check for chapters
    chapter_files = sorted([
        f for f in os.listdir(project_folder)
        if f.endswith(".md") and f.startswith("chapter") and f != "chapter_template.md"
    ])
    
    if not chapter_files:
        warnings.append("No chapters written yet")
    else:
        successes.append(f"{len(chapter_files)} chapter(s) created")
        
        # Validate first and last chapter quality
        for idx, fname in enumerate([chapter_files[0], chapter_files[-1]] if len(chapter_files) > 1 else [chapter_files[0]]):
            chapter_path = os.path.join(project_folder, fname)
            with open(chapter_path, "r", encoding="utf-8") as f:
                chapter_content = f.read()
            
            validation = validate_chapter_content_impl(chapter_content)
            label = "first" if idx == 0 else "last"
            if "STATUS: OK" in validation:
                successes.append(f"Chapter quality: {fname} ({label}) meets masterpiece standards")
            elif "STATUS: WARN" in validation:
                warnings.append(f"Chapter quality: {fname} ({label}) needs improvement")
    
    # Check story bible
    bible_path = os.path.join(project_folder, "story_bible.json")
    if os.path.exists(bible_path):
        successes.append("Story bible present for consistency tracking")
    else:
        warnings.append("No story bible (consider using build_story_bible)")
    
    # Build final report
    if issues:
        status = "ERROR"
        msg = f"STATUS: {status} | Project has critical issues\n\n"
        msg += "ISSUES:\n" + "\n".join(f"  - {i}" for i in issues) + "\n"
    elif warnings:
        status = "WARN"
        msg = f"STATUS: {status} | Project needs attention\n\n"
    else:
        status = "OK"
        msg = f"STATUS: {status} | Project ready for masterpiece completion\n\n"
    
    if successes:
        msg += "SUCCESSES:\n" + "\n".join(f"  + {s}" for s in successes) + "\n"
    
    if warnings:
        msg += "\nWARNINGS:\n" + "\n".join(f"  - {w}" for w in warnings) + "\n"
    
    if status == "OK":
        msg += "\nProject demonstrates masterpiece-level preparation and execution."
    elif status == "WARN":
        msg += "\nRecommendation: Address warnings before final completion."
    else:
        msg += "\nAction required: Fix critical issues before proceeding."
    
    return msg


# ============================================================================
# TOOL WRAPPERS (for utils.py registration)
# ============================================================================

def get_masterpiece_guidelines() -> str:
    """Wrapper for tool registration."""
    from .run_logger import log_event
    log_event("get_masterpiece_guidelines | called")
    return get_masterpiece_guidelines_impl()


def validate_project_setup() -> str:
    """Wrapper for tool registration."""
    from .run_logger import log_event
    log_event("validate_project_setup | called")
    return validate_project_setup_impl()


def validate_chapter_content(content: str) -> str:
    """Wrapper for tool registration."""
    from .run_logger import log_event
    log_event(f"validate_chapter_content | word_count={len(content.split())}")
    return validate_chapter_content_impl(content)


def check_completeness() -> str:
    """Wrapper for tool registration."""
    from .run_logger import log_event
    log_event("check_completeness | called")
    return check_completeness_impl()
