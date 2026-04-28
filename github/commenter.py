"""
github/commenter.py
-------------------
Posts review findings back to GitHub as:
  - Inline pull request review comments (tied to file + line)
  - A summary issue comment with all findings grouped by severity
"""
import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "info": "🔵",
}


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def post_inline_comment(
    token: str,
    owner: str,
    repo: str,
    pr_number: int,
    commit_sha: str,
    finding: Dict[str, Any],
) -> None:
    """
    Post a single inline review comment on a specific file + line.
    GitHub API: POST /repos/{owner}/{repo}/pulls/{pull_number}/comments
    """
    severity = finding.get("severity", "medium")
    emoji = SEVERITY_EMOJI.get(severity, "🟡")
    agent_label = finding.get("agent", "ReviewAgent").replace("Agent", "")

    body = (
        f"**{emoji} [{severity.upper()}] {agent_label} Agent**\n\n"
        f"**Issue:** {finding.get('issue', '')}\n\n"
        f"**Suggestion:** {finding.get('fix_suggestion', 'No fix suggestion.')}"
    )

    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    payload = {
        "body": body,
        "commit_id": commit_sha,
        "path": finding.get("file", ""),
        "line": finding.get("line", 1),
        "side": "RIGHT",  # comment on the new (right) side of the diff
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=_headers(token), json=payload)
        if resp.status_code not in (200, 201):
            logger.warning(
                f"[Commenter] Inline comment failed: {resp.status_code} – {resp.text[:200]}"
            )


async def post_summary_comment(
    token: str,
    owner: str,
    repo: str,
    pr_number: int,
    findings: List[Dict[str, Any]],
    meta: Dict[str, Any],
) -> None:
    """
    Post a top-level PR summary comment with all findings grouped by severity.
    GitHub API: POST /repos/{owner}/{repo}/issues/{pr_number}/comments
    """
    if not findings:
        body = "✅ **AI Code Review Complete** – No significant issues found. Great work!"
    else:
        # Group findings by severity
        by_severity: Dict[str, List] = {}
        for f in findings:
            sev = f.get("severity", "medium")
            by_severity.setdefault(sev, []).append(f)

        lines = [
            f"## 🤖 AI Code Review — {meta['repo_full']} PR #{meta['pr_number']}\n",
            f"**{len(findings)} issue(s) found across {len(set(f['file'] for f in findings))} file(s)**\n",
            "---",
        ]

        for sev in ("critical", "high", "medium", "low", "info"):
            if sev not in by_severity:
                continue
            emoji = SEVERITY_EMOJI[sev]
            lines.append(f"\n### {emoji} {sev.capitalize()} ({len(by_severity[sev])})\n")
            for f in by_severity[sev]:
                lines.append(
                    f"- **`{f.get('file', '')}` L{f.get('line', '?')}** "
                    f"[{f.get('agent', '')}]: {f.get('issue', '')}"
                )

        lines.append("\n---\n*Powered by DevIQ · NVIDIA NIM Multi-Agent Review*")
        body = "\n".join(lines)

    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=_headers(token), json={"body": body})
        if resp.status_code not in (200, 201):
            logger.warning(
                f"[Commenter] Summary comment failed: {resp.status_code} – {resp.text[:200]}"
            )
        else:
            logger.info("[Commenter] Summary comment posted successfully.")
