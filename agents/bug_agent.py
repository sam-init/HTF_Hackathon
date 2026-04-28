"""
agents/bug_agent.py
-------------------
Detects bugs, logical errors, null-pointer risks, off-by-one errors,
exception handling issues, and safety problems in PR diffs.
"""
from typing import List, Dict, Any
from agents.base_agent import BaseReviewAgent


def _format_diff_for_prompt(diff_files: List[Dict[str, Any]]) -> str:
    """Build a readable diff representation for the prompt."""
    parts = []
    for df in diff_files:
        added = "\n".join(f"  L{ln}: {code}" for ln, code in df["added_lines"][:80])
        parts.append(f"### File: {df['file']}\n```\n{added}\n```")
    return "\n\n".join(parts)


class BugAndSafetyAgent(BaseReviewAgent):
    name = "BugAndSafetyAgent"

    def build_prompt(
        self,
        diff_files: List[Dict[str, Any]],
        meta: Dict[str, Any],
    ) -> str:
        diff_text = _format_diff_for_prompt(diff_files)
        return f"""Review the following PR diff for bugs and safety issues.

PR Info:
- Repo: {meta.get('repo_full')}
- PR #{meta.get('pr_number')}: {meta.get('pr_title')}
- Author: {meta.get('author')}

Focus ONLY on:
1. Null/undefined pointer dereferences
2. Off-by-one errors (index out of bounds)
3. Uncaught exceptions or missing try/catch
4. Logic errors (wrong conditions, incorrect loop bounds)
5. Race conditions or shared state mutation
6. Unsafe type casting / coercion
7. Division by zero risks
8. Use of deprecated or unsafe APIs

Added lines in this PR:
{diff_text}

Respond with a JSON array. Only report real bugs, not style issues.
Each finding must include: file, line (integer), issue, fix_suggestion, severity.
"""
