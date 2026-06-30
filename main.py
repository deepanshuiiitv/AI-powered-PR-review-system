#!/usr/bin/env python3
"""
AI-Powered PR Review System - Main Entry Point (Agentic Version)

AGENTIC ARCHITECTURE:
1. Preprocessing Agent - analyzes PR complexity
2. Planner Agent - decides which tools needed
3. Tool Executor - runs tools (can loop)
4. Decision Node - continue or stop?
5. Summarizer - aggregates findings
6. Reporter - formats output

Usage:
  python main.py --pr https://github.com/owner/repo/pull/42
  python main.py --owner owner --repo repo --number 42
  python main.py --pr URL --output file --post-comment
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from src.state import ReviewState
from src.workflow import ReviewAgentWorkflow
from src.github_client import GitHubClient


def parse_pr_url(url: str) -> tuple:
    """
    Parse GitHub PR URL to extract owner, repo, number.
    Accepts formats:
    - https://github.com/owner/repo/pull/123
    - https://github.com/owner/repo/pulls/123
    """
    parts = url.rstrip('/').split('/')
    try:
        pr_number = int(parts[-1])
        # parts[-2] = 'pull'/'pulls', parts[-3] = repo, parts[-4] = owner
        owner = parts[-4] if parts[-2] in ['pull', 'pulls'] else None
        repo = parts[-3]
        if not owner:
            raise ValueError
        return owner, repo, pr_number
    except (ValueError, IndexError):
        raise ValueError(f"Invalid PR URL: {url}")

def main():
    parser = argparse.ArgumentParser(
        description="AI-Powered PR Review System (Agentic Architecture)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple usage with PR URL
  python main.py --pr https://github.com/owner/repo/pull/42
  
  # Save to file
  python main.py --pr URL --output file
  
  # Post as GitHub comment
  python main.py --pr URL --post-comment
  
  # Alternative syntax (owner/repo/number)
  python main.py --owner owner --repo repo --number 42
        """
    )
    
    # PR specification (mutually exclusive)
    pr_spec = parser.add_mutually_exclusive_group(required=True)
    pr_spec.add_argument(
        "--pr",
        type=str,
        help="Full GitHub PR URL (https://github.com/owner/repo/pull/42)"
    )
    pr_spec.add_argument(
        "--owner",
        type=str,
        help="GitHub repo owner (use with --repo and --number)"
    )
    
    # Additional options
    parser.add_argument("--repo", type=str, help="GitHub repo name")
    parser.add_argument("--number", type=int, help="PR number")
    parser.add_argument(
        "--model",
        type=str,
        default="llama-3.3-70b-versatile",
        help="Groq model to use (default: llama-3.3-70b-versatile)"
    )
    parser.add_argument(
        "--output",
        choices=["terminal", "file", "both"],
        default="terminal",
        help="Output destination (default: terminal)"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--post-comment",
        action="store_true",
        help="Post review as GitHub PR comment"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = Config()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Parse PR location
    try:
        if args.pr:
            owner, repo, pr_number = parse_pr_url(args.pr)
            pr_url = args.pr
        else:
            owner = args.owner
            repo = args.repo
            pr_number = args.number
            if not all([owner, repo, pr_number]):
                parser.error("--owner, --repo, and --number are all required")
            pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"
    except Exception as e:
        print(f"❌ PR URL parsing error: {e}")
        sys.exit(1)
    
    # Create initial state
    initial_state = ReviewState(
        pr_url=pr_url,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )
    
    print("=" * 70)
    print("🤖 AI-POWERED PR REVIEW SYSTEM (Agentic Architecture)")
    print("=" * 70)
    print(f"\n📍 PR: {owner}/{repo}#{pr_number}")
    print(f"🔗 URL: {pr_url}\n")
    
    # Create and run agentic workflow
    try:
        print("→ Initializing agentic workflow...\n")
        workflow = ReviewAgentWorkflow(
            groq_api_key=config.groq_api_key,
            github_token=config.github_token
        )
        
        print("→ Starting agent loop...\n")
        print("=" * 70)
        
        # Run the workflow
        final_state = workflow.run(initial_state)
        
        print("=" * 70)
        
        # Handle output
        if final_state.errors:
            print("\n⚠️  Errors encountered:")
            for error in final_state.errors:
                print(f"   - {error}")
        
        if final_state.formatted_report:
            report = final_state.formatted_report
            
            if args.output in ["terminal", "both"]:
                print("\n" + report)
            
            if args.output in ["file", "both"]:
                filename = f"pr_review_{owner}_{repo}_{pr_number}.md"
                with open(filename, "w") as f:
                    f.write(report)
                print(f"\n✅ Report saved to: {filename}")
            
            if args.post_comment:
                if not config.github_token:
                    print("\n⚠️  --post-comment requires GITHUB_TOKEN in .env (skipping)")
                else:
                    print("\n→ Posting comment to GitHub...")
                    try:
                        client = GitHubClient(config.github_token)
                        client.post_comment(
                            owner=owner,
                            repo=repo,
                            number=pr_number,
                            body=final_state.formatted_report,
                        )
                        print(f"   ✓ Comment posted on PR #{pr_number}")
                    except Exception as e:
                        print(f"   ✗ Failed to post comment: {e}")

        
        print("\n✨ Review complete!")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n❌ Review cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Workflow error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()