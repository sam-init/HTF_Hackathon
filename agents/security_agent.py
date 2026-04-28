"""
agents/security_agent.py
-------------------------
Detects OWASP Top 10 and general security vulnerabilities in PR diffs:
SQL injection, XSS, hardcoded secrets, insecure dependencies, path traversal, etc.
"""
from typing import List, Dict, Any
from agents.base_agent import BaseReviewAgent


def _format_diff_for_prompt(diff_files: List[Dict[str, Any]]) -> str:
    parts = []
    for df in diff_files:
        added = "\n".join(f"  L{ln}: {code}" for ln, code in df["added_lines"][:80])
        parts.append(f"### File: {df['file']}\n```\n{added}\n```")
    return "\n\n".join(parts)


class SecurityAgent(BaseReviewAgent):
    name = "SecurityAgent"

    def build_prompt(
        self,
        diff_files: List[Dict[str, Any]],
        meta: Dict[str, Any],
    ) -> str:
        diff_text = _format_diff_for_prompt(diff_files)
        return f"""Perform a security audit on the following PR diff.

PR: {meta.get('repo_full')} #{meta.get('pr_number')} — {meta.get('pr_title')}

Identify ONLY real security vulnerabilities from the OWASP Top 10 and beyond:
1. SQL Injection (string concatenation in queries)
2. Cross-Site Scripting (XSS) – unsanitised user input in HTML/JS
3. Hardcoded secrets, API keys, passwords, tokens
4. Insecure Deserialization (pickle, eval, exec on user input)
5. Path Traversal (user-controlled file paths)
6. Command Injection (os.system, subprocess with user input)
7. Broken Authentication (weak JWT, missing auth checks)
8. Sensitive Data Exposure (logging passwords, PII)
9. CSRF vulnerabilities
10. Insecure Direct Object References (IDOR)

Added lines in this PR:
{diff_text}

Return a JSON array. Each finding: file, line (integer), issue, fix_suggestion, severity.
Mark critical/high for exploitable vulns, medium for risky patterns.
"""
