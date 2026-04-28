"""
agents/accessibility_agent.py
------------------------------
Reviews frontend code for WCAG 2.1 accessibility violations:
missing alt text, ARIA labels, keyboard navigation, color contrast, etc.
Skips non-frontend files automatically.
"""
from typing import List, Dict, Any
from agents.base_agent import BaseReviewAgent

# File extensions where accessibility checks are relevant
FRONTEND_EXTENSIONS = {".html", ".jsx", ".tsx", ".vue", ".svelte", ".css", ".scss"}


def _is_frontend_file(file_path: str) -> bool:
    return any(file_path.endswith(ext) for ext in FRONTEND_EXTENSIONS)


def _format_diff_for_prompt(diff_files: List[Dict[str, Any]]) -> str:
    parts = []
    for df in diff_files:
        if not _is_frontend_file(df["file"]):
            continue
        added = "\n".join(f"  L{ln}: {code}" for ln, code in df["added_lines"][:80])
        parts.append(f"### File: {df['file']}\n```\n{added}\n```")
    return "\n\n".join(parts)


class AccessibilityAgent(BaseReviewAgent):
    name = "AccessibilityAgent"

    async def run(self, diff_files: List[Dict[str, Any]], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Only run if the PR touches frontend files
        has_frontend = any(_is_frontend_file(df["file"]) for df in diff_files)
        if not has_frontend:
            return []
        return await super().run(diff_files, meta)

    def build_prompt(self, diff_files: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
        diff_text = _format_diff_for_prompt(diff_files)
        if not diff_text:
            return "No frontend files in this PR. Return []."

        return f"""Review the following frontend code for WCAG 2.1 accessibility violations.

PR: {meta.get('repo_full')} #{meta.get('pr_number')} — {meta.get('pr_title')}

Check for:
1. <img> elements missing alt attribute
2. Form inputs missing associated <label> or aria-label
3. Interactive elements (div/span with onClick) missing role and keyboard handler
4. Missing focus indicators (outline: none without replacement)
5. Insufficient color contrast (hardcoded low-contrast colors)
6. Missing skip-navigation links on full-page components
7. ARIA roles used incorrectly
8. Inaccessible modal/dialog (missing focus trap, aria-modal)
9. Links with non-descriptive text ("click here", "read more")

Frontend files changed:
{diff_text}

Return JSON array. Each finding: file, line (integer), issue, fix_suggestion, severity.
"""
