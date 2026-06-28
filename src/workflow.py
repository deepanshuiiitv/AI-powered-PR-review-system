"""
Agentic Workflow: LangGraph-based PR review workflow with decision loops.

Flow:
1. fetch_pr → parse_diff → preprocessing
2. Branch: if complex → llm_planner, else → simple_planner
3. Agent Loop (can iterate):
   - execute tools (parallel)
   - decision node → continue or stop?
4. summarizer
5. reporter
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from src.state import ReviewState
from src.reporter import Reporter

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
    """LangGraph-based agentic PR review workflow"""
    
    def __init__(self, groq_api_key: str, github_token: str = None):
        self.groq_api_key = groq_api_key
        self.github_token = github_token
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(ReviewState)
        
        # ========== NODES ==========
        
        # Node 1: Fetch PR
        def node_fetch_pr(state: ReviewState):
            return fetch_pr_tool(state, self.github_token)
        
        workflow.add_node("fetch_pr", node_fetch_pr)
        
        # Node 2: Parse Diff
        def node_parse_diff(state: ReviewState):
            return parse_diff_tool(state)
        
        workflow.add_node("parse_diff", node_parse_diff)
        
        # Node 3: Preprocessing
        def node_preprocessing(state: ReviewState):
            return analyze_pr_complexity(state)
        
        workflow.add_node("preprocessing", node_preprocessing)
        
        # Node 4a: Simple Planner
        def node_simple_planner(state: ReviewState):
            return simple_plan_tools(state)
        
        workflow.add_node("simple_planner", node_simple_planner)
        
        # Node 4b: LLM Planner
        def node_llm_planner(state: ReviewState):
            return llm_plan_tools(state, self.groq_api_key)
        
        workflow.add_node("llm_planner", node_llm_planner)
        
        # Node 5: Tool Executor (runs planned tools)
        def node_tool_executor(state: ReviewState):
            print(f"\n→ Tool Execution [Iteration {state.loop_iteration + 1}]")
            
            state.loop_iteration += 1
            
            # Execute each planned tool
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
        
        workflow.add_node("tool_executor", node_tool_executor)
        
        # Node 6: Decision Node
        def node_decision(state: ReviewState) -> str:
            """
            Agent decides: continue looping or move to summarize?
            
            Rules:
            - If critical issues found → run deeper security if not done
            - If enough data collected → move to summarize
            - Max iterations → move to summarize
            """
            
            if state.loop_iteration >= state.max_iterations:
                return "summarizer"
            
            # Check if we found critical issues and haven't done deep security yet
            if (len(state.critical_issues) > 0 and 
                not state.deep_security_done and
                "security_analysis" not in state.planned_tools):
                
                print("\n→ Agent Decision: Critical issues found, running deeper security check")
                state.planned_tools = ["security_analysis"]
                state.deep_security_done = True
                return "tool_executor"
            
            # Check if we should run more tools based on findings
            if (len(state.code_quality_issues) > 0 and
                "static_analysis" not in state.planned_tools and
                state.loop_iteration < 2):
                
                print("\n→ Agent Decision: Code issues found, running static analysis")
                state.planned_tools = ["static_analysis"]
                return "tool_executor"
            
            # Otherwise, move to summarizer
            print("\n→ Agent Decision: Enough analysis done, moving to summarize")
            return "summarizer"
        
        workflow.add_node("decision", node_decision)
        
        # Node 7: Summarizer
        def node_summarizer(state: ReviewState):
            # Only run if not already run
            if state.final_score is None:
                state = summarizer_tool(state)
            return state
        
        workflow.add_node("summarizer", node_summarizer)
        
        # Node 8: Reporter
        def node_reporter(state: ReviewState):
            print("\n→ Formatting report...")
            try:
                reporter = Reporter()
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
                state.formatted_report = report
                print("  ✓ Report formatted")
            except Exception as e:
                print(f"  ✗ Report formatting error: {e}")
                state.add_error(f"Reporter error: {e}")
            
            return state
        
        workflow.add_node("reporter", node_reporter)
        
        # ========== EDGES ==========
        
        # Start → fetch_pr
        workflow.add_edge(START, "fetch_pr")
        
        # fetch_pr → parse_diff → preprocessing
        workflow.add_edge("fetch_pr", "parse_diff")
        workflow.add_edge("parse_diff", "preprocessing")
        
        # preprocessing → conditional: complex or simple?
        def route_planner(state: ReviewState) -> str:
            return "llm_planner" if state.is_complex else "simple_planner"
        
        workflow.add_conditional_edges(
            "preprocessing",
            route_planner,
            {"llm_planner": "llm_planner", "simple_planner": "simple_planner"}
        )
        
        # planner → tool_executor
        workflow.add_edge("simple_planner", "tool_executor")
        workflow.add_edge("llm_planner", "tool_executor")
        
        # tool_executor → decision
        workflow.add_edge("tool_executor", "decision")
        
        # decision → conditional: loop or summarize?
        def route_decision(state: ReviewState) -> str:
            # This is handled in node_decision return value
            return state  # Let decision node handle routing
        
        workflow.add_conditional_edges(
            "decision",
            lambda state: "tool_executor" if state.planned_tools and state.loop_iteration < state.max_iterations else "summarizer"
        )
        
        # summarizer → reporter
        workflow.add_edge("summarizer", "reporter")
        
        # reporter → END
        workflow.add_edge("reporter", END)
        
        return workflow.compile()
    
    def run(self, state: ReviewState) -> ReviewState:
        """Execute the workflow"""
        result = self.graph.invoke(state)
        return result