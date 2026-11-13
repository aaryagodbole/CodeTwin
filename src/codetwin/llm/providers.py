"""Provider table and a small client for OpenAI-compatible chat completions (Groq, Gemini)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str              # OpenAI-compatible base, without the trailing /chat/completions
    key_env: str               # environment variable holding the API key
    default_model: str
    docs: str


PROVIDERS: dict[str, Provider] = {
    "groq": Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-120b",
                     "https://console.groq.com/keys"),
    "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
                       "gemini-3.8-flash", "https://aistudio.google.com/apikey"),
}


class LLMError(RuntimeError):
    """The provider returned an error."""


class LLMNotConfigured(LLMError):
    """No provider has an API key; LLM features are switched off, everything else works."""


class LLMRateLimited(LLMError):
    """The provider's free-tier limit was reached (HTTP 429)."""


@dataclass
class Settings:
    provider: str = "groq"
    fallback: str = "gemini"
    model: str | None = None              # override for the main provider
    timeout: float = 60.0

    def chain(self) -> list[tuple[Provider, str]]:
        """Providers to try in order, with the model for each."""
        out = [(PROVIDERS[self.provider], self.model or PROVIDERS[self.provider].default_model)]
        if self.fallback and self.fallback != self.provider:
            out.append((PROVIDERS[self.fallback], PROVIDERS[self.fallback].default_model))
        return out


def settings_from_config(cfg) -> Settings:
    sec = cfg.section("llm")
    sec = sec if isinstance(sec, dict) else {}
    s = Settings(provider=str(sec.get("provider", "groq")).lower(),
                 fallback=str(sec.get("fallback", "gemini")).lower(),
                 model=sec.get("model") or None, timeout=float(sec.get("timeout", 60)))
    for name in (s.provider, s.fallback):
        if name and name not in PROVIDERS:
            raise ValueError(f"[llm] unknown provider {name!r}; choose one of {', '.join(PROVIDERS)}")
    return s


@dataclass
class LLMClient:
    settings: Settings
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    transport: httpx.BaseTransport | None = None     # tests inject a mock transport

    def available(self) -> list[tuple[Provider, str]]:
        return [(p, m) for p, m in self.settings.chain() if self.env.get(p.key_env)]

    def status(self) -> dict[str, Any]:
        return {"providers": [{"name": p.name, "model": m, "key_env": p.key_env,
                               "has_key": bool(self.env.get(p.key_env)), "get_key": p.docs}
                              for p, m in self.settings.chain()],
                "enabled": bool(self.available())}

    def chat(self, messages: list[dict], tools: list[dict] | None = None, **extra: Any) -> dict[str, Any]:
        """One chat completion. Tries the provider, then the fallback on a missing key or rate limit.
        Returns the OpenAI-format response plus ``codetwin_provider`` and ``codetwin_model``."""
        chain = self.available()
        if not chain:
            names = " or ".join(p.key_env for p, _ in self.settings.chain())
            raise LLMNotConfigured(f"no LLM API key set; export {names} to enable explanations")
        last: LLMError | None = None
        for provider, model in chain:
            body: dict[str, Any] = {"model": model, "messages": messages, **extra}
            if tools:
                body["tools"] = tools
            try:
                with httpx.Client(timeout=self.settings.timeout, transport=self.transport) as http:
                    r = http.post(f"{provider.base_url}/chat/completions", json=body,
                                  headers={"Authorization": f"Bearer {self.env[provider.key_env]}"})
            except httpx.HTTPError as e:
                last = LLMError(f"{provider.name}: {e}")
                continue
            if r.status_code == 429:
                last = LLMRateLimited(f"{provider.name}: free-tier rate limit reached; try again shortly")
                continue
            if r.status_code >= 400:
                raise LLMError(f"{provider.name} returned {r.status_code}: {r.text[:300]}")
            data = r.json()
            data["codetwin_provider"], data["codetwin_model"] = provider.name, model
            return data
        raise last or LLMError("no provider answered")


def client_from_config(cfg) -> LLMClient:
    return LLMClient(settings_from_config(cfg))
