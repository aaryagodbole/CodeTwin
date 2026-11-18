import json

import pytest

pytest.importorskip("httpx")  # an optional extra ([server] or [llm]): skip without it

import httpx

from codetwin import config
from codetwin.cli import main
from codetwin.llm import LLMClient, LLMNotConfigured, LLMRateLimited, Settings, settings_from_config


def _ok(model):
    return {"choices": [{"message": {"role": "assistant", "content": "ok"}}], "model": model}


def test_defaults_and_config(toy_repo):
    main(["-C", str(toy_repo), "init"])
    s = settings_from_config(config.load(toy_repo))          # the template has an [llm] section
    assert (s.provider, s.fallback) == ("groq", "gemini")
    chain = [(p.name, m) for p, m in s.chain()]
    assert chain == [("groq", "openai/gpt-oss-120b"), ("gemini", "gemini-3.8-flash")]
    path = toy_repo / ".codetwin.toml"
    path.write_text(path.read_text().replace('provider = "groq"', 'provider = "openai"'))
    with pytest.raises(ValueError, match="unknown provider"):
        settings_from_config(config.load(toy_repo))


def test_no_key_means_switched_off():
    c = LLMClient(Settings(), env={})
    assert c.status()["enabled"] is False
    with pytest.raises(LLMNotConfigured, match="GROQ_API_KEY or GEMINI_API_KEY"):
        c.chat([{"role": "user", "content": "hi"}])


def test_request_shape_and_fallback_on_rate_limit():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append((req.url.host, req.headers["authorization"], body["model"], "tools" in body))
        if req.url.host == "api.groq.com":
            return httpx.Response(429, json={"error": "rate limit"})
        return httpx.Response(200, json=_ok(body["model"]))

    c = LLMClient(Settings(), env={"GROQ_API_KEY": "g", "GEMINI_API_KEY": "m"},
                  transport=httpx.MockTransport(handler))
    tools = [{"type": "function", "function": {"name": "get_graph", "parameters": {"type": "object"}}}]
    r = c.chat([{"role": "user", "content": "hi"}], tools=tools)
    assert r["codetwin_provider"] == "gemini" and r["codetwin_model"] == "gemini-3.8-flash"
    assert seen == [("api.groq.com", "Bearer g", "openai/gpt-oss-120b", True),
                    ("generativelanguage.googleapis.com", "Bearer m", "gemini-3.8-flash", True)]


def test_only_fallback_key_and_rate_limit_everywhere():
    c = LLMClient(Settings(), env={"GEMINI_API_KEY": "m"},
                  transport=httpx.MockTransport(lambda req: httpx.Response(429)))
    assert [p.name for p, _ in c.available()] == ["gemini"]
    with pytest.raises(LLMRateLimited):
        c.chat([{"role": "user", "content": "hi"}])


def test_cli_status(toy_repo, capsys, monkeypatch):
    main(["-C", str(toy_repo), "init"])
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "llm", "--json"]) == 0
    st = json.loads(capsys.readouterr().out)
    assert st["enabled"] and [p["has_key"] for p in st["providers"]] == [False, True]
