"""
agents/base_agent.py
--------------------
Abstract base class for all review agents.

Each concrete agent must:
  - Set self.name: str
  - Implement `build_prompt(diff_files, meta) -> str`
  - Optionally override `parse_response(text) -> list[dict]`
    (default JSON parsing is provided)

Each agent returns a list of findings:
  {
    "agent":          str,   # agent name
    "file":           str,   # relative path
    "line":           int,   # line number in the PR diff
    "issue":          str,   # description of the problem
    "fix_suggestion": str,   # concrete fix recommendation
    "severity":       str,   # critical / high / medium / low / info
  }
"""
import json
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from openai import AsyncOpenAI
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseReviewAgent(ABC):
    """
    Abstract review agent backed by NVIDIA NIM (OpenAI-compatible API).
    All agents share one async OpenAI client configured to hit NIM endpoints.
    """

    name: str = "BaseAgent"

    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key,
        )
        self.model = settings.nim_review_model

    @abstractmethod
    def build_prompt(
        self,
        diff_files: List[Dict[str, Any]],
        meta: Dict[str, Any],
    ) -> str:
        """
        Construct the user prompt from the diff and PR metadata.
        Must return a string that instructs the model to respond in JSON.
        """
        ...

    def _system_prompt(self) -> str:
        return (
            "You are an expert code reviewer specialised in "
            f"{self.name.replace('Agent', '').strip()} analysis. "
            "Respond ONLY with a JSON array of finding objects. "
            "Each object must have exactly these keys: "
            "'file' (string), 'line' (integer), 'issue' (string), "
            "'fix_suggestion' (string), 'severity' (one of: critical, high, medium, low, info). "
            "Do NOT include any text outside the JSON array. "
            "If no issues found, return an empty array []."
        )

    def parse_response(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract JSON array from model output.
        Handles both clean JSON and JSON embedded in markdown code fences.
        """
        # Strip markdown code fences if present
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            # Try extracting first [...] block
            match = re.search(r"\[.*?\]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        logger.warning(f"[{self.name}] Could not parse response: {text[:300]}")
        return []

    async def run(
        self,
        diff_files: List[Dict[str, Any]],
        meta: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Send prompt to NIM model and return structured findings list.
        Adds agent name to each finding.
        """
        prompt = self.build_prompt(diff_files, meta)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,       # low temp for deterministic review
                max_tokens=2048,
            )
            raw_text = response.choices[0].message.content or "[]"
        except Exception as e:
            logger.error(f"[{self.name}] LLM call failed: {e}")
            return []

        findings = self.parse_response(raw_text)

        # Tag each finding with this agent's name
        for f in findings:
            f["agent"] = self.name
            # Ensure required keys have defaults
            f.setdefault("severity", "medium")
            f.setdefault("fix_suggestion", "No specific fix provided.")

        return findings
