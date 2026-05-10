"""
AI-Powered PR Review System — Zero Cost Edition
Uses: Groq (free LLM) + GitHub API (free)
"""

import argparse
import sys
import json
from config import Config
from src.github_client import GitHubClient
from src.pr_parser import PRParser
from src.ai_reviewer import AIReviewer
from src.reporter import Reporter


def parse_pr_url(url):
    """Extract owner, repo, pr_number from a GitHub PR URL."""
    parts = url.rstrip("/").split("/")
    try:
        pull_idx = parts.index("pull")
        return parts[pull_idx - 2], parts[pull_idx - 1], int(parts[pull_idx + 1])
   

def main():
    parser = argparse.ArgumentParser(
        description="🤖 AI-Powered PR Reviewer — Zero Cost",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLES:

  # Review by PR URL (simplest):
  python main.py --pr https://github.com/owner/repo/pull/42

  # Review and post comment back to GitHub:
  python main.py --pr https://github.com/owner/repo/pull/42 --post-comment

  # Review using owner/repo/number separately:
  python main.py --owner facebook --repo react --number 123

  # Save review to a markdown file:
  python main.py --pr https://github.com/owner/repo/pull/42 --output file

  # Use a specific Groq model:
  python main.py --pr https://github.com/owner/repo/pull/42 --model mixtral-8x7b-32768

  # Output as raw JSON:
  python main.py --pr https://github.com/owner/repo/pull/42 --format json

FREE SETUP:
  1. Get free Groq API key: https://console.groq.com
  2. Get free GitHub token: https://github.com/settings/tokens
  3. Copy .env.example -> .env and fill in values
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """,
    )

    # PR identification
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pr", metavar="URL", help="Full GitHub PR URL")
    group.add_argument("--owner", metavar="OWNER", help="GitHub repo owner (use with --repo & --number)")

    parser.add_argument("--repo", metavar="REPO", help="GitHub repo name")
    parser.add_argument("--number", type=int, metavar="N", help="PR number")

    # Options
    parser.add_argument(
        "--model",
        default="llama-3.3-70b-versatile",
        metavar="MODEL",
        help="Groq model (default: llama-3.3-70b-versatile)",
    )
    parser.add_argument(
        "--output",
        choices=["terminal", "file", "both"],
        default="terminal",
        help="Where to output the review (default: terminal)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--post-comment",
        action="store_true",
        help="Post the review as a GitHub PR comment",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored terminal output",
    )

    args = parser.parse_args()

    # Resolve owner/repo/number
    if args.pr:
        owner, repo, number = parse_pr_url(args.pr)
    else:
        if not args.repo or not args.number:
            print("❌ --owner requires --repo and --number")
            sys.exit(1)
        owner, repo, number = args.owner, args.repo, args.number

    # Load config
    try:
        config = Config()
    except ValueError as e:
        print(f"❌ Config error: {e}")
        sys.exit(1)

    # ── Fetch PR ──────────────────────────────────────────────
    _print_step("Fetching PR data from GitHub", args.no_color)
    print(f"   Repo  : {owner}/{repo}")
    print(f"   PR #  : {number}\n")

    github = GitHubClient(config.github_token)
    print("hello world")
    try:
        pr_data = github.get_pr(owner, repo, number)
        pr_files = github.get_pr_files(owner, repo, number)
        pr_diff = github.get_pr_diff(owner, repo, number)
    except Exception as e:
        print(f"❌ GitHub API error: {e}")
        print("   → For private repos, ensure GITHUB_TOKEN is set in .env")
        sys.exit(1)

    print(f"   Title : {pr_data['title']}")
    print(f"   Author: {pr_data['user']['login']}")
    print(f"   Files : {len(pr_files)} changed\n")

    # ── Parse ─────────────────────────────────────────────────
    pr_parser = PRParser()
    parsed = pr_parser.parse(pr_data, pr_files, pr_diff)

    # ── AI Review ─────────────────────────────────────────────
    _print_step(f"Running AI review with {args.model}", args.no_color)
    chunks = len(parsed["diff_chunks"])
    if chunks > 1:
        print(f"   Large PR detected — splitting into {chunks} chunks\n")

    reviewer = AIReviewer(config.groq_api_key, model=args.model)
    try:
        review = reviewer.review(parsed)
    except Exception as e:
        print(f"❌ Groq API error: {e}")
        print("   → Check your GROQ_API_KEY in .env")
        sys.exit(1)

    # ── Report ────────────────────────────────────────────────
    reporter = Reporter()

    if args.format == "json":
        output_text = json.dumps(review, indent=2)
    else:
        output_text = reporter.format(pr_data, review, parsed)

    # Terminal output
    if args.output in ("terminal", "both"):
        print("\n" + "━" * 60)
        print(output_text)
        print("━" * 60 + "\n")

    # File output
    if args.output in ("file", "both"):
        ext = "json" if args.format == "json" else "md"
        filename = f"pr_review_{owner}_{repo}_{number}.{ext}"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(output_text)
        print(f"💾 Review saved → {filename}\n")

    # Post GitHub comment
    if args.post_comment:
        _print_step("Posting review as GitHub comment", args.no_color)
        if not config.github_token:
            print("❌ --post-comment requires GITHUB_TOKEN in .env")
            sys.exit(1)
        try:
            comment_body = output_text if args.format == "markdown" else reporter.format(pr_data, review, parsed)
            github.post_comment(owner, repo, number, comment_body)
            print("   ✅ Comment posted successfully!\n")
        except Exception as e:
            print(f"   ❌ Failed to post comment: {e}\n")

    _verdict_summary(review, args.no_color)


def _print_step(msg, no_color=False):
    prefix = "──" if no_color else "\033[36m──\033[0m"
    print(f"{prefix} {msg} ...")


def _verdict_summary(review, no_color=False):
    verdict = review.get("verdict", "COMMENT")
    score = review.get("score", "?")

    colors = {
        "APPROVE": "\033[32m",
        "REQUEST_CHANGES": "\033[31m",
        "COMMENT": "\033[33m",
    }
    emojis = {"APPROVE": "✅", "REQUEST_CHANGES": "❌", "COMMENT": "💬"}

    color = "" if no_color else colors.get(verdict, "")
    reset = "" if no_color else "\033[0m"
    emoji = emojis.get(verdict, "💬")

    print(f"  {emoji} Verdict : {color}{verdict}{reset}")
    print(f"  📊 Score   : {score}/10")
    print(f"\n✨ Review complete!\n")


if __name__ == "__main__":
    main()
