"""
AI Reviewer — sends PR diff chunks to Groq (free LLM API) and returns
a structured review dict.

Free Groq models (as of 2025):
  - llama-3.3-70b-versatile   ← default (best quality)
  - llama-3.1-8b-instant      ← faster / smaller
  - mixtral-8x7b-32768        ← large context window
  - gemma2-9b-it              ← Google Gemma

Rate limits (free tier):
  - 14,400 requests/day
  - 30 requests/minute
  - 6,000 tokens/minute (varies by model)
"""

import json
import time
import requests
from typing import Any

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are an expert senior software engineer performing a thorough code review.
Analyze the provided pull request diff and return a structured JSON review.

Your review MUST cover ALL of the following dimensions:
1. Code Quality     — readability, naming, complexity, dead code
2. Correctness      — bugs, off-by-one errors, null/undefined handling, logic errors
3. Security         — injection, secrets in code, auth bypass, insecure deps
4. Performance      — N+1 queries, unnecessary loops, memory leaks, blocking I/O
5. Best Practices   — SOLID, DRY, error handling, logging
6. Tests            — missing tests, weak assertions, test coverage gaps
7. Documentation    — missing docstrings, misleading comments

Return ONLY valid JSON (no markdown fences, no preamble) in this exact schema:
{
  "summary": "<2-3 sentence overall assessment>",
  "score": <integer 1-10>,
  "verdict": "<APPROVE | REQUEST_CHANGES | COMMENT>",
  "critical_issues": [
    { "file": "<filename>", "line_hint": "<approx line or function>", "issue": "<description>", "suggestion": "<fix>" }
  ],
  "security_concerns": [
    { "file": "<filename>", "concern": "<description>", "risk_level": "<high | medium | low>" }
  ],
  "improvements": [
    { "file": "<filename>", "issue": "<what could be better>", "suggestion": "<how>" }
  ],
  "positive_aspects": ["<thing done well>"],
  "missing_tests": ["<what should be tested>"],
  "recommendations": ["<general advice>"]
}

Scoring guide:
  1-3  → Major bugs or security issues present
  4-5  → Needs significant work before merge
  6-7  → Minor issues, mostly okay
  8-9  → Good, small tweaks needed
  10   → Exceptional, no issues

Verdict guide:
  APPROVE          → Safe to merge as-is
  REQUEST_CHANGES  → Needs fixes before merge
  COMMENT          → Observations only, no block
"""


class AIReviewer:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ── Public ────────────────────────────────────────────────

    def review(self, parsed: dict) -> dict:
        """
        Review the parsed PR. If the diff is large, reviews chunk-by-chunk
        and merges the results into a single coherent review.
        """
        chunks = parsed["diff_chunks"]
        context_header = self._build_context_header(parsed)

        if len(chunks) == 1:
            print("   Sending diff to Groq...\n")
            return self._call_groq(context_header, chunks[0])

        # Multi-chunk: review each, then merge
        partial_reviews = []
        for i, chunk in enumerate(chunks, 1):
            print(f"   Chunk {i}/{len(chunks)}: sending to Groq...")
            try:
                result = self._call_groq(context_header, chunk)
                partial_reviews.append(result)
                if i < len(chunks):
                    time.sleep(1)   # respect rate limit
            except Exception as e:
                print(f"   ⚠️  Chunk {i} failed: {e}")

        print()
        return self._merge(partial_reviews)

    # ── Helpers ───────────────────────────────────────────────

    def _build_context_header(self, parsed: dict) -> str:
        files_list = "\n".join(
            f"  [{f['status']:8s}] {f['filename']}  (+{f['additions']}/-{f['deletions']})"
            for f in parsed["files"]
        )
        skipped = parsed.get("skipped_files", [])
        skipped_note = (
            f"\n(Skipped {len(skipped)} auto-generated/lock files)" if skipped else ""
        )

        labels = ", ".join(parsed["labels"]) if parsed["labels"] else "none"
        draft = "  ⚠️ DRAFT PR" if parsed["is_draft"] else ""

        return f"""\
PR TITLE:    {parsed['title']}{draft}
AUTHOR:      {parsed['author']}
BRANCH:      {parsed['head_branch']} → {parsed['base_branch']}
LABELS:      {labels}
DESCRIPTION:
{parsed['description']}

STATS: {parsed['stats']['reviewed_files']} files reviewed  \
+{parsed['stats']['total_additions']} / -{parsed['stats']['total_deletions']} lines{skipped_note}

FILES CHANGED:
{files_list}
"""

    def _call_groq(self, context: str, diff_chunk: str) -> dict:
        user_msg = (
            f"{context}\n\nDIFF:\n```diff\n{diff_chunk}\n```\n\n"
            "Return your review as JSON only."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }

        for attempt in range(3):
            try:
                resp = requests.post(GROQ_URL, headers=self.headers, json=payload, timeout=60)

                if resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    print(f"   Rate limited — waiting {wait}s...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"]
                return self._safe_parse(raw)

            except requests.RequestException as e:
                if attempt == 2:
                    raise
                time.sleep(5)

        raise RuntimeError("Groq API failed after 3 attempts")

    def _safe_parse(self, text: str) -> dict:
        """Parse JSON response, stripping any accidental markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip().rstrip("`").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Return a minimal fallback so the reporter doesn't crash
            return {
                "summary": text[:500] if text else "AI returned an unparseable response.",
                "score": 5,
                "verdict": "COMMENT",
                "critical_issues": [],
                "security_concerns": [],
                "improvements": [],
                "positive_aspects": [],
                "missing_tests": [],
                "recommendations": [],
            }

    def _merge(self, reviews: list) -> dict:
        """Merge multiple chunk-reviews into one coherent review."""
        if not reviews:
            return {"error": "No review data returned", "verdict": "COMMENT", "score": 5}
        if len(reviews) == 1:
            return reviews[0]

        def collect(key):
            result = []
            seen = set()
            for r in reviews:
                for item in r.get(key, []):
                    key_str = json.dumps(item, sort_keys=True)
                    if key_str not in seen:
                        seen.add(key_str)
                        result.append(item)
            return result

        scores = [r.get("score", 5) for r in reviews if isinstance(r.get("score"), (int, float))]
        avg_score = round(sum(scores) / len(scores)) if scores else 5

        # Pessimistic verdict merge
        verdicts = [r.get("verdict", "COMMENT") for r in reviews]
        if "REQUEST_CHANGES" in verdicts:
            final_verdict = "REQUEST_CHANGES"
        elif all(v == "APPROVE" for v in verdicts):
            final_verdict = "APPROVE"
        else:
            final_verdict = "COMMENT"

        summaries = [r.get("summary", "") for r in reviews if r.get("summary")]
        combined_summary = " | ".join(summaries) if summaries else "Multi-chunk review completed."

        return {
            "summary": combined_summary,
            "score": avg_score,
            "verdict": final_verdict,
            "critical_issues": collect("critical_issues"),
            "security_concerns": collect("security_concerns"),
            "improvements": collect("improvements"),
            "positive_aspects": collect("positive_aspects"),
            "missing_tests": collect("missing_tests"),
            "recommendations": collect("recommendations"),
        }