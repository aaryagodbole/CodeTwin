"""Link contract changes to code that may rely on them, in this repository and in connected ones."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import lang as langmod
from ..crossrepo.analysis import _dependent_config, _recorded_run, declared
from ..graph.impact import build_graph, impact_of
from .diff import ContractChange, at_commit, contract_files_at, diff_documents, find_contract_files, load, renames

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
    end = r"(?![\w./-])"                 # "/health" is not "/health/status" nor "/health.json"; "?q=" may follow
    literal_prefix = parts[0].rstrip("/")
    if len(parts) > 1 and literal_prefix.count("/") >= 1 and len(literal_prefix) > 1:
        # a path built by concatenation: the literal part before the first parameter, then the literal that
        # follows it ("/users/" + id + "/orders"); with nothing after the parameter, the prefix alone
        q = r"['\"`]"
        nxt = parts[2] if len(parts) > 2 else ""
        concat = (rf"{re.escape(parts[0])}{q}\s*\+[^+\n]*\+\s*{q}{re.escape(nxt)}" if nxt
                  else rf"{re.escape(parts[0])}{q}\s*\+")
        return re.compile(rf"(?:{rx}{end}|{concat}{end if nxt else ''})")
    return re.compile(rf"{rx}{end}")


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


def removed_contract(old_doc, file: str) -> list[ContractChange]:
    """A contract file deleted since the base: its whole API or schema is removed."""
    if not isinstance(old_doc, dict):
        return []
    if "openapi" in old_doc or "swagger" in old_doc or "paths" in old_doc:
        return diff_documents(old_doc, {"openapi": old_doc.get("openapi", "3"), "paths": {}}, file)
    title = str(old_doc.get("title") or Path(file).stem.split(".")[0])
    return [ContractChange(file, "schema-removed", title, f"contract file {file} deleted", True, field=title)]


def for_change(cfg, lang_adapter, base: str) -> dict:
    """Breaking changes of every contract file between `base` and the working tree, with their consumers."""
    sec = cfg.section("contracts")
    configured = list(sec.get("files", [])) if isinstance(sec, dict) else []
    root = Path(cfg.root)
    now = find_contract_files(root, configured)
    before = contract_files_at(root, base, configured)
    gone = [f for f in before if not (root / f).exists()]
    added = [f for f in now if f not in before]
    moved = renames(root, base, gone + added) if gone else {}
    for g in gone:                                     # moved without git knowing (untracked): same content
        if g not in moved:
            old = at_commit(root, base, g)
            same = [a for a in added if a not in moved.values() and (root / a).read_text(encoding="utf-8",
                                                                                        errors="replace") == old]
            if old is not None and same:
                moved[g] = same[0]
    files = sorted(set(now) | set(gone))
    changes: list[ContractChange] = []
    errors: list[str] = []
    for f in files:
        if f in moved.values():
            continue                                   # compared under its old name below
        old_text = at_commit(root, base, f)
        if old_text is None:
            continue                                   # new contract file: nothing can break yet
        try:
            new_path = moved.get(f, f)
            old_doc = load(old_text, f)
            if (root / new_path).exists():
                new_doc = load((root / new_path).read_text(encoding="utf-8"), new_path)
                changes += diff_documents(old_doc, new_doc, new_path)
            else:                                      # deleted: everything it described is gone
                changes += removed_contract(old_doc, f)
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
                for u in reach.unknowns:
                    msg = f"{name}: {u}"
                    if msg not in unknowns:
                        unknowns.append(msg)
        if not consumers:
            unknowns.append(f"{c.location}: no code found that uses it (it may be built dynamically or used "
                                   "by clients outside the connected repositories)")
        found.append(entry)
    n_cons = sum(len(b["consumers"]) for b in found)
    out["summary"] = (f"{len(breaking)} breaking contract changes, {n_cons} code sites, "
                      f"{len({t for b in found for t in b['tests']})} tests")
    return out
