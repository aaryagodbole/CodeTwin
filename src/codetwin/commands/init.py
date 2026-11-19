from __future__ import annotations

from pathlib import Path

from ..config import CONFIG_FILE, Config
from ..config_templates import MULTI_HEAD, SELECTION, toml_list

NAME, HELP, ORDER = "init", "write .codetwin.toml with guessed settings", 10


def add_arguments(p) -> None:
    p.add_argument("--language", help="python, javascript, go, java, ... or a comma-separated list (default: detected)")


def write_config(root: str | Path = ".", language: str | None = None) -> Path:
    """Write `.codetwin.toml` for the detected (or named) languages; each language's adapter writes its part."""
    from .. import lang
    root = Path(root).resolve()
    if language:
        names = [lang.ALIASES.get(x.strip().lower(), x.strip().lower()) for x in language.split(",") if x.strip()]
    else:
        names = lang.detect_all(root)
    adapters = [lang.adapter(Config(root=root, language=n), n) for n in names]
    if len(adapters) > 1:
        text = MULTI_HEAD.format(languages=toml_list(names)) + "\n".join(a.config_table() for a in adapters) \
            + "\n" + SELECTION
    else:
        text = adapters[0].config_file()
    path = root / CONFIG_FILE
    path.write_text(text)
    return path


def run(args) -> int:
    path = write_config(args.root, getattr(args, "language", None))
    print(f"wrote {path}; review it, then run `codetwin record`")
    return 0
