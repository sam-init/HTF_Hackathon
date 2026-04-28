"""
docs/repo_loader.py
--------------------
Handles loading source code from:
  1. A local ZIP file upload
  2. A GitHub repo URL (public, using GitHub API)

Returns a {relative_path: source_code} dict for all text files.
"""
import io
import zipfile
import logging
import httpx
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
MAX_FILE_SIZE = 500_000  # 500KB per file limit

# Extensions to index (skip binary, compiled, etc.)
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".rs",
    ".cpp", ".c", ".h", ".cs", ".php", ".html", ".css", ".scss",
    ".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".env",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
    "build", ".next", "target", "vendor",
}


def load_from_zip(zip_bytes: bytes) -> Dict[str, str]:
    """
    Extract readable source files from a ZIP archive bytes.

    Returns:
        {relative_path: source_code}
    """
    file_dict: Dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue

                path = Path(info.filename)

                # Skip directories we don't care about
                if any(part in SKIP_DIRS for part in path.parts):
                    continue

                # Only include known text extensions
                if path.suffix not in TEXT_EXTENSIONS:
                    continue

                # Skip oversized files
                if info.file_size > MAX_FILE_SIZE:
                    logger.debug(f"[ZipLoader] Skipping large file: {info.filename}")
                    continue

                try:
                    content = zf.read(info.filename).decode("utf-8", errors="replace")
                    file_dict[str(path)] = content
                except Exception as e:
                    logger.warning(f"[ZipLoader] Could not read {info.filename}: {e}")

    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid ZIP file: {e}")

    logger.info(f"[ZipLoader] Loaded {len(file_dict)} files from ZIP")
    return file_dict


async def load_from_github(repo_full: str, token: str = "", ref: str = "main") -> Dict[str, str]:
    """
    Fetch all source files from a public GitHub repo via the Git Trees API.
    Uses recursive tree listing to avoid multiple API calls.

    Args:
        repo_full: "owner/repo" string
        token: optional GitHub OAuth/PAT token for private repos
        ref: branch name or commit SHA (default: "main")

    Returns:
        {relative_path: source_code}
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    file_dict: Dict[str, str] = {}

    async with httpx.AsyncClient(timeout=60) as client:
        # Get the recursive file tree
        tree_url = f"{GITHUB_API}/repos/{repo_full}/git/trees/{ref}?recursive=1"
        resp = await client.get(tree_url, headers=headers)
        resp.raise_for_status()
        tree_data = resp.json()

        blobs = [
            item for item in tree_data.get("tree", [])
            if item["type"] == "blob"
            and Path(item["path"]).suffix in TEXT_EXTENSIONS
            and item.get("size", 0) < MAX_FILE_SIZE
            and not any(part in SKIP_DIRS for part in Path(item["path"]).parts)
        ]

        logger.info(f"[GHLoader] Found {len(blobs)} indexable files in {repo_full}")

        # Fetch file contents (limited concurrency to avoid rate limits)
        import asyncio
        semaphore = asyncio.Semaphore(5)

        async def fetch_file(blob: dict) -> None:
            async with semaphore:
                raw_url = f"https://raw.githubusercontent.com/{repo_full}/{ref}/{blob['path']}"
                try:
                    r = await client.get(raw_url, headers=headers, timeout=15)
                    if r.status_code == 200:
                        file_dict[blob["path"]] = r.text
                except Exception as e:
                    logger.warning(f"[GHLoader] Failed to fetch {blob['path']}: {e}")

        await asyncio.gather(*[fetch_file(b) for b in blobs])

    logger.info(f"[GHLoader] Successfully loaded {len(file_dict)} files")
    return file_dict
