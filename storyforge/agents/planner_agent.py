"""
Planner Agent - Creates comprehensive story plans and structure.

Responsibilities:
- Analyze user prompt to extract genre, themes, length
- Load appropriate genre templates
- Create character profiles and world-building
- Design plot structure and beat sheets
- Generate analysis_plan.md
- Create story_bible.json for consistency
- Validate project setup
"""

import logging
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Agent responsible for story planning and structure."""

    def __init__(self, client: OpenAI, config: Dict[str, Any], tools: list, tool_map: Dict):
        self.client = client
        self.config = config
        self.tools = tools
        self.tool_map = tool_map
        self.project_path = None

        # RESEARCH-BACKED: Hierarchical Planning (coarse-to-fine)
        # Source: AI Story Generation (Mark Riedl)
        # First generate high-level structure, then refine to scene-level details
        self.enable_hierarchical = True
        self.planning_levels = ["series_arc", "episode_beats", "scene_cards"]

    def plan(self, user_prompt: str) -> Dict[str, Any]:
        """
        Create a comprehensive story plan based on user prompt.

        Args:
            user_prompt: User's story request

        Returns:
            Dict containing plan details, project path, and status
        """
        logger.info("PlannerAgent: Starting story planning...")

        # 1. Brainstorming Phase
        logger.info("PlannerAgent: Brainstorming concepts...")
        best_concept = self._brainstorm_concepts(user_prompt)
        logger.info(f"Selected concept: {best_concept[:100]}...")

        # 1.5. Hierarchical Planning (if enabled)
        if self.enable_hierarchical:
            logger.info("PlannerAgent: Starting hierarchical planning (coarse-to-fine)...")
            hierarchical_plan = self._hierarchical_planning(best_concept, user_prompt)
            best_concept = f"{best_concept}\n\n=== HIERARCHICAL STRUCTURE ===\n{hierarchical_plan}"

        # 2. Planning Phase
        system_prompt = self._get_planning_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create a detailed story plan for this concept:\n\n{best_concept}\n\nOriginal Request: {user_prompt}"}
        ]

        # Planning loop (max 10 iterations)
        max_iterations = 10
        for iteration in range(1, max_iterations + 1):
            logger.info(f"PlannerAgent: Iteration {iteration}/{max_iterations}")

            try:
                # Call AI model
                response = self.client.chat.completions.create(
                    model=self.config["model"],
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=4096
                )

                message = response.choices[0].message
                content = message.content or ""

                # Check for completion signal
                if "PLANNING COMPLETE" in content:
                    logger.info("PlannerAgent: Initial planning complete. Running self-critique...")
                    
                    # 3. Self-Critique & Refinement
                    critique_result = self._critique_and_refine(messages)
                    if critique_result:
                        content = critique_result
                        
                    return {
                        "success": True,
                        "project_path": self.project_path,
                        "message": content,
                        "iterations": iteration
                    }

                # Add assistant message
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

                        # Execute tool
                        tool_func = self.tool_map.get(func_name)
                        if tool_func:
                            try:
                                result = tool_func(**args)
                                logger.debug(f"Tool {func_name} executed successfully")

                                # Track project path from create_project
                                if func_name == "create_project" and "Active project:" in str(result):
                                    import re
                                    match = re.search(r"Active project:\s*'([^']+)'", str(result))
                                    if match:
                                        self.project_path = match.group(1)
                                        logger.info(f"Project path: {self.project_path}")

                                # Add tool result
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
                        else:
                            logger.warning(f"Unknown tool: {func_name}")

            except Exception as e:
                logger.error(f"PlannerAgent error: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "iterations": iteration
                }

        # Max iterations reached
        return {
            "success": False,
            "error": "Max planning iterations reached without completion",
            "iterations": max_iterations
        }

    def _brainstorm_concepts(self, user_prompt: str) -> str:
        """Generate multiple concepts and select the best one."""
        system_prompt = """You are a Master Story Architect.
        
        TASK:
        1. Analyze the user's request.
        2. Generate 3 DISTINCT, high-concept story angles/premises based on the request.
           - Angle A: The expected/classic approach (executed perfectly)
           - Angle B: The subversive/twist approach (flips tropes)
           - Angle C: The artistic/psychological approach (deep character focus)
        3. Evaluate each against "Masterpiece Criteria" (Originality, Conflict, Theme).
        4. Select the BEST one.
        5. Output ONLY the selected concept with a brief rationale.
        
        Format:
        SELECTED CONCEPT: [Title]
        PREMISE: [Logline]
        SYNOPSIS: [1 paragraph summary]
        WHY IT WORKS: [Rationale]
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=messages,
                temperature=0.8, # High temp for creativity
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Brainstorming failed: {e}")
            return user_prompt # Fallback to original prompt

    def _critique_and_refine(self, messages: list) -> str:
        """Critique the generated plan and request refinements."""
        # RESEARCH-BACKED: Expanded from 3 to 5 dimensions (Analytics Vidhya, Agentic AI Reflection)
        critique_prompt = """CRITICAL REVIEW:
        Review the plan above. Identify weaknesses across 5 dimensions:
        1. CONFLICT: Is the conflict strong enough? Are stakes high and escalating?
        2. CHARACTER AGENCY: Are the characters active or passive? Do they make meaningful choices?
        3. PACING: Is the structure well-paced? Are there natural highs and lows?
        4. THEME COHERENCE: Does the theme resonate throughout? Is there a clear thematic spine?
        5. ENDING: Is the ending satisfying and earned? Does it deliver on the promise?

        If the plan is solid across all 5 dimensions, say "PLAN VERIFIED".
        If needs work, output "REFINEMENT NEEDED: [Specific dimension] - [Instructions]" and fix it.
        """
        
        messages.append({"role": "user", "content": critique_prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=messages,
                tools=self.tools, # Keep tools available for updates
                tool_choice="auto",
                temperature=0.5,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Critique failed: {e}")
            return None

    def _hierarchical_planning(self, concept: str, user_prompt: str) -> str:
        """
        Generate hierarchical story structure (coarse-to-fine).

        RESEARCH-BACKED: Coarse-to-fine planning (Mark Riedl, AI Story Generation)
        - Level 1: High-level series arc (beginning, middle, end)
        - Level 2: Episode beats (key moments per episode)
        - Level 3: Scene cards (scene-by-scene breakdown)

        Args:
            concept: Selected story concept
            user_prompt: Original user request

        Returns:
            Hierarchical plan structure
        """
        logger.info("Generating hierarchical plan...")

        # Level 1: Series Arc
        arc_prompt = f"""Based on this concept, outline the HIGH-LEVEL SERIES ARC.

CONCEPT:
{concept}

OUTPUT FORMAT:
**SERIES ARC:**
- Beginning: [Setup and hook]
- Middle: [Rising action and complications]
- End: [Climax and resolution]
"""

        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": "You are a Story Architect. Create high-level structure."},
                    {"role": "user", "content": arc_prompt}
                ],
                temperature=0.6,
                max_tokens=500
            )
            series_arc = response.choices[0].message.content
            logger.info("Level 1 (Series Arc) complete")

            # Level 2: Episode Beats (if multi-episode)
            import re
            episode_match = re.search(r'(\d+)[-\s]*(episode)', user_prompt.lower())
            if episode_match:
                count = int(episode_match.group(1))
                beats_prompt = f"""Break the series arc into {count} episode beats.

SERIES ARC:
{series_arc}

OUTPUT FORMAT:
**EPISODE BEATS:**
Episode 1: [Key moment and hook]
Episode 2: [Key moment and hook]
...
"""

                response = self.client.chat.completions.create(
                    model=self.config["model"],
                    messages=[
                        {"role": "system", "content": "You are a Story Architect. Break arc into episode beats."},
                        {"role": "user", "content": beats_prompt}
                    ],
                    temperature=0.6,
                    max_tokens=800
                )
                episode_beats = response.choices[0].message.content
                logger.info(f"Level 2 (Episode Beats) complete for {count} episodes")

                return f"{series_arc}\n\n{episode_beats}"
            else:
                return series_arc

        except Exception as e:
            logger.error(f"Hierarchical planning failed: {e}")
            return "Hierarchical planning unavailable, proceeding with standard planning."

    def _get_planning_system_prompt(self) -> str:
        """Get system prompt optimized for deep planning."""
        return """You are a Story Planning Agent. Your goal is to create a MASTERPIECE plan.
        
        PLANNING WORKFLOW:
        1. Create project using create_project
        2. Load masterpiece guidelines using get_masterpiece_guidelines
        3. Load genre template using load_genre_template (if applicable)
        4. Analyze the selected concept (Theme, Irony, Dramatic Question)
        5. Create detailed analysis_plan.md covering:
           - HIGH CONCEPT: Logline, Hook, Core Conflict
           - CHARACTERS: 
             * Protagonist: Ghost, Lie, Want, Need
             * Antagonist: Mirror of Protagonist, Justification
             * Supporting: Thematic function
           - THEME: Thematic Spine, Value Shift (e.g., Life to Death)
           - WORLD: Rules, Paradoxes, Setting as Character
           - STRUCTURE: 
             * Inciting Incident (destabilizes world)
             * Turning Points (irreversible changes)
             * Crisis (best bad choice)
             * Climax (truth revealed)
             * Resolution (new equilibrium)
           - FOR MULTI-EPISODE SERIES: Detailed Episode Arcs
        6. Create story_bible.json with key details for consistency
        7. Validate setup using validate_project_setup
        8. When complete, say "PLANNING COMPLETE"
        
        MULTI-EPISODE/CHAPTER PLANNING:
        - Ensure each episode has its own Mini-Plot (Beginning, Middle, End)
        - Ensure the Series Arc advances in every episode
        - Plan "Watercooler Moments" (shocking twists/reveals)
        
        IMPORTANT:
        - Don't settle for clichés. Twist them.
        - Ensure the Protagonist is ACTIVE. They must make choices.
        - The Antagonist must be formidable and competent.
        - Use tools to save all plans to files.
        - Never write actual story content - that's the Writer Agent's job.
        
        Available tools: create_project, get_masterpiece_guidelines, load_genre_template, write_file, validate_project_setup, update_story_bible
        """

    def print_report(self, result: Dict, console=None):
        """Print planning report."""
        if console:
            from rich.panel import Panel
            from rich.text import Text

            report = Text()
            report.append("Story Planning Report\n\n", style="bold cyan")

            if result["success"]:
                report.append("[OK] Planning completed successfully\n", style="bold green")
                report.append(f"Iterations: {result['iterations']}\n", style="green")
                if result.get('project_path'):
                    report.append(f"Project: {result['project_path']}\n", style="green")
                report.append("\nFiles created:\n", style="bold")
                report.append("  - analysis_plan.md\n")
                report.append("  - story_bible.json\n")
            else:
                report.append("[ERROR] Planning failed\n", style="bold red")
                report.append(f"Error: {result.get('error', 'Unknown')}\n", style="red")

            console.print(Panel(report, title="Agent 2: Planner", border_style="cyan"))
        else:
            print("\n=== Story Planning Report ===")
            if result["success"]:
                print(f"[OK] Planning completed ({result['iterations']} iterations)")
                if result.get('project_path'):
                    print(f"Project: {result['project_path']}")
            else:
                print(f"[ERROR] Planning failed: {result.get('error')}")
            print("")
