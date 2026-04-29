from __future__ import annotations

import time

import jwt
import requests


class GitHubAppAuthError(Exception):
    pass


class GitHubAppAuth:
    def __init__(self, app_id: str, private_key: str) -> None:
        self.app_id = app_id.strip()
        self.private_key = private_key.strip()

    @property
    def enabled(self) -> bool:
        return bool(self.app_id and self.private_key)

    def get_installation_token(self, installation_id: int) -> str:
        if not self.enabled:
            raise GitHubAppAuthError("GitHub App auth is not configured")

        app_jwt = self._build_jwt()
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        response = requests.post(url, headers=headers, timeout=20)
        if response.status_code >= 400:
            raise GitHubAppAuthError(
                f"Failed to create installation token ({response.status_code}): {response.text[:240]}"
            )

        token = response.json().get("token")
        if not token:
            raise GitHubAppAuthError("GitHub installation token response did not include a token")
        return token

    def _build_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": self.app_id,
        }
        key = self.private_key.replace("\\n", "\n")
        encoded = jwt.encode(payload, key, algorithm="RS256")
        return encoded if isinstance(encoded, str) else encoded.decode("utf-8")
