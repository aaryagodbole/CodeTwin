"""Text of the `.codetwin.toml` files `codetwin init` writes. Imports nothing from CodeTwin, so the configuration
module, the language adapters and the init command can all use it without an import cycle."""
from __future__ import annotations

SELECTION = """[selection]
alpha = 0.10                     # target miss rate
budget = 0.25                    # share of full-suite time in budget mode
aci_gamma = 0.02                 # step size of adaptive calibration
fallback = "file-coverage"       # broader run on abstention: file-coverage | full

[llm]
# Explanations in the dashboard and editor. The LLM never makes the proceed/abstain decision.
# API keys come from the environment (GROQ_API_KEY, GEMINI_API_KEY), never from this file.
provider = "groq"                # groq | gemini
fallback = "gemini"              # used when the provider has no key or hits its rate limit; "" for none
# model = "openai/gpt-oss-120b"  # optional: override the provider's default model
"""

GENERIC_TEMPLATE = """# CodeTwin AI configuration
[project]
language = "{language}"
source_dirs = {source_dirs}      # directories that contain source files ("." = whole repository)
tests_dir = "{tests_dir}"

[runner]
# Detected test runner: {runner}. Each test file runs on its own with coverage; override here if needed
# (placeholders: {{test}}, {{cov_dir}}; formats: lcov | gocover | jacoco | cobertura | clover). See docs/languages.md.
# test_command = ""
# coverage_format = "lcov"
# workers = 1
# timeout = 600

""" + SELECTION

TEMPLATE = """# CodeTwin AI configuration
[project]
language = "python"
src_root = "{src_root}"          # directory added to PYTHONPATH (\".\" or \"src\")
packages = {packages}            # packages measured by coverage
source_dirs = {source_dirs}      # directories that contain source files
tests_dir = "{tests_dir}"

""" + SELECTION


MULTI_HEAD = """# CodeTwin AI configuration
[project]
languages = {languages}          # every language of this repository; each has its own table below

"""


def toml_list(xs: list[str]) -> str:
    return "[" + ", ".join(f'"{x}"' for x in xs) + "]"
