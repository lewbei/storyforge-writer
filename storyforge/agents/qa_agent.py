"""
Quality Assurance Agent - Validates content quality for professional publishing.

Responsibilities:
- Review chapters/stories for professional quality
- Check grammar, readability, pacing, engagement
- Validate dialogue sounds natural
- Ensure "show don't tell" principles
- Score content 0-100
- Auto-revise if quality score below threshold
"""

import logging
from typing import Dict, Any, List
from openai import OpenAI

logger = logging.getLogger(__name__)


class QualityAssuranceAgent:
    """Agent responsible for quality assurance and content validation."""

    def __init__(self, client: OpenAI, config: Dict[str, Any], tools: list, tool_map: Dict):
        self.client = client
        self.config = config
        self.tools = tools
        self.tool_map = tool_map
        self.quality_threshold = 90  # Default threshold (can be overridden dynamically)
        self.iteration_count = 0  # Track review iterations for progressive thresholds

        # RESEARCH-BACKED: Progressive QA iteration tracking
        # Track quality improvements across multiple review cycles
        self.review_history = []  # Track all reviews
        self.score_progression = []  # Track score improvements
        self.enable_progression_analysis = True

    def _get_context_aware_threshold(self, phase: str = "final", iteration: int = 1) -> int:
        """
        Calculate context-aware quality threshold based on phase and iteration.

        RESEARCH-BACKED: Dynamic thresholds from Databricks LLM Evaluation Best Practices

        Args:
            phase: "draft", "revision", or "final"
            iteration: Current iteration number (for progressive thresholds)

        Returns:
            Quality threshold (0-100)
        """
        base_thresholds = {
            "draft": 70,      # Lower for early drafts
            "revision": 80,   # Mid-range for revisions
            "final": 90       # High for final publication
        }

        base = base_thresholds.get(phase, 80)

        # Progressive increase: +5 per iteration (max 90)
        progressive = min(base + (iteration * 5), 90)

        logger.info(f"Context-aware threshold: {progressive} (phase={phase}, iteration={iteration})")
        return progressive

    def review_content(self, project_path: str, file_path: str = "story.md", phase: str = "final") -> Dict[str, Any]:
        """
        Review content for quality and provide detailed feedback.

        Args:
            project_path: Path to project directory
            file_path: File to review (default: story.md)
            phase: Content phase ("draft", "revision", or "final") for dynamic threshold

        Returns:
            Dict with quality score, issues, suggestions, and approval status
        """
        logger.info(f"QualityAssuranceAgent: Reviewing {file_path}...")
        self.iteration_count += 1

        # Calculate context-aware threshold
        dynamic_threshold = self._get_context_aware_threshold(phase, self.iteration_count)
        self.quality_threshold = dynamic_threshold

        # System prompt for QA
        system_prompt = self._get_qa_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Review the content from {project_path}/{file_path} for professional publishing quality."}
        ]

        # QA review loop (max 5 iterations for reading + analysis)
        max_iterations = 5
        review_result = None

        for iteration in range(1, max_iterations + 1):
            logger.info(f"QualityAssuranceAgent: Iteration {iteration}/{max_iterations}")

            try:
                response = self.client.chat.completions.create(
                    model=self.config["model"],
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.3,  # Lower temp for consistent analysis
                    max_tokens=4096
                )

                message = response.choices[0].message
                content = message.content or ""

                # Check for QA complete signal
                if "QA REVIEW COMPLETE" in content:
                    logger.info("QualityAssuranceAgent: Review complete!")
                    review_result = self._parse_qa_result(content)
                    break

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
                logger.error(f"QualityAssuranceAgent error: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "score": 0
                }

        if not review_result:
            review_result = {
                "score": 50,
                "issues": ["Review incomplete - max iterations reached"],
                "suggestions": ["Manual review recommended"],
                "approved": False
            }

        review_result["success"] = True

        # Track progression
        if self.enable_progression_analysis:
            self._track_review_progression(review_result)

        return review_result

    def _track_review_progression(self, review_result: Dict[str, Any]) -> None:
        """
        Track QA progression across multiple reviews.

        RESEARCH-BACKED: Progressive quality improvement tracking

        Args:
            review_result: Current review result
        """
        from datetime import datetime

        entry = {
            "timestamp": datetime.now().isoformat(),
            "iteration": self.iteration_count,
            "score": review_result.get("score", 0),
            "approved": review_result.get("approved", False),
            "threshold": self.quality_threshold,
            "issues_count": len(review_result.get("issues", [])),
            "suggestions_count": len(review_result.get("suggestions", []))
        }

        self.review_history.append(entry)
        self.score_progression.append(review_result.get("score", 0))

        logger.info(f"[QA Progression] Score: {entry['score']}, Iteration: {entry['iteration']}, Threshold: {entry['threshold']}")

    def get_progression_stats(self) -> Dict[str, Any]:
        """
        Get QA progression statistics.

        Returns:
            Dict with progression stats
        """
        if not self.score_progression:
            return {"error": "No review history available"}

        return {
            "total_reviews": len(self.review_history),
            "current_score": self.score_progression[-1] if self.score_progression else 0,
            "starting_score": self.score_progression[0] if self.score_progression else 0,
            "improvement": self.score_progression[-1] - self.score_progression[0] if len(self.score_progression) > 1 else 0,
            "average_score": sum(self.score_progression) / len(self.score_progression),
            "highest_score": max(self.score_progression),
            "progression_trend": "improving" if self._is_improving() else "declining",
            "review_history": self.review_history
        }

    def _is_improving(self) -> bool:
        """Check if quality is improving over time."""
        if len(self.score_progression) < 2:
            return True

        # Check if last 3 scores show improvement
        recent = self.score_progression[-3:]
        if len(recent) < 2:
            return True

        # Simple trend: last score > first of recent scores
        return recent[-1] >= recent[0]

    def _get_qa_system_prompt(self) -> str:
        """Get system prompt optimized for quality assurance."""
        return """You are a Master Editor for a Top-Tier Publishing House.
        
        Your job: Ensure every sentence justifies its existence.
        
        QUALITY ASSESSMENT WORKFLOW:
        1. Read the content using read_project_files
        2. Analyze across 7 dimensions (0-100 total):
        
           A. PROSE & MECHANICS (0-15 points)
              - Grammar, spelling, punctuation
              - Sentence variety and rhythm
              - "Invisible" prose that doesn't distract
              
           B. SHOW DON'T TELL (0-15 points)
              - Sensory immersion (sight, sound, smell, touch, taste)
              - Active character choices
              - No info-dumping
              
           C. DIALOGUE (0-15 points)
              - Subtext (what is NOT said)
              - Distinct voices
              - No "As you know, Bob" exposition
              
           D. PACING (0-15 points)
              - Scene structure (Goal -> Conflict -> Disaster)
              - Tension management
              - No boring parts
              
           E. THEME & RESONANCE (0-15 points)
              - Connection to core theme
              - Emotional impact
              - Universal truth
              
           F. CHARACTER DEPTH (0-15 points)
              - Interiority (thoughts/feelings)
              - Motivation is clear
              - Flaws are evident
              
           G. X-FACTOR (0-10 points)
              - Originality
              - Voice
              - The "Wow" factor
              
        3. Calculate total score (0-100)
        4. List specific issues with line/paragraph references
        5. Provide actionable suggestions
        6. Determine if approved (score >= 90)
        
        When complete, respond with:
        QA REVIEW COMPLETE:
        Score: [0-100]
        Issues:
        - [Specific issue with location]
        - [Another issue]
        Suggestions:
        - [Actionable fix]
        - [Another suggestion]
        Approved: [Yes/No]
        
        STANDARDS:
        - Score 90-100: Publishable Masterpiece
        - Score < 90: Needs Revision (Be harsh. We want perfection.)
        
        Use read_project_files to analyze content.
        """

    def _parse_qa_result(self, content: str) -> Dict[str, Any]:
        """Parse QA review result from agent response."""
        import re

        result = {
            "score": 0,
            "issues": [],
            "suggestions": [],
            "approved": False,
            "raw_review": content
        }

        # Extract score
        score_match = re.search(r"Score:\s*(\d+)", content)
        if score_match:
            result["score"] = int(score_match.group(1))

        # Extract issues
        issues_section = re.search(r"Issues:(.*?)(?:Suggestions:|Approved:|$)", content, re.DOTALL)
        if issues_section:
            issues_text = issues_section.group(1)
            result["issues"] = [
                line.strip().lstrip('-').strip()
                for line in issues_text.split('\n')
                if line.strip() and line.strip().startswith('-')
            ]

        # Extract suggestions
        suggestions_section = re.search(r"Suggestions:(.*?)(?:Approved:|$)", content, re.DOTALL)
        if suggestions_section:
            suggestions_text = suggestions_section.group(1)
            result["suggestions"] = [
                line.strip().lstrip('-').strip()
                for line in suggestions_text.split('\n')
                if line.strip() and line.strip().startswith('-')
            ]

        # Extract approval
        approved_match = re.search(r"Approved:\s*(Yes|No)", content, re.IGNORECASE)
        if approved_match:
            result["approved"] = approved_match.group(1).lower() == "yes"
        else:
            # Auto-determine based on score
            result["approved"] = result["score"] >= self.quality_threshold

        return result

    def revise_if_needed(self, project_path: str, review_result: Dict, file_path: str = "story.md") -> Dict[str, Any]:
        """
        Automatically revise content if quality score is below threshold.

        Args:
            project_path: Path to project directory
            review_result: Result from review_content
            file_path: File to revise

        Returns:
            Dict with revision status
        """
        if review_result["approved"]:
            logger.info("Content approved - no revision needed")
            return {"revised": False, "reason": "Quality score meets threshold"}

        logger.info(f"Content needs revision (score: {review_result['score']})")

        # Categorize issues by type for targeted fixes
        issue_categories = self._categorize_issues(review_result['issues'])
        priority_focus = self._get_priority_focus(issue_categories)

        # System prompt for revision - TARGETED approach
        system_prompt = f"""You are a Professional Editor. The content scored {review_result['score']}/100.

PRIORITY FOCUS AREAS (fix these first):
{priority_focus}

All Issues Found:
{chr(10).join('- ' + issue for issue in review_result['issues'])}

Suggestions:
{chr(10).join('- ' + sug for sug in review_result['suggestions'])}

Your job: Make SURGICAL, TARGETED fixes to address the priority issues while maintaining story essence.

CRITICAL INSTRUCTIONS:
1. Output ONLY the final polished prose in the revised file
2. NO meta-comments like "Wait, repurpose:" or "Adjust:"
3. NO editing notes or thought process
4. MAINTAIN all character names exactly as written (do NOT change names between chapters)
5. MAINTAIN plot points, continuity, and story structure
6. MAINTAIN or INCREASE word count (do NOT truncate or summarize)
7. Make SURGICAL fixes - don't rewrite sections that are already good
8. Focus on the PRIORITY FOCUS AREAS first - these will have the biggest score impact

TARGETED FIX TECHNIQUES:
- For SHOW-DON'T-TELL issues: Replace abstract emotions with physical actions/sensations
- For DIALOGUE issues: Add subtext, vary speech patterns between characters
- For PACING issues: Vary sentence length, add micro-breathers for tension
- For CHARACTER issues: Add interiority (thoughts/feelings) and motivation
- For PROSE issues: Fix grammar, vary sentence structure

WORKFLOW:
1. Read the current content using read_project_files
2. Identify specific paragraphs/sentences matching the issues
3. Make targeted surgical improvements to those specific areas
4. Write revised version using write_file with mode="overwrite"
5. Output MUST be clean prose ready for publication
6. Say "REVISION COMPLETE" when done

Remember: Precision > Wholesale rewriting. Fix what's broken, preserve what works.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Revise {project_path}/{file_path} to meet professional quality standards. Remember: Output ONLY clean prose, NO editing notes or meta-comments!"}
        ]

        # Revision loop - limit to 3 iterations to prevent compounding errors
        max_iterations = 3
        for iteration in range(1, max_iterations + 1):
            logger.info(f"Revision iteration {iteration}/{max_iterations}")

            try:
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

                if "REVISION COMPLETE" in content:
                    logger.info("Revision complete!")
                    return {"revised": True, "iterations": iteration}

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
                logger.error(f"Revision error: {e}")
                return {"revised": False, "error": str(e)}

        return {"revised": False, "reason": "Max iterations reached"}

    def _categorize_issues(self, issues: List[str]) -> Dict[str, List[str]]:
        """
        Categorize issues by QA dimension for targeted fixes.

        Categories match the 7 QA scoring dimensions:
        - prose: Grammar, mechanics, sentence variety
        - show_dont_tell: Sensory details, exposition
        - dialogue: Subtext, distinct voices
        - pacing: Scene structure, tension
        - theme: Thematic resonance, emotional impact
        - character: Interiority, motivation, depth
        - xfactor: Originality, voice

        Args:
            issues: List of issue descriptions

        Returns:
            Dict mapping category to list of issues
        """
        categories = {
            "prose": [],
            "show_dont_tell": [],
            "dialogue": [],
            "pacing": [],
            "theme": [],
            "character": [],
            "xfactor": []
        }

        # Keywords for categorization
        keywords = {
            "prose": ["grammar", "spelling", "punctuation", "sentence", "awkward", "clunky", "repetitive", "word choice"],
            "show_dont_tell": ["tell", "show", "sensory", "abstract", "exposition", "info-dump", "describe", "felt", "was sad", "was angry"],
            "dialogue": ["dialogue", "speech", "voice", "conversation", "subtext", "talking", "said", "generic"],
            "pacing": ["pace", "pacing", "slow", "fast", "rushed", "dragging", "tension", "rhythm", "scene"],
            "theme": ["theme", "meaning", "resonance", "emotional", "impact", "message", "universal"],
            "character": ["character", "motivation", "interiority", "depth", "flat", "personality", "thought", "feeling"],
            "xfactor": ["original", "unique", "voice", "wow", "predictable", "cliche", "fresh"]
        }

        for issue in issues:
            issue_lower = issue.lower()
            categorized = False

            for category, kws in keywords.items():
                if any(kw in issue_lower for kw in kws):
                    categories[category].append(issue)
                    categorized = True
                    break

            # Default to prose if no category matched
            if not categorized:
                categories["prose"].append(issue)

        return categories

    def _get_priority_focus(self, issue_categories: Dict[str, List[str]]) -> str:
        """
        Generate priority focus areas based on categorized issues.

        Prioritizes categories with most issues for maximum score improvement.

        Args:
            issue_categories: Dict from _categorize_issues

        Returns:
            Formatted string of priority areas with counts
        """
        # Sort categories by issue count (descending)
        sorted_categories = sorted(
            issue_categories.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        # Map category names to readable labels
        labels = {
            "prose": "PROSE & MECHANICS",
            "show_dont_tell": "SHOW DON'T TELL",
            "dialogue": "DIALOGUE",
            "pacing": "PACING",
            "theme": "THEME & RESONANCE",
            "character": "CHARACTER DEPTH",
            "xfactor": "X-FACTOR (Originality)"
        }

        # Build priority list (top 3 with issues)
        priority_lines = []
        for category, issues in sorted_categories[:3]:
            if issues:
                label = labels.get(category, category.upper())
                priority_lines.append(f"- {label}: {len(issues)} issue(s)")
                # Add first example issue
                if issues:
                    priority_lines.append(f"  Example: {issues[0][:80]}...")

        if not priority_lines:
            return "- No specific issues identified"

        return "\n".join(priority_lines)

    def _sanitize_unicode(self, text: str) -> str:
        """
        Sanitize unicode characters for Windows console compatibility.
        Replaces common unicode characters with ASCII equivalents.
        """
        replacements = {
            '\u2192': '->',      # → (right arrow)
            '\u2190': '<-',      # ← (left arrow)
            '\u2014': '--',      # — (em dash)
            '\u2013': '-',       # – (en dash)
            '\u201c': '"',       # " (left double quote)
            '\u201d': '"',       # " (right double quote)
            '\u2018': "'",       # ' (left single quote)
            '\u2019': "'",       # ' (right single quote)
            '\u2026': '...',     # … (ellipsis)
            '\u00e9': 'e',       # é
            '\u00f1': 'n',       # ñ
            '\u2022': '-',       # • (bullet point)
            '\u00b7': '-',       # · (middle dot)
            '\u2713': '[OK]',    # ✓ (checkmark)
            '\u2717': '[X]',     # ✗ (cross)
            '\u00a0': ' ',       # non-breaking space
        }

        for unicode_char, ascii_char in replacements.items():
            text = text.replace(unicode_char, ascii_char)

        # Remove any remaining non-ASCII characters
        text = text.encode('ascii', 'ignore').decode('ascii')
        return text

    def print_report(self, result: Dict, console=None):
        """Print QA report."""
        if console:
            from rich.panel import Panel
            from rich.text import Text

            report = Text()
            report.append("Quality Assurance Report\n\n", style="bold cyan")

            # Score with color
            score = result.get("score", 0)
            if score >= 90:
                score_style = "bold green"
                grade = "EXCEPTIONAL"
            elif score >= 75:
                score_style = "bold yellow"
                grade = "GOOD"
            elif score >= 60:
                score_style = "bold orange"
                grade = "NEEDS WORK"
            else:
                score_style = "bold red"
                grade = "MAJOR REVISION NEEDED"

            report.append(f"Quality Score: {score}/100 ({grade})\n", style=score_style)
            report.append(f"Approved: {'Yes' if result.get('approved') else 'No'}\n\n", style="bold")

            if result.get("issues"):
                report.append("Issues Found:\n", style="bold red")
                for issue in result["issues"][:5]:  # Show max 5
                    sanitized_issue = self._sanitize_unicode(issue)
                    report.append(f"  - {sanitized_issue}\n", style="red")
                if len(result["issues"]) > 5:
                    report.append(f"  ... and {len(result['issues']) - 5} more\n", style="dim")
                report.append("\n")

            if result.get("suggestions"):
                report.append("Suggestions:\n", style="bold yellow")
                for sug in result["suggestions"][:5]:
                    sanitized_sug = self._sanitize_unicode(sug)
                    report.append(f"  - {sanitized_sug}\n", style="yellow")
                if len(result["suggestions"]) > 5:
                    report.append(f"  ... and {len(result['suggestions']) - 5} more\n", style="dim")

            # Use safe ASCII printing to avoid Windows console unicode issues
            try:
                console.print(Panel(report, title="Agent 4: Quality Assurance", border_style="cyan"))
            except UnicodeEncodeError:
                # Fallback: print plain text if Rich panel fails
                print("\n=== Agent 4: Quality Assurance ===")
                print(self._sanitize_unicode(report.plain))
                print("=" * 40)
        else:
            print("\n=== Quality Assurance Report ===")
            score = result.get("score", 0)
            print(f"Quality Score: {score}/100")
            print(f"Approved: {'Yes' if result.get('approved') else 'No'}")
            if result.get("issues"):
                print(f"\nIssues: {len(result['issues'])} found")
            if result.get("suggestions"):
                print(f"Suggestions: {len(result['suggestions'])} provided")
            print("")
