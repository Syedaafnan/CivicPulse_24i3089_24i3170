"""LLMTriage against an in-process fake HTTP server (httpx.MockTransport): no network, no sleeps."""

import json

import httpx
import pytest

from app.providers.triage.base import TriageBadRequest, TriageMalformedOutput, TriageTimeout
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage

GOOD = {"category": "water", "priority": "high", "summary": "Burst main flooding Street 12", "confidence": 0.9}


def chat(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def make(handler, sleeps: list[int] | None = None) -> LLMTriage:  # noqa: ANN001
    sleeps = sleeps if sleeps is not None else []
    return LLMTriage(
        base_url="https://fake.test/v1",
        api_key="sk-test-secret",
        model="m",
        timeout=10,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
    )


def test_success_sends_json_mode_and_parses() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        return chat(json.dumps(GOOD))

    result = make(handler).triage("Burst main", "St 12")
    assert result.category.value == "water"
    assert seen["response_format"] == {"type": "json_object"}


def test_retries_once_on_429_then_succeeds() -> None:
    calls, sleeps = [], []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429) if len(calls) == 1 else chat(json.dumps(GOOD))

    assert make(handler, sleeps).triage("x" * 20, "loc").priority.value == "high"
    assert len(calls) == 2 and len(sleeps) == 1


def test_timeout_retried_once_then_raises() -> None:
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(TriageTimeout):
        make(handler).triage("x" * 20, "loc")
    assert len(calls) == 2  # exactly one retry


def test_400_is_never_retried() -> None:
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": "bad"})

    with pytest.raises(TriageBadRequest):
        make(handler).triage("x" * 20, "loc")
    assert len(calls) == 1


def test_malformed_output_not_retried() -> None:
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return chat("I think it is about water.")

    with pytest.raises(TriageMalformedOutput):
        make(handler).triage("x" * 20, "loc")
    assert len(calls) == 1


def test_api_key_never_in_repr() -> None:
    provider = make(lambda r: chat(json.dumps(GOOD)))
    assert "sk-test-secret" not in repr(provider)
    assert "sk-test-secret" not in str(vars(provider).get("_model"))


def test_missing_api_key_rejected() -> None:
    with pytest.raises(ValueError):
        LLMTriage(base_url="https://x", api_key="", model="m", timeout=10)


def test_ollama_uses_format_json() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"message": {"content": json.dumps(GOOD)}})

    p = OllamaTriage(
        base_url="http://ollama:11434",
        model="llama3.2:1b",
        timeout=10,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert p.triage("x" * 20, "loc").category.value == "water"
    assert seen["format"] == "json" and p.name == "llm:ollama"
