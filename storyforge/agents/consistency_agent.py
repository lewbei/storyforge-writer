"""
Consistency Agent - Validates narrative consistency for professional publishing.

Responsibilities:
- Track character names, appearances, traits across chapters
- Validate timeline and chronology
- Check world rules consistency (magic, tech, geography)
- Detect plot holes and contradictions
- Reference story_bible.json for canonical truth
- Prevent continuity errors that break reader immersion
"""

import logging
from typing import Dict, Any, List
from openai import OpenAI

logger = logging.getLogger(__name__)


class ConsistencyAgent:
    """Agent responsible for consistency validation and continuity checking."""

    def __init__(self, client: OpenAI, config: Dict[str, Any], tools: list, tool_map: Dict):
        self.client = client
        self.config = config
        self.tools = tools
        self.tool_map = tool_map

        # SCORE Framework inspired components (arXiv:2503.23512)
        # Episode summaries and item tracking for consistency
        self.episode_summaries = {}  # Track plot development across episodes
        self.item_status = {}        # Track objects and character states
        self.character_states = {}   # Track character development and actions

    def validate_consistency(self, project_path: str) -> Dict[str, Any]:
        """
        Validate all content for consistency and continuity.

        Args:
            project_path: Path to project directory

        Returns:
            Dict with errors, warnings, and approval status
        """
        logger.info("ConsistencyAgent: Starting consistency validation...")

        # System prompt for consistency checking
        system_prompt = self._get_consistency_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Validate consistency for all content in {project_path}"}
        ]

        # Consistency check loop
        max_iterations = 8
        validation_result = None

        for iteration in range(1, max_iterations + 1):
            logger.info(f"ConsistencyAgent: Iteration {iteration}/{max_iterations}")

            try:
                response = self.client.chat.completions.create(
                    model=self.config["model"],
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.2,  # Very low temp for consistent analysis
                    max_tokens=4096
                )

                message = response.choices[0].message
                content = message.content or ""

                # Check for completion signal
                if "CONSISTENCY CHECK COMPLETE" in content:
                    logger.info("ConsistencyAgent: Validation complete!")
                    validation_result = self._parse_consistency_result(content)
                    break

                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": getattr(message, "tool_calls", None) or []
                })

                # Execute tool calls
                tool_calls = getattr(message, "tool_calls", None) or []
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc.function.name
                        args_str = tc.function.arguments

                        try:
                            import json
                            args = json.loads(args_str)
                        except Exception as e:
                            logger.error(f"Failed to parse args for {func_name}: {e}")
                            continue

                        tool_func = self.tool_map.get(func_name)
                        if tool_func:
                            try:
                                result = tool_func(**args)
                                logger.debug(f"Tool {func_name} executed successfully")

                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": func_name,
                                    "content": str(result)
                                })
                            except Exception as e:
                                logger.error(f"Tool {func_name} failed: {e}")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": func_name,
                                    "content": f"ERROR: {e}"
                                })

            except Exception as e:
                logger.error(f"ConsistencyAgent error: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }

        if not validation_result:
            validation_result = {
                "errors": ["Validation incomplete - max iterations reached"],
                "warnings": [],
                "approved": False
            }

        validation_result["success"] = True
        return validation_result

    def _generate_episode_summary(self, episode_number: int, content: str) -> str:
        """
        Generate SCORE-style episode summary for continuity tracking.

        RESEARCH-BACKED: SCORE Framework (arXiv:2503.23512)

        Args:
            episode_number: Episode number
            content: Episode content

        Returns:
            Structured summary with key events, character actions, and item status changes
        """
        summary_prompt = f"""Summarize Episode {episode_number} for continuity tracking.

REQUIRED FORMAT:
**Key Events:** [List 3-5 major plot points]
**Character Actions:** [What did main characters do?]
**Item Status Changes:** [Objects introduced, destroyed, or changed]
**Timeline:** [When did this happen relative to other episodes?]
**Continuity Notes:** [Important details for future episodes]

Content:
{content[:1500]}... (first 1500 chars)
"""

        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": "You are a Continuity Tracker. Generate concise, structured episode summaries."},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0.3,  # Low temp for factual summarization
                max_tokens=500
            )
            summary = response.choices[0].message.content
            self.episode_summaries[episode_number] = summary
            logger.info(f"Generated SCORE summary for Episode {episode_number}")
            return summary
        except Exception as e:
            logger.error(f"Failed to generate episode summary: {e}")
            return ""

    def _track_item_status(self, episode_number: int, content: str) -> Dict[str, str]:
        """
        Track status of key items (objects, weapons, artifacts) across episodes.

        SCORE-inspired item tracking for consistency checking.

        Args:
            episode_number: Episode number
            content: Episode content

        Returns:
            Dict mapping item names to their current status
        """
        tracking_prompt = f"""Identify all significant items in Episode {episode_number} and their status.

TRACK:
- Physical objects (weapons, artifacts, documents, keys)
- Status: introduced/used/destroyed/lost/given-to-[character]

FORMAT:
Item Name: Status

Content:
{content[:1000]}...
"""

        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": "You are an Item Tracker. List items and their status changes."},
                    {"role": "user", "content": tracking_prompt}
                ],
                temperature=0.2,
                max_tokens=300
            )
            # Parse response into dict
            items = {}
            for line in response.choices[0].message.content.split('\n'):
                if ':' in line:
                    item, status = line.split(':', 1)
                    items[item.strip()] = status.strip()

            self.item_status[episode_number] = items
            logger.info(f"Tracked {len(items)} items in Episode {episode_number}")
            return items
        except Exception as e:
            logger.error(f"Failed to track items: {e}")
            return {}

    def _get_consistency_system_prompt(self) -> str:
        """Get system prompt optimized for consistency checking."""
        return """You are a Continuity Editor for a complex series.
        
        Your job: Ensure the universe holds together perfectly.
        
        CONSISTENCY VALIDATION WORKFLOW:
        1. Read story_bible.json using read_project_files - this is CANONICAL TRUTH
        2. Read all story content (story.md or Chapter_*.md files)
        3. CONSTRUCT A TIMELINE:
           - List every major event in order.
           - Check for overlaps or impossibilities (e.g., travel time).
        4. Track and validate across 5 dimensions:
        
           A. CHARACTER CONSISTENCY
              - Names spelled identically (not "Sarah" then "Sara")
              - Physical descriptions match (eye color, height, age)
              - Personality traits remain consistent
              - Speech patterns/dialect consistent
              - Known relationships maintained
        
           B. TIMELINE CONSISTENCY
              - Events in chronological order
              - No time travel accidents (character at two places)
              - Ages/dates make sense
              - Seasons/weather logical
              - "Two weeks later" math checks out
        
           C. WORLD RULES CONSISTENCY
              - Magic/tech systems work the same way
              - Geography doesn't change (city to east stays east)
              - Established rules aren't broken
              - Technology level consistent
              - Cultural norms maintained
        
           D. PLOT CONSISTENCY
              - Resolved conflicts stay resolved
              - Dead characters stay dead
              - Revealed secrets stay revealed
              - Objects don't vanish/reappear
              - Motivations make sense
        
           E. FACT CONSISTENCY
              - Details from story_bible match text
              - Previously stated facts remain true
              - No contradictory information
              - Proper noun spellings consistent
        
        5. Classify findings:
           - ERROR: Critical continuity break (must fix)
           - WARNING: Minor inconsistency (should review)
        
        6. Reference specific locations (Chapter/paragraph)
        
        When complete, respond with:
        CONSISTENCY CHECK COMPLETE:
        Errors: [count]
        - [CRITICAL ERROR with location]
        Warnings: [count]
        - [Minor issue with location]
        Approved: [Yes/No]
        
        STANDARDS:
        - 0 errors = Approved
        - 1-2 errors = Not approved, must fix
        - 3+ errors = Major consistency problems
        - Warnings don't block approval but should be reviewed
        
        Use read_project_files to analyze story_bible.json and all content.
        Be THOROUGH - one mistake ruins reader trust.
        """

    def _parse_consistency_result(self, content: str) -> Dict[str, Any]:
        """Parse consistency validation result from agent response."""
        import re

        result = {
            "errors": [],
            "warnings": [],
            "approved": True,
            "raw_report": content
        }

        # Extract errors
        errors_section = re.search(r"Errors:\s*(\d+)(.*?)(?:Warnings:|Approved:|$)", content, re.DOTALL)
        if errors_section:
            count = int(errors_section.group(1))
            if count > 0:
                result["approved"] = False
                errors_text = errors_section.group(2)
                result["errors"] = [
                    line.strip().lstrip('-').strip()
                    for line in errors_text.split('\n')
                    if line.strip() and line.strip().startswith('-')
                ]

        # Extract warnings
        warnings_section = re.search(r"Warnings:\s*(\d+)(.*?)(?:Approved:|$)", content, re.DOTALL)
        if warnings_section:
            warnings_text = warnings_section.group(2)
            result["warnings"] = [
                line.strip().lstrip('-').strip()
                for line in warnings_text.split('\n')
                if line.strip() and line.strip().startswith('-')
            ]

        # Extract approval
        approved_match = re.search(r"Approved:\s*(Yes|No)", content, re.IGNORECASE)
        if approved_match:
            result["approved"] = approved_match.group(1).lower() == "yes"

        return result

    def fix_if_needed(self, project_path: str, validation_result: Dict) -> Dict[str, Any]:
        """
        Automatically fix consistency errors if found.

        Args:
            project_path: Path to project directory
            validation_result: Result from validate_consistency

        Returns:
            Dict with fix status
        """
        if validation_result["approved"]:
            logger.info("Content consistent - no fixes needed")
            return {"fixed": False, "reason": "No consistency errors found"}

        logger.info(f"Content has {len(validation_result['errors'])} consistency errors")

        # System prompt for fixing
        system_prompt = f"""You are a Professional Editor fixing continuity errors.

Errors found:
{chr(10).join('- ' + error for error in validation_result['errors'])}

Warnings:
{chr(10).join('- ' + warning for warning in validation_result.get('warnings', []))}

Your job: Fix ALL consistency errors while preserving the story.

WORKFLOW:
1. Read story_bible.json - this is TRUTH
2. Read the story content
3. Fix each error:
   - Character name: Update to match story_bible
   - Timeline: Adjust dates/events
   - World rules: Fix contradictions
   - Plot: Resolve logical issues
4. Update story_bible.json if needed
5. Write corrected content using write_file
6. Say "CONSISTENCY FIXES COMPLETE" when done

Be minimal - only fix the specific errors, don't rewrite unnecessarily.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Fix consistency errors in {project_path}"}
        ]

        # Fix loop
        max_iterations = 10
        for iteration in range(1, max_iterations + 1):
            logger.info(f"Fix iteration {iteration}/{max_iterations}")

            try:
                response = self.client.chat.completions.create(
                    model=self.config["model"],
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=4096
                )

                message = response.choices[0].message
                content = message.content or ""

                if "CONSISTENCY FIXES COMPLETE" in content:
                    logger.info("Fixes complete! Verifying...")
                    
                    # Verification pass
                    verify_result = self.validate_consistency(project_path)
                    if verify_result["approved"]:
                        logger.info("Verification successful!")
                        return {"fixed": True, "iterations": iteration}
                    else:
                        logger.warning("Verification failed - errors remain.")
                        # Continue loop to fix remaining errors
                        messages.append({
                            "role": "user", 
                            "content": f"Verification failed. Remaining errors: {verify_result['errors']}. Please fix them."
                        })
                        continue

                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": getattr(message, "tool_calls", None) or []
                })

                # Execute tool calls
                tool_calls = getattr(message, "tool_calls", None) or []
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc.function.name
                        args_str = tc.function.arguments

                        try:
                            import json
                            args = json.loads(args_str)
                        except:
                            continue

                        tool_func = self.tool_map.get(func_name)
                        if tool_func:
                            try:
                                result = tool_func(**args)
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": func_name,
                                    "content": str(result)
                                })
                            except Exception as e:
                                logger.error(f"Tool {func_name} failed: {e}")

            except Exception as e:
                logger.error(f"Fix error: {e}")
                return {"fixed": False, "error": str(e)}

        return {"fixed": False, "reason": "Max iterations reached"}

    def print_report(self, result: Dict, console=None):
        """Print consistency report."""
        if console:
            from rich.panel import Panel
            from rich.text import Text

            report = Text()
            report.append("Consistency Validation Report\n\n", style="bold cyan")

            # Status
            if result.get("approved"):
                report.append("[OK] No continuity errors found!\n", style="bold green")
            else:
                report.append("[ERROR] Continuity errors detected!\n", style="bold red")

            report.append(f"Errors: {len(result.get('errors', []))}\n", style="red" if result.get("errors") else "green")
            report.append(f"Warnings: {len(result.get('warnings', []))}\n\n", style="yellow" if result.get("warnings") else "green")

            if result.get("errors"):
                report.append("Critical Errors:\n", style="bold red")
                for error in result["errors"][:5]:
                    report.append(f"  - {error}\n", style="red")
                if len(result["errors"]) > 5:
                    report.append(f"  ... and {len(result['errors']) - 5} more\n", style="dim")
                report.append("\n")

            if result.get("warnings"):
                report.append("Warnings:\n", style="bold yellow")
                for warning in result["warnings"][:3]:
                    report.append(f"  - {warning}\n", style="yellow")
                if len(result["warnings"]) > 3:
                    report.append(f"  ... and {len(result['warnings']) - 3} more\n", style="dim")

            console.print(Panel(report, title="Agent 5: Consistency", border_style="cyan"))
        else:
            print("\n=== Consistency Validation Report ===")
            print(f"Approved: {'Yes' if result.get('approved') else 'No'}")
            print(f"Errors: {len(result.get('errors', []))}")
            print(f"Warnings: {len(result.get('warnings', []))}")
            print("")
