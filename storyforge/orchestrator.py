"""
Multi-Agent Orchestrator for StoryForge AI

Coordinates the execution of multiple specialized agents in sequence:
1. SettingsAgent - Validates environment and configuration
2. PlannerAgent - Creates story plans and structure
3. WriterAgent - Generates story content

This provides a clean, modular architecture where each agent has a single responsibility.

Supports session resumption - if the pipeline is interrupted, it can resume from
the last completed stage.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from openai import OpenAI

from .agents import SettingsAgent, PlannerAgent, WriterAgent, QualityAssuranceAgent, ConsistencyAgent
from .utils import get_tool_definitions, get_tool_map
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class StoryForgeOrchestrator:
    """
    Orchestrates the multi-agent pipeline for story generation.

    Pipeline:
        User Input -> SettingsAgent -> PlannerAgent -> WriterAgent -> QualityAssuranceAgent -> ConsistencyAgent -> Interactive Mode

    Supports resumption from incomplete sessions.
    """

    def __init__(self, console=None, session_manager: Optional[SessionManager] = None):
        """
        Initialize orchestrator.

        Args:
            console: Rich Console instance for pretty output (optional)
            session_manager: SessionManager for state persistence (optional)
        """
        self.console = console
        self.config: Optional[Dict[str, Any]] = None
        self.client: Optional[OpenAI] = None
        self.tools = None
        self.tool_map = None
        self.session_manager = session_manager or SessionManager()

    def run(self, user_prompt: str, resume_session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the full multi-agent pipeline.

        Args:
            user_prompt: User's story generation request
            resume_session_id: Optional session ID to resume from

        Returns:
            Dict with results from all agents
        """
        logger.info("=" * 60)
        logger.info("StoryForge Orchestrator: Starting multi-agent pipeline")
        logger.info(f"User Prompt: {user_prompt}")
        logger.info("=" * 60)

        # Initialize or resume session
        if resume_session_id:
            session = self.session_manager.load_session(resume_session_id)
            if session:
                logger.info(f"Resuming session {resume_session_id} from stage: {session.get('current_stage')}")
                if self.console:
                    self.console.print(f"[green]Resuming session from: {session.get('current_stage')}[/]")
            else:
                logger.warning(f"Session {resume_session_id} not found, starting fresh")
                session = self.session_manager.create_session(user_prompt)
        else:
            session = self.session_manager.create_session(user_prompt)

        results = {
            "user_prompt": user_prompt,
            "settings": None,
            "planning": None,
            "writing": None,
            "qa": None,
            "consistency": None,
            "success": False,
            "session_id": session.get("session_id")
        }

        # ========================================
        # AGENT 1: Settings Validation
        # ========================================
        if not self.session_manager.should_skip_stage("settings"):
            self._print_stage("Agent 1: Settings Validation")

            settings_agent = SettingsAgent()
            success, config, errors, warnings = settings_agent.validate()
            settings_agent.print_report(self.console)

            results["settings"] = {
                "success": success,
                "config": config,
                "errors": errors,
                "warnings": warnings
            }

            # Save session state
            self.session_manager.update_stage("settings", results["settings"], success)

            if not success:
                logger.error("Settings validation failed. Aborting pipeline.")
                self.session_manager.mark_failed("settings", "Settings validation failed")
                return results

            # Store config and initialize client
            self.config = config
        else:
            logger.info("Skipping settings (already completed)")
            results["settings"] = self.session_manager.get_stage_result("settings")
            self.config = results["settings"]["config"]

        self._initialize_client()
        self._initialize_tools()

        # ========================================
        # AGENT 2: Story Planning
        # ========================================
        if not self.session_manager.should_skip_stage("planning"):
            self._print_stage("Agent 2: Story Planning")

            planner_agent = PlannerAgent(
                client=self.client,
                config=self.config,
                tools=self.tools,
                tool_map=self.tool_map
            )

            planning_result = planner_agent.plan(user_prompt)
            planner_agent.print_report(planning_result, self.console)

            results["planning"] = planning_result

            # Save session state
            self.session_manager.update_stage("planning", planning_result, planning_result["success"])

            if not planning_result["success"]:
                logger.error("Story planning failed. Aborting pipeline.")
                self.session_manager.mark_failed("planning", "Story planning failed")
                return results
        else:
            logger.info("Skipping planning (already completed)")
            results["planning"] = self.session_manager.get_stage_result("planning")
            planning_result = results["planning"]

        # ========================================
        # AGENT 3: Story Writing
        # ========================================
        if not self.session_manager.should_skip_stage("writing"):
            self._print_stage("Agent 3: Story Writing")

            writer_agent = WriterAgent(
                client=self.client,
                config=self.config,
                tools=self.tools,
                tool_map=self.tool_map,
                project_path=planning_result.get("project_path", "")
            )

            writing_result = writer_agent.write(user_prompt)
            writer_agent.print_report(writing_result, self.console)

            results["writing"] = writing_result

            # Save session state
            self.session_manager.update_stage("writing", writing_result, writing_result["success"])

            if not writing_result["success"]:
                logger.error("Story writing failed. Aborting pipeline.")
                self.session_manager.mark_failed("writing", "Story writing failed")
                return results
        else:
            logger.info("Skipping writing (already completed)")
            results["writing"] = self.session_manager.get_stage_result("writing")
            writing_result = results["writing"]

        # ========================================
        # AGENT 4: Quality Assurance
        # ========================================
        project_path = planning_result.get("project_path", "")

        if not self.session_manager.should_skip_stage("qa"):
            self._print_stage("Agent 4: Quality Assurance")

            qa_agent = QualityAssuranceAgent(
                client=self.client,
                config=self.config,
                tools=self.tools,
                tool_map=self.tool_map
            )

            qa_result = qa_agent.review_content(project_path)
            qa_agent.print_report(qa_result, self.console)

            results["qa"] = qa_result

            # Auto-revise if quality score too low - LOOP until threshold or max cycles
            max_revision_cycles = 3
            revision_cycle = 0

            while not qa_result.get("approved", False) and qa_result.get("success", False) and revision_cycle < max_revision_cycles:
                revision_cycle += 1
                current_score = qa_result.get("score", 0)
                logger.info(f"Quality score {current_score}/100 below threshold - auto-revising (cycle {revision_cycle}/{max_revision_cycles})...")
                self._print_stage(f"Auto-Revision Cycle {revision_cycle}/{max_revision_cycles}")

                revision_result = qa_agent.revise_if_needed(project_path, qa_result)

                if revision_result.get("revised"):
                    # Re-review after revision
                    logger.info("Re-reviewing after revision...")
                    qa_result = qa_agent.review_content(project_path)
                    qa_agent.print_report(qa_result, self.console)
                    results["qa"] = qa_result

                    # Check if we've reached threshold
                    new_score = qa_result.get("score", 0)
                    if new_score >= 90:
                        logger.info(f"Quality threshold met! Score: {new_score}/100")
                        break
                    elif new_score <= current_score:
                        logger.warning(f"Score not improving ({current_score} -> {new_score}), stopping revision cycles")
                        break
                else:
                    logger.warning("Revision failed, stopping revision cycles")
                    break

            # Save session state
            self.session_manager.update_stage("qa", qa_result, qa_result.get("success", False))
        else:
            logger.info("Skipping QA (already completed)")
            results["qa"] = self.session_manager.get_stage_result("qa")
            qa_result = results["qa"]

        # ========================================
        # AGENT 5: Consistency Validation
        # ========================================
        if not self.session_manager.should_skip_stage("consistency"):
            self._print_stage("Agent 5: Consistency Validation")

            consistency_agent = ConsistencyAgent(
                client=self.client,
                config=self.config,
                tools=self.tools,
                tool_map=self.tool_map
            )

            consistency_result = consistency_agent.validate_consistency(project_path)
            consistency_agent.print_report(consistency_result, self.console)

            results["consistency"] = consistency_result

            # Auto-fix consistency errors if found
            if not consistency_result.get("approved", False) and consistency_result.get("success", False):
                logger.info("Consistency errors found - auto-fixing...")
                self._print_stage("Auto-Fixing Consistency")
                fix_result = consistency_agent.fix_if_needed(project_path, consistency_result)

                if fix_result.get("fixed"):
                    # Re-validate after fixes
                    logger.info("Re-validating after fixes...")
                    consistency_result = consistency_agent.validate_consistency(project_path)
                    consistency_agent.print_report(consistency_result, self.console)
                    results["consistency"] = consistency_result

            # Save session state
            self.session_manager.update_stage("consistency", consistency_result, consistency_result.get("success", False))
        else:
            logger.info("Skipping consistency (already completed)")
            results["consistency"] = self.session_manager.get_stage_result("consistency")
            consistency_result = results["consistency"]

        # ========================================
        # Pipeline Complete
        # ========================================
        # Determine success level
        writing_ok = writing_result["success"]
        qa_approved = qa_result.get("approved", False)
        consistency_approved = consistency_result.get("approved", False)

        # Full success requires all stages to pass
        results["success"] = writing_ok and qa_approved and consistency_approved

        # Track partial success (content generated but quality not met)
        results["partial_success"] = writing_ok and not results["success"]

        if results["success"]:
            self._print_success_summary(results)
            logger.info("Multi-agent pipeline completed successfully!")
            self.session_manager.mark_complete(qa_result.get("score"))
        elif results["partial_success"]:
            # Content was generated but didn't meet quality threshold
            self._print_success_summary(results)
            qa_score = qa_result.get("score", 0)
            if not qa_approved:
                logger.warning(f"Pipeline completed but QA threshold not met (score: {qa_score}/100, threshold: 90)")
            if not consistency_approved:
                logger.warning(f"Pipeline completed but consistency errors remain")
            logger.info("Content generated successfully - available for manual review/editing")
            self.session_manager.mark_complete(qa_score)
        else:
            logger.error("Multi-agent pipeline failed - content generation incomplete")
            self.session_manager.mark_failed("pipeline", "Content generation incomplete")

        return results

    def _initialize_client(self):
        """Initialize OpenAI client from config."""
        try:
            client_kwargs = {
                "api_key": self.config["api_key"],
                "base_url": self.config.get("base_url")
            }

            # Add headers for OpenRouter if applicable
            if self.config.get("provider") == "openrouter":
                headers = {}
                import os
                app_url = os.getenv("OPENROUTER_APP_URL")
                app_title = os.getenv("OPENROUTER_APP_TITLE")
                if app_url:
                    headers["X-OpenRouter-App-Url"] = app_url
                if app_title:
                    headers["X-OpenRouter-App-Title"] = app_title
                if headers:
                    client_kwargs["default_headers"] = headers

            self.client = OpenAI(**client_kwargs)
            logger.info(f"OpenAI client initialized for {self.config.get('provider')}")

        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise

    def _initialize_tools(self):
        """Initialize tools and tool map."""
        try:
            self.tools = get_tool_definitions()
            self.tool_map = get_tool_map()
            logger.info(f"Loaded {len(self.tools)} tools")
        except Exception as e:
            logger.error(f"Failed to initialize tools: {e}")
            raise

    def _print_stage(self, stage: str):
        """Print stage separator."""
        if self.console:
            from rich.panel import Panel
            self.console.print()
            self.console.print(Panel(f"[bold cyan]{stage}[/]", border_style="cyan"))
            self.console.print()
        else:
            print(f"\n{'=' * 60}")
            print(f"  {stage}")
            print(f"{'=' * 60}\n")

    def _print_success_summary(self, results: Dict):
        """Print final success summary."""
        if self.console:
            from rich.panel import Panel
            from rich.text import Text

            summary = Text()
            summary.append("\n[SUCCESS] Story Generation Complete!\n\n", style="bold green")

            # Stats
            planning = results.get("planning", {})
            writing = results.get("writing", {})
            qa = results.get("qa", {})
            consistency = results.get("consistency", {})

            summary.append("Stats:\n", style="bold")
            summary.append(f"  - Planning iterations: {planning.get('iterations', 0)}\n")
            summary.append(f"  - Writing iterations: {writing.get('iterations', 0)}\n")
            summary.append(f"  - Word count: ~{writing.get('word_count', 0):,}\n")
            summary.append(f"  - Quality score: {qa.get('score', 0)}/100\n")
            summary.append(f"  - Consistency: {len(consistency.get('errors', []))} errors, {len(consistency.get('warnings', []))} warnings\n")

            if planning.get("project_path"):
                summary.append(f"\nProject: {planning['project_path']}\n", style="cyan")

            summary.append("\n[OK] Ready for interactive refinement!\n", style="green")

            self.console.print(Panel(summary, title="Pipeline Complete", border_style="green"))
        else:
            print("\n" + "=" * 60)
            print("[SUCCESS] Story Generation Complete!")
            print("=" * 60)
            planning = results.get("planning", {})
            writing = results.get("writing", {})
            qa = results.get("qa", {})
            consistency = results.get("consistency", {})
            print(f"Planning iterations: {planning.get('iterations', 0)}")
            print(f"Writing iterations: {writing.get('iterations', 0)}")
            print(f"Word count: ~{writing.get('word_count', 0):,}")
            print(f"Quality score: {qa.get('score', 0)}/100")
            print(f"Consistency: {len(consistency.get('errors', []))} errors")
            if planning.get("project_path"):
                print(f"Project: {planning['project_path']}")
            print("\n[OK] Ready for interactive refinement!")
            print("=" * 60 + "\n")


def run_autonomous_pipeline(user_prompt: str, console=None, resume_session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to run the full pipeline.

    Args:
        user_prompt: User's story request
        console: Optional Rich Console for pretty output
        resume_session_id: Optional session ID to resume from

    Returns:
        Pipeline results
    """
    orchestrator = StoryForgeOrchestrator(console=console)
    return orchestrator.run(user_prompt, resume_session_id=resume_session_id)


def get_incomplete_sessions() -> list:
    """
    Get list of incomplete sessions that can be resumed.

    Returns:
        List of incomplete session dicts with session_id, user_prompt, current_stage, etc.
    """
    session_manager = SessionManager()
    return session_manager.get_incomplete_sessions()


def resume_session(session_id: str, console=None) -> Dict[str, Any]:
    """
    Resume an incomplete session.

    Args:
        session_id: Session ID to resume
        console: Optional Rich Console for pretty output

    Returns:
        Pipeline results
    """
    session_manager = SessionManager()
    session = session_manager.load_session(session_id)

    if not session:
        return {"success": False, "error": f"Session {session_id} not found"}

    if session.get("status") == "complete":
        return {"success": False, "error": f"Session {session_id} is already complete"}

    user_prompt = session.get("user_prompt", "")

    orchestrator = StoryForgeOrchestrator(console=console, session_manager=session_manager)
    return orchestrator.run(user_prompt, resume_session_id=session_id)
