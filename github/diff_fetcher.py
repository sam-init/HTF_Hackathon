"""
github/diff_fetcher.py
----------------------
Fetches the raw unified diff for a PR using the GitHub REST API,
then parses it into structured file-level chunks.
"""
import httpx
import re
from typing import List, Dict, Any

GITHUB_API = "https://api.github.com"


async def fetch_pr_diff(token: str, owner: str, repo: str, pr_number: int) -> str:
    """
    Download the raw unified diff for a PR.
    GitHub returns diff content when Accept is application/vnd.github.v3.diff
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3.diff",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        return resp.text


def parse_diff_to_files(raw_diff: str) -> List[Dict[str, Any]]:
    """
    Parse a unified diff string into a list of per-file structures:

    Returns:
        [
          {
            "file": "path/to/file.py",
            "patch": "... raw hunk ...",
            "added_lines": [(line_number, code_line), ...]
          },
          ...
        ]

    Only includes files with added lines (i.e., new/modified code).
    """
    files = []
    # Split on "diff --git" headers
    file_blocks = re.split(r"^diff --git ", raw_diff, flags=re.MULTILINE)

    for block in file_blocks:
        if not block.strip():
            continue

        # Extract the b/filename (the new file path)
        header_match = re.match(r"a/.+? b/(.+)", block)
        if not header_match:
            continue
        file_path = header_match.group(1).strip()

        # Skip binary files and delete-only diffs
        if "Binary files" in block or "deleted file mode" in block:
            continue

        # Collect all added lines with their new-file line numbers
        added_lines = []
        current_line_no = 0

        for line in block.splitlines():
            # Hunk header: @@ -old_start,count +new_start,count @@
            hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if hunk_match:
                current_line_no = int(hunk_match.group(1)) - 1
                continue

            if line.startswith("+") and not line.startswith("+++"):
                current_line_no += 1
                added_lines.append((current_line_no, line[1:]))  # strip leading '+'
            elif not line.startswith("-"):
                current_line_no += 1

        if added_lines:
            files.append({
                "file": file_path,
                "patch": block,
                "added_lines": added_lines,
            })

    return files
