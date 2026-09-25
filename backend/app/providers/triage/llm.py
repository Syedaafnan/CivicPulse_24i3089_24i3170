"""LLMTriage — production path against a free-tier OpenAI-compatible endpoint (Groq by default).

Engineering around the call:
  * JSON mode requested (response_format=json_object) AND validated with Pydantic anyway.
  * Hard 10 s timeout on every call.
  * Exactly one retry, with jitter, on timeout / 429 / 5xx only. A 400 is never retried.
  * The API key is read from settings as a SecretStr and never logged.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.providers.triage.base import (
    RETRYABLE,
    TriageBadRequest,
    TriageError,
    TriageMalformedOutput,
    TriageRateLimited,
    TriageTimeout,
    TriageUpstreamError,
)
from app.providers.triage.prompt import build_messages, parse_triage_json
from app.schemas import TriageResult


def _jitter_sleep(attempt: int) -> None:
    # 250–750 ms, grows a little per attempt. Jitter avoids synchronised retries across pods.
    time.sleep(0.25 * attempt + random.uniform(0, 0.5))


class _HttpJsonProvider:
    """Shared transport/retry logic for HTTP LLM providers."""

    name: str = "llm"

    def __init__(
        self,
        *,
        timeout: float,
        client: httpx.Client | None = None,
        sleep: Callable[[int], None] = _jitter_sleep,
        max_attempts: int = 2,
    ) -> None:
        self._timeout = timeout
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout))
        self._sleep = sleep
        self._max_attempts = max_attempts

    # -- subclass hooks ------------------------------------------------------
    def _request(self, text: str, location: str) -> tuple[str, dict[str, Any], dict[str, str]]:
        raise NotImplementedError

    def _extract_content(self, body: dict[str, Any]) -> str:
        raise NotImplementedError

    # -- template method -----------------------------------------------------
    def _call_once(self, text: str, location: str) -> TriageResult:
        url, payload, headers = self._request(text, location)
        try:
            resp = self._client.post(url, json=payload, headers=headers, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise TriageTimeout(type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise TriageUpstreamError(type(exc).__name__) from exc

        if resp.status_code == 429:
            raise TriageRateLimited("429 from provider")
        if resp.status_code >= 500:
            raise TriageUpstreamError(f"{resp.status_code} from provider")
        if resp.status_code >= 400:
            raise TriageBadRequest(f"{resp.status_code} from provider")
        try:
            content = self._extract_content(resp.json())
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise TriageMalformedOutput("unexpected response envelope") from exc
        return parse_triage_json(content)

    def triage(self, text: str, location: str) -> TriageResult:
        last: TriageError | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._call_once(text, location)
            except RETRYABLE as exc:
                last = exc
                if attempt < self._max_attempts:
                    self._sleep(attempt)
            # TriageBadRequest / TriageMalformedOutput propagate immediately: retrying won't help.
        assert last is not None
        raise last


class LLMTriage(_HttpJsonProvider):
    """OpenAI-compatible chat completions (Groq, OpenRouter, Gemini's OpenAI endpoint...)."""

    def __init__(self, *, base_url: str, api_key: str, model: str, label: str = "groq", **kw: Any) -> None:
        super().__init__(**kw)
        if not api_key:
            # Fail loudly at construction; the factory turns this into a rules-only setup.
            raise ValueError("LLM_API_KEY is not set")
        self._base_url = base_url.rstrip("/")
        self.__api_key = api_key  # name-mangled; never included in repr/logs
        self._model = model
        self.name = f"llm:{label}"

    def __repr__(self) -> str:
        return f"LLMTriage(model={self._model!r}, base_url={self._base_url!r})"

    def _request(self, text: str, location: str) -> tuple[str, dict[str, Any], dict[str, str]]:
        payload = {
            "model": self._model,
            "messages": build_messages(text, location),
            "temperature": 0,
            "max_tokens": 200,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.__api_key}"}
        return f"{self._base_url}/chat/completions", payload, headers

    def _extract_content(self, body: dict[str, Any]) -> str:
        return str(body["choices"][0]["message"]["content"])
