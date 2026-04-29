from __future__ import annotations

from typing import Any

import httpx

from backend.utils.settings import settings


class NIMClient:
    def __init__(self) -> None:
        self.base_url = settings.nim_base_url.rstrip("/")
        self.api_key = settings.nim_api_key

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def chat(self, model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str | None:
        if not self.enabled:
            return None

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            return None
