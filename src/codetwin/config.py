"""Project configuration, read from .codetwin.toml in the repository root."""
from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = ".codetwin.toml"
STATE_DIR = ".codetwin"

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


@dataclass
class Config:
    root: Path
    language: str = "auto"
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
    return Config(root=root, language=str(p.get("language", "auto")), src_root=p.get("src_root", "."), packages=list(p.get("packages", [])),
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


MULTI_HEAD = """# CodeTwin AI configuration
[project]
languages = {languages}          # every language of this repository; each has its own table below

"""


def _lang_table(root: Path, name: str) -> str:
    from . import lang
    if name == "python":
        g = guess(root)
        return (f'[lang.python]\nsrc_root = "{g["src_root"]}"\npackages = {_toml_list(g["packages"])}\n'
                f'source_dirs = {_toml_list(g["source_dirs"] or ["."])}\ntests_dir = "{g["tests_dir"]}"\n')
    a = lang.adapter(Config(root=root, language=name), name)
    g = a.guess_config()
    runner = g.get("runner")
    if not runner:
        # monorepo or mixed repository: the build file (package.json, Cargo.toml, go.mod, ...) is in a sub-folder,
        # and each test runs from its own project folder
        from .lang.generic import Generic
        per: dict[str, str] = {}
        if isinstance(a, Generic):
            for t in a.list_tests():
                r = a.runner_for(t, is_dir=False)
                if r is not None:
                    per.setdefault(a.project_dir(t) or ".", r.name)
        runner = ("per project folder: " + ", ".join(f"{d}/ ({n})" for d, n in sorted(per.items())[:6])
                  + (" and others" if len(per) > 6 else "")) if per else \
            "none found: static evidence only until you set test_command"
    return (f"[lang.{name}]\nsource_dirs = {_toml_list(g['source_dirs'])}\ntests_dir = \"{g['tests_dir']}\"\n"
            f"# test runner: {runner}; override with a [lang.{name}.runner] table (docs/languages.md)\n")


def write_template(root: str | Path = ".", language: str | None = None) -> Path:
    from . import lang
    root = Path(root).resolve()
    if language:
        names = [lang.ALIASES.get(x.strip().lower(), x.strip().lower()) for x in language.split(",") if x.strip()]
    else:
        names = lang.detect_all(root)
    name = names[0]
    if len(names) > 1:
        text = MULTI_HEAD.format(languages=_toml_list(names)) + "\n".join(_lang_table(root, n) for n in names) \
            + "\n" + SELECTION
    elif name == "python":
        g = guess(root)
        text = TEMPLATE.format(src_root=g["src_root"], packages=_toml_list(g["packages"]),
                               source_dirs=_toml_list(g["source_dirs"]), tests_dir=g["tests_dir"])
    else:
        g = lang.adapter(Config(root=root, language=name), name).guess_config()
        text = GENERIC_TEMPLATE.format(language=name, source_dirs=_toml_list(g["source_dirs"]),
                                       tests_dir=g["tests_dir"],
                                       runner=g.get("runner") or "none found (static evidence only until you set test_command)")
    path = root / CONFIG_FILE
    path.write_text(text)
    return path


def _toml_list(xs: list[str]) -> str:
    return "[" + ", ".join(f'"{x}"' for x in xs) + "]"
