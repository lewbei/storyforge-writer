from typing import Dict, Any, Optional

# Structured templates for genres, including prompt instructions and beat sheet models.
# Based on "The Synthetic Quill" recommendations for genre-specific constraints.

GENRE_STRUCTURES = {
    "romance": {
        "system_prompt_addendum": (
            "Focus on emotional arcs and relationship tension (Heat Level). "
            "Prioritize the 'Meet Cute', 'Forced Proximity', and 'Dark Moment' beats. "
            "Use deep POV to show internal emotional states."
        ),
        "bible_overrides": {
            "Tropes to Include": "Enemies to Lovers, Fake Dating, One Bed, Soulmates",
            "Core Themes": "Love conquers all, Vulnerability, Trust",
        },
        "beat_sheet_model": [
            "1. Introduction (Status Quo): Hero is incomplete.",
            "2. Inciting Incident (Meet Cute): Hero meets Love Interest.",
            "3. Refusal of the Call: They clash or deny attraction.",
            "4. Fun and Games: Forced proximity, attraction builds.",
            "5. Midpoint (First Kiss/Deepening): Major shift in relationship.",
            "6. Bad Guys Close In: Internal fears or external rivals threaten the bond.",
            "7. All Hope Is Lost (The Breakup): They separate due to a misunderstanding or fear.",
            "8. Dark Night of the Soul: Hero realizes they can't live without Love Interest.",
            "9. Climax (Grand Gesture): Hero fights for the relationship.",
            "10. Resolution (HEA): Happily Ever After."
        ]
    },
    "fantasy": {
        "system_prompt_addendum": (
            "Emphasize worldbuilding, magic systems, and mythic stakes. "
            "Ensure the magic has rules and costs. "
            "Balance macro-politics with character micro-stakes."
        ),
        "bible_overrides": {
            "Tropes to Include": "The Chosen One (subverted), The Quest, Magical Artifact",
            "Core Themes": "Power vs. Responsibility, Good vs. Evil, Destiny",
        },
        "beat_sheet_model": [
            "1. Introduction (The Ordinary World): Hero's mundane life.",
            "2. Inciting Incident (Call to Adventure): Threat to the world or personal loss.",
            "3. Refusal of the Call: Hero doubts their ability.",
            "4. Crossing the Threshold: Hero leaves home/enters the magical realm.",
            "5. Tests, Allies, Enemies: Learning the magic system/rules.",
            "6. The Approach: Preparing for the major threat.",
            "7. The Ordeal (Midpoint): High stakes battle or loss.",
            "8. The Reward: Gaining power or insight.",
            "9. The Road Back: The villain strikes back harder.",
            "10. Climax: Final battle determining the fate of the world.",
            "11. Resolution: The new normal."
        ]
    },
    "dark fantasy": {
        "system_prompt_addendum": (
            "Focus on moral ambiguity, high stakes, and a grim atmosphere. "
            "Magic should be dangerous and have a heavy cost. "
            "Blur the lines between hero and villain."
        ),
        "bible_overrides": {
            "Tropes to Include": "Anti-Hero, Eldritch Abomination, Faustian Bargain, Grimdark",
            "Core Themes": "Survival, Corruption, The Cost of Power, Hopelessness",
        },
        "beat_sheet_model": [
            "1. Introduction (The Gray World): Hero's harsh reality.",
            "2. Inciting Incident (The Curse): A dark power awakens or a terrible choice is made.",
            "3. Refusal of the Call: Hero tries to ignore the darkness.",
            "4. The Descent: Hero is dragged into the shadow world.",
            "5. Tests, Allies, Enemies: Betrayals and uneasy alliances.",
            "6. The Approach: Deeper into the abyss.",
            "7. The Ordeal (Midpoint): A sacrifice must be made.",
            "8. The Reward (Cursed Gift): Power gained at a terrible price.",
            "9. The Road Back: The darkness follows them home.",
            "10. Climax: A pyrrhic victory or a tragic realization.",
            "11. Resolution: Scars that will never heal."
        ]
    },
    "mystery": {
        "system_prompt_addendum": (
            "Center clues, red herrings, and logical deduction. "
            "Maintain 'Fair Play' - the reader must have the clues to solve it. "
            "Pacing should accelerate as the investigation deepens."
        ),
        "bible_overrides": {
            "Tropes to Include": "Red Herring, Ticking Clock, Locked Room, Unreliable Narrator",
            "Core Themes": "Truth, Justice, The Past Haunting the Present",
        },
        "beat_sheet_model": [
            "1. Introduction: The Detective's status quo.",
            "2. Inciting Incident (The Crime): The body is found / client enters.",
            "3. Refusal: Detective is reluctant or blocked.",
            "4. Investigation Begins: First clues and interviews.",
            "5. Midpoint (The Twist): A major clue changes the theory.",
            "6. Bad Guys Close In: The killer targets the Detective or a second victim falls.",
            "7. All Hope Is Lost: The wrong person is arrested or the trail goes cold.",
            "8. The Breakthrough: A overlooked detail reveals the truth.",
            "9. Climax (The Confrontation): Catching the killer.",
            "10. Resolution: Explaining the 'How' and 'Why'."
        ]
    },
    "thriller": {
        "system_prompt_addendum": (
            "Maintain high tension, short sentences, and ticking clocks. "
            "End scenes with cliffhangers. "
            "Focus on 'Flight or Fight' visceral reactions."
        ),
        "bible_overrides": {
            "Tropes to Include": "Ticking Clock, The Chase, Trust No One",
            "Core Themes": "Survival, Corruption, Safety vs. Freedom",
        },
        "beat_sheet_model": [
            "1. Introduction: Normalcy with an undercurrent of unease.",
            "2. Inciting Incident: The Threat reveals itself.",
            "3. Plot Point 1: Hero is locked in/cannot escape the threat.",
            "4. Pinch Point 1: The Villain demonstrates power.",
            "5. Midpoint: Hero shifts from reactive to proactive.",
            "6. Pinch Point 2: All escape routes are cut off.",
            "7. All Hope Is Lost: Hero is captured or cornered.",
            "8. Climax: Final confrontation/escape.",
            "9. Resolution: Safety, but changed forever."
        ]
    }
}

def get_genre_structure(genre: str) -> Optional[Dict[str, Any]]:
    """Retrieve the structured template for a given genre."""
    if not genre:
        return None
    return GENRE_STRUCTURES.get(genre.strip().lower())

def list_available_templates() -> list[str]:
    return list(GENRE_STRUCTURES.keys())

def load_genre_template_impl(genre: str) -> str:
    """Legacy wrapper for tool compatibility. Generates dynamic templates for unknown genres."""
    structure = get_genre_structure(genre)

    if structure:
        # Known genre - return structured template
        prompt_add = structure.get("system_prompt_addendum", "")
        bible_add = structure.get("bible_overrides", {})
        beats = structure.get("beat_sheet_model", [])

        bible_str = "\n".join([f"- {k}: {v}" for k, v in bible_add.items()])
        beats_str = "\n".join(beats)

        return f"""STATUS: OK | template_loaded
GENRE: {genre}
INSTRUCTIONS: {prompt_add}
BIBLE SUGGESTIONS:
{bible_str}
BEAT SHEET:
{beats_str}"""

    # Unknown genre - generate dynamic template
    genre_lower = genre.lower().strip()
    available = list_available_templates()

    # Generate a dynamic template based on common storytelling principles
    dynamic_template = generate_dynamic_template(genre_lower)

    return f"""STATUS: OK | dynamic_template_generated
GENRE: {genre_lower}
NOTE: No predefined template found. Generated dynamic template based on genre conventions.
AVAILABLE TEMPLATES: {', '.join(available)}

{dynamic_template}"""


def generate_dynamic_template(genre: str) -> str:
    """
    Generate a dynamic template for unknown genres using common storytelling principles.

    Args:
        genre: The genre name

    Returns:
        A formatted template string with genre-appropriate guidance
    """
    # Common genre elements database
    genre_elements = {
        # Horror elements
        "horror": {
            "tropes": "Isolation, The Unknown, Body Horror, Jump Scares, Slow Burn Dread",
            "themes": "Fear of death, Loss of control, The monstrous within, Survival",
            "prompt": "Build atmosphere through sensory details. Use the unseen as much as the seen. Pacing should alternate between tension and release. End scenes with lingering dread.",
            "beats": [
                "1. Introduction: False sense of safety/normalcy",
                "2. Inciting Incident: First hint of the horror",
                "3. Investigation/Denial: Characters dismiss warnings",
                "4. First Encounter: Direct confrontation with the horror",
                "5. Escalation: The horror grows stronger/closer",
                "6. Isolation: Characters are cut off from help",
                "7. Revelation: The true nature of the horror is revealed",
                "8. Climax: Final confrontation or escape attempt",
                "9. Resolution: Survival (or not), but forever changed"
            ]
        },
        "sci-fi": {
            "tropes": "First Contact, AI Rebellion, Space Opera, Time Travel, Dystopia",
            "themes": "Humanity vs. Technology, Ethics of Progress, What makes us human",
            "prompt": "Ground speculative elements in character stakes. Technology should serve the story, not overshadow it. Explore the human implications of scientific concepts.",
            "beats": [
                "1. Introduction: The world and its rules",
                "2. Inciting Incident: Discovery or disruption",
                "3. Exploration: Learning the implications",
                "4. Complication: Unintended consequences",
                "5. Midpoint: Major revelation about the technology/world",
                "6. Escalation: Stakes become personal",
                "7. Crisis: Technology/discovery threatens everything",
                "8. Climax: Resolution through understanding or action",
                "9. Resolution: New equilibrium"
            ]
        },
        "literary": {
            "tropes": "Unreliable Narrator, Stream of Consciousness, Symbolism, Epiphany",
            "themes": "Human condition, Identity, Memory, Relationships, Mortality",
            "prompt": "Prioritize character interiority and thematic depth over plot. Use language as an artistic tool. Every detail should resonate symbolically.",
            "beats": [
                "1. Introduction: Character in stasis or routine",
                "2. Disturbance: Something disrupts the pattern",
                "3. Reflection: Character examines their life",
                "4. Confrontation: Facing uncomfortable truths",
                "5. Complication: External/internal conflict deepens",
                "6. Crisis: Moment of truth",
                "7. Epiphany: Understanding (or failure to understand)",
                "8. Resolution: Changed perspective (not necessarily plot)"
            ]
        },
        "historical": {
            "tropes": "Fish Out of Water, Secret History, Parallel to Present",
            "themes": "Legacy, Progress vs. Tradition, The weight of the past",
            "prompt": "Balance historical accuracy with narrative engagement. Use period details to illuminate character, not just decorate. Connect past themes to universal human experiences.",
            "beats": [
                "1. Introduction: The historical world and its constraints",
                "2. Inciting Incident: Event that challenges status quo",
                "3. Engagement: Character drawn into historical events",
                "4. Escalation: Personal stakes intertwine with historical",
                "5. Midpoint: Historical turning point",
                "6. Consequences: History's weight on characters",
                "7. Climax: Character's role in historical moment",
                "8. Resolution: Personal resolution amid historical change"
            ]
        },
        "comedy": {
            "tropes": "Mistaken Identity, Fish Out of Water, Escalating Absurdity, Comic Timing",
            "themes": "Human folly, Social commentary, Joy in absurdity",
            "prompt": "Timing is everything. Use the Rule of Three. Ground humor in character and situation, not just jokes. Subvert expectations.",
            "beats": [
                "1. Introduction: Normal world with comedic potential",
                "2. Inciting Incident: The complication that sets off the comedy",
                "3. Escalation 1: First attempt to fix things makes it worse",
                "4. Escalation 2: Second attempt compounds the problem",
                "5. Peak Absurdity: Everything goes maximally wrong",
                "6. Climax: The clever (or lucky) resolution",
                "7. Resolution: Return to normalcy with a twist"
            ]
        },
        "action": {
            "tropes": "The Chase, Ticking Clock, One Against Many, Unlikely Hero",
            "themes": "Survival, Justice, Courage under fire",
            "prompt": "Keep the pace relentless. Use short sentences and paragraphs. Make action sequences visceral and clear. Stakes must be personal.",
            "beats": [
                "1. Introduction: Hero's world before the storm",
                "2. Inciting Incident: Call to action",
                "3. First Action: Initial confrontation",
                "4. Escalation: Stakes and opponents increase",
                "5. Setback: Hero is defeated or captured",
                "6. Regrouping: Hero finds new strength/ally",
                "7. Final Push: All-out assault on the objective",
                "8. Climax: Ultimate confrontation",
                "9. Resolution: Victory and aftermath"
            ]
        },
        "western": {
            "tropes": "The Stranger, Frontier Justice, The Showdown, Redemption",
            "themes": "Law vs. Chaos, Civilization vs. Wilderness, Personal codes",
            "prompt": "Use sparse, direct prose. The landscape is a character. Silence speaks as loudly as dialogue. Honor and codes matter.",
            "beats": [
                "1. Introduction: The town/territory and its tensions",
                "2. Inciting Incident: The stranger arrives or injustice occurs",
                "3. Investigation: Learning the lay of the land",
                "4. Escalation: Lines are drawn",
                "5. Preparation: Both sides prepare for confrontation",
                "6. The Showdown: The climactic confrontation",
                "7. Resolution: Justice (or its absence) and departure"
            ]
        }
    }

    # Check for exact or partial match
    elements = None
    for key, value in genre_elements.items():
        if key in genre or genre in key:
            elements = value
            break

    if elements:
        beats_str = "\n".join(elements["beats"])
        return f"""INSTRUCTIONS: {elements['prompt']}

TROPES TO CONSIDER: {elements['tropes']}

CORE THEMES: {elements['themes']}

SUGGESTED BEAT SHEET:
{beats_str}"""

    # Completely unknown genre - provide generic guidance
    return f"""INSTRUCTIONS: Focus on the core conventions and reader expectations of {genre} fiction.
Research common tropes and subvert them where appropriate.
Ensure emotional resonance regardless of genre conventions.

UNIVERSAL STORY BEATS (adapt to {genre}):
1. Introduction: Establish world, character, and tone
2. Inciting Incident: The event that launches the story
3. Rising Action: Complications and escalating stakes
4. Midpoint: A major shift or revelation
5. Crisis: The protagonist faces their greatest challenge
6. Climax: The decisive confrontation or choice
7. Resolution: The new equilibrium

GENERAL GUIDANCE:
- Identify what makes {genre} unique and lean into those elements
- Balance genre expectations with fresh perspectives
- Ground fantastical elements in emotional truth
- Use genre conventions to set up expectations, then subvert some
- Ensure characters have agency regardless of genre constraints"""

def apply_template_impl() -> str:
    """Minimal stub."""
    return "STATUS: OK | template guidance available (check load_genre_template output)"