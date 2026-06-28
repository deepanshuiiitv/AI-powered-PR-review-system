"""
Code Review Tool: AI-powered code quality, readability, and design review.
Uses Groq LLM to analyze code chunks.
"""

import json
from groq import Groq
from src.state import ReviewState


def code_review_tool(state: ReviewState, groq_api_key: str) -> ReviewState:
    """
    Run AI code review on all diff chunks.
    Checks: readability, naming, design patterns, SOLID principles
    Updates: code_quality_issues, positive_aspects, recommendations
    """
    
    print("  [Tool] Running AI code review...")
    
    if not state.parsed_diff_chunks:
        print("    ✓ No chunks to review")
        return state
    
    client = Groq(api_key=groq_api_key)
    
    try:
        # Review each chunk
        all_issues = []
        all_positives = []
        all_recommendations = []
        
        for i, chunk in enumerate(state.parsed_diff_chunks):
            if not chunk.strip():
                continue
            
            review_prompt = f"""Review this code diff for quality and readability issues.

DIFF CHUNK:
```
{chunk[:3000]}  # limit size
```

REVIEW DIMENSIONS:
1. Code Readability - clear variable names, understandable logic
2. Code Design - adherence to SOLID principles
3. Error Handling - proper exception handling
4. Documentation - sufficient docstrings/comments
5. Maintainability - DRY principle, no code duplication

Return JSON with this structure:
{{
    "issues": [
        {{"file": "...", "issue": "...", "severity": "low/medium/high", "suggestion": "..."}}
    ],
    "positives": ["good point 1", "good point 2"],
    "recommendations": [
        {{"area": "...", "suggestion": "..."}}
    ]
}}

Be specific and actionable. If no issues, return empty issues list.
"""
            
            response = client.messages.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": review_prompt}],
                temperature=0.3,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            response_text = response.content[0].text.strip()
            
            # Parse response
            try:
                review_data = json.loads(response_text)
                all_issues.extend(review_data.get("issues", []))
                all_positives.extend(review_data.get("positives", []))
                all_recommendations.extend(review_data.get("recommendations", []))
            except json.JSONDecodeError:
                state.add_error(f"Failed to parse code review response for chunk {i}")
        
        # Deduplicate and limit
        state.code_quality_issues.extend(all_issues[:10])
        state.positive_aspects.extend(list(set(all_positives))[:5])
        state.recommendations.extend(all_recommendations[:5])
        
        print(f"    ✓ Reviewed {len(state.parsed_diff_chunks)} chunk(s)")
        print(f"      - Issues: {len(all_issues)}")
        print(f"      - Positives: {len(all_positives)}")
        
    except Exception as e:
        error_msg = f"Code review error: {e}"
        print(f"    ✗ {error_msg}")
        state.add_error(error_msg)
    
    return state