from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from backend.utils.settings import settings

logger = logging.getLogger(__name__)

# Conservative timeout for Render free-tier: NIM must respond within 120 s or we skip.
_NIM_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)


class NIMClient:
    def __init__(self) -> None:
        # Normalise: strip trailing slash, then strip accidental trailing /v1
        # so we can safely append /v1/chat/completions ourselves.
        base = settings.nim_base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self.base_url = base
        self.api_key = settings.nim_api_key

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def chat(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str | None:
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
            "max_tokens": 4096,
        }

        try:
            async with httpx.AsyncClient(timeout=_NIM_TIMEOUT) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "NIM HTTP error %s for model %s: %s",
                exc.response.status_code,
                model,
                exc.response.text[:300],
            )
            return None
        except Exception as exc:
            logger.warning("NIM call failed for model %s: %s", model, exc)
            return None
