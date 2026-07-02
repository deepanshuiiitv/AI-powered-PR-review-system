"""
Parse Diff Tool: Processes raw diff into chunks.
Uses manual chunking as fallback since PRParser method names vary.
"""

from src.state import ReviewState


def parse_diff_tool(state: ReviewState) -> ReviewState:
    print("  [Tool] Parsing PR diff...")

    try:
        diff = state.pr_diff or ""

        if not diff:
            state.parsed_diff_chunks = []
            state.parsed_metadata = {}
            print("    No diff to parse")
            return state

        # Manual chunking 
        CHUNK_SIZE = 3000
        chunks = []
        if len(diff) <= CHUNK_SIZE:
            chunks = [diff]
        else:
            # Split by file sections (lines starting with 'diff --git')
            sections = diff.split('\ndiff --git')
            current_chunk = ""
            for i, section in enumerate(sections):
                part = section if i == 0 else '\ndiff --git' + section
                if len(current_chunk) + len(part) > CHUNK_SIZE:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = part
                else:
                    current_chunk += part
            if current_chunk:
                chunks.append(current_chunk)

        state.parsed_diff_chunks = chunks

        # Basic metadata from state
        state.parsed_metadata = {
            "title": state.pr_data.get("title", ""),
            "author": state.pr_data.get("user", {}).get("login", ""),
            "files_count": len(state.pr_files),
            "additions": state.pr_data.get("additions", 0),
            "deletions": state.pr_data.get("deletions", 0),
        }

        print(f"Created {len(chunks)} chunk(s)")

    except Exception as e:
        error_msg = f"Failed to parse diff: {e}"
        print(f"{error_msg}")
        state.add_error(error_msg)

    return state