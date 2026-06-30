"""
Code Review Tool: Uses ChatGroq for automatic LangSmith tracing.
"""

import json
from langchain_groq import ChatGroq
from src.state import ReviewState


def code_review_tool(state: ReviewState, groq_api_key: str) -> ReviewState:
    print("  [Tool] Running AI code review...")

    if not state.parsed_diff_chunks:
        print("    ✓ No chunks to review")
        return state

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=groq_api_key,
        temperature=0.3,
        max_tokens=800,
    )

    try:
        all_issues = []
        all_positives = []
        all_recommendations = []

        for i, chunk in enumerate(state.parsed_diff_chunks):
            if not chunk.strip():
                continue

            review_prompt = f"""Review this code diff for quality issues.

DIFF:
```
{chunk[:3000]}
```

Return JSON only (no markdown fences):
{{
    "issues": [{{"file": "...", "issue": "...", "severity": "low/medium/high", "suggestion": "..."}}],
    "positives": ["..."],
    "recommendations": [{{"area": "...", "suggestion": "..."}}]
}}
"""
            response = llm.invoke(review_prompt)
            response_text = response.content.strip()
            response_text = response_text.replace("```json", "").replace("```", "").strip()

            try:
                review_data = json.loads(response_text)
                all_issues.extend(review_data.get("issues", []))
                all_positives.extend(review_data.get("positives", []))
                all_recommendations.extend(review_data.get("recommendations", []))
            except json.JSONDecodeError:
                state.add_error(f"Failed to parse code review for chunk {i}")

        state.code_quality_issues.extend(all_issues[:10])
        state.positive_aspects.extend(list(set(all_positives))[:5])
        state.recommendations.extend(all_recommendations[:5])

        print(f"    ✓ Reviewed {len(state.parsed_diff_chunks)} chunk(s), found {len(all_issues)} issues")

    except Exception as e:
        print(f"    ✗ Code review error: {e}")
        state.add_error(f"Code review error: {e}")

    return state