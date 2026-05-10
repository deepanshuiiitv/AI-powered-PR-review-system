"""
PR Parser — converts raw GitHub API data into a structured dict
ready to feed into the AI reviewer.

Handles large diffs by splitting into overlapping chunks so the AI
can review the whole PR even when it exceeds the token limit.
"""

import re
from typing import List


# Max characters of diff per AI call (~6 000 tokens safety margin)
CHUNK_SIZE = 12_000

# File extensions worth reviewing (skip binary/generated/lock files)
REVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".cs", ".rb", ".php", ".swift", ".kt",
    ".scala", ".vue", ".svelte", ".html", ".css", ".scss", ".less",
    ".sh", ".bash", ".yaml", ".yml", ".json", ".toml", ".sql",
    ".tf", ".hcl", ".dockerfile", "dockerfile",
}

SKIP_PATTERNS = re.compile(
    r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|"
    r"Pipfile\.lock|poetry\.lock|composer\.lock|"
    r"\.min\.(js|css)|\.map$|__pycache__|\.pb\.go|_pb2\.py)",
    re.IGNORECASE,
)


class PRParser:
    def parse(self, pr_data: dict, pr_files: list, pr_diff: str) -> dict:
        """
        Returns a structured dict with everything the AI reviewer needs.
        """
        filtered_files = self._filter_files(pr_files)
        diff_chunks = self._chunk_diff(pr_diff)

        return {
            # PR metadata
            "title": pr_data.get("title", ""),
            "description": (pr_data.get("body") or "No description provided.").strip(),
            "author": pr_data["user"]["login"],
            "base_branch": pr_data["base"]["ref"],
            "head_branch": pr_data["head"]["ref"],
            "pr_url": pr_data.get("html_url", ""),
            "is_draft": pr_data.get("draft", False),
            "labels": [lb["name"] for lb in pr_data.get("labels", [])],

            # File-level summary (used in every chunk's context header)
            "files": [
                {
                    "filename": f["filename"],
                    "status": f["status"],          # added | modified | removed | renamed
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                    "patch": (f.get("patch") or "")[:2_000],  # first 2k chars of patch
                }
                for f in filtered_files
            ],

            # Skipped files (let the AI know what it's not seeing)
            "skipped_files": [
                f["filename"]
                for f in pr_files
                if f not in filtered_files
            ],

            # Chunked diff for AI calls
            "diff_chunks": diff_chunks,

            # Aggregated stats
            "stats": {
                "total_files": len(pr_files),
                "reviewed_files": len(filtered_files),
                "total_additions": sum(f.get("additions", 0) for f in pr_files),
                "total_deletions": sum(f.get("deletions", 0) for f in pr_files),
                "diff_size_chars": len(pr_diff),
                "num_chunks": len(diff_chunks),
            },
        }

    # ── Helpers ───────────────────────────────────────────────

    def _filter_files(self, pr_files: list) -> list:
        """Remove binary, lock, and auto-generated files."""
        result = []
        for f in pr_files:
            filename = f["filename"]
            if SKIP_PATTERNS.search(filename):
                continue
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else filename.lower()
            base = filename.split("/")[-1].lower()
            if ext in REVIEWABLE_EXTENSIONS or base in REVIEWABLE_EXTENSIONS:
                result.append(f)
        return result

    def _chunk_diff(self, diff: str) -> List[str]:
        """
        Split diff into CHUNK_SIZE pieces, always breaking on file boundaries
        (lines starting with 'diff --git') so each chunk contains whole files.
        """
        if len(diff) <= CHUNK_SIZE:
            return [diff] if diff.strip() else ["(no diff available)"]

        # Split on file headers
        file_sections = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)

        chunks: List[str] = []
        current = ""

        for section in file_sections:
            if len(current) + len(section) > CHUNK_SIZE and current:
                chunks.append(current)
                current = section
            else:
                current += section

        if current:
            chunks.append(current)

        return chunks or ["(no diff available)"]