import re
import json
from langchain_groq import ChatGroq
from src.state import ReviewState


def security_analysis_tool(state: ReviewState, groq_api_key: str) -> ReviewState:
    print("  [Tool] Running security analysis...")

    if not state.parsed_diff_chunks:
        print("    No chunks to analyze")
        return state

    # Phase 1: Pattern-based checks (fast, no LLM, won't show in LangSmith)
    pattern_issues = _check_security_patterns(state.pr_diff or "")
    state.critical_issues.extend(pattern_issues)

    # Phase 2: AI security review (traced)
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=groq_api_key,
        temperature=0.2,
        max_tokens=800,
    )

    try:
        for i, chunk in enumerate(state.parsed_diff_chunks):
            if not chunk.strip():
                continue

            security_prompt = f"""Analyze this code diff for security vulnerabilities.

                                DIFF:
                                ```
                                {chunk[:3000]}
                                ```

                                Return JSON only (no markdown fences):
                                {{
                                    "vulnerabilities": [
                                        {{"type": "SQL_INJECTION/XSS/AUTH/etc", "file": "...", "risk": "critical/high/medium", "description": "...", "remediation": "..."}}
                                    ]
                                }}

                                If no vulnerabilities found, return: {{"vulnerabilities": []}}
                                """
            response = llm.invoke(security_prompt)
            response_text = response.content.strip()
            response_text = response_text.replace("```json", "").replace("```", "").strip()

            try:
                security_data = json.loads(response_text)
                for vuln in security_data.get("vulnerabilities", []):
                    issue = {
                        "file": vuln.get("file", "unknown"),
                        "issue": vuln.get("description", ""),
                        "type": vuln.get("type", ""),
                        "severity": vuln.get("risk", "medium"),
                        "remediation": vuln.get("remediation", "")
                    }
                    if vuln.get("risk") == "critical":
                        state.critical_issues.append(issue)
                    else:
                        state.security_issues.append(issue)
            except json.JSONDecodeError:
                state.add_error(f"Failed to parse security review for chunk {i}")

        print(f"    Analyzed {len(state.parsed_diff_chunks)} chunk(s)")
        print(f"      - Critical: {len(state.critical_issues)}, Security: {len(state.security_issues)}")

    except Exception as e:
        print(f"    Security analysis error: {e}")
        state.add_error(f"Security analysis error: {e}")

    return state


def _check_security_patterns(diff_text: str) -> list:
    issues = []

    if re.findall(r'(?:query|sql|execute)\s*\(\s*["\'].*\s*\+', diff_text, re.IGNORECASE):
        issues.append({"file": "multiple", "issue": "SQL query string concatenation", "severity": "critical", "suggestion": "Use parameterized queries"})

    secrets = re.findall(r'(?:api[_-]?key|password|secret|token)\s*[=:]\s*["\']([^"\']{8,})["\']', diff_text, re.IGNORECASE)
    if secrets:
        issues.append({"file": "multiple", "issue": f"Potential hardcoded secret(s) ({len(secrets)} found)", "severity": "critical", "suggestion": "Use environment variables"})

    if re.findall(r'\n\+.*\b(?:eval|exec|pickle\.loads)\s*\(', diff_text):
        issues.append({"file": "multiple", "issue": "Dangerous function (eval/exec/pickle)", "severity": "critical", "suggestion": "Avoid for untrusted input"})

    if re.findall(r'\n\+.*(?:verify=False|ssl=False)', diff_text, re.IGNORECASE):
        issues.append({"file": "multiple", "issue": "SSL verification disabled", "severity": "high", "suggestion": "Keep SSL verification enabled"})

    return issues