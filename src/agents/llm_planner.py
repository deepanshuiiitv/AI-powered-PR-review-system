"""
LLM Planner: For complex PRs, ask Groq LLM which tools should run.

LLM decides dynamically based on:
- PR complexity
- Risk level
- File types touched
- Keywords in description
"""

import json
from groq import Groq
from src.state import ReviewState


def llm_plan_tools(state: ReviewState, groq_api_key: str) -> ReviewState:
    """
    Call Groq LLM to plan which tools should analyze this complex PR.
    
    LLM decides from:
    - static_analysis: lint, complexity checks
    - code_review: code quality & readability
    - security_analysis: security risks
    - performance_analysis: performance issues
    - test_coverage_check: test adequacy
    
    Returns the planned_tools list.
    """
    
    client = Groq(api_key=groq_api_key)
    
    pr_data = state.pr_data or {}
    pr_files = state.pr_files or []
    
    # Build context for LLM
    file_list = ", ".join(f.get("filename", "") for f in pr_files[:10])
    if len(pr_files) > 10:
        file_list += f", ... and {len(pr_files) - 10} more"
    
    planner_prompt = f"""
You are an expert code reviewer planning which analysis tools to run on a GitHub PR.

PR CONTEXT:
- Title: {pr_data.get('title', 'N/A')}
- Complexity: {'Complex' if state.is_complex else 'Simple'}
- Risk Level: {state.risk_level}
- Changes: {pr_data.get('additions', 0) + pr_data.get('deletions', 0)} LOC
- Files: {len(pr_files)} files changed
- Files touched: {file_list}

ANALYSIS HINTS:
{', '.join(state.analysis_hints) if state.analysis_hints else 'None'}

AVAILABLE TOOLS:
1. static_analysis - runs linters, checks code complexity, finds code smells
2. code_review - AI-powered review of code quality, readability, design
3. security_analysis - checks for security vulnerabilities, injection risks, secrets
4. performance_analysis - identifies N+1, blocking I/O, memory leaks
5. test_coverage_check - evaluates test adequacy and edge cases

TASK:
Based on the PR context above, decide which tools MUST run for a thorough review.
Think about:
- Does this PR modify security-critical code?
- Is it large (>100 LOC)?
- Does it touch multiple unrelated areas?
- Are there performance-sensitive changes?
- Are tests included?

Return ONLY a JSON array of tool names to run, like:
["code_review", "security_analysis"]

Be concise. Pick only the tools that add value for THIS specific PR.
"""
    
    try:
        response = client.messages.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": planner_prompt}
            ],
            temperature=0.3,
            max_tokens=200,
        )
        
        response_text = response.content[0].text.strip()
        
        # Parse JSON response
        tools = json.loads(response_text)
        if not isinstance(tools, list):
            tools = ["code_review", "security_analysis"]
        
        # Validate tool names
        valid_tools = {
            "static_analysis", "code_review", "security_analysis",
            "performance_analysis", "test_coverage_check", "summarizer"
        }
        tools = [t for t in tools if t in valid_tools]
        
        # Ensure summarizer is always last (if present)
        if "summarizer" in tools:
            tools.remove("summarizer")
        tools.append("summarizer")
        
        state.planned_tools = tools
        state.planner_reasoning = response_text
        
        print(f"  [LLM Planner] Groq decided: {' → '.join(tools)}")
        
    except json.JSONDecodeError:
        # Fallback if LLM doesn't return valid JSON
        print(f"  [LLM Planner] Failed to parse response, using fallback plan")
        state.planned_tools = ["code_review", "security_analysis", "summarizer"]
        state.add_error("LLM planner JSON parse failed, used fallback")
    except Exception as e:
        print(f"  [LLM Planner] Error: {e}")
        state.planned_tools = ["code_review", "security_analysis", "summarizer"]
        state.add_error(f"LLM planner error: {e}")
    
    return state