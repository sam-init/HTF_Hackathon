"""
github/pr_handler.py
--------------------
Orchestrates the full PR review lifecycle:
  1. Extract metadata from webhook payload
  2. Fetch the diff via GitHub API
  3. Run all review agents in parallel
  4. Aggregate + deduplicate findings
  5. Post inline + summary comments back to GitHub
"""
import asyncio
import logging
from github.auth import get_installation_token
from github.diff_fetcher import fetch_pr_diff, parse_diff_to_files
from github.commenter import post_inline_comment, post_summary_comment
from agents.orchestrator import run_all_agents
from config.database import get_db

logger = logging.getLogger(__name__)


def _extract_pr_metadata(payload: dict) -> dict:
    """
    Pull out the fields we need from the raw webhook payload.
    Returns a clean dict with installation_id, repo info, PR number, etc.
    """
    pr = payload["pull_request"]
    repo = payload["repository"]

    return {
        "installation_id": payload["installation"]["id"],
        "repo_full": repo["full_name"],        # e.g. "owner/repo"
        "repo_owner": repo["owner"]["login"],
        "repo_name": repo["name"],
        "pr_number": pr["number"],
        "pr_title": pr["title"],
        "head_sha": pr["head"]["sha"],
        "base_sha": pr["base"]["sha"],
        "head_ref": pr["head"]["ref"],         # branch name
        "base_ref": pr["base"]["ref"],
        "pr_body": pr.get("body") or "",
        "author": pr["user"]["login"],
    }


async def handle_pull_request_event(payload: dict):
    """
    Main async handler – called from background task in webhook.py.
    """
    try:
        meta = _extract_pr_metadata(payload)
        logger.info(f"[PR Review] Starting review for {meta['repo_full']}#{meta['pr_number']}")

        # 1. Get installation token (short-lived, repo-scoped)
        token = await get_installation_token(meta["installation_id"])

        # 2. Fetch the raw unified diff
        raw_diff = await fetch_pr_diff(
            token=token,
            owner=meta["repo_owner"],
            repo=meta["repo_name"],
            pr_number=meta["pr_number"],
        )

        # 3. Parse diff → list of {file, patch, added_lines}
        diff_files = parse_diff_to_files(raw_diff)
        if not diff_files:
            logger.info("[PR Review] Empty diff, skipping review.")
            return

        # 4. Run all agents concurrently
        all_findings = await run_all_agents(diff_files, meta)

        # 5. Post inline comments for each finding
        comment_tasks = [
            post_inline_comment(
                token=token,
                owner=meta["repo_owner"],
                repo=meta["repo_name"],
                pr_number=meta["pr_number"],
                commit_sha=meta["head_sha"],
                finding=f,
            )
            for f in all_findings
        ]
        await asyncio.gather(*comment_tasks, return_exceptions=True)

        # 6. Post a consolidated summary comment
        await post_summary_comment(
            token=token,
            owner=meta["repo_owner"],
            repo=meta["repo_name"],
            pr_number=meta["pr_number"],
            findings=all_findings,
            meta=meta,
        )

        # 7. Persist review record to DB
        async with get_db() as db:
            result = await db.execute(
                "INSERT INTO reviews (repo_full, pr_number, status) VALUES (?, ?, 'completed')",
                (meta["repo_full"], meta["pr_number"]),
            )
            review_id = result.lastrowid
            for f in all_findings:
                await db.execute(
                    """INSERT INTO review_comments
                       (review_id, agent, file_path, line, issue, suggestion, severity)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (review_id, f.get("agent"), f.get("file"), f.get("line"),
                     f.get("issue"), f.get("fix_suggestion"), f.get("severity", "medium")),
                )
            await db.commit()

        logger.info(f"[PR Review] Completed. {len(all_findings)} findings posted.")

    except Exception as e:
        logger.exception(f"[PR Review] Error handling PR event: {e}")
