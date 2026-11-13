"""LLM access for explanations (dashboard chat, editor), through OpenAI-compatible chat endpoints.

Providers: Groq and Google Gemini (both have free tiers). Settings come from ``[llm]`` in .codetwin.toml,
keys from the environment. The LLM explains evidence; it never decides proceed/abstain and its output is
never stored as evidence (see AGENTS.md).

Planned here as well: LLM-suggested links for dynamic calls, trusted only after a runtime probe (U3, RQ6).
"""
from .providers import (
    PROVIDERS,
    LLMClient,
    LLMError,
    LLMNotConfigured,
    LLMRateLimited,
    Provider,
    Settings,
    client_from_config,
    settings_from_config,
)

__all__ = ["PROVIDERS", "LLMClient", "LLMError", "LLMNotConfigured", "LLMRateLimited", "Provider", "Settings",
           "client_from_config", "settings_from_config"]
