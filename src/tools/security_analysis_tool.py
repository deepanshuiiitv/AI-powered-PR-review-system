"""
Security Analysis Tool: Detects security vulnerabilities, injection risks, hardcoded secrets.
"""

import re
import json
from groq import Groq
from src.state import ReviewState


def security_analysis_tool(state: ReviewState, groq_api_key: str) -> ReviewState:
    """
    Run security analysis on diff chunks.
    Checks: SQL injection, XSS, hardcoded secrets, insecure auth
    Updates: security_issues, critical_issues
    """
    
    print("  [Tool] Running security analysis...")
    
    if not state.parsed_diff_chunks:
        print("    ✓ No chunks to analyze")
        return state
    
    # First, run pattern-based checks
    pattern_issues = _check_security_patterns(state.pr_diff or "")
    state.critical_issues.extend(pattern_issues)
    
    # Then run AI security review
    client = Groq(api_key=groq_api_key)
    
    try:
        ai_issues = []
        
        for i, chunk in enumerate(state.parsed_diff_chunks):
            if not chunk.strip():
                continue
            
            security_prompt = f"""Analyze this code diff for SECURITY vulnerabilities.

DIFF CHUNK:
```
{chunk[:3000]}
```

SECURITY DIMENSIONS:
1. Injection Risks - SQL, command, path injection
2. Authentication - weak auth, hardcoded credentials
3. Data Protection - sensitive data handling, encryption
4. Input Validation - user input validation
5. Error Messages - information disclosure in errors
6. Access Control - authorization bypass risks
7. Dependencies - known vulnerable packages

Return JSON:
{{
    "vulnerabilities": [
        {{"type": "SQL_INJECTION|XSS|AUTH|etc", "file": "...", "risk": "critical/high/medium", "description": "...", "remediation": "..."}}
    ],
    "recommendations": ["...", "..."]
}}

Focus on actual risks, not false positives. Be specific.
"""
            
            response = client.messages.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": security_prompt}],
                temperature=0.2,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            response_text = response.content[0].text.strip()
            
            try:
                security_data = json.loads(response_text)
                vulns = security_data.get("vulnerabilities", [])
                
                # Convert to critical/security issues
                for vuln in vulns:
                    issue = {
                        "file": vuln.get("file", "unknown"),
                        "issue": vuln.get("description", ""),
                        "type": vuln.get("type", ""),
                        "severity": "critical" if vuln.get("risk") == "critical" else "high",
                        "remediation": vuln.get("remediation", "")
                    }
                    
                    if vuln.get("risk") == "critical":
                        state.critical_issues.append(issue)
                    else:
                        state.security_issues.append(issue)
                
                ai_issues.extend(vulns)
            except json.JSONDecodeError:
                state.add_error(f"Failed to parse security review for chunk {i}")
        
        print(f"    ✓ Analyzed {len(state.parsed_diff_chunks)} chunk(s)")
        print(f"      - Critical: {len([x for x in state.critical_issues if x.get('severity')=='critical'])}")
        print(f"      - Security issues: {len(state.security_issues)}")
        
    except Exception as e:
        error_msg = f"Security analysis error: {e}"
        print(f"    ✗ {error_msg}")
        state.add_error(error_msg)
    
    return state


def _check_security_patterns(diff_text: str) -> list:
    """Quick regex-based security checks"""
    issues = []
    
    # Pattern 1: SQL queries with string concatenation
    sql_concat = re.findall(r'(?:query|sql|execute)\s*\(\s*["\'].*\s*\+', diff_text, re.IGNORECASE)
    if sql_concat:
        issues.append({
            "file": "multiple",
            "issue": "SQL query using string concatenation detected",
            "severity": "critical",
            "suggestion": "Use parameterized queries instead of string concatenation"
        })
    
    # Pattern 2: Hardcoded API keys/passwords
    secrets = re.findall(r'(?:api[_-]?key|password|secret|token)\s*[=:]\s*["\']([^"\']{8,})["\']', diff_text, re.IGNORECASE)
    if secrets:
        issues.append({
            "file": "multiple",
            "issue": f"Potential hardcoded secret(s) detected ({len(secrets)} found)",
            "severity": "critical",
            "suggestion": "Move secrets to environment variables or secure vault"
        })
    
    # Pattern 3: eval() or exec()
    dangerous_funcs = re.findall(r'\n\+.*\b(?:eval|exec|pickle\.loads)\s*\(', diff_text)
    if dangerous_funcs:
        issues.append({
            "file": "multiple",
            "issue": f"Dangerous function call(s) detected: {len(dangerous_funcs)} found",
            "severity": "critical",
            "suggestion": "Avoid eval/exec/pickle for untrusted input"
        })
    
    # Pattern 4: Disabled security checks
    disabled_security = re.findall(r'\n\+.*(?:verify=False|ssl=False|insecure|skip.*check)', diff_text, re.IGNORECASE)
    if disabled_security:
        issues.append({
            "file": "multiple",
            "issue": "Security check disabled",
            "severity": "high",
            "suggestion": "Keep SSL/TLS verification enabled in production"
        })
    
    return issues