"""
agents/readability_agent.py
---------------------------
Reviews code readability, documentation quality, naming conventions,
complexity, and dead code.
"""
from typing import List, Dict, Any
from agents.base_agent import BaseReviewAgent


def _format_diff_for_prompt(diff_files: List[Dict[str, Any]]) -> str:
    parts = []
    for df in diff_files:
        added = "\n".join(f"  L{ln}: {code}" for ln, code in df["added_lines"][:80])
        parts.append(f"### File: {df['file']}\n```\n{added}\n```")
    return "\n\n".join(parts)


class ReadabilityDocsAgent(BaseReviewAgent):
    name = "ReadabilityDocsAgent"

    def build_prompt(self, diff_files: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
        diff_text = _format_diff_for_prompt(diff_files)
        return f"""Review the following PR diff for readability and documentation issues.

PR: {meta.get('repo_full')} #{meta.get('pr_number')} — {meta.get('pr_title')}

Focus on:
1. Missing or inadequate docstrings/JSDoc on public functions and classes
2. Cryptic variable names (single-letter vars outside list comprehensions)
3. Functions longer than 50 lines that should be decomposed
4. Deeply nested code (>3 levels) that could be flattened
5. Magic numbers/strings that should be constants
6. Commented-out dead code that should be removed
7. Misleading or outdated comments
8. Missing type annotations on public API functions
9. Inconsistent naming conventions within a file

Added lines:
{diff_text}

Return JSON array. Each finding: file, line (integer), issue, fix_suggestion, severity.
Severity for docs issues should be low/info unless critically confusing.
"""
