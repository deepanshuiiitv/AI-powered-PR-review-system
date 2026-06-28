"""
Simple Planner: For simple PRs, use a fixed tool plan.
No LLM call needed. Fast and deterministic.

For SIMPLE PRs: always [code_review, security_analysis, summarizer]
"""

from src.state import ReviewState


def simple_plan_tools(state: ReviewState) -> ReviewState:
    """
    Create a fixed tool plan for simple PRs.
    
    Simple PRs always get the same tool sequence:
    1. code_review - check code quality
    2. security_analysis - quick security check
    3. summarizer - aggregate findings
    """
    
    # Fixed plan for simple PRs
    planned_tools = ["code_review", "security_analysis", "summarizer"]
    
    state.planned_tools = planned_tools
    state.planner_reasoning = "Simple PR detected. Using fixed tool plan."
    
    print(f"  [Simple Planner] Plan: {' → '.join(planned_tools)}")
    
    return state