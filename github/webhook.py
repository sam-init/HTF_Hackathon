"""
github/webhook.py
-----------------
FastAPI router handling incoming GitHub webhook events.

Security: HMAC-SHA256 signature verification using GITHUB_WEBHOOK_SECRET.
Supported events: pull_request (opened, synchronize, reopened)
"""
import hashlib
import hmac
import asyncio
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from config.settings import get_settings
from github.pr_handler import handle_pull_request_event

router = APIRouter(prefix="/webhook", tags=["webhook"])
settings = get_settings()


def _verify_signature(payload_bytes: bytes, sig_header: str | None) -> bool:
    """
    Verify that the X-Hub-Signature-256 header matches HMAC-SHA256 of the payload.
    Returns False if secret is unconfigured or signature is missing/invalid.
    """
    if not settings.github_webhook_secret:
        # No secret configured → accept all (dev only!)
        return True

    if not sig_header or not sig_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, sig_header)


@router.post("/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive all GitHub webhook events.
    Only processes pull_request events; ignores everything else.
    """
    payload_bytes = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(payload_bytes, sig_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event_type == "pull_request":
        action = payload.get("action", "")
        # Only trigger on open/update actions
        if action in ("opened", "synchronize", "reopened"):
            # Run review in background – respond immediately to GitHub
            background_tasks.add_task(handle_pull_request_event, payload)

    return {"status": "accepted"}
