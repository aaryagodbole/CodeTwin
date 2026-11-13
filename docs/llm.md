# LLM settings (Groq, Gemini)

CodeTwin can use an LLM to **explain** its evidence in plain language (dashboard chat, editor). The LLM
never decides proceed/abstain, never changes the risk number, and its text is never stored as evidence;
those come from the calibrated engine only.

Both supported providers have free tiers and use the OpenAI-compatible chat API.

| Provider | Default model | Key variable | Get a key |
|---|---|---|---|
| `groq` (default) | `openai/gpt-oss-120b` | `GROQ_API_KEY` | https://console.groq.com/keys |
| `gemini` (fallback) | `gemini-3.8-flash` | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |

## Setup

```bash
export GROQ_API_KEY=...        # and/or
export GEMINI_API_KEY=...
codetwin llm --test            # shows the settings and sends one short request
```

Keys are read from the environment only; never put them in `.codetwin.toml` or commit them
(`.env` files are gitignored; `.env.example` lists the variables). Without any key, LLM features are off and
everything else works.

## Settings (`.codetwin.toml`)

```toml
[llm]
provider = "groq"                # groq | gemini
fallback = "gemini"              # tried when the provider has no key or hits its free-tier limit; "" for none
# model = "openai/gpt-oss-120b"  # override the provider's default model
# timeout = 60                   # seconds
```

## Free tiers and privacy

- Free-tier limits are set per account or project by the provider and change over time; check the provider's
  console. When a limit is hit (HTTP 429), CodeTwin tries the fallback provider, then reports the limit.
- What is sent: the question and the evidence the tools return (file paths, test names, line numbers, short
  code context). Groq states it does not train on API data; Gemini's free tier may use content to improve
  Google's products. For code you are not allowed to share, leave the keys unset.
