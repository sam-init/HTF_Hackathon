"""
github/auth.py
--------------
GitHub App JWT + Installation token generation.

Flow:
    App ID + Private Key → JWT (10-min TTL)
    JWT → POST /app/installations/{id}/access_tokens
    → Installation Token (valid 1 hour)
"""
import time
import jwt
import httpx
from pathlib import Path
from config.settings import get_settings

settings = get_settings()


def _load_private_key() -> str:
    """Read PEM private key from disk."""
    key_path = Path(settings.github_private_key_path)
    if not key_path.exists():
        raise FileNotFoundError(
            f"GitHub App private key not found at {key_path}. "
            "Download it from your GitHub App settings."
        )
    return key_path.read_text()


def generate_jwt() -> str:
    """
    Generate a JWT signed with the GitHub App private key.
    JWT is valid for 9 minutes (GitHub max is 10).
    """
    private_key = _load_private_key()
    now = int(time.time())
    payload = {
        "iat": now - 60,       # issued-at (60s in past to handle clock skew)
        "exp": now + (9 * 60), # expires in 9 minutes
        "iss": settings.github_app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    """
    Exchange JWT for an installation access token.
    This token authenticates API calls on behalf of a specific repo installation.
    """
    jwt_token = generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        return resp.json()["token"]
