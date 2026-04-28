"""
agents/performance_agent.py
---------------------------
Detects performance anti-patterns: N+1 queries, blocking I/O in async,
unnecessary re-renders, memory leaks, inefficient data structures, etc.
"""
from typing import List, Dict, Any
from agents.base_agent import BaseReviewAgent


def _format_diff_for_prompt(diff_files: List[Dict[str, Any]]) -> str:
    parts = []
    for df in diff_files:
        added = "\n".join(f"  L{ln}: {code}" for ln, code in df["added_lines"][:80])
        parts.append(f"### File: {df['file']}\n```\n{added}\n```")
    return "\n\n".join(parts)


class PerformanceAgent(BaseReviewAgent):
    name = "PerformanceAgent"

    def build_prompt(self, diff_files: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
        diff_text = _format_diff_for_prompt(diff_files)
        return f"""Analyse the following PR diff for performance issues.

PR: {meta.get('repo_full')} #{meta.get('pr_number')} — {meta.get('pr_title')}

Look specifically for:
1. N+1 database query patterns (queries inside loops)
2. Missing database indexes implied by new queries
3. Blocking/synchronous I/O in async context
4. Redundant computation that should be cached
5. Inefficient data structures (O(n) lookups where O(1) is possible)
6. Large payloads loaded into memory at once (should be streamed)
7. Unbounded loops or missing pagination
8. Unoptimised React re-renders (missing useMemo/useCallback)
9. Missing connection pooling

Added lines:
{diff_text}

Return JSON array. Each finding: file, line (integer), issue, fix_suggestion, severity.
"""
