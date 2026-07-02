"""
Preprocessing Agent: Analyzes PR to determine complexity level.
- Simple PR: few LOC, low risk → use Simple Planner
- Complex PR: many LOC, security files, high risk → use LLM Planner
"""

from src.state import ReviewState


def analyze_pr_complexity(state: ReviewState) -> ReviewState:
    """
    Analyze PR metadata to decide: simple or complex?
    
    Simple PR criteria:
      - < 100 LOC changed
      - No security/critical files touched
      - No "security" keyword in title
      - Low risk indicators
    
    Complex PR criteria:
      - > 100 LOC changed, OR
      - Security files modified, OR
      - "security"/"auth"/"crypto" in title, OR
      - Multiple files changed
    """
    
    # Extract PR data
    pr_data = state.pr_data or {}
    pr_files = state.pr_files or []
    pr_title = pr_data.get("title", "").lower()
    pr_description = pr_data.get("body", "").lower()
    
    # Count stats
    additions = pr_data.get("additions", 0)
    deletions = pr_data.get("deletions", 0)
    total_changes = additions + deletions
    files_changed = len(pr_files)
    
    # Security-related file patterns
    security_patterns = [
        "auth", "security", "secret", "crypto", "password",
        "token", "ssl", "tls", "encryption"
    ]
    
    # Check if any critical files modified
    security_files_modified = False
    for file in pr_files:
        file_path = file.get("filename", "").lower()
        if any(pattern in file_path for pattern in security_patterns):
            security_files_modified = True
            break
    
    # Security keywords in PR title/description
    security_keywords_found = any(
        keyword in pr_title or keyword in pr_description
        for keyword in security_patterns
    )
    
    # Determine complexity
    is_complex = (
        total_changes > 100 or
        files_changed > 5 or
        security_files_modified or
        security_keywords_found
    )
    
    # Determine risk level
    risk_level = "low"
    if security_files_modified or security_keywords_found:
        risk_level = "high"
    elif total_changes > 200 or files_changed > 10:
        risk_level = "medium"
    
    # Collect analysis hints (files of interest)
    analysis_hints = []
    if security_files_modified:
        for file in pr_files:
            file_path = file.get("filename", "").lower()
            if any(pattern in file_path for pattern in security_patterns):
                analysis_hints.append(file.get("filename", ""))
    
    # Update state
    state.is_complex = is_complex
    state.risk_level = risk_level
    state.analysis_hints = analysis_hints
    
    # Logging
    complexity_type = "COMPLEX" if is_complex else "SIMPLE"
    print(f"  [Preprocessing] {complexity_type} PR detected")
    print(f"    -Changes: {total_changes} LOC, {files_changed} files")
    print(f"    -Risk level: {risk_level}")
    if analysis_hints:
        print(f"    -Files to focus: {', '.join(analysis_hints)}")
    
    return state