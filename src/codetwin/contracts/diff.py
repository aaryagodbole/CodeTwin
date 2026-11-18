"""Breaking-change diff of OpenAPI (2/3) and JSON-schema documents."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..lang.base import glob_match, repo_files

PATTERNS = ["openapi*.json", "openapi*.yaml", "openapi*.yml", "swagger*.json", "swagger*.yaml", "swagger*.yml",
            "*.openapi.json", "*.openapi.yaml", "*.openapi.yml", "*.schema.json", "**/schemas/*.json"]
METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")


@dataclass
class ContractChange:
    file: str
    kind: str              # path-removed, operation-removed, parameter-removed, parameter-required, type-changed, ...
    location: str          # "GET /users/{id}", "User.email", "GET /users/{id} param id"
    detail: str
    breaking: bool
    path: str | None = None        # the API path, for linking path literals
    field: str | None = None       # the field or parameter name, for linking uses

    def to_dict(self) -> dict:
        return {"file": self.file, "kind": self.kind, "location": self.location, "detail": self.detail,
                "breaking": self.breaking}


def load(text: str, name: str):
    if name.endswith((".yaml", ".yml")):
        import yaml
        return yaml.safe_load(text)
    return json.loads(text)


def find_contract_files(root: Path, configured: list[str] | None = None) -> list[str]:
    if configured:
        return sorted(f for f in configured if (root / f).exists())
    files = repo_files(root, (".json", ".yaml", ".yml"))
    return sorted(f for f in files if glob_match(f, PATTERNS) and not f.startswith(("node_modules/", ".")))


def contract_files_at(root: Path, sha: str, configured: list[str] | None = None) -> list[str]:
    """Contract files in the tree of commit `sha` (configured paths, or the patterns)."""
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha], cwd=root, capture_output=True, text=True,
                       check=False)
    tree = r.stdout.splitlines() if r.returncode == 0 else []
    if configured:
        return sorted(f for f in configured if f in set(tree))
    return sorted(f for f in tree if glob_match(f, PATTERNS) and not f.startswith(("node_modules/", ".")))


def renames(root: Path, sha: str, paths: list[str]) -> dict[str, str]:
    """Old path -> new path for files git sees as renamed between `sha` and the working tree."""
    r = subprocess.run(["git", "diff", "-M", "--name-status", sha, "--", *paths], cwd=root, capture_output=True,
                       text=True, check=False) if paths else None
    out = {}
    for line in (r.stdout.splitlines() if r is not None and r.returncode == 0 else []):
        parts = line.split("\t")
        if parts[0].startswith("R") and len(parts) == 3:
            out[parts[1]] = parts[2]
    return out


def at_commit(root: Path, sha: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=root, capture_output=True, text=True, check=False)
    return r.stdout if r.returncode == 0 else None


# ------------------------------------------------------------------ schema helpers
def _resolve(doc: dict, node, depth: int = 0):
    """Follow a local $ref ("#/components/schemas/User")."""
    while isinstance(node, dict) and "$ref" in node and isinstance(node["$ref"], str) and node["$ref"].startswith("#/") \
            and depth < 20:
        cur = doc
        for part in node["$ref"][2:].split("/"):
            cur = cur.get(part.replace("~1", "/").replace("~0", "~"), {}) if isinstance(cur, dict) else {}
        node, depth = cur, depth + 1
    return node


def _type(s) -> str | None:
    if not isinstance(s, dict):
        return None
    t = s.get("type")
    if isinstance(t, list):
        t = "|".join(sorted(map(str, t)))
    return f"{t}:{s['format']}" if t and s.get("format") else t


def diff_schema(old, new, where: str, file: str, old_doc: dict, new_doc: dict, out: list[ContractChange],
                seen: set | None = None) -> None:
    seen = seen if seen is not None else set()
    key = (where, id(old), id(new))
    if key in seen or len(seen) > 5000:
        return
    seen.add(key)
    old, new = _resolve(old_doc, old), _resolve(new_doc, new)
    if not isinstance(old, dict) or not isinstance(new, dict):
        return
    field = where.rsplit(".", 1)[-1]
    to, tn = _type(old), _type(new)
    if to and tn and to != tn:
        out.append(ContractChange(file, "type-changed", where, f"type {to} -> {tn}", True, field=field))
    eo, en = old.get("enum"), new.get("enum")
    if isinstance(eo, list) and isinstance(en, list):
        gone = [v for v in eo if v not in en]
        if gone:
            out.append(ContractChange(file, "enum-value-removed", where, f"removed {gone}", True, field=field))
    po, pn = old.get("properties") or {}, new.get("properties") or {}
    ro, rn = set(old.get("required") or []), set(new.get("required") or [])
    for name in sorted(po):
        loc = f"{where}.{name}"
        if name not in pn:
            out.append(ContractChange(file, "property-removed", loc, f"property {name} removed", True, field=name))
        else:
            diff_schema(po[name], pn[name], loc, file, old_doc, new_doc, out, seen)
    for name in sorted(rn - ro):
        out.append(ContractChange(file, "property-required", f"{where}.{name}", f"{name} became required", True,
                                  field=name))
    for name in sorted(set(pn) - set(po)):
        out.append(ContractChange(file, "property-added", f"{where}.{name}", f"property {name} added", False, field=name))
    for k in ("items", "additionalProperties"):
        if isinstance(old.get(k), dict) and isinstance(new.get(k), dict):
            diff_schema(old[k], new[k], f"{where}[]" if k == "items" else where, file, old_doc, new_doc, out, seen)
    for k in ("allOf", "oneOf", "anyOf"):
        a, b = old.get(k), new.get(k)
        if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for x, y in zip(a, b, strict=True):
                diff_schema(x, y, where, file, old_doc, new_doc, out, seen)


def _params(doc: dict, op: dict, path_item: dict) -> dict[tuple[str, str], dict]:
    out = {}
    for p in list(path_item.get("parameters") or []) + list(op.get("parameters") or []):
        p = _resolve(doc, p)
        if isinstance(p, dict) and p.get("name"):
            out[(p.get("in", "query"), p["name"])] = p
    return out


def _body_param(params: dict[tuple[str, str], dict]) -> dict | None:
    return next((p for (where, _name), p in sorted(params.items()) if where == "body"), None)


def _json_body(doc: dict, node) -> dict | None:
    node = _resolve(doc, node)
    if not isinstance(node, dict):
        return None
    content = node.get("content") or {}
    for mt in ("application/json", *content):
        if mt in content and isinstance(content[mt], dict):
            return content[mt].get("schema")
    return node.get("schema")                    # OpenAPI 2 response / body parameter


def _code(responses: dict, code: str):
    """Response by status code; YAML reads 200 as an integer key."""
    if code in responses:
        return responses[code]
    return responses.get(int(code)) if code.isdigit() else None


def diff_openapi(old: dict, new: dict, file: str) -> list[ContractChange]:
    out: list[ContractChange] = []
    po, pn = old.get("paths") or {}, new.get("paths") or {}
    for path in sorted(po):
        if path not in pn:
            out.append(ContractChange(file, "path-removed", path, "path removed", True, path=path))
            continue
        io, inn = po[path] or {}, pn[path] or {}
        for m in METHODS:
            if m not in io:
                continue
            loc = f"{m.upper()} {path}"
            if m not in inn:
                out.append(ContractChange(file, "operation-removed", loc, "operation removed", True, path=path))
                continue
            oo, on = io[m] or {}, inn[m] or {}
            pa, pb = _params(old, oo, io), _params(new, on, inn)
            for (where, name), p in sorted(pa.items()):
                q = pb.get((where, name))
                if q is None:
                    out.append(ContractChange(file, "parameter-removed", f"{loc} {where} {name}",
                                              f"{where} parameter {name} removed", True, path=path, field=name))
                    continue
                ta, tb = _type(p.get("schema", p)), _type(q.get("schema", q))
                if ta and tb and ta != tb:
                    out.append(ContractChange(file, "type-changed", f"{loc} {where} {name}", f"type {ta} -> {tb}",
                                              True, path=path, field=name))
            for (where, name), q in sorted(pb.items()):
                if q.get("required") and not (pa.get((where, name)) or {}).get("required"):
                    out.append(ContractChange(file, "parameter-required", f"{loc} {where} {name}",
                                              f"{where} parameter {name} is now required", True, path=path, field=name))
            # OpenAPI 3 requestBody, or the OpenAPI 2 `in: body` parameter
            bo = _json_body(old, oo.get("requestBody") or _body_param(pa))
            bn = _json_body(new, on.get("requestBody") or _body_param(pb))
            if bo is not None and bn is not None:
                diff_schema(bo, bn, f"{loc} request", file, old, new, out)
            ro, rn = oo.get("responses") or {}, on.get("responses") or {}
            for code in sorted(map(str, ro)):
                if code not in map(str, rn):
                    out.append(ContractChange(file, "response-removed", f"{loc} {code}", f"response {code} removed",
                                              True, path=path))
                else:
                    a, b = _json_body(old, _code(ro, code)), _json_body(new, _code(rn, code))
                    if a is not None and b is not None:
                        diff_schema(a, b, f"{loc} {code}", file, old, new, out)
        for m in METHODS:
            if m in inn and m not in io:
                out.append(ContractChange(file, "operation-added", f"{m.upper()} {path}", "operation added", False,
                                          path=path))
    for path in sorted(set(pn) - set(po)):
        out.append(ContractChange(file, "path-added", path, "path added", False, path=path))
    so = (old.get("components") or {}).get("schemas") or old.get("definitions") or {}
    sn = (new.get("components") or {}).get("schemas") or new.get("definitions") or {}
    for name in sorted(so):
        if name not in sn:
            out.append(ContractChange(file, "schema-removed", name, f"schema {name} removed", True, field=name))
        else:
            diff_schema(so[name], sn[name], name, file, old, new, out)
    # a schema reached through several operations is reported once per location; keep the first of each
    uniq: dict[tuple, ContractChange] = {}
    for c in out:
        uniq.setdefault((c.kind, c.location), c)
    return list(uniq.values())


def diff_documents(old, new, file: str) -> list[ContractChange]:
    if not isinstance(old, dict) or not isinstance(new, dict):
        return []
    if "openapi" in old or "swagger" in old or "paths" in old:
        return diff_openapi(old, new, file)
    out: list[ContractChange] = []
    title = str(new.get("title") or old.get("title") or Path(file).stem.split(".")[0])
    diff_schema(old, new, title, file, old, new, out)
    for key in ("$defs", "definitions"):
        do, dn = old.get(key) or {}, new.get(key) or {}
        for name in sorted(do):
            if name not in dn:
                out.append(ContractChange(file, "schema-removed", name, f"definition {name} removed", True, field=name))
            else:
                diff_schema(do[name], dn[name], name, file, old, new, out)
    return out
