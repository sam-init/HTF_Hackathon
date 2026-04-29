from __future__ import annotations

import io
import shutil
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = ROOT / "data" / "workspaces"
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


class IngestionError(Exception):
    pass


def _ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def create_workspace() -> Path:
    run_id = str(uuid.uuid4())
    target = WORKSPACE_ROOT / run_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def cleanup_workspace(workspace: Path) -> None:
    shutil.rmtree(workspace, ignore_errors=True)


def ingest_zip_bytes(blob: bytes, workspace: Path) -> Path:
    _ensure_clean_dir(workspace)
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            zf.extractall(workspace)
    except zipfile.BadZipFile as exc:
        raise IngestionError("Uploaded file is not a valid ZIP archive") from exc

    inner_dirs = [p for p in workspace.iterdir() if p.is_dir()]
    if len(inner_dirs) == 1 and not any(p.is_file() for p in workspace.iterdir()):
        return inner_dirs[0]
    return workspace


def ingest_from_url(repo_url: str, workspace: Path, github_token: str = "") -> Path:
    parsed = urlparse(repo_url)
    if not parsed.scheme:
        raise IngestionError("Repository URL must include a valid scheme (https://)")

    url = repo_url
    headers = {}
    if "github.com" in parsed.netloc:
        cleaned = repo_url.rstrip("/")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]
        owner_repo = "/".join(cleaned.split("/")[-2:])
        url = f"https://api.github.com/repos/{owner_repo}/zipball"
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code >= 400:
        raise IngestionError(f"Failed to fetch repository archive ({response.status_code})")

    return ingest_zip_bytes(response.content, workspace)
