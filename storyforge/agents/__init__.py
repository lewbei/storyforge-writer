"""
Multi-Agent System for StoryForge AI

This package contains specialized agents for different aspects of story generation:
- SettingsAgent: Validates environment and configuration
- PlannerAgent: Creates story plans and structure
- WriterAgent: Generates story content
- QualityAssuranceAgent: Reviews content for professional quality
- ConsistencyAgent: Validates continuity and catches plot holes
"""

from .settings_agent import SettingsAgent
from .planner_agent import PlannerAgent
from .writer_agent import WriterAgent
from .qa_agent import QualityAssuranceAgent
from .consistency_agent import ConsistencyAgent

__all__ = [
    "SettingsAgent",
    "PlannerAgent",
    "WriterAgent",
    "QualityAssuranceAgent",
    "ConsistencyAgent"
]
