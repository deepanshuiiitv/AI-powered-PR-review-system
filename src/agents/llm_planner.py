"""
LLM Planner: Uses LangChain's ChatGroq wrapper instead of raw Groq SDK.
This enables automatic LangSmith tracing
"""

import json
from langchain_groq import ChatGroq
from src.state import ReviewState


def llm_plan_tools(state: ReviewState, groq_api_key: str) -> ReviewState:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=groq_api_key,
        temperature=0.3,
        max_tokens=200,
    )

    pr_data = state.pr_data or {}
    pr_files = state.pr_files or []
    file_list = ", ".join(f.get("filename", "") for f in pr_files[:10])

    planner_prompt = f"""You are planning which tools to run for a GitHub PR review.

                        PR CONTEXT:
                        - Title: {pr_data.get('title', 'N/A')}
                        - Risk Level: {state.risk_level}
                        - Changes: {pr_data.get('additions', 0) + pr_data.get('deletions', 0)} LOC
                        - Files: {len(pr_files)} files changed: {file_list}

                        AVAILABLE TOOLS:
                        - static_analysis
                        - code_review
                        - security_analysis

                        Return ONLY a JSON array of tool names. Example: ["code_review", "security_analysis"]
                        No explanation, just the JSON array.
                        """

    try:
        # .invoke() instead of .chat.completions.create()
        # This call is automatically traced by LangSmith if env vars are set
        response = llm.invoke(planner_prompt)
        response_text = response.content.strip()
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        tools = json.loads(response_text)
        if not isinstance(tools, list):
            tools = ["code_review", "security_analysis"]

        valid_tools = {"static_analysis", "code_review", "security_analysis", "summarizer"}
        tools = [t for t in tools if t in valid_tools]

        if "summarizer" in tools:
            tools.remove("summarizer")
        tools.append("summarizer")

        state.planned_tools = tools
        state.planner_reasoning = response_text
        print(f"  [LLM Planner] Groq decided: {' ->  '.join(tools)}")

    except json.JSONDecodeError:
        print("  [LLM Planner] JSON parse failed, using fallback plan")
        state.planned_tools = ["code_review", "security_analysis", "summarizer"]
    except Exception as e:
        print(f"  [LLM Planner] Error: {e}")
        state.planned_tools = ["code_review", "security_analysis", "summarizer"]
        state.add_error(f"LLM planner error: {e}")

    return state