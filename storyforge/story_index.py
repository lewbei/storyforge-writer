"""
Story Index - Keyword-Based Consistency Tracking for Story Continuity

Provides keyword-based search and tracking for:
- Episode indexing and retrieval
- Character consistency checking
- Item/location tracking
- Timeline validation

Note: Uses keyword matching, not embeddings/vectors.
"""

import logging
from typing import List, Dict, Any, Optional
import json
import re

logger = logging.getLogger(__name__)


class StoryIndex:
    """
    Keyword-based indexing system for story consistency checking.

    Tracks characters, items, locations, and events across episodes
    using simple keyword matching and regex extraction.
    """

    def __init__(self):
        self.episode_index = {}  # Store episode summaries
        self.character_memory = {}  # Track character information
        self.world_rules = {}  # Track world-building rules
        self.timeline = []  # Chronological event ordering

    def add_episode(self, episode_number: int, content: str, summary: str) -> None:
        """
        Add episode to the index.

        Args:
            episode_number: Episode number
            content: Full episode content
            summary: Episode summary
        """
        # Extract key entities
        characters = self._extract_characters(content)
        locations = self._extract_locations(content)
        items = self._extract_items(content)

        entry = {
            "episode": episode_number,
            "summary": summary,
            "characters": characters,
            "locations": locations,
            "items": items,
            "word_count": len(content.split()),
            "key_events": self._extract_key_events(content)
        }

        self.episode_index[episode_number] = entry
        logger.info(f"[StoryIndex] Indexed Episode {episode_number}: {len(characters)} chars, {len(items)} items")

    def find_related_episodes(self, current_episode: int, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Find episodes related to query using keyword matching.

        Args:
            current_episode: Current episode number
            query: Search query (e.g., character name, item, location)
            top_k: Number of related episodes to return

        Returns:
            List of related episode entries
        """
        query_lower = query.lower()
        scores = []

        for ep_num, ep_data in self.episode_index.items():
            if ep_num >= current_episode:
                continue  # Only look at previous episodes

            score = 0

            # Check summary
            if query_lower in ep_data["summary"].lower():
                score += 10

            # Check characters
            for char in ep_data["characters"]:
                if query_lower in char.lower():
                    score += 5

            # Check locations
            for loc in ep_data["locations"]:
                if query_lower in loc.lower():
                    score += 3

            # Check items
            for item in ep_data["items"]:
                if query_lower in item.lower():
                    score += 4

            if score > 0:
                scores.append((ep_num, score, ep_data))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        results = [
            {
                "episode": ep_num,
                "relevance_score": score,
                "summary": ep_data["summary"],
                "key_events": ep_data["key_events"]
            }
            for ep_num, score, ep_data in scores[:top_k]
        ]

        logger.info(f"[StoryIndex] Found {len(results)} related episodes for query: '{query}'")
        return results

    def check_character_consistency(self, character: str, current_episode: int) -> Dict[str, Any]:
        """
        Check character consistency across episodes.

        Args:
            character: Character name
            current_episode: Current episode number

        Returns:
            Dict with character history and potential inconsistencies
        """
        appearances = []
        attributes = {}

        for ep_num, ep_data in self.episode_index.items():
            if ep_num >= current_episode:
                continue

            if character in ep_data["characters"]:
                appearances.append({
                    "episode": ep_num,
                    "summary": ep_data["summary"]
                })

                # Extract character attributes from summary
                self._update_character_attributes(character, ep_data["summary"], attributes)

        return {
            "character": character,
            "appearances": appearances,
            "total_appearances": len(appearances),
            "known_attributes": attributes,
            "first_appearance": appearances[0]["episode"] if appearances else None
        }

    def check_item_status(self, item: str, current_episode: int) -> Dict[str, Any]:
        """
        Check item status across episodes.

        Args:
            item: Item name
            current_episode: Current episode number

        Returns:
            Dict with item history
        """
        history = []

        for ep_num, ep_data in self.episode_index.items():
            if ep_num >= current_episode:
                continue

            if item in ep_data["items"]:
                history.append({
                    "episode": ep_num,
                    "status": "present",
                    "context": ep_data["summary"]
                })

        if not history:
            return {
                "item": item,
                "status": "not_found",
                "message": f"Item '{item}' has not appeared in previous episodes"
            }

        return {
            "item": item,
            "status": "tracked",
            "first_appearance": history[0]["episode"],
            "last_seen": history[-1]["episode"],
            "total_appearances": len(history),
            "history": history
        }

    def validate_timeline(self, current_episode: int) -> List[str]:
        """
        Validate timeline consistency.

        Returns:
            List of timeline inconsistencies
        """
        inconsistencies = []

        # Check for temporal paradoxes
        events = []
        for ep_num in range(1, current_episode):
            if ep_num in self.episode_index:
                ep_events = self.episode_index[ep_num]["key_events"]
                for event in ep_events:
                    events.append((ep_num, event))

        # Simple check: look for contradictions
        for i, (ep1, event1) in enumerate(events):
            for ep2, event2 in events[i+1:]:
                if self._are_contradictory(event1, event2):
                    inconsistencies.append(
                        f"Timeline conflict: Episode {ep1} says '{event1}' but Episode {ep2} says '{event2}'"
                    )

        return inconsistencies

    def _extract_characters(self, content: str) -> List[str]:
        """Extract character names from content (simple regex)."""
        # Look for capitalized names (2-3 words)
        pattern = r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})\b'
        matches = re.findall(pattern, content)

        # Filter common words, count frequency
        common_words = {"The", "A", "An", "It", "He", "She", "They", "I", "We"}
        names = [m for m in matches if m not in common_words]

        # Return unique names that appear multiple times
        from collections import Counter
        counts = Counter(names)
        return [name for name, count in counts.items() if count >= 3]

    def _extract_locations(self, content: str) -> List[str]:
        """Extract location names from content."""
        # Simple pattern: "at/in/to [Location Name]"
        pattern = r'(?:at|in|to|from)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)'
        matches = re.findall(pattern, content)
        return list(set(matches))

    def _extract_items(self, content: str) -> List[str]:
        """Extract significant items from content."""
        # Look for "the [Specific Item]" patterns
        pattern = r'the\s+([A-Z][a-z]+(?:\s+of\s+[A-Z][a-z]+)?)'
        matches = re.findall(pattern, content)

        # Filter to items that appear multiple times
        from collections import Counter
        counts = Counter(matches)
        return [item for item, count in counts.items() if count >= 2]

    def _extract_key_events(self, content: str) -> List[str]:
        """Extract key events from content (first 5 paragraphs)."""
        paragraphs = content.split('\n\n')[:5]
        # Take first sentence of first 5 paragraphs as key events
        events = []
        for para in paragraphs:
            sentences = para.split('.')
            if sentences:
                events.append(sentences[0].strip() + '.')
        return events

    def _update_character_attributes(self, character: str, summary: str, attributes: Dict) -> None:
        """Update character attributes from summary."""
        # Simple keyword extraction
        summary_lower = summary.lower()

        # Physical attributes
        if "tall" in summary_lower:
            attributes["height"] = "tall"
        if "short" in summary_lower:
            attributes["height"] = "short"

        # Hair color
        for color in ["blonde", "brown", "black", "red", "gray", "white"]:
            if color in summary_lower:
                attributes["hair"] = color

        # Age indicators
        if "young" in summary_lower:
            attributes["age_category"] = "young"
        if "old" in summary_lower:
            attributes["age_category"] = "old"

    def _are_contradictory(self, event1: str, event2: str) -> bool:
        """Check if two events contradict each other."""
        # Simple contradiction detection
        # Look for negations or opposite statements
        event1_lower = event1.lower()
        event2_lower = event2.lower()

        # Check for "died" vs "alive" contradictions
        if ("died" in event1_lower or "dead" in event1_lower) and "alive" in event2_lower:
            return True
        if "alive" in event1_lower and ("died" in event2_lower or "dead" in event2_lower):
            return True

        # Check for "destroyed" vs "used" contradictions
        if "destroyed" in event1_lower and "used" in event2_lower:
            return True

        return False

    def export_memory(self) -> Dict[str, Any]:
        """Export complete index for checkpointing."""
        return {
            "episode_index": self.episode_index,
            "character_memory": self.character_memory,
            "world_rules": self.world_rules,
            "timeline": self.timeline
        }

    def import_memory(self, memory: Dict[str, Any]) -> None:
        """Import index from checkpoint."""
        self.episode_index = memory.get("episode_index", {})
        self.character_memory = memory.get("character_memory", {})
        self.world_rules = memory.get("world_rules", {})
        self.timeline = memory.get("timeline", [])
        logger.info("[StoryIndex] Memory imported from checkpoint")


# Backward compatibility alias
RAGRetriever = StoryIndex
