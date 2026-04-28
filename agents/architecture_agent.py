"""
agents/architecture_agent.py
-----------------------------
Reviews architectural concerns: SOLID violations, circular dependencies,
layering violations, god classes, and improper abstraction.
"""
from typing import List, Dict, Any
from agents.base_agent import BaseReviewAgent


def _format_diff_for_prompt(diff_files: List[Dict[str, Any]]) -> str:
    parts = []
    for df in diff_files:
        added = "\n".join(f"  L{ln}: {code}" for ln, code in df["added_lines"][:60])
        parts.append(f"### File: {df['file']}\n```\n{added}\n```")
    return "\n\n".join(parts)


class ArchitectureAgent(BaseReviewAgent):
    name = "ArchitectureAgent"

    def build_prompt(self, diff_files: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
        diff_text = _format_diff_for_prompt(diff_files)
        return f"""Analyse the following PR diff for architectural and design issues.

PR: {meta.get('repo_full')} #{meta.get('pr_number')} — {meta.get('pr_title')}

Focus on:
1. SOLID principle violations
   - Single Responsibility: classes/functions doing too many things
   - Open/Closed: modifications require changing core logic
   - Dependency Inversion: high-level modules depending on low-level details
2. God classes (classes with >10 methods or >300 lines)
3. Circular imports or bidirectional dependencies
4. Business logic leaking into presentation/transport layer
5. Missing abstractions (repeated complex logic that should be a service)
6. Incorrect layering (e.g., DB calls in a route handler with no service layer)
7. Tight coupling between unrelated modules
8. Global mutable state

Added lines:
{diff_text}

Return JSON array. Each finding: file, line (integer), issue, fix_suggestion, severity.
"""
