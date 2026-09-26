"""Select the TriageProvider from TRIAGE_PROVIDER. The only place that knows concrete classes."""

from __future__ import annotations

import logging

from app.config import Settings
from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage

log = logging.getLogger(__name__)

AVAILABLE = ["llm", "ollama", "rules", "simulated"]


def build_provider(settings: Settings) -> TriageProvider:
    choice = settings.triage_provider
    timeout = settings.triage_timeout_seconds
    if choice == "llm":
        try:
            return LLMTriage(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key.get_secret_value(),
                model=settings.llm_model,
                label=settings.llm_provider_label,
                timeout=timeout,
            )
        except ValueError as exc:
            log.warning("LLM provider unavailable, using rules", extra={"reason": str(exc)})
            return RuleBasedTriage()
    if choice == "ollama":
        return OllamaTriage(base_url=settings.ollama_base_url, model=settings.ollama_model, timeout=timeout)
    if choice == "simulated":
        return SimulatedTriage(failure_mode=settings.simulated_failure_mode)
    return RuleBasedTriage()
