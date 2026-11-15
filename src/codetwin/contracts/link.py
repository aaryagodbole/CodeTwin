"""Link contract changes to code that may rely on them, in this repository and in connected ones."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import lang as langmod
from ..crossrepo.analysis import _dependent_config, _recorded_run, declared
from ..graph.impact import build_graph, impact_of
from .diff import ContractChange, at_commit, diff_documents, find_contract_files, load

MAX_SITES = 30


def path_regex(api_path: str) -> re.Pattern:
    """`/users/{id}/orders` matches "/users/42/orders", `/users/${id}/orders` and "/users/" + id + "/orders"
    up to the first parameter (a literal prefix of at least one segment)."""
    parts = re.split(r"(\{[^}]+\})", api_path)
    rx = ""
    for p in parts:
        if p.startswith("{"):
            rx += r"[^\s/'\"`?]*"
        else:
            rx += re.escape(p)
    literal_prefix = parts[0].rstrip("/")
    if len(parts) > 1 and literal_prefix.count("/") >= 1 and len(literal_prefix) > 1:
        # a path built by concatenation: the literal part before the first parameter
        return re.compile(rf"(?:{rx}|{re.escape(parts[0])}['\"`]\s*\+)(?![\w-])")
    return re.compile(rf"{rx}(?![\w-])")


def field_regex(name: str) -> re.Pattern:
    """A field used as a key or attribute: "email", 'email', .email, email: / email= (not a substring)."""
    n = re.escape(name)
    return re.compile(rf"(['\"`]{n}['\"`]|\.{n}\b|(?<![\w$.]){n}\s*[:=](?!=))")


def _sites(root: Path, files: list[str], change: ContractChange) -> list[dict]:
    pats = []
    if change.path:
        pats.append(("path-literal", path_regex(change.path)))
    if change.field and change.kind not in ("path-removed", "operation-removed", "response-removed"):
        pats.append(("name-match", field_regex(change.field)))
    out = []
    for f in files:
        try:
            lines = (root / f).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, text in enumerate(lines, start=1):
            for how, rx in pats:
                if rx.search(text):
                    out.append({"file": f, "line": i, "how": how})
                    break
            if len(out) >= MAX_SITES:
                return out
    return out


def _scope(root: Path, adapter, contract_files: set[str]):
    facts = adapter.facts()
    files = sorted(f for f in facts if f not in contract_files)
    return facts, files, adapter.list_tests()


def for_change(cfg, lang_adapter, base: str) -> dict:
    """Breaking changes of every contract file between `base` and the working tree, with their consumers."""
    sec = cfg.section("contracts")
    configured = list(sec.get("files", [])) if isinstance(sec, dict) else []
    root = Path(cfg.root)
    files = find_contract_files(root, configured)
    changes: list[ContractChange] = []
    errors: list[str] = []
    for f in files:
        old_text = at_commit(root, base, f)
        if old_text is None:
            continue                                   # new contract file: nothing can break yet
        try:
            new_text = (root / f).read_text(encoding="utf-8")
            changes += diff_documents(load(old_text, f), load(new_text, f), f)
        except Exception as e:  # noqa: BLE001 - an unreadable contract is reported, never skipped silently
            errors.append(f"{f}: could not be read as OpenAPI/JSON schema ({type(e).__name__}: {e})")
    breaking = [c for c in changes if c.breaking]
    unknowns: list[str] = errors
    found: list[dict] = []
    out: dict[str, Any] = {"files": files, "changes": [c.to_dict() for c in changes], "breaking": found,
                           "unknowns": unknowns}
    if not breaking:
        out["summary"] = (f"{len(files)} contract files, no breaking change" if files
                          else "no OpenAPI or JSON-schema files found")
        return out

    scopes = []
    facts, src, tests = _scope(root, lang_adapter, set(files))
    run = _recorded_run(cfg)
    scopes.append(("this repository", root, facts, src, tests, run, lang_adapter.is_test))
    for r in declared(cfg):
        path = (root / str(r["path"])).resolve()
        name = str(r.get("name") or path.name)
        if not path.exists():
            unknowns.append(f"repository {name} not found at {path}: its uses of the contract are unknown")
            continue
        dcfg = _dependent_config(path)
        try:
            ad = langmod.get(dcfg)
        except Exception as e:  # noqa: BLE001
            unknowns.append(f"{name}: language not supported ({e})")
            continue
        f2, s2, t2 = _scope(path, ad, set())
        scopes.append((name, path, f2, s2, t2, _recorded_run(dcfg), ad.is_test))

    for c in breaking:
        consumers: list[dict] = []
        etests: dict[str, list[str]] = {}
        entry: dict[str, Any] = {**c.to_dict(), "consumers": consumers, "tests": etests}
        for name, path, fx, src_files, tlist, rrun, is_test in scopes:
            sites = _sites(path, src_files, c)
            for s in sites:
                consumers.append({"repo": name, **s})
            code = sorted({s["file"] for s in sites if not is_test(s["file"])})
            for s in sites:
                if is_test(s["file"]):
                    etests.setdefault(f"{name}:{s['file']}", ["direct"])
            if code:
                reach = impact_of(build_graph(fx, rrun), code, tlist)
                for t, ev in reach.tests.items():
                    etests.setdefault(f"{name}:{t}", sorted(ev))
        if not consumers:
            unknowns.append(f"{c.location}: no code found that uses it (it may be built dynamically or used "
                                   "by clients outside the connected repositories)")
        found.append(entry)
    n_cons = sum(len(b["consumers"]) for b in found)
    out["summary"] = (f"{len(breaking)} breaking contract changes, {n_cons} code sites, "
                      f"{len({t for b in found for t in b['tests']})} tests")
    return out
