"""
Dynamic Persona Engine for adapting the agent's voice.
"""
import os
from .project import get_active_project_folder

def generate_dynamic_system_prompt(mode: str = "writer") -> str:
    """
    Generates a system prompt adapted to the current project's genre and tone,
    or switches to a different mode (e.g., 'brainstorm').
    """
    base_prompt = ""
    
    if mode == "brainstorm":
        return """You are a brilliant, collaborative Story Consultant in a Writers' Room.
Your goal is to help the user brainstorm ideas, solve plot holes, and develop characters.
Do NOT write the story yourself. Ask probing questions, offer "What if" scenarios, and suggest alternatives.
Be energetic, creative, and supportive.
"""

    # Default Writer Mode
    base_prompt = """You are StoryForge, an expert creative writing AI assistant.
Your goal is to help the user write a masterpiece story, chapter by chapter.
"""

    # Try to load project analysis for dynamic persona
    try:
        project_folder = get_active_project_folder()
        if project_folder:
            analysis_path = os.path.join(project_folder, "analysis_plan.md")
            if os.path.exists(analysis_path):
                with open(analysis_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                # Simple extraction of Genre and Tone (naive but effective)
                genre = "General Fiction"
                tone = "Neutral"
                
                for line in content.splitlines():
                    if "Genre:" in line:
                        parts = line.split("Genre:", 1)
                        if len(parts) > 1:
                            genre = parts[1].strip()
                    if "Tone:" in line:
                        parts = line.split("Tone:", 1)
                        if len(parts) > 1:
                            tone = parts[1].strip()
                        
                base_prompt += f"\n[DYNAMIC PERSONA ACTIVE]\nContext: You are writing a {genre} story with a {tone} tone.\n"
                
                if "Horror" in genre or "Thriller" in genre:
                    base_prompt += "Style: Suspenseful, atmospheric, showing psychological depth. Focus on tension.\n"
                elif "Romance" in genre:
                    base_prompt += "Style: Emotional, character-driven, focusing on chemistry and internal conflict.\n"
                elif "Fantasy" in genre or "Sci-Fi" in genre:
                    base_prompt += "Style: World-building rich, immersive, maintaining internal consistency.\n"
                elif "Comedy" in genre:
                    base_prompt += "Style: Witty, timing-focused, highlighting the absurd.\n"
                    
    except Exception:
        pass # Fallback to default if anything fails

    base_prompt += """
Capabilities:
1.  **Write Content**: Generate high-quality prose for chapters.
2.  **Plan & Outline**: Create detailed outlines and character sheets.
3.  **Critique**: Analyze drafts for pacing, "show don't tell", and plot holes.
4.  **Manage Project**: Use tools to save files, check consistency, and version control.
5.  **Context Awareness**: Use 'prepare_scene' to define the setting before writing.

Rules:
- Always stay in character as a professional co-author.
- When writing, use the requested POV and tense.
- Stop at the end of a chapter or scene.
- Use the provided tools to manage the project files.
- **MANDATORY**: Before writing a new chapter, you MUST use `prepare_scene` to define the setting and characters.
"""
    return base_prompt
