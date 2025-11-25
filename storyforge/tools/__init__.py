"""
Tools module for the StoryForge AI Agent.
Exports all available tools for the agent to use.
"""

from .writer import (
    write_file_impl,
    write_episode_impl,
    write_chapter_impl,
    analyze_project_characters_impl,
    analyze_project_world_impl,
    analyze_project_plot_impl,
    propose_continuation_outline_impl,
)
from .project import (
    create_project_impl,
    git_init_impl,
    git_status_impl,
    git_commit_impl,
)
from .compression import compress_context_impl
from .reader import read_project_files_impl, clear_file_cache
from .consistency import build_story_bible_impl, validate_chapter_consistency_impl
from .templates import load_genre_template_impl, apply_template_impl
from .conflict import detect_manual_edits_impl, resolve_conflicts_impl
from .critique import critique_chapter_impl
from .writer import prepare_scene_impl

__all__ = [
    'write_file_impl',
    'write_episode_impl',
    'write_chapter_impl',
    'analyze_project_characters_impl',
    'analyze_project_world_impl',
    'analyze_project_plot_impl',
    'propose_continuation_outline_impl',
    'create_project_impl',
    'git_init_impl',
    'git_status_impl',
    'git_commit_impl',
    'critique_chapter_impl',
    'prepare_scene_impl',
    'compress_context_impl',
    'read_project_files_impl',
    'clear_file_cache',
    'build_story_bible_impl',
    'validate_chapter_consistency_impl',
    'load_genre_template_impl',
    'apply_template_impl',
    'detect_manual_edits_impl',
    'resolve_conflicts_impl',
]

