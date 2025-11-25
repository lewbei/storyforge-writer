"""
Writer Agent - Generates story content based on plan.

Responsibilities:
- Read the plan from PlannerAgent
- Write story content (chapters or complete story)
- Auto-expand content if too short
- Validate content quality
- Signal completion when done
"""

import logging
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class WriterAgent:
    """Agent responsible for generating story content."""

    def __init__(self, client: OpenAI, config: Dict[str, Any], tools: list, tool_map: Dict, project_path: str):
        self.client = client
        self.config = config
        self.tools = tools
        self.tool_map = tool_map
        self.project_path = project_path
        self.word_count = 0

        # Loaded context from planning files
        self.story_bible = None
        self.analysis_plan = None

        # RESEARCH-BACKED: Dynamic temperature scheduling (EDT Sampling, arXiv:2403.14541)
        # Higher temp for drafting (creativity), lower for critique (analytical), balanced for polish
        self.temperature_schedule = {
            "draft": 0.8,      # High creativity for initial content generation
            "critique": 0.5,   # Analytical precision for identifying issues
            "polish": 0.6      # Balance between creativity and coherence
        }

        # RESEARCH-BACKED: Best-of-N sampling (EQ-Bench, Verbalized Sampling)
        # Generates N drafts, selects best one - achieves 2-3x diversity improvement
        self.enable_best_of_n = True  # Set to False to disable
        self.n_drafts = 3  # Generate 3 drafts per episode (higher quality selection)

        # RESEARCH-BACKED: Show-don't-tell enhancement (Midgen AI, Sudowrite)
        # Replaces abstract statements with concrete sensory details
        self.enable_sensory_pass = True  # Set to False to disable

    def write(self, user_prompt: str) -> Dict[str, Any]:
        """
        Write story content using a Draft-Critique-Polish pipeline.
        
        Args:
            user_prompt: Original user request
            
        Returns:
            Dict containing writing status and stats
        """
        logger.info("WriterAgent: Starting structured content generation...")
        
        # 1. Analyze Request & Plan
        structure = self._analyze_request(user_prompt)
        logger.info(f"WriterAgent: Detected structure: {structure}")
        
        # 2. Load Context
        self._load_context()
        
        # 3. Execute Pipeline for each unit
        total_words = 0
        
        for unit in structure:
            unit_type = unit["type"]
            number = unit["number"]
            logger.info(f"WriterAgent: Processing {unit_type} {number}...")
            
            # A. Draft (with optional Best-of-N sampling)
            if self.enable_best_of_n and self.n_drafts > 1:
                logger.info(f"Generating {self.n_drafts} draft candidates (Best-of-N)...")
                drafts = [self._draft_content(unit, user_prompt) for _ in range(self.n_drafts)]

                # Critique each draft
                critiques = [self._critique_content(d, unit) for d in drafts]

                # Select best draft
                draft, critique = self._select_best_draft(drafts, critiques, unit)
                logger.info(f"Selected best draft from {self.n_drafts} candidates")
            else:
                # Standard single draft
                draft = self._draft_content(unit, user_prompt)

                # B. Critique
                critique = self._critique_content(draft, unit)

            # B.5. Show-Don't-Tell Enhancement (optional)
            if self.enable_sensory_pass:
                draft = self._enhance_sensory_details(draft, unit)
                logger.info("Applied show-don't-tell sensory enhancement")

            # C. Polish
            final_content = self._polish_content(draft, critique, unit)
            
            # D. Save
            self._save_content(unit, final_content)
            
            # Estimate words
            words = len(final_content.split())
            total_words += words
            self.word_count = total_words
            
        return {
            "success": True,
            "word_count": total_words,
            "message": "Writing complete with Draft-Critique-Polish pipeline",
            "iterations": len(structure) * 3
        }

    def _analyze_request(self, user_prompt: str) -> list:
        """Determine episodes/chapters to write."""
        import re
        prompt_lower = user_prompt.lower()
        
        # Detect count
        count = 1
        unit_type = "chapter"
        
        episode_match = re.search(r'(\d+)[-\s]*(episode)', prompt_lower)
        chapter_match = re.search(r'(\d+)[-\s]*(chapter)', prompt_lower)
        
        if episode_match:
            count = int(episode_match.group(1))
            unit_type = "episode"
        elif chapter_match:
            count = int(chapter_match.group(1))
            unit_type = "chapter"
            
        return [{"type": unit_type, "number": i} for i in range(1, count + 1)]

    def _load_context(self):
        """Load project files into context for the LLM to use."""
        import os
        import json

        # Load story_bible.json
        bible_path = os.path.join(self.project_path, "story_bible.json")
        if os.path.exists(bible_path):
            try:
                with open(bible_path, 'r', encoding='utf-8') as f:
                    self.story_bible = json.load(f)
                logger.info(f"Loaded story_bible.json from {bible_path}")
            except Exception as e:
                logger.warning(f"Could not load story_bible.json: {e}")
                self.story_bible = None
        else:
            logger.warning(f"story_bible.json not found at {bible_path}")

        # Load analysis_plan.md
        plan_path = os.path.join(self.project_path, "analysis_plan.md")
        if os.path.exists(plan_path):
            try:
                with open(plan_path, 'r', encoding='utf-8') as f:
                    self.analysis_plan = f.read()
                logger.info(f"Loaded analysis_plan.md ({len(self.analysis_plan)} chars)")
            except Exception as e:
                logger.warning(f"Could not load analysis_plan.md: {e}")
                self.analysis_plan = None
        else:
            logger.warning(f"analysis_plan.md not found at {plan_path}")

    def _draft_content(self, unit: Dict, user_prompt: str) -> str:
        """Generate initial draft."""
        import json
        logger.info(f"Drafting {unit['type']} {unit['number']}...")

        # Build context from loaded planning files
        context_section = ""
        if self.story_bible:
            context_section += f"\n\n=== STORY BIBLE (USE THESE NAMES EXACTLY) ===\n{json.dumps(self.story_bible, indent=2)}\n"
        if self.analysis_plan:
            # Include first 4000 chars of plan to stay within context limits
            plan_excerpt = self.analysis_plan[:4000]
            if len(self.analysis_plan) > 4000:
                plan_excerpt += "\n... (plan continues)"
            context_section += f"\n\n=== ANALYSIS PLAN (FOLLOW THIS STRUCTURE) ===\n{plan_excerpt}\n"

        system_prompt = """You are a Story Writer. Write a COMPLETE ROUGH DRAFT with professional quality.

CRITICAL: You MUST follow the STORY BIBLE and ANALYSIS PLAN provided below.
- Use character names EXACTLY as specified in the story bible
- Follow the plot structure from the analysis plan
- Do NOT invent new character names - use ONLY names from the story bible

QUALITY GUIDELINES:

1. DIALOGUE QUALITY:
   - Every character needs a UNIQUE voice (not generic)
   - Include subtext - what's NOT said is important
   - Use action beats between dialogue (e.g., "She looked away. 'Fine.'")
   - Example: Instead of "Okay" use "Sure. Whatever you say." (reveals attitude)

2. SHOW DON'T TELL:
   - NEVER summarize emotions (e.g., "she was scared")
   - SHOW through action (e.g., "Her hand trembled on the doorknob")
   - SHOW through sensory details (e.g., "Cold sweat trickled down her spine")

3. PACING & SENTENCE VARIETY:
   - Vary sentence length: mix short (5-10 words) with longer (20-30 words)
   - Average 15-20 words per sentence
   - Use micro-breathers for emphasis: One-sentence paragraphs for tension
   - Example: "The door opened. Silence. Then footsteps."

4. CHARACTER NAMES - MANDATORY:
   - Use ONLY character names from the STORY BIBLE below
   - NEVER invent or change character names
   - If story bible says protagonist is "Lena Voss", use "Lena Voss" - not Elena, not Vasquez
   - Maintain name consistency throughout

5. SENSORY DETAILS:
   - Choose the MOST impactful detail, not every detail
   - Limit to 2-3 sensory elements per sentence
   - Balance sensory prose with action and dialogue
""" + context_section

        user_message = f"""Write a FULL-LENGTH draft for {unit['type']} {unit['number']}.
        Original Request: {user_prompt}

        CRITICAL REQUIREMENTS:
        - TARGET LENGTH: Extract word count from user prompt (e.g., "2500+ words" means write 2500+ words)
        - If no specific count mentioned, write minimum 2000 words
        - MANDATORY: Use character names from the STORY BIBLE above - do NOT invent names
        - MANDATORY: Follow the plot structure from the ANALYSIS PLAN above
        - End with a compelling hook/cliffhanger
        - Include complete scenes with beginning, middle, end
        - DO NOT write a summary or outline - write the FULL prose narrative
        - Apply ALL quality guidelines above

        This is a DRAFT, not a summary. Write the complete narrative prose for this {unit['type']}."""

        response = self.client.chat.completions.create(
            model=self.config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=self.temperature_schedule["draft"]  # 0.8 - High creativity
            # No max_tokens limit - let model generate full content
        )

        draft = response.choices[0].message.content
        word_count = len(draft.split())
        logger.info(f"Draft generated: {word_count} words")
        return draft

    def _critique_content(self, draft: str, unit: Dict) -> str:
        """Critique the draft."""
        logger.info(f"Critiquing {unit['type']} {unit['number']}...")
        
        system_prompt = """You are a Ruthless Editor. Analyze the draft.
        Identify 3 specific areas for improvement:
        1. SHOW DON'T TELL: Where is the writing too expository?
        2. SENSORY DETAILS: Where can we add sight, sound, smell, touch, taste?
        3. PACING: Is it too fast or too slow?
        """
        
        user_message = f"""Critique this draft for {unit['type']} {unit['number']}:\n\n{draft[:2000]}... (truncated)"""
        
        response = self.client.chat.completions.create(
            model=self.config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=self.temperature_schedule["critique"],  # 0.5 - Analytical
            max_tokens=1000
        )
        return response.choices[0].message.content

    def _polish_content(self, draft: str, critique: str, unit: Dict) -> str:
        """Apply critique and polish."""
        logger.info(f"Polishing {unit['type']} {unit['number']}...")

        system_prompt = """You are a Best-Selling Author. POLISH this draft.

        GOAL: Transform the draft into a MASTERPIECE.
        - Fix all issues identified in the critique.
        - Maximize sensory immersion.
        - Sharpen dialogue.
        - Ensure emotional resonance.
        - MAINTAIN THE FULL LENGTH - do not truncate or summarize
        """

        user_message = f"""Rewrite {unit['type']} {unit['number']} based on this critique:

        CRITIQUE:
        {critique}

        ORIGINAL DRAFT:
        {draft}

        CRITICAL: Output the COMPLETE polished version at full length. Do not summarize or truncate."""

        response = self.client.chat.completions.create(
            model=self.config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=self.temperature_schedule["polish"]  # 0.6 - Balanced
            # No max_tokens limit - let model generate full content
        )
        return response.choices[0].message.content

    def _select_best_draft(self, drafts: list, critiques: list, unit: Dict) -> tuple:
        """
        Select the best draft from multiple candidates using LLM judgment.

        RESEARCH-BACKED: Pairwise comparison from EQ-Bench Creative Writing v3

        Args:
            drafts: List of draft candidates
            critiques: List of corresponding critiques
            unit: Episode/chapter info

        Returns:
            Tuple of (best_draft, best_critique)
        """
        logger.info(f"Selecting best draft from {len(drafts)} candidates...")

        # Use LLM to judge which draft is best
        judgment_prompt = f"""Compare these {len(drafts)} drafts for {unit['type']} {unit['number']}.

CRITERIA:
1. Storytelling quality (engaging, compelling)
2. Show-don't-tell (sensory details, not exposition)
3. Character voice (distinct, authentic)
4. Pacing (proper rhythm, tension)
5. Technical quality (grammar, flow)

Rate each draft 1-10 on each criterion, then select the BEST one.

DRAFTS:
"""

        for i, draft in enumerate(drafts, 1):
            judgment_prompt += f"\n--- DRAFT {i} ---\n{draft[:800]}...\n"

        judgment_prompt += "\n\nOUTPUT: Best draft number (1, 2, etc.) with brief justification."

        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": "You are a Master Editor. Select the best draft objectively."},
                    {"role": "user", "content": judgment_prompt}
                ],
                temperature=0.3,  # Low temp for consistent judgment
                max_tokens=300
            )

            judgment = response.choices[0].message.content
            logger.info(f"Selection judgment: {judgment[:100]}...")

            # Extract best draft number (look for "Draft 1", "Draft 2", "**Draft 1**", etc.)
            import re
            # Handle various formats: "Draft 1", "**Draft 1**", "draft 1", "DRAFT 1"
            match = re.search(r'\*{0,2}(?:draft|DRAFT|Draft)\s*(\d+)\*{0,2}', judgment)
            if match:
                best_idx = int(match.group(1)) - 1
                if 0 <= best_idx < len(drafts):
                    logger.info(f"Selected Draft {best_idx + 1} as best")
                    return drafts[best_idx], critiques[best_idx]

            # Fallback: use first draft if parsing fails
            logger.warning("Could not parse draft selection, using first draft")
            return drafts[0], critiques[0]

        except Exception as e:
            logger.error(f"Draft selection failed: {e}, using first draft")
            return drafts[0], critiques[0]

    def _enhance_sensory_details(self, draft: str, unit: Dict) -> str:
        """
        Apply show-don't-tell enhancement pass to add sensory details.

        RESEARCH-BACKED: Midgen AI Show-Don't-Tell Converter, Sudowrite sensory tools

        Args:
            draft: Current draft content
            unit: Episode/chapter info

        Returns:
            Enhanced draft with concrete sensory details
        """
        logger.info(f"Enhancing sensory details for {unit['type']} {unit['number']}...")

        enhancement_prompt = f"""Perform a SELECTIVE 'Show-Don't-Tell' pass on this draft.

TASK: Identify abstract statements and replace them with CONCRETE sensory details.

CRITICAL BALANCE RULES:
1. Be SELECTIVE - not every sentence needs enhancement
2. Limit to 2-3 sensory details per sentence MAX
3. Choose the MOST IMPACTFUL detail, not every detail
4. Maintain readability - avoid "prose overload"
5. Balance enhanced descriptions with clean action and dialogue

TECHNIQUES (Use Selectively):
1. SIGHT: Visual details (colors, shapes, movements, lighting)
2. SOUND: Specific sounds (not just "a noise" but "creaking floorboards")
3. SMELL: Olfactory details (musty, acrid, sweet, etc.)
4. TOUCH: Physical sensations (rough texture, cold metal, sticky residue)
5. TASTE: Taste descriptions where relevant
6. ACTION: Replace "he was angry" with "he clenched his fists, jaw tight"
7. DIALOGUE SUBTEXT: What characters DON'T say is as important as what they do

AVOID:
- Abstract emotions stated directly ("she was sad")
- STACKING TOO MANY DETAILS (e.g., "rain stung, wind howled, thunder crashed, lightning flashed" - pick 1-2!)
- Info-dumping backstory
- "As you know, Bob" exposition
- Overloading EVERY sentence with sensory details

EXAMPLES:
❌ "He was nervous."
✅ "His hands trembled."

❌ "The room was messy with clothes, papers, food, trash, and dirt everywhere."
✅ "Empty takeout containers covered every surface."

❌ TOO MUCH: "Rain lashed the cobblestones, wind howled through alleyways, thunder crashed overhead, lightning flickered, and the smell of ozone filled the air."
✅ BALANCED: "Rain lashed the cobblestones. Thunder crashed overhead."

DRAFT TO ENHANCE:
{draft}

OUTPUT: The COMPLETE enhanced draft with SELECTIVE improvements to abstract statements. Keep the plot, structure, and LENGTH intact. Maintain readability - enhance KEY moments, not every sentence. DO NOT TRUNCATE OR SHORTEN THE CONTENT."""

        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": "You are a Sensory Enhancement Specialist. Transform telling into showing through concrete details."},
                    {"role": "user", "content": enhancement_prompt}
                ],
                temperature=0.6  # Balanced creativity
                # No max_tokens limit - let model generate full enhanced content
            )
            enhanced = response.choices[0].message.content

            # BUGFIX: Validate word count isn't lost during enhancement
            draft_words = len(draft.split())
            enhanced_words = len(enhanced.split())
            if enhanced_words < draft_words * 0.8:  # Lost more than 20% of words
                logger.warning(f"Sensory enhancement truncated content ({draft_words} -> {enhanced_words} words), using original draft")
                return draft

            logger.info(f"Sensory enhancement complete ({draft_words} -> {enhanced_words} words)")
            return enhanced
        except Exception as e:
            logger.error(f"Sensory enhancement failed: {e}, returning original draft")
            return draft

    def _save_content(self, unit: Dict, content: str):
        """Save the content using the appropriate tool."""
        func_name = f"write_{unit['type']}" # write_chapter or write_episode
        
        # Find the tool function
        tool_func = self.tool_map.get(func_name)
        if not tool_func:
            # Fallback to write_file
            tool_func = self.tool_map.get("write_file")
            filename = f"{unit['type']}_{unit['number']:02d}.md"
            tool_func(filename=filename, content=content, mode="overwrite")
        else:
            if unit['type'] == 'episode':
                tool_func(episode_number=unit['number'], content=content)
            else:
                tool_func(chapter_number=unit['number'], content=content)

    def print_report(self, result: Dict, console=None):
        """Print writing report."""
        if console:
            from rich.panel import Panel
            from rich.text import Text

            report = Text()
            report.append("Story Writing Report\n\n", style="bold cyan")

            if result["success"]:
                report.append("[OK] Writing completed successfully\n", style="bold green")
                report.append(f"Iterations: {result['iterations']}\n", style="green")
                report.append(f"Est. Word Count: {result['word_count']:,}\n", style="green")
            else:
                report.append("[ERROR] Writing failed\n", style="bold red")
                report.append(f"Error: {result.get('error', 'Unknown')}\n", style="red")
                if result.get('word_count'):
                    report.append(f"Partial word count: {result['word_count']:,}\n", style="yellow")

            console.print(Panel(report, title="Agent 3: Writer", border_style="cyan"))
        else:
            print("\n=== Story Writing Report ===")
            if result["success"]:
                print(f"[OK] Writing completed ({result['iterations']} iterations)")
                print(f"Est. Word Count: {result['word_count']:,}")
            else:
                print(f"[ERROR] Writing failed: {result.get('error')}")
                if result.get('word_count'):
                    print(f"Partial word count: {result['word_count']:,}")
            print("")
