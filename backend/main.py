from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.models.schemas import DocsResponse, HealthResponse, RepoInput, ReviewResponse, WebhookAck
from backend.services.doc_service import DocumentationService
from backend.services.github_app_auth import GitHubAppAuth, GitHubAppAuthError
from backend.services.ingestion import (
    IngestionError,
    cleanup_workspace,
    create_workspace,
    ingest_from_url,
    ingest_zip_bytes,
)
from backend.services.review_service import ReviewService
from backend.utils.settings import settings
from docs.parser import parse_repository
from docs.repo_loader import iter_code_files
from github.commenter import format_inline_comments, post_pr_review
from github.diff_fetcher import GitHubDiffError, fetch_pr_diff
from github.pr_handler import build_virtual_files_from_diff
from github.webhook import SignatureValidationError, validate_github_signature
from rag.rag_pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Developer Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_pipeline = RAGPipeline()
review_service = ReviewService(rag_pipeline)
doc_service = DocumentationService(rag_pipeline)
github_app_auth = GitHubAppAuth(settings.github_app_id, settings.github_private_key)
RUN_CACHE: dict[str, dict[str, Any]] = {}


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
    )


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        cache_runs=len(RUN_CACHE),
        rag_chunks=len(rag_pipeline.store.items),
    )


# ── Shared workspace helper ───────────────────────────────────────────────────
def _parse_workspace(repo_root: Path) -> list[dict[str, Any]]:
    try:
        files = iter_code_files(repo_root)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File scan failed: {exc}") from exc

    if not files:
        raise HTTPException(status_code=400, detail="No supported source files found in repository")

    try:
        return parse_repository(files, repo_root)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Repository parsing failed: {exc}") from exc


# ── Review endpoints ──────────────────────────────────────────────────────────
@app.post("/api/review/repo", response_model=ReviewResponse)
def review_repo(payload: RepoInput) -> ReviewResponse:
    workspace = create_workspace()
    try:
        try:
            repo_root = ingest_from_url(payload.repo_url, workspace, github_token=settings.github_token)
        except IngestionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        parsed_files = _parse_workspace(repo_root)
        try:
            result = review_service.review(parsed_files, payload.persona)
        except Exception as exc:
            logger.exception("ReviewService.review failed")
            raise HTTPException(status_code=500, detail=f"Review pipeline error: {exc}") from exc

        run_id = str(uuid.uuid4())
        response = ReviewResponse(run_id=run_id, persona=payload.persona, **result)
        RUN_CACHE[run_id] = response.model_dump()
        return response
    finally:
        if not settings.keep_workspaces:
            cleanup_workspace(workspace)


@app.post("/api/review/upload", response_model=ReviewResponse)
async def review_upload(persona: str = Form(...), file: UploadFile = File(...)) -> ReviewResponse:
    blob = await file.read()
    workspace = create_workspace()
    try:
        try:
            repo_root = ingest_zip_bytes(blob, workspace)
        except IngestionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        parsed_files = _parse_workspace(repo_root)
        try:
            result = review_service.review(parsed_files, persona)
        except Exception as exc:
            logger.exception("ReviewService.review failed")
            raise HTTPException(status_code=500, detail=f"Review pipeline error: {exc}") from exc

        run_id = str(uuid.uuid4())
        response = ReviewResponse(run_id=run_id, persona=persona, **result)
        RUN_CACHE[run_id] = response.model_dump()
        return response
    finally:
        if not settings.keep_workspaces:
            cleanup_workspace(workspace)


# ── Docs endpoints ────────────────────────────────────────────────────────────
@app.post("/api/docs/repo", response_model=DocsResponse)
def docs_repo(payload: RepoInput) -> DocsResponse:
    workspace = create_workspace()
    try:
        try:
            repo_root = ingest_from_url(payload.repo_url, workspace, github_token=settings.github_token)
        except IngestionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        parsed_files = _parse_workspace(repo_root)
        try:
            result = doc_service.generate(parsed_files, payload.persona)
        except Exception as exc:
            logger.exception("DocumentationService.generate failed")
            raise HTTPException(status_code=500, detail=f"Documentation pipeline error: {exc}") from exc

        run_id = str(uuid.uuid4())
        response = DocsResponse(run_id=run_id, persona=payload.persona, **result)
        RUN_CACHE[run_id] = response.model_dump()
        return response
    finally:
        if not settings.keep_workspaces:
            cleanup_workspace(workspace)


@app.post("/api/docs/upload", response_model=DocsResponse)
async def docs_upload(persona: str = Form(...), file: UploadFile = File(...)) -> DocsResponse:
    blob = await file.read()
    workspace = create_workspace()
    try:
        try:
            repo_root = ingest_zip_bytes(blob, workspace)
        except IngestionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        parsed_files = _parse_workspace(repo_root)
        try:
            result = doc_service.generate(parsed_files, persona)
        except Exception as exc:
            logger.exception("DocumentationService.generate failed")
            raise HTTPException(status_code=500, detail=f"Documentation pipeline error: {exc}") from exc

        run_id = str(uuid.uuid4())
        response = DocsResponse(run_id=run_id, persona=persona, **result)
        RUN_CACHE[run_id] = response.model_dump()
        return response
    finally:
        if not settings.keep_workspaces:
            cleanup_workspace(workspace)


# ── GitHub webhook ────────────────────────────────────────────────────────────
@app.post("/api/github/webhook", response_model=WebhookAck)
async def github_webhook(request: Request) -> WebhookAck:
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event", "")

    try:
        validate_github_signature(raw_body, settings.github_webhook_secret, signature)
    except SignatureValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if event != "pull_request":
        return WebhookAck(accepted=True, action="ignored", message=f"Event {event!r} ignored")

    action = payload.get("action", "")
    if action not in {"opened", "synchronize", "reopened"}:
        return WebhookAck(accepted=True, action="ignored", message=f"Action {action!r} ignored")

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    repo_name = repo.get("full_name")
    pr_number = pr.get("number")
    installation_id = payload.get("installation", {}).get("id")

    if not repo_name or not pr_number:
        raise HTTPException(status_code=400, detail="Invalid pull_request payload: missing repo or pr_number")

    # Resolve auth token (GitHub App takes priority)
    auth_token = settings.github_token
    if github_app_auth.enabled and installation_id:
        try:
            auth_token = github_app_auth.get_installation_token(int(installation_id))
        except GitHubAppAuthError as exc:
            logger.warning("GitHub App auth failed, falling back to PAT: %s", exc)
            # Don't block the webhook — continue with PAT

    try:
        diff_text = fetch_pr_diff(repo_name, pr_number, auth_token)
    except GitHubDiffError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    parsed_files = build_virtual_files_from_diff(diff_text)
    if not parsed_files:
        return WebhookAck(
            accepted=True,
            action=action,
            message="PR diff contained no reviewable files.",
        )

    try:
        result = review_service.review(parsed_files, persona="Backend Developer")
    except Exception as exc:
        logger.exception("ReviewService failed on webhook PR#%d", pr_number)
        return WebhookAck(
            accepted=True,
            action=action,
            message=f"Review pipeline error: {exc}",
        )

    run_id = str(uuid.uuid4())
    inline_comments = format_inline_comments(result["findings"])

    RUN_CACHE[run_id] = {
        "type": "github_pr_review",
        "repo": repo_name,
        "pr_number": pr_number,
        "review": result,
        "comments": inline_comments,
    }

    # POST the review back to GitHub
    posted = post_pr_review(
        repo_full_name=repo_name,
        pr_number=pr_number,
        token=auth_token,
        findings=result["findings"],
        summary=result.get("summary", ""),
    )

    message = (
        f"PR reviewed successfully — {len(result['findings'])} finding(s). "
        + ("Inline feedback posted to GitHub." if posted else "Comment posting skipped (no token or GitHub error).")
    )

    return WebhookAck(
        accepted=True,
        action=action,
        message=message,
        run_id=run_id,
    )
