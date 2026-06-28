"""
Parse Diff Tool: Processes raw diff into chunks and context.
Wrapper around existing pr_parser.py
"""

from src.pr_parser import PRParser
from src.state import ReviewState


def parse_diff_tool(state: ReviewState) -> ReviewState:
    """
    Parse and chunk the PR diff.
    Updates: parsed_diff_chunks, parsed_metadata
    """
    
    print("  [Tool] Parsing PR diff...")
    
    try:
        parser = PRParser()
        
        # Build structured context
        context = parser.build_context(
            pr_data=state.pr_data or {},
            pr_files=state.pr_files or [],
        )
        state.parsed_metadata = context
        
        # Filter and chunk diff
        diff = state.pr_diff or ""
        chunks = parser.chunk_diff(diff)
        state.parsed_diff_chunks = chunks
        
        print(f"    ✓ Created {len(chunks)} chunk(s)")
        
    except Exception as e:
        error_msg = f"Failed to parse diff: {e}"
        print(f"    ✗ {error_msg}")
        state.add_error(error_msg)
    
    return state