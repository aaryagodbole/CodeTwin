"""Store cross-repository and contract analyses (migration 0004).

The analyses themselves (crossrepo/, contracts/) compute results without touching the database; when given a Store
they call these functions, which write one `impact_analysis` with everything it looked at, in one transaction.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import __version__
from .db import SELF, SYMBOL_KINDS

if TYPE_CHECKING:
    from .db import Store

KEEP = 200                      # analyses kept per kind; older ones are deleted with everything that hangs off them
WORKING_TREE = "working-tree"


def resolve_sha(path: str | Path, ref: str) -> str | None:
    """Commit sha of `ref` in the git checkout at `path`, or None (not a checkout, unknown ref)."""
    try:
        r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=path,
                           capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    sha = r.stdout.strip()
    return sha if r.returncode == 0 and sha else None


def _analysis(store: Store, kind: str, root: str | Path, base: str, summary: str) -> int:
    base_sha = resolve_sha(root, base) or base
    aid = store.con.execute("insert into impact_analysis (kind, recorded, base_revision_id, tool_version, summary) "
                            "values (?,?,?,?,?)", (kind, time.time(), store._revision(base_sha), __version__,
                                                   summary)).lastrowid
    store.con.execute("delete from impact_analysis where kind=? and id not in (select id from impact_analysis "
                      "where kind=? order by id desc limit ?)", (kind, kind, KEEP))
    return _id(aid)


def _id(rowid: int | None) -> int:
    if rowid is None:
        raise RuntimeError("row was not stored")
    return rowid


def _target(store: Store, aid: int, repo: int, path: str | Path | None, language: str | None, status: str,
            runtime: bool) -> int:
    """A repository the analysis read. Its revision is the checkout's HEAD (the working tree of this repository)."""
    if repo == SELF:
        rev: int | None = store._revision(WORKING_TREE)
    else:
        sha = resolve_sha(path, "HEAD") if path is not None and Path(path).exists() else None
        rev = store._revision(sha, repo=repo) if sha else None
    tid = store.con.execute("insert into analysis_target (analysis_id, repository_id, revision_id, language, status, "
                            "runtime_evidence) values (?,?,?,?,?,?)",
                            (aid, repo, rev, language, status, int(runtime))).lastrowid
    return _id(tid)


def _unknowns(store: Store, aid: int, items: list[tuple[int | None, str]]) -> None:
    store.con.executemany("insert into analysis_unknown values (?,?,?,?)",
                          [(aid, i, t, text) for i, (t, text) in enumerate(items)])


def _package(store: Store, name: str) -> int:
    store.con.execute("insert or ignore into package (manager, name) values ('.', ?)", (name,))
    return store.con.execute("select id from package where manager='.' and name=?", (name,)).fetchone()[0]


def _provides(store: Store, repo: int, names: list[str], source: str) -> None:
    for n in names:
        store.con.execute("insert or ignore into package_provider values (?,?,?)", (repo, _package(store, n), source))


def _test_rows(store: Store, tid: int, repo: int, tests: dict[str, Any], change_id: int | None = None) -> None:
    store.con.executemany("insert or ignore into impacted_test (target_id, test_id, change_id, evidence) values (?,?,?,?)",
                          [(tid, store._entity(t, repo=repo), change_id, e) for t, evs in sorted(tests.items())
                           for e in sorted(evs)])


# ===================================================================== cross-repository
def save_crossrepo(store: Store, cfg, base: str, out: dict, symbols: list[dict], repos: list) -> int:
    """`repos`: crossrepo.analysis.RepoImpact objects behind `out["repos"]`."""
    with store._tx():
        aid = _analysis(store, "cross-repo", cfg.root, base, out["summary"])
        for s in symbols:
            if s.get("kind") in SYMBOL_KINDS and s.get("file") and s.get("name"):
                store.con.execute("insert or ignore into analysis_changed_symbol values (?,?)",
                                  (aid, store._entity(s["file"], s["kind"], s["name"])))
        own_src = "config" if out.get("packages_source") == "config" else "detected"
        _provides(store, SELF, list(out.get("packages") or []), own_src)
        now = time.time()
        unknowns: list[tuple[int | None, str]] = []
        current = []
        for ri in repos:
            rid = store.repository(ri.name, getattr(ri, "url", None) or ri.path or None)
            current.append(rid)
            store.con.execute("insert into repository_link (consumer_id, provider_id, first_seen, last_seen) "
                              "values (?,?,?,?) on conflict (consumer_id, provider_id) do update set "
                              "last_seen=excluded.last_seen, ended=null", (rid, SELF, now, now))
            here = ri.path if ri.path and ri.status not in ("not-found", "not-synced", "invalid") else None
            tid = _target(store, aid, rid, here, ri.language, ri.status, ri.runtime)
            for c in ri.consumers:
                cid = store.con.execute("insert into consumer_file (target_id, file_id, link, is_test) values (?,?,?,?)",
                                        (tid, store._entity(c["file"], repo=rid), c["link"], int(c["is_test"]))).lastrowid
                store.con.executemany("insert into consumer_import values (?,?,?)",
                                      [(cid, i, imp) for i, imp in enumerate(c["imports"])])
                store.con.executemany("insert into consumer_symbol_use values (?,?,?)",
                                      [(cid, sym, ln) for sym, lines in sorted(ri.uses.get(c["file"], {}).items())
                                       for ln in sorted(set(lines))])
            _test_rows(store, tid, rid, ri.tests)
            unknowns += [(tid, u) for u in ri.unknowns]
        # a dependent no longer declared in [[repos]]: the link ended now (kept for history)
        store.con.execute("update repository_link set ended=? where provider_id=? and ended is null and consumer_id "
                          "not in (select value from json_each(?))", (now, SELF, json.dumps(current)))
        _unknowns(store, aid, unknowns)
    return aid


def crossrepo_history(store: Store, limit: int = 20) -> list[dict]:
    """Newest first: when, base, and per repository its revision, status and counts."""
    out = []
    for aid, rec, sha, summary in store.con.execute(
            "select a.id, a.recorded, r.sha, a.summary from impact_analysis a join revision r on r.id = a.base_revision_id "
            "where a.kind='cross-repo' order by a.id desc limit ?", (limit,)).fetchall():
        repos = [{"name": n, "revision": s, "status": st, "consumers": nc, "tests": nt} for n, s, st, nc, nt in
                 store.con.execute(
                     "select rp.name, rv.sha, t.status, (select count(*) from consumer_file c where c.target_id = t.id), "
                     "(select count(distinct test_id) from impacted_test i where i.target_id = t.id) "
                     "from analysis_target t join repository rp on rp.id = t.repository_id "
                     "left join revision rv on rv.id = t.revision_id where t.analysis_id=? order by rp.name", (aid,))]
        out.append({"id": aid, "recorded": rec, "base": sha, "summary": summary, "repos": repos})
    return out


# ===================================================================== contracts
@dataclass
class ContractDoc:
    file: str
    old_text: str
    new_text: str
    old_doc: Any
    new_doc: Any
    changes: list = field(default_factory=list)       # contracts.diff.ContractChange


@dataclass
class Scope:
    name: str                                         # "this repository" or the [[repos]] name
    path: str | None
    status: str
    language: str | None = None
    runtime: bool = False
    is_self: bool = False


def element_kind(change) -> str:
    """The kind of API element a change is about (api_element.kind)."""
    k = change.kind
    for prefix in ("path", "operation", "parameter", "response", "schema", "property"):
        if k.startswith(prefix + "-"):
            return prefix
    if change.path:                                   # type-changed / enum-value-removed of a parameter
        return "parameter"
    return "property" if ("." in change.location or "[]" in change.location) else "schema"


def _format(doc: Any) -> tuple[str, str | None, str | None]:
    if isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc or "paths" in doc):
        info = doc.get("info")
        info = info if isinstance(info, dict) else {}
        return "openapi", str(doc.get("openapi") or doc.get("swagger") or "") or None, info.get("title")
    return "json-schema", None, doc.get("title") if isinstance(doc, dict) else None


def _version(store: Store, api_id: int, text: str, spec: str | None) -> int:
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    store.con.execute("insert or ignore into contract_version (api_id, content_sha, spec_version, content, recorded) "
                      "values (?,?,?,?,?)", (api_id, sha, spec, text, time.time()))
    return store.con.execute("select id from contract_version where api_id=? and content_sha=?", (api_id, sha)).fetchone()[0]


def _publish(store: Store, rev: int, api_id: int, version_id: int) -> None:
    store.con.execute("insert or replace into contract_publication values (?,?,?,?)", (rev, api_id, version_id, time.time()))


def _diff(store: Store, api_id: int, old_v: int, new_v: int, changes: list) -> tuple[int, list[int]]:
    """Diff row of two contents (reused when this differ version already stored it) and the change ids, in order."""
    row = store.con.execute("select id from contract_diff where old_version_id=? and new_version_id=? and tool_version=?",
                            (old_v, new_v, __version__)).fetchone()
    if row:
        old = [r[0] for r in store.con.execute("select id from contract_change where diff_id=? order by ordinal", (row[0],))]
        if len(old) == len(changes):
            return row[0], old
        store.con.execute("delete from contract_diff where id=?", (row[0],))     # differ output changed: recompute
    did = store.con.execute("insert into contract_diff (old_version_id, new_version_id, tool_version, recorded) "
                            "values (?,?,?,?)", (old_v, new_v, __version__, time.time())).lastrowid
    ids: list[int | None] = []
    for i, c in enumerate(changes):
        store.con.execute("insert or ignore into api_element (api_id, kind, location) values (?,?,?)",
                          (api_id, element_kind(c), c.location))
        el = store.con.execute("select id from api_element where api_id=? and location=?", (api_id, c.location)).fetchone()[0]
        ids.append(store.con.execute(
            "insert into contract_change (diff_id, ordinal, element_id, check_id, level, detail, api_path, field) "
            "values (?,?,?,?,?,?,?,?)", (did, i, el, c.kind, "error" if c.breaking else "info", c.detail, c.path,
                                         c.field)).lastrowid)
    return _id(did), [_id(i) for i in ids]


def save_contracts(store: Store, cfg, base: str, out: dict, docs: list[ContractDoc], scopes: list[Scope],
                   sites: list[tuple[str, Any, str, int, str]], tests: list[tuple[str, Any, str, list[str]]]) -> int:
    """`sites`: (scope name, change, file, line, how); `tests`: (scope name, change, test file, evidence)."""
    with store._tx():
        aid = _analysis(store, "contracts", cfg.root, base, out["summary"])
        base_rev = store._revision(resolve_sha(cfg.root, base) or base)
        wt_rev = store._revision(WORKING_TREE)
        change_ids: dict[int, int] = {}               # id(ContractChange) -> contract_change.id
        for d in docs:
            fmt, spec, title = _format(d.new_doc or d.old_doc)          # a deleted file keeps its format
            fid = store._entity(d.file)
            store.con.execute("insert into api (repository_id, file_id, format, title) values (?,?,?,?) "
                              "on conflict (file_id) do update set format=excluded.format, title=excluded.title",
                              (SELF, fid, fmt, title))
            api_id = store.con.execute("select id from api where file_id=?", (fid,)).fetchone()[0]
            old_v = _version(store, api_id, d.old_text, _format(d.old_doc)[1])
            new_v = _version(store, api_id, d.new_text, spec if d.new_doc else None)
            _publish(store, base_rev, api_id, old_v)
            _publish(store, wt_rev, api_id, new_v)
            if old_v == new_v:
                continue
            did, ids = _diff(store, api_id, old_v, new_v, d.changes)
            store.con.execute("insert or ignore into analysis_diff values (?,?)", (aid, did))
            change_ids.update({id(c): i for c, i in zip(d.changes, ids, strict=True)})
        targets: dict[str, tuple[int, int]] = {}
        for s in scopes:
            repo = SELF if s.is_self else store.repository(s.name, s.path)
            targets[s.name] = (_target(store, aid, repo, s.path, s.language, s.status, s.runtime), repo)
        for name, change, file, line, how in sites:
            tid, repo = targets[name]
            store.con.execute("insert or ignore into contract_site (target_id, change_id, file_id, line, how) "
                              "values (?,?,?,?,?)", (tid, change_ids[id(change)], store._entity(file, repo=repo), line, how))
        for name, change, test, evs in tests:
            tid, repo = targets[name]
            _test_rows(store, tid, repo, {test: evs}, change_ids[id(change)])
        _unknowns(store, aid, [(None, u) for u in out.get("unknowns", [])])
    return aid


def breaking_matrix(store: Store, analysis_id: int) -> list[dict]:
    keys = ["change_id", "location", "check_id", "repository", "state", "sites", "tests"]
    return [dict(zip(keys, r, strict=True)) for r in store.con.execute(
        "select change_id, location, check_id, repository, state, sites, tests from breaking_matrix "
        "where analysis_id=? order by change_id, repository", (analysis_id,))]


def api_history(store: Store, file: str) -> list[dict]:
    return [{"sha": s, "content_sha": c, "spec_version": v, "recorded": t} for s, c, v, t in store.con.execute(
        "select sha, content_sha, spec_version, recorded from api_history where file=? order by recorded", (file,))]
