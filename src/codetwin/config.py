"""Project configuration, read from .codetwin.toml in the repository root."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = ".codetwin.toml"
STATE_DIR = ".codetwin"

TEMPLATE = """# CodeTwin AI configuration
[project]
src_root = "{src_root}"          # directory added to PYTHONPATH (\".\" or \"src\")
packages = {packages}            # packages measured by coverage
source_dirs = {source_dirs}      # directories that contain source files
tests_dir = "{tests_dir}"

[selection]
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


@dataclass
class Config:
    root: Path
    src_root: str = "."
    packages: list[str] = field(default_factory=list)
    source_dirs: list[str] = field(default_factory=list)
    tests_dir: str = "tests"
    alpha: float = 0.10
    budget: float = 0.25
    aci_gamma: float = 0.02
    fallback: str = "file-coverage"
    raw: dict = field(default_factory=dict)          # the whole parsed .codetwin.toml

    def section(self, name: str) -> dict | list:
        """A feature's own table in .codetwin.toml (e.g. [crossrepo]); new features read it here
        instead of adding fields to this class."""
        v = self.raw.get(name, {})
        return v if isinstance(v, (dict, list)) else {}

    @property
    def state_dir(self) -> Path:
        return self.root / STATE_DIR

    @property
    def db_path(self) -> Path:
        return self.state_dir / "evidence.sqlite"


def load(root: str | Path = ".") -> Config:
    root = Path(root).resolve()
    path = root / CONFIG_FILE
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `codetwin init` first")
    data = tomllib.loads(path.read_text())
    p, s = data.get("project", {}), data.get("selection", {})
    return Config(root=root, src_root=p.get("src_root", "."), packages=list(p.get("packages", [])),
                  source_dirs=list(p.get("source_dirs", [])), tests_dir=p.get("tests_dir", "tests"),
                  alpha=float(s.get("alpha", 0.10)), budget=float(s.get("budget", 0.25)),
                  aci_gamma=float(s.get("aci_gamma", 0.02)), fallback=s.get("fallback", "file-coverage"), raw=data)


def guess(root: str | Path = ".") -> dict:
    """Guess src_root, packages and tests_dir for `codetwin init`."""
    root = Path(root).resolve()
    src_root = "src" if (root / "src").is_dir() else "."
    base = root / src_root if src_root != "." else root
    skip = {"tests", "test", "docs", "build", "dist", "examples", ".git", ".codetwin"}
    pkgs = sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "__init__.py").exists() and p.name not in skip)
    tests_dir = next((d for d in ("tests", "test") if (root / d).is_dir()), "tests")
    dirs = [f"{src_root}/{p}" if src_root != "." else p for p in pkgs]
    return {"src_root": src_root, "packages": pkgs, "source_dirs": dirs, "tests_dir": tests_dir}


def write_template(root: str | Path = ".") -> Path:
    root = Path(root).resolve()
    g = guess(root)
    text = TEMPLATE.format(src_root=g["src_root"], packages=_toml_list(g["packages"]),
                           source_dirs=_toml_list(g["source_dirs"]), tests_dir=g["tests_dir"])
    path = root / CONFIG_FILE
    path.write_text(text)
    return path


def _toml_list(xs: list[str]) -> str:
    return "[" + ", ".join(f'"{x}"' for x in xs) + "]"
