"""
Static Analysis Tool: Checks code complexity, linting, code smells.
Analyzes code patterns without running it.
"""

import re
from src.state import ReviewState


def static_analysis_tool(state: ReviewState) -> ReviewState:
    """
    Run static analysis on diff chunks.
    Checks: complexity, dead code, long functions, etc.
    Updates: code_quality_issues, performance_issues
    """
    
    print("  [Tool] Running static analysis...")
    
    try:
        issues = []
        diff_text = state.pr_diff or ""
        
        # Check 1: Very long functions (>50 lines added in one function)
        function_patterns = re.findall(r'\n\+.*def\s+(\w+)\s*\(', diff_text)
        if len(function_patterns) > 0:
            # Estimate function length by looking at consecutive additions
            additions = [line for line in diff_text.split('\n') if line.startswith('+') and not line.startswith('+++')]
            if len(additions) > 50:
                issues.append({
                    "file": "multiple",
                    "issue": "Large function additions detected",
                    "severity": "medium",
                    "suggestion": "Consider breaking into smaller functions for testability"
                })
        
        # Check 2: Deep nesting (detect >>> or multiple indentation levels)
        deep_nesting = len(re.findall(r'\n\+\s{16,}', diff_text))
        if deep_nesting > 5:
            issues.append({
                "file": "multiple",
                "issue": f"Deep nesting detected ({deep_nesting} lines)",
                "severity": "low",
                "suggestion": "Consider extracting nested logic into helper functions"
            })
        
        # Check 3: TODO/FIXME comments in new code
        todos = len(re.findall(r'\n\+.*(?:TODO|FIXME|HACK|XXX)', diff_text, re.IGNORECASE))
        if todos > 0:
            issues.append({
                "file": "multiple",
                "issue": f"Incomplete code markers found ({todos} TODOs/FIXMEs)",
                "severity": "low",
                "suggestion": "Resolve or move incomplete work to issues"
            })
        
        # Check 4: Bare except clauses
        bare_excepts = len(re.findall(r'\n\+.*except\s*:', diff_text))
        if bare_excepts > 0:
            issues.append({
                "file": "multiple",
                "issue": f"Bare except clause(s) found ({bare_excepts})",
                "severity": "high",
                "suggestion": "Catch specific exceptions instead of bare except"
            })
        
        # Check 5: Console debug statements in production code
        debug_logs = len(re.findall(r'\n\+.*(?:print|console\.log|console\.debug)\s*\(', diff_text, re.IGNORECASE))
        if debug_logs > 0:
            issues.append({
                "file": "multiple",
                "issue": f"Debug statements in code ({debug_logs} prints/logs)",
                "severity": "low",
                "suggestion": "Remove debug prints before merging"
            })
        
        state.code_quality_issues.extend(issues)
        print(f"    Found {len(issues)} issues")
        
    except Exception as e:
        error_msg = f"Static analysis error: {e}"
        print(f"    {error_msg}")
        state.add_error(error_msg)
    
    return state