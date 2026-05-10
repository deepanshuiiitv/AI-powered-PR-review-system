"""
GitHub REST API client — fetches PR data, diffs, and posts comments.
Works for public repos without a token; private repos need GITHUB_TOKEN.
"""

import requests


class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: str = ""):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ai-pr-reviewer/1.0",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    # ── PR metadata ───────────────────────────────────────────

    def get_pr(self, owner: str, repo: str, number: int) -> dict:
        """Return full PR object."""
        return self._get(f"/repos/{owner}/{repo}/pulls/{number}")

    def get_pr_files(self, owner: str, repo: str, number: int) -> list:
        """Return list of files changed in the PR (up to 300 files)."""
        files = []
        page = 1
        while True:
            batch = self._get(
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return files

    def get_pr_diff(self, owner: str, repo: str, number: int) -> str:
        """Return raw unified diff of the PR."""
        url = f"{self.BASE}/repos/{owner}/{repo}/pulls/{number}"
        resp = self.session.get(
            url,
            headers={**dict(self.session.headers), "Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    def get_pr_comments(self, owner: str, repo: str, number: int) -> list:
        """Return existing review comments on the PR."""
        return self._get(f"/repos/{owner}/{repo}/issues/{number}/comments")

    # ── Post comment ──────────────────────────────────────────

    def post_comment(self, owner: str, repo: str, number: int, body: str) -> dict:
        """Post a comment on the PR (issue comment — visible in the conversation)."""
        url = f"{self.BASE}/repos/{owner}/{repo}/issues/{number}/comments"
        resp = self.session.post(url, json={"body": body})
        resp.raise_for_status()
        return resp.json()

    # ── Helpers ───────────────────────────────────────────────

    def _get(self, path: str, params: dict = None) -> any:
        resp = self.session.get(f"{self.BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()