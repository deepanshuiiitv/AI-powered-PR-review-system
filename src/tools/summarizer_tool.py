"""
Summarizer Tool: Aggregates findings from all tools into final score and verdict.
"""

from src.state import ReviewState


def summarizer_tool(state: ReviewState) -> ReviewState:
    """
    Aggregate all findings into final score and verdict.
    Calculates: final_score, final_verdict, final_summary
    """
    
    print("  [Tool] Summarizing findings...")
    
    try:
        # Count issues by severity
        critical_count = len([x for x in state.critical_issues if x.get('severity') == 'critical'])
        high_count = len([x for x in state.security_issues if x.get('severity') == 'high'])
        medium_count = len([x for x in state.code_quality_issues if x.get('severity') == 'medium'])
        low_count = len([x for x in state.code_quality_issues if x.get('severity') == 'low'])
        
        # Calculate score (0-10)
        # Start at 10, deduct for issues
        score = 10.0
        score -= critical_count * 2.0  # Each critical = -2
        score -= high_count * 1.5      # Each high = -1.5
        score -= medium_count * 0.5    # Each medium = -0.5
        score -= low_count * 0.2       # Each low = -0.2
        
        score = max(1.0, min(10.0, score))  # Clamp to 1-10
        
        # Determine verdict
        if critical_count > 0:
            verdict = "REQUEST_CHANGES"
            summary = f"Found {critical_count} critical issue(s) that must be fixed before merging."
        elif high_count > 2 or medium_count > 5:
            verdict = "REQUEST_CHANGES"
            summary = f"Found {high_count} high-severity and {medium_count} medium issues. Please address before merging."
        elif high_count > 0 or medium_count > 0:
            verdict = "COMMENT"
            summary = f"Found {high_count} high and {medium_count} medium issues. Consider addressing these improvements."
        elif state.positive_aspects:
            verdict = "APPROVE"
            summary = "Code looks good! No critical issues found."
        else:
            verdict = "COMMENT"
            summary = "Minor suggestions for improvement, but code is acceptable."
        
        state.final_score = score
        state.final_verdict = verdict
        state.final_summary = summary
        
        print(f"    ✓ Score: {score:.1f}/10")
        print(f"    ✓ Verdict: {verdict}")
        print(f"      Issues - Critical: {critical_count}, High: {high_count}, Medium: {medium_count}, Low: {low_count}")
        
    except Exception as e:
        error_msg = f"Summarizer error: {e}"
        print(f"    ✗ {error_msg}")
        state.add_error(error_msg)
        # Set safe defaults
        state.final_score = 5.0
        state.final_verdict = "COMMENT"
        state.final_summary = "Unable to complete review due to error"
    
    return state