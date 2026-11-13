"""`codetwin llm [--test]`: show the LLM settings and whether the API keys are set; optionally send a test request."""
from __future__ import annotations

from .. import config
from ._util import print_json

NAME, HELP, ORDER = "llm", "LLM settings for explanations (Groq, Gemini) and a connection test", 80


def add_arguments(p) -> None:
    p.add_argument("--test", action="store_true", help="send one short request to check the key and model")
    p.add_argument("--json", action="store_true")


def run(args) -> int:
    try:
        from ..llm import LLMError, client_from_config
    except ImportError:
        print('LLM features need httpx: pip install "codetwin[llm]"')
        return 2
    client = client_from_config(config.load(args.root))
    status = client.status()
    if args.test:
        try:
            r = client.chat([{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=20)
            status["test"] = {"ok": True, "provider": r["codetwin_provider"], "model": r["codetwin_model"]}
        except LLMError as e:
            status["test"] = {"ok": False, "error": str(e)}
    if args.json:
        print_json(status)
        return 0 if status.get("test", {}).get("ok", True) else 1
    for i, p in enumerate(status["providers"]):
        role = "provider" if i == 0 else "fallback"
        key = "key set" if p["has_key"] else f"no key: export {p['key_env']}=...  (get one at {p['get_key']})"
        print(f"{role:9} {p['name']:7} model {p['model']:24} {key}")
    print("LLM explanations:", "on" if status["enabled"] else "off (the rest of CodeTwin works without them)")
    if "test" in status:
        t = status["test"]
        print("test:", f"ok ({t['provider']}, {t['model']})" if t["ok"] else f"failed: {t['error']}")
        return 0 if t["ok"] else 1
    return 0
