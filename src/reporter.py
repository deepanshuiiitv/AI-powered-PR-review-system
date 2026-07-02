"""
Reporter — formats the raw AI review dict into a polished Markdown report.
"""

from datetime import datetime, timezone
from typing import Any


VERDICT_BADGE = {
    "APPROVE":         " APPROVE",
    "REQUEST_CHANGES": " REQUEST CHANGES",
    "COMMENT":         " COMMENT",
}

RISK_EMOJI = {
    "high":   "!!!",
    "medium": "!!",
    "low":    "!",
}


class Reporter:
    def format(self, pr_data: dict, review: dict, parsed: dict) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        verdict = review.get("verdict", "COMMENT")
        score = review.get("score", "N/A")
        badge = VERDICT_BADGE.get(verdict, verdict)
        stars = self._score_bar(score)

        lines = [
            "# AI Code Review",
            "",
            f"> **Generated:** {now}  ",
            f"> **Model:** Groq LLM (free tier)  ",
            f"> **PR:** [{pr_data.get('title', '')}]({pr_data.get('html_url', '')})",
            "",
            "---",
            "",
            f"## {badge}",
            "",
            f"**Quality Score:** {score}/10  {stars}",
            "",
            "### Summary",
            "",
            review.get("summary", "_No summary provided._"),
            "",
        ]

        # ── Critical Issues ───────────────────────────────────
        critical = review.get("critical_issues", [])
        if critical:
            lines += [
                f"---",
                "",
                f"## Critical Issues  ({len(critical)})",
                "",
                "_These must be addressed before merging._",
                "",
            ]
            for i, item in enumerate(critical, 1):
                lines += [
                    f"### {i}. `{item.get('file', 'unknown')}`",
                    f"**Location:** {item.get('line_hint', 'N/A')}",
                    "",
                    f" **Issue:** {item.get('issue', '')}",
                    "",
                    f" **Fix:** {item.get('suggestion', '')}",
                    "",
                ]

        # ── Security ──────────────────────────────────────────
        security = review.get("security_concerns", [])
        if security:
            lines += [
                "---",
                "",
                f"## Security Concerns  ({len(security)})",
                "",
            ]
            for item in security:
                risk = item.get("risk_level", "medium").lower()
                emoji = RISK_EMOJI.get(risk, "")
                lines += [
                    f"- {emoji} **[{risk.upper()}]** `{item.get('file', 'unknown')}`  ",
                    f"  {item.get('concern', '')}",
                    "",
                ]

        # ── Improvements ──────────────────────────────────────
        improvements = review.get("improvements", [])
        if improvements:
            lines += [
                "---",
                "",
                f"## Suggested Improvements  ({len(improvements)})",
                "",
            ]
            for item in improvements[:15]:   # cap at 15
                lines += [
                    f"- **`{item.get('file', 'unknown')}`** — {item.get('issue', '')}",
                    f"  → {item.get('suggestion', '')}",
                    "",
                ]

        # ── Missing Tests ─────────────────────────────────────
        missing_tests = review.get("missing_tests", [])
        if missing_tests:
            lines += [
                "---",
                "",
                f"## Missing Test Coverage  ({len(missing_tests)})",
                "",
            ]
            for t in missing_tests:
                lines.append(f"- {t}")
            lines.append("")

        # ── Positive ──────────────────────────────────────────
        positive = review.get("positive_aspects", [])
        if positive:
            lines += [
                "---",
                "",
                "## Positive Aspects",
                "",
            ]
            for p in positive:
                lines.append(f"- {p}")
            lines.append("")

        # ── Recommendations ───────────────────────────────────
        recs = review.get("recommendations", [])
        if recs:
            lines += [
                "---",
                "",
                "## General Recommendations",
                "",
            ]

            for r in recs:
                area = r.get("area", "General")
                suggestion = r.get("suggestion", "")

                lines.extend([
                    f"### {area}",
                    f"- {suggestion}",
                    ""
                ])

        # ── Stats footer ──────────────────────────────────────
        stats = parsed.get("stats", {})
        lines += [
            "---",
            "",
            "## PR Statistics",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Files changed | {stats.get('total_files', 0)} |",
            f"| Files reviewed | {stats.get('reviewed_files', 0)} |",
            f"| Lines added | +{stats.get('total_additions', 0)} |",
            f"| Lines removed | -{stats.get('total_deletions', 0)} |",
            f"| Diff size | {stats.get('diff_size_chars', 0):,} chars |",
            "",
            "Reviewed by [AI PR Reviewer](https://github.com/deepanshuiiitv/AI-powered-PR-review-system) using Groq (free tier) — zero cost.",
        ]

        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────

    def _score_bar(self, score: Any) -> str:
        try:
            n = int(score)
        except (TypeError, ValueError):
            return ""
        filled = "#" * n
        empty = "-" * (10 - n)
        return f"`{filled}{empty}`"