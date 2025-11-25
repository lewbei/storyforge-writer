"""
Character Behavior Tracking with Memory

RESEARCH-BACKED:
- Multi-Agent System for TV Series (arXiv:2503.04817)
- Character consistency AI tools
- Agent Memory patterns (Letta)

Tracks character development, personality consistency, and behavioral patterns
across multi-episode narratives.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CharacterTracker:
    """
    Track character behavior and ensure consistency across episodes.

    RESEARCH-BACKED: arXiv:2503.04817 - Multi-Agent TV Series Analysis
    - Maintains character "memory" across episodes
    - Recognizes recurring themes and character development
    - Validates behavioral consistency
    """

    def __init__(self):
        self.characters = {}  # Character database
        self.relationships = {}  # Character relationships
        self.arcs = {}  # Character arcs across episodes
        self.dialogue_patterns = {}  # Speech patterns

    def register_character(self, name: str, attributes: Dict[str, Any]) -> None:
        """
        Register a new character.

        Args:
            name: Character name
            attributes: Initial attributes (personality, appearance, background)
        """
        if name not in self.characters:
            self.characters[name] = {
                "name": name,
                "first_appearance": attributes.get("episode", 1),
                "personality_traits": attributes.get("personality", []),
                "physical_description": attributes.get("physical", {}),
                "backstory": attributes.get("backstory", ""),
                "goals": attributes.get("goals", []),
                "fears": attributes.get("fears", []),
                "relationships": {},
                "development_history": [],
                "dialogue_samples": []
            }
            logger.info(f"[CharTracker] Registered character: {name}")
        else:
            logger.warning(f"[CharTracker] Character {name} already registered")

    def track_appearance(self, episode: int, character: str, actions: List[str], dialogue: List[str]) -> None:
        """
        Track character appearance in an episode.

        Args:
            episode: Episode number
            character: Character name
            actions: List of actions performed
            dialogue: Sample dialogue lines
        """
        if character not in self.characters:
            # Auto-register with minimal info
            self.register_character(character, {"episode": episode})

        char_data = self.characters[character]

        # Add appearance record
        appearance = {
            "episode": episode,
            "actions": actions,
            "dialogue": dialogue,
            "timestamp": datetime.now().isoformat()
        }

        char_data["development_history"].append(appearance)
        char_data["dialogue_samples"].extend(dialogue[:5])  # Keep last 5 samples

        # Analyze personality from actions
        self._update_personality_from_actions(character, actions)

        logger.info(f"[CharTracker] Tracked {character} in Episode {episode}")

    def validate_consistency(self, episode: int, character: str, current_behavior: Dict[str, Any]) -> List[str]:
        """
        Validate character behavior consistency.

        RESEARCH-BACKED: Character consistency validation patterns

        Args:
            episode: Current episode
            character: Character name
            current_behavior: Current behavior description

        Returns:
            List of consistency errors
        """
        errors = []

        if character not in self.characters:
            return [f"ERROR: Character {character} not in database"]

        char_data = self.characters[character]
        established_personality = char_data["personality_traits"]

        # Check personality consistency
        current_actions = current_behavior.get("actions", [])
        for action in current_actions:
            if not self._is_action_consistent(action, established_personality):
                errors.append(
                    f"INCONSISTENCY: {character}'s action '{action}' contradicts established personality {established_personality}"
                )

        # Check physical description consistency
        if "physical_description" in current_behavior:
            current_desc = current_behavior["physical_description"]
            established_desc = char_data["physical_description"]

            for attr, value in current_desc.items():
                if attr in established_desc and established_desc[attr] != value:
                    errors.append(
                        f"INCONSISTENCY: {character}'s {attr} changed from '{established_desc[attr]}' to '{value}'"
                    )

        # Check dialogue voice consistency
        if "dialogue" in current_behavior:
            current_dialogue = current_behavior["dialogue"]
            if not self._is_dialogue_consistent(character, current_dialogue):
                errors.append(
                    f"INCONSISTENCY: {character}'s dialogue voice doesn't match previous episodes"
                )

        return errors

    def get_character_arc(self, character: str) -> Dict[str, Any]:
        """
        Get character's development arc across episodes.

        Args:
            character: Character name

        Returns:
            Dict with arc information
        """
        if character not in self.characters:
            return {"error": f"Character {character} not found"}

        char_data = self.characters[character]
        history = char_data["development_history"]

        arc = {
            "character": character,
            "first_appearance": char_data["first_appearance"],
            "total_appearances": len(history),
            "episodes": [h["episode"] for h in history],
            "personality_evolution": self._analyze_personality_evolution(character),
            "key_moments": self._extract_key_moments(character),
            "relationships": char_data["relationships"]
        }

        return arc

    def track_relationship(self, char1: str, char2: str, relationship_type: str, episode: int) -> None:
        """
        Track relationship between characters.

        Args:
            char1: First character name
            char2: Second character name
            relationship_type: Type of relationship (ally, enemy, family, etc.)
            episode: Episode where relationship is established/changes
        """
        for char in [char1, char2]:
            if char not in self.characters:
                self.register_character(char, {"episode": episode})

        # Bidirectional relationship tracking
        self.characters[char1]["relationships"][char2] = {
            "type": relationship_type,
            "since_episode": episode
        }
        self.characters[char2]["relationships"][char1] = {
            "type": relationship_type,
            "since_episode": episode
        }

        logger.info(f"[CharTracker] Tracked relationship: {char1} <-> {char2} ({relationship_type})")

    def get_character_state(self, character: str, at_episode: int) -> Dict[str, Any]:
        """
        Get character state at a specific episode.

        RESEARCH-BACKED: Agent memory state management

        Args:
            character: Character name
            at_episode: Episode number

        Returns:
            Dict with character state at that point
        """
        if character not in self.characters:
            return {"error": f"Character {character} not found"}

        char_data = self.characters[character]

        # Filter history up to specified episode
        relevant_history = [h for h in char_data["development_history"] if h["episode"] <= at_episode]

        if not relevant_history:
            return {"error": f"{character} hasn't appeared by Episode {at_episode}"}

        latest = relevant_history[-1]

        return {
            "character": character,
            "episode": at_episode,
            "personality": char_data["personality_traits"],
            "physical": char_data["physical_description"],
            "last_known_actions": latest["actions"],
            "relationships": char_data["relationships"],
            "arc_stage": self._determine_arc_stage(character, at_episode)
        }

    def _update_personality_from_actions(self, character: str, actions: List[str]) -> None:
        """Infer personality traits from actions."""
        char_data = self.characters[character]
        traits = char_data["personality_traits"]

        # Simple trait inference
        for action in actions:
            action_lower = action.lower()

            if any(word in action_lower for word in ["fought", "attacked", "confronted"]):
                if "brave" not in traits:
                    traits.append("brave")

            if any(word in action_lower for word in ["helped", "saved", "protected"]):
                if "compassionate" not in traits:
                    traits.append("compassionate")

            if any(word in action_lower for word in ["lied", "deceived", "betrayed"]):
                if "deceptive" not in traits:
                    traits.append("deceptive")

            if any(word in action_lower for word in ["analyzed", "investigated", "reasoned"]):
                if "analytical" not in traits:
                    traits.append("analytical")

    def _is_action_consistent(self, action: str, personality: List[str]) -> bool:
        """Check if action is consistent with personality."""
        action_lower = action.lower()

        # Brave characters don't flee without reason
        if "brave" in personality and any(word in action_lower for word in ["fled", "ran away", "cowered"]):
            return False

        # Compassionate characters don't harm innocents
        if "compassionate" in personality and any(word in action_lower for word in ["murdered", "killed innocent"]):
            return False

        # Deceptive characters wouldn't confess easily
        if "deceptive" in personality and any(word in action_lower for word in ["confessed immediately", "told truth"]):
            return False

        return True  # Default: assume consistent

    def _is_dialogue_consistent(self, character: str, new_dialogue: List[str]) -> bool:
        """Check dialogue voice consistency."""
        char_data = self.characters[character]
        previous_samples = char_data["dialogue_samples"]

        if not previous_samples:
            return True  # No history to compare against

        # Simple check: average word length
        prev_avg_len = sum(len(d.split()) for d in previous_samples) / len(previous_samples)
        new_avg_len = sum(len(d.split()) for d in new_dialogue) / len(new_dialogue) if new_dialogue else 0

        # Allow 50% variation
        if abs(new_avg_len - prev_avg_len) > prev_avg_len * 0.5:
            return False

        return True

    def _analyze_personality_evolution(self, character: str) -> List[Dict[str, Any]]:
        """Analyze how character's personality has evolved."""
        char_data = self.characters[character]
        history = char_data["development_history"]

        evolution = []
        for i, entry in enumerate(history):
            evolution.append({
                "episode": entry["episode"],
                "stage": f"Stage {i+1}/{len(history)}",
                "actions_count": len(entry["actions"])
            })

        return evolution

    def _extract_key_moments(self, character: str) -> List[str]:
        """Extract key character moments."""
        char_data = self.characters[character]
        history = char_data["development_history"]

        key_moments = []
        for entry in history:
            # Take first major action per episode
            if entry["actions"]:
                key_moments.append(f"Episode {entry['episode']}: {entry['actions'][0]}")

        return key_moments

    def _determine_arc_stage(self, character: str, at_episode: int) -> str:
        """Determine character arc stage."""
        char_data = self.characters[character]
        total_appearances = len([h for h in char_data["development_history"] if h["episode"] <= at_episode])

        if total_appearances == 1:
            return "introduction"
        elif total_appearances <= 3:
            return "development"
        elif total_appearances <= 6:
            return "conflict"
        else:
            return "resolution"

    def export_state(self) -> Dict[str, Any]:
        """Export character tracker state."""
        return {
            "characters": self.characters,
            "relationships": self.relationships,
            "arcs": self.arcs
        }

    def import_state(self, state: Dict[str, Any]) -> None:
        """Import character tracker state."""
        self.characters = state.get("characters", {})
        self.relationships = state.get("relationships", {})
        self.arcs = state.get("arcs", {})
        logger.info("[CharTracker] State imported")
