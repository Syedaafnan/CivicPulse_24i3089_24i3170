"""OllamaTriage — fully offline path, a container in the Compose stack. Same interface."""

from __future__ import annotations

from typing import Any

from app.providers.triage.llm import _HttpJsonProvider
from app.providers.triage.prompt import build_messages


class OllamaTriage(_HttpJsonProvider):
    name = "llm:ollama"

    def __init__(self, *, base_url: str, model: str, **kw: Any) -> None:
        super().__init__(**kw)
        self._base_url = base_url.rstrip("/")
        self._model = model

    def _request(self, text: str, location: str) -> tuple[str, dict[str, Any], dict[str, str]]:
        payload = {
            "model": self._model,
            "messages": build_messages(text, location),
            "stream": False,
            "format": "json",  # Ollama's structured-output switch
            "options": {"temperature": 0},
        }
        return f"{self._base_url}/api/chat", payload, {}

    def _extract_content(self, body: dict[str, Any]) -> str:
        return str(body["message"]["content"])
