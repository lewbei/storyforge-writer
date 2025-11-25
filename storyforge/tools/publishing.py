import os
import re
from typing import Dict, Any
from .project import get_active_project_folder

def export_manuscript(output_format: str = "markdown") -> str:
    """
    Concatenates all chapter files into a single manuscript file.
    """
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project."
    
    # Find chapter files
    files = os.listdir(project_folder)
    chapter_files = sorted([f for f in files if f.lower().startswith("chapter") and f.endswith(".md")])
    
    if not chapter_files:
        return "STATUS: ERROR | No chapters found to export."
    
    manuscript_content = []
    project_name = os.path.basename(project_folder)
    manuscript_content.append(f"# {project_name}\n\n")
    
    for ch_file in chapter_files:
        path = os.path.join(project_folder, ch_file)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            manuscript_content.append(f"\n\n{content}\n\n")
            manuscript_content.append("---") # Scene break / Chapter break
            
    export_filename = f"{project_name}_Manuscript.md"
    export_path = os.path.join(project_folder, export_filename)
    
    try:
        with open(export_path, "w", encoding="utf-8") as f:
            f.write("\n".join(manuscript_content))
        return f"STATUS: OK | Manuscript exported to {export_path}"
    except Exception as e:
        return f"STATUS: ERROR | Export failed: {e}"

def check_readiness() -> str:
    """
    Scans the project for readiness issues:
    - Word count consistency
    - Placeholders (e.g., [INSERT SCENE HERE])
    - Missing beats
    """
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project."
    
    files = os.listdir(project_folder)
    chapter_files = sorted([f for f in files if f.lower().startswith("chapter") and f.endswith(".md")])
    
    report = []
    report.append(f"READINESS REPORT for {os.path.basename(project_folder)}")
    report.append("-" * 40)
    
    total_words = 0
    issues_found = 0
    
    for ch_file in chapter_files:
        path = os.path.join(project_folder, ch_file)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        word_count = len(content.split())
        total_words += word_count
        
        file_issues = []
        
        # Check for placeholders
        if re.search(r"[.*insert.*]", content, re.IGNORECASE):
            file_issues.append("Found placeholder marker '[...insert...]'")
        if re.search(r"TODO:", content):
            file_issues.append("Found 'TODO:' marker")
            
        # Check for length (arbitrary heuristic)
        if word_count < 500:
            file_issues.append(f"Very short chapter ({word_count} words)")
            
        if file_issues:
            issues_found += 1
            report.append(f"\n[!]{ch_file}:")
            for issue in file_issues:
                report.append(f"  - {issue}")
        else:
            report.append(f"[OK] {ch_file} ({word_count} words)")
            
    report.append("-" * 40)
    report.append(f"Total Words: {total_words}")
    report.append(f"Chapters: {len(chapter_files)}")
    
    if issues_found == 0:
        report.append("\nSTATUS: READY FOR EXPORT")
    else:
        report.append(f"\nSTATUS: {issues_found} ISSUES FOUND")
        
    return "\n".join(report)
