from __future__ import annotations

from typing import Any


def format_inline_comments(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comments = []
    for finding in findings:
        comments.append(
            {
                "path": finding["file"],
                "line": finding["line"],
                "body": (
                    f"[{finding['severity'].upper()}] {finding['issue_title']}\n\n"
                    f"{finding['explanation']}\n\n"
                    f"Suggested fix: {finding['fix_suggestion']}"
                ),
            }
        )
    return comments
