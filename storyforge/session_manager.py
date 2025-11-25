"""
Session Manager - Handles saving and resuming pipeline state.

Enables resuming story generation from the last completed stage if the process
is interrupted (crash, timeout, user abort, etc.)
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages session state for resumable story generation.

    State is saved after each pipeline stage completes, enabling
    resumption from the last successful checkpoint.
    """

    STAGES = ["settings", "planning", "writing", "qa", "consistency"]

    def __init__(self, output_dir: str = "output"):
        """
        Initialize session manager.

        Args:
            output_dir: Base output directory for sessions
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.sessions_dir = self.output_dir / ".sessions"
        self.sessions_dir.mkdir(exist_ok=True)

        self.current_session: Optional[Dict[str, Any]] = None
        self.session_file: Optional[Path] = None

    def create_session(self, user_prompt: str) -> Dict[str, Any]:
        """
        Create a new session for a story generation run.

        Args:
            user_prompt: The user's story request

        Returns:
            New session state dict
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_session = {
            "session_id": session_id,
            "user_prompt": user_prompt,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "status": "in_progress",
            "current_stage": "settings",
            "completed_stages": [],
            "project_path": None,
            "results": {
                "settings": None,
                "planning": None,
                "writing": None,
                "qa": None,
                "consistency": None
            },
            "qa_iterations": 0,
            "final_score": None
        }

        self.session_file = self.sessions_dir / f"session_{session_id}.json"
        self._save_session()

        logger.info(f"Created new session: {session_id}")
        return self.current_session

    def update_stage(self, stage: str, result: Dict[str, Any], success: bool = True) -> None:
        """
        Update session state after a stage completes.

        Args:
            stage: Stage name (settings, planning, writing, qa, consistency)
            result: Result dict from the stage
            success: Whether the stage succeeded
        """
        if not self.current_session:
            logger.warning("No active session to update")
            return

        self.current_session["results"][stage] = result
        self.current_session["updated_at"] = datetime.now().isoformat()

        if success:
            if stage not in self.current_session["completed_stages"]:
                self.current_session["completed_stages"].append(stage)

            # Update current stage to next
            stage_index = self.STAGES.index(stage)
            if stage_index < len(self.STAGES) - 1:
                self.current_session["current_stage"] = self.STAGES[stage_index + 1]
            else:
                self.current_session["current_stage"] = "complete"
                self.current_session["status"] = "complete"

        # Track project path from planning
        if stage == "planning" and result.get("project_path"):
            self.current_session["project_path"] = result["project_path"]

        # Track QA score
        if stage == "qa":
            self.current_session["qa_iterations"] = self.current_session.get("qa_iterations", 0) + 1
            if result.get("score"):
                self.current_session["final_score"] = result["score"]

        self._save_session()
        logger.info(f"Updated session stage: {stage} (success={success})")

    def mark_failed(self, stage: str, error: str) -> None:
        """
        Mark session as failed at a specific stage.

        Args:
            stage: Stage where failure occurred
            error: Error message
        """
        if not self.current_session:
            return

        self.current_session["status"] = "failed"
        self.current_session["current_stage"] = stage
        self.current_session["error"] = error
        self.current_session["updated_at"] = datetime.now().isoformat()

        self._save_session()
        logger.error(f"Session failed at {stage}: {error}")

    def mark_complete(self, final_score: Optional[int] = None) -> None:
        """
        Mark session as complete.

        Args:
            final_score: Final QA score (optional)
        """
        if not self.current_session:
            return

        self.current_session["status"] = "complete"
        self.current_session["current_stage"] = "complete"
        self.current_session["updated_at"] = datetime.now().isoformat()

        if final_score is not None:
            self.current_session["final_score"] = final_score

        self._save_session()
        logger.info(f"Session marked complete (score: {final_score})")

    def get_incomplete_sessions(self) -> List[Dict[str, Any]]:
        """
        Find all incomplete sessions that can be resumed.

        Returns:
            List of incomplete session dicts
        """
        incomplete = []

        for session_file in self.sessions_dir.glob("session_*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session = json.load(f)

                if session.get("status") == "in_progress":
                    session["session_file"] = str(session_file)
                    incomplete.append(session)

            except Exception as e:
                logger.warning(f"Failed to load session {session_file}: {e}")

        # Sort by most recent first
        incomplete.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return incomplete

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific session by ID.

        Args:
            session_id: Session ID to load

        Returns:
            Session dict or None if not found
        """
        session_file = self.sessions_dir / f"session_{session_id}.json"

        if not session_file.exists():
            logger.warning(f"Session not found: {session_id}")
            return None

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                self.current_session = json.load(f)
                self.session_file = session_file

            logger.info(f"Loaded session: {session_id}")
            return self.current_session

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def get_resume_stage(self) -> Optional[str]:
        """
        Get the stage to resume from.

        Returns:
            Stage name to resume from, or None if session is complete
        """
        if not self.current_session:
            return None

        if self.current_session.get("status") == "complete":
            return None

        return self.current_session.get("current_stage")

    def should_skip_stage(self, stage: str) -> bool:
        """
        Check if a stage should be skipped (already completed).

        Args:
            stage: Stage name to check

        Returns:
            True if stage was already completed successfully
        """
        if not self.current_session:
            return False

        return stage in self.current_session.get("completed_stages", [])

    def get_stage_result(self, stage: str) -> Optional[Dict[str, Any]]:
        """
        Get the result from a previously completed stage.

        Args:
            stage: Stage name

        Returns:
            Stage result dict or None
        """
        if not self.current_session:
            return None

        return self.current_session.get("results", {}).get(stage)

    def _save_session(self) -> None:
        """Save current session to disk."""
        if not self.current_session or not self.session_file:
            return

        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_session, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def cleanup_old_sessions(self, max_age_days: int = 7) -> int:
        """
        Remove sessions older than max_age_days.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of sessions cleaned up
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=max_age_days)
        cleaned = 0

        for session_file in self.sessions_dir.glob("session_*.json"):
            try:
                mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                if mtime < cutoff:
                    session_file.unlink()
                    cleaned += 1
                    logger.info(f"Cleaned up old session: {session_file.name}")

            except Exception as e:
                logger.warning(f"Failed to cleanup {session_file}: {e}")

        return cleaned


def get_session_manager(output_dir: str = "output") -> SessionManager:
    """
    Get a session manager instance.

    Args:
        output_dir: Base output directory

    Returns:
        SessionManager instance
    """
    return SessionManager(output_dir)
