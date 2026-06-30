"""
Fetch PR Tool: Gets PR metadata, file list, and raw diff from GitHub API.
Wrapper around existing github_client.py
"""

from src.github_client import GitHubClient
from src.state import ReviewState


def fetch_pr_tool(state: ReviewState, github_token: str = None) -> ReviewState:
    """
    Fetch PR data from GitHub.
    Updates: pr_data, pr_files, pr_diff
    """

    print("  [Tool] Fetching PR from GitHub...")

    try:
        # ✅ FIX: Check GitHubClient's actual __init__ signature
        # Most use positional or 'token' not 'github_token'
        if github_token:
            client = GitHubClient(github_token)
        else:
            client = GitHubClient()

        owner = state.owner
        repo = state.repo
        pr_number = state.pr_number

        # Fetch PR metadata
        pr_data = client.get_pr(owner, repo, pr_number)
        state.pr_data = pr_data

        # Fetch files changed
        pr_files = client.get_pr_files(owner, repo, pr_number)
        state.pr_files = pr_files

        # Fetch raw diff
        pr_diff = client.get_pr_diff(owner, repo, pr_number)
        state.pr_diff = pr_diff

        print(f"    ✓ Fetched {len(pr_files)} files, {len(pr_diff)} chars diff")

    except Exception as e:
        error_msg = f"Failed to fetch PR: {e}"
        print(f"    ✗ {error_msg}")
        state.add_error(error_msg)

    return state