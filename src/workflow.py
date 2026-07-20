"""
Agentic Workflow: LangGraph-based PR review workflow with decision loops.
"""

from langgraph.graph import StateGraph, START, END
from src.state import ReviewState

# Import agents
from src.agents.preprocessing_agent import analyze_pr_complexity
from src.agents.simple_planner import simple_plan_tools
from src.agents.llm_planner import llm_plan_tools

# Import tools
from src.tools.fetch_pr_tool import fetch_pr_tool
from src.tools.parse_diff_tool import parse_diff_tool
from src.tools.code_review_tool import code_review_tool
from src.tools.security_analysis_tool import security_analysis_tool
from src.tools.static_analysis_tool import static_analysis_tool
from src.tools.summarizer_tool import summarizer_tool


class ReviewAgentWorkflow:

    def __init__(self, groq_api_key: str, github_token: str = None):
        self.groq_api_key = groq_api_key
        self.github_token = github_token
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ReviewState)

        def node_fetch_pr(state: ReviewState):
            return fetch_pr_tool(state, self.github_token)

        def node_parse_diff(state: ReviewState):
            return parse_diff_tool(state)

        def node_preprocessing(state: ReviewState):
            return analyze_pr_complexity(state)

        def node_simple_planner(state: ReviewState):
            return simple_plan_tools(state)

        def node_llm_planner(state: ReviewState):
            return llm_plan_tools(state, self.groq_api_key)

        def node_tool_executor(state: ReviewState):
            print(f"\n->  Tool Execution [Iteration {state.loop_iteration + 1}]")
            state.loop_iteration += 1

            for tool_name in state.planned_tools:
                print(f"\n  Running: {tool_name}")
                if tool_name == "code_review":
                    state = code_review_tool(state, self.groq_api_key)
                elif tool_name == "security_analysis":
                    state = security_analysis_tool(state, self.groq_api_key)
                elif tool_name == "static_analysis":
                    state = static_analysis_tool(state)
                elif tool_name == "summarizer":
                    state = summarizer_tool(state)

            return state

        def node_decision(state: ReviewState):
            if state.loop_iteration >= state.max_iterations:
                print("\n->  Agent Decision: Max iterations reached, moving to summarize")
                state.needs_more_analysis = False
                return state

            if len(state.critical_issues) > 0 and not state.deep_security_done:
                print("\n->  Agent Decision: Critical issues found, running deeper security")
                state.critical_issues = []      
                state.security_issues = []      
                state.planned_tools = ["security_analysis"]
                state.deep_security_done = True
                state.needs_more_analysis = True
                return state

            if len(state.code_quality_issues) > 0 and state.loop_iteration < 2:
                already_ran = any("static" in t for t in state.planned_tools)
                if not already_ran:
                    print("\n->  Agent Decision: Code issues found, running static analysis")
                    state.code_quality_issues = []   
                    state.planned_tools = ["static_analysis"]
                    state.needs_more_analysis = True
                    return state

            print("\n-> Agent Decision: Enough analysis done, moving to summarize")
            state.needs_more_analysis = False
            return state

        def node_summarizer(state: ReviewState):
            if state.final_score is None:
                state = summarizer_tool(state)
            return state

        def node_reporter(state: ReviewState):
            print("\n->  Formatting report...")
            try:
                from src.reporter import Reporter
                reporter = Reporter()

                report = None
                if hasattr(reporter, 'format_review'):
                    report = reporter.format_review(
                        score=state.final_score or 0,
                        verdict=state.final_verdict or "COMMENT",
                        summary=state.final_summary or "",
                        critical_issues=state.critical_issues,
                        security_issues=state.security_issues,
                        code_quality_issues=state.code_quality_issues,
                        test_coverage_issues=state.test_coverage_issues,
                        positive_aspects=state.positive_aspects,
                        recommendations=state.recommendations,
                        pr_title=state.pr_data.get("title", ""),
                        pr_url=state.pr_url,
                    )
                elif hasattr(reporter, 'generate_review'):
                    report = reporter.generate_review(state)
                elif hasattr(reporter, 'format'):
                    review_dict = {
                        "verdict": state.final_verdict or "COMMENT",
                        "score": state.final_score or 0,
                        "summary": state.final_summary or "",
                        "critical_issues": state.critical_issues or [],
                        "security_concerns": state.security_issues or [],
                        "improvements": state.code_quality_issues or [],
                        "positive_aspects": state.positive_aspects or [],
                        "missing_tests": state.test_coverage_issues or [],
                        "recommendations": state.recommendations or [],
                    }
                    parsed_dict = {
                        "stats": {
                            "total_files": len(getattr(state, 'pr_files', [])),
                            "reviewed_files": len(getattr(state, 'pr_files', [])),
                            "total_additions": sum(f.get("additions", 0) for f in getattr(state, 'pr_files', [])),
                            "total_deletions": sum(f.get("deletions", 0) for f in getattr(state, 'pr_files', [])),
                            "diff_size_chars": len(getattr(state, 'raw_diff', "") or ""),
                        }
                    }
                    report = reporter.format(state.pr_data, review_dict, parsed_dict)
                elif hasattr(reporter, 'create_report'):
                    report = reporter.create_report(state)
                else:
                    # Fallback: build a simple report manually
                    report = _build_fallback_report(state)

                state.formatted_report = report
                print("  Report formatted")

            except Exception as e:
                print(f"  Reporter error: {e}")
                state.formatted_report = _build_fallback_report(state)
                state.add_error(f"Reporter error: {e}")

            return state

        # Register nodes
        workflow.add_node("fetch_pr", node_fetch_pr)
        workflow.add_node("parse_diff", node_parse_diff)
        workflow.add_node("preprocessing", node_preprocessing)
        workflow.add_node("simple_planner", node_simple_planner)
        workflow.add_node("llm_planner", node_llm_planner)
        workflow.add_node("tool_executor", node_tool_executor)
        workflow.add_node("decision", node_decision)
        workflow.add_node("summarizer", node_summarizer)
        workflow.add_node("reporter", node_reporter)

        # Edges
        workflow.add_edge(START, "fetch_pr")
        workflow.add_edge("fetch_pr", "parse_diff")
        workflow.add_edge("parse_diff", "preprocessing")

        def route_planner(state: ReviewState) -> str:
            return "llm_planner" if state.is_complex else "simple_planner"

        workflow.add_conditional_edges(
            "preprocessing", route_planner,
            {"llm_planner": "llm_planner", "simple_planner": "simple_planner"}
        )

        workflow.add_edge("simple_planner", "tool_executor")
        workflow.add_edge("llm_planner", "tool_executor")
        workflow.add_edge("tool_executor", "decision")

        #  Routing function for decision (separate from node)
        def route_after_decision(state: ReviewState) -> str:
            return "tool_executor" if state.needs_more_analysis else "summarizer"

        workflow.add_conditional_edges(
            "decision", route_after_decision,
            {"tool_executor": "tool_executor", "summarizer": "summarizer"}
        )

        workflow.add_edge("summarizer", "reporter")
        workflow.add_edge("reporter", END)

        return workflow.compile()

    def run(self, state: ReviewState) -> ReviewState:
        result = self.graph.invoke(state)

        #  FIX: LangGraph returns dict, convert back to ReviewState
        if isinstance(result, dict):
            final_state = ReviewState()
            for key, value in result.items():
                if hasattr(final_state, key):
                    setattr(final_state, key, value)
            return final_state

        return result


def _build_fallback_report(state: ReviewState) -> str:
    """Fallback report if Reporter fails"""
    lines = [
        f"#  AI PR Review Report",
        f"",
        f"**PR:** {state.pr_url}",
        f"**Score:** {state.final_score:.1f}/10" if state.final_score else "**Score:** N/A",
        f"**Verdict:** {state.final_verdict or 'COMMENT'}",
        f"",
        f"## Summary",
        f"{state.final_summary or 'No summary available.'}",
        f"",
    ]

    if state.critical_issues:
        lines.append("## Critical Issues")
        for issue in state.critical_issues:
            lines.append(f"- **{issue.get('file', 'unknown')}**: {issue.get('issue', '')}")
        lines.append("")

    if state.security_issues:
        lines.append("## Security Issues")
        for issue in state.security_issues:
            lines.append(f"- {issue.get('issue', '')}")
        lines.append("")

    if state.code_quality_issues:
        lines.append("## Code Quality")
        for issue in state.code_quality_issues:
            lines.append(f"- [{issue.get('severity', '?').upper()}] {issue.get('issue', '')}")
        lines.append("")

    if state.positive_aspects:
        lines.append("## Positives")
        for p in state.positive_aspects:
            lines.append(f"- {p}")

    return "\n".join(lines)