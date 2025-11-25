"""
Blackboard Architecture for Multi-Agent Communication

RESEARCH-BACKED: Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture
Source: arXiv:2507.01701

The blackboard acts as a shared workspace where all agents can read and write,
enabling transparent, asynchronous collaboration and emergent problem-solving.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class Blackboard:
    """
    Blackboard architecture for multi-agent communication.

    RESEARCH-BACKED: arXiv:2507.01701 - Blackboard Architecture
    - All agents communicate through shared blackboard
    - Full transparency of all agent actions
    - Async collaboration support
    - Emergent problem-solving
    """

    def __init__(self):
        self.public_space = {}  # All agents can read/write
        self.private_spaces = {}  # Per-agent private workspace
        self.history = []  # Full communication history
        self.locks = {}  # Prevent race conditions

    def write(self, agent_name: str, key: str, value: Any, private: bool = False) -> None:
        """
        Write data to blackboard.

        Args:
            agent_name: Name of agent writing
            key: Data key
            value: Data value
            private: If True, write to agent's private space
        """
        entry = {
            "agent": agent_name,
            "key": key,
            "value": value,
            "timestamp": datetime.now().isoformat(),
            "action": "write"
        }

        if private:
            if agent_name not in self.private_spaces:
                self.private_spaces[agent_name] = {}
            self.private_spaces[agent_name][key] = entry
            logger.debug(f"[Blackboard] {agent_name} wrote to private space: {key}")
        else:
            self.public_space[key] = entry
            logger.info(f"[Blackboard] {agent_name} wrote to public: {key}")

        self.history.append(entry)

    def read(self, agent_name: str, key: str, from_agent: Optional[str] = None) -> Optional[Any]:
        """
        Read data from blackboard.

        Args:
            agent_name: Name of agent reading
            key: Data key to read
            from_agent: If provided, read from specific agent's private space

        Returns:
            Data value or None if not found
        """
        # Read from public space by default
        if from_agent is None:
            if key in self.public_space:
                value = self.public_space[key]["value"]
                logger.debug(f"[Blackboard] {agent_name} read from public: {key}")

                # Log read action
                self.history.append({
                    "agent": agent_name,
                    "key": key,
                    "timestamp": datetime.now().isoformat(),
                    "action": "read"
                })

                return value
        else:
            # Read from another agent's private space (if allowed)
            if from_agent in self.private_spaces and key in self.private_spaces[from_agent]:
                value = self.private_spaces[from_agent][key]["value"]
                logger.debug(f"[Blackboard] {agent_name} read from {from_agent}'s private: {key}")
                return value

        logger.warning(f"[Blackboard] {agent_name} failed to read: {key}")
        return None

    def query(self, agent_name: str, pattern: str) -> List[Dict[str, Any]]:
        """
        Query blackboard for entries matching pattern.

        Args:
            agent_name: Name of agent querying
            pattern: Key pattern to match (supports wildcards)

        Returns:
            List of matching entries
        """
        import re
        regex = re.compile(pattern.replace("*", ".*"))

        matches = []
        for key, entry in self.public_space.items():
            if regex.match(key):
                matches.append({"key": key, **entry})

        logger.info(f"[Blackboard] {agent_name} queried '{pattern}': {len(matches)} matches")
        return matches

    def subscribe(self, agent_name: str, key_pattern: str) -> None:
        """
        Subscribe to updates on specific keys.

        Args:
            agent_name: Name of agent subscribing
            key_pattern: Key pattern to subscribe to
        """
        if "subscriptions" not in self.public_space:
            self.public_space["subscriptions"] = {"value": {}, "agent": "system", "timestamp": datetime.now().isoformat()}

        subs = self.public_space["subscriptions"]["value"]
        if agent_name not in subs:
            subs[agent_name] = []

        subs[agent_name].append(key_pattern)
        logger.info(f"[Blackboard] {agent_name} subscribed to: {key_pattern}")

    def get_history(self, agent_name: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get communication history.

        Args:
            agent_name: Filter by agent name (optional)
            limit: Maximum number of entries

        Returns:
            List of history entries
        """
        if agent_name:
            filtered = [h for h in self.history if h.get("agent") == agent_name]
            return filtered[-limit:]
        return self.history[-limit:]

    def clear(self, agent_name: str = "system") -> None:
        """
        Clear blackboard (admin only).

        Args:
            agent_name: Name of agent clearing (must be system)
        """
        if agent_name == "system":
            self.public_space.clear()
            self.private_spaces.clear()
            logger.info("[Blackboard] Cleared by system")
        else:
            logger.warning(f"[Blackboard] {agent_name} attempted unauthorized clear")

    def export_state(self) -> Dict[str, Any]:
        """
        Export complete blackboard state for checkpointing.

        Returns:
            Dict containing full blackboard state
        """
        return {
            "public_space": self.public_space,
            "private_spaces": self.private_spaces,
            "history": self.history[-100:]  # Last 100 entries
        }

    def import_state(self, state: Dict[str, Any]) -> None:
        """
        Import blackboard state from checkpoint.

        Args:
            state: Previously exported state
        """
        self.public_space = state.get("public_space", {})
        self.private_spaces = state.get("private_spaces", {})
        self.history = state.get("history", [])
        logger.info("[Blackboard] State imported from checkpoint")

    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get status of all agents using blackboard.

        Returns:
            Dict with agent activity stats
        """
        agent_stats = {}
        for entry in self.history:
            agent = entry.get("agent")
            if agent not in agent_stats:
                agent_stats[agent] = {"reads": 0, "writes": 0}

            if entry.get("action") == "read":
                agent_stats[agent]["reads"] += 1
            elif entry.get("action") == "write":
                agent_stats[agent]["writes"] += 1

        return agent_stats
