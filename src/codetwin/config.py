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


