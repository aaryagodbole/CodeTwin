"""Where connected repositories are: a local folder (`path`) or a git URL (`url`), any number of each.

    [[repos]]
    name = "web"
    url = "https://github.com/acme/web.git"   # cloned into .codetwin/repos/web by `codetwin crossrepo --sync`
    # ref = "main"                            # optional: branch or tag (default: the remote's default branch)

    [[repos]]
    name = "mobile"
    url = "git@github.com:acme/mobile.git"

    [[repos]]
    name = "admin"
    path = "../admin"                         # a checkout next to this one

Analysis never touches the network: a URL entry is read from its local copy, and a missing copy is an unknown that
says to run `codetwin crossrepo --sync`. Only `--sync` clones or updates (shallow, one commit), so `select`, the
review and the MCP tools stay fast and work offline.

Safety: only https, ssh (`ssh://` or `user@host:path`) and `file://` URLs are accepted; git's `ext::` transport is
disabled; arguments are separated from URLs with `--`. Credentials are never read from `.codetwin.toml`: an https
URL with any user name (a token is often given as one) and an ssh URL with a password are refused; private
repositories use git's own credential setup (a credential helper, an SSH key, or the Action's token). The Action
does not sync for pull requests from forks, whose `.codetwin.toml` could name any URL.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_SCP = re.compile(r"^[\w.-]+@[\w.-]+:[\w./~-]+$")                 # git@github.com:acme/web.git
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_GIT = ["git", "-c", "protocol.ext.allow=never", "-c", "core.hooksPath=/dev/null", "-c", "advice.detachedHead=false"]


@dataclass
class Source:
    """One `[[repos]]` entry, resolved to where its files are (or why they are not available)."""
    name: str
    path: Path | None              # the folder to analyse (None when the entry is invalid)
    url: str | None = None
    ref: str | None = None
    error: str | None = None       # why this entry cannot be used; reported as an unknown
    entry: dict | None = None      # the raw table (packages and any other per-repository settings)

    @property
    def available(self) -> bool:
        return self.error is None and self.path is not None and self.path.is_dir()

    def missing(self) -> str:
        """The unknown to report when the files are not there."""
        if self.error:
            return f"repository {self.name}: {self.error}; its consumers are unknown"
        if self.url:
            return (f"repository {self.name} ({self.url}) is not synced: run `codetwin crossrepo --sync`; "
                    "its consumers are unknown")
        return f"repository {self.name} not found at {self.path}: its consumers are unknown"


def url_problem(url: str) -> str | None:
    """Why a URL is not accepted, or None."""
    if not url or url != url.strip() or url.startswith("-") or any(c in url for c in "\n\r\t "):
        return "the url is empty, starts with '-' or contains whitespace"
    userinfo = urlsplit(url).netloc.rpartition("@")[0] if url.startswith(("https://", "ssh://")) else ""
    # https carries no user at all (a token is often given as the user name); ssh may name a user, never a password.
    if (url.startswith("https://") and userinfo) or ":" in userinfo:
        return "the url contains a user name, password or token; use git's credential helper or an SSH key instead"
    if url.startswith(("https://", "ssh://", "file://")) or _SCP.match(url):
        return None
    return "only https://, ssh://, user@host:path and file:// URLs are accepted"


def _name_from_url(url: str) -> str:
    tail = re.split(r"[/:]", url.rstrip("/"))[-1]
    return tail[:-4] if tail.endswith(".git") else tail


def cache_dir(cfg: Any) -> Path:
    return Path(cfg.state_dir) / "repos"


def connected(cfg: Any) -> list[Source]:
    """Every `[[repos]]` entry, in order. Entries are never dropped: a bad one carries its error."""
    raw = cfg.raw.get("repos", [])
    entries = raw if isinstance(raw, list) else []
    out: list[Source] = []
    seen: set[str] = set()
    for i, r in enumerate(entries, 1):
        if not isinstance(r, dict):
            out.append(Source(f"repos[{i}]", None, error="each [[repos]] entry must be a table"))
            continue
        url = r.get("url")
        path = r.get("path")
        ref = r.get("ref")
        bad_url = url is not None and not isinstance(url, str)
        if bad_url:
            url = None
        default = _name_from_url(url) if url else Path(str(path or "")).name
        name = str(r.get("name") or default or f"repos[{i}]")
        src = Source(name, None, url=url, ref=str(ref) if ref else None, entry=r)
        if bad_url:
            src.error = "url must be a string"
        elif url and path:
            src.error = "give either path or url, not both"
        elif not url and not path:
            src.error = "needs a path or a url"
        elif name.lower() in seen:         # names become folder names: unique also on case-insensitive filesystems
            src.error = f"the name {name!r} is used by another [[repos]] entry; give each a unique name"
        elif url and not _NAME.match(name):
            src.error = "name must be letters, digits, '.', '_' or '-' (it names the local copy's folder)"
        elif url and (problem := url_problem(url)):
            src.error = problem
        elif ref and (not re.match(r"^[\w./-]+$", str(ref)) or str(ref).startswith("-")):
            src.error = "ref must be a branch or tag name"
        else:
            src.path = cache_dir(cfg) / name if url else (Path(cfg.root) / str(path)).resolve()
        seen.add(name.lower())
        out.append(src)
    return out


def _git(args: list[str], cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run([*_GIT, *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


def _origin(path: Path) -> str | None:
    r = _git(["remote", "get-url", "origin"], cwd=path)
    return r.stdout.strip() if r.returncode == 0 else None


def sync(cfg: Any, timeout: int = 600) -> list[dict]:
    """Clone or update every URL entry into `.codetwin/repos/<name>` (one commit deep). Path entries are left
    alone. Returns one status per entry: name, url, status (cloned | updated | local | failed | invalid), detail."""
    out: list[dict] = []
    for s in connected(cfg):
        if s.error:
            out.append({"name": s.name, "url": s.url, "status": "invalid", "detail": s.error})
            continue
        if not s.url:
            out.append({"name": s.name, "url": None, "status": "local", "detail": str(s.path)})
            continue
        if s.path is None:          # connected() sets a path for every valid entry
            out.append({"name": s.name, "url": s.url, "status": "invalid", "detail": "no folder"})
            continue
        try:
            out.append({"name": s.name, "url": s.url, **_sync_one(s.url, s.ref, s.path, timeout)})
        except subprocess.TimeoutExpired:
            out.append({"name": s.name, "url": s.url, "status": "failed", "detail": f"timed out after {timeout}s"})
    return out


def _last_line(r: subprocess.CompletedProcess, what: str) -> str:
    lines = (r.stderr or r.stdout).strip().splitlines()
    return lines[-1] if lines else f"git {what} exited {r.returncode}"


def _sync_one(url: str, ref: str | None, dest: Path, timeout: int) -> dict:
    """Update the copy in `dest`, or clone it. A failure never leaves a partial folder at `dest` (analysis would
    read it as synced) and never deletes a working copy (a network or auth error keeps the last good one)."""
    if dest.is_dir() and _origin(dest) == url:
        fetch = _git(["fetch", "--depth", "1", "origin", "--", ref or "HEAD"], cwd=dest, timeout=timeout)
        if fetch.returncode != 0:
            return {"status": "failed", "detail": f"{_last_line(fetch, 'fetch')} (kept the previous copy)"}
        reset = _git(["reset", "--hard", "FETCH_HEAD"], cwd=dest, timeout=timeout)   # our own cache folder
        if reset.returncode == 0:
            return {"status": "updated", "detail": _head(dest)}
        # an unusable copy: clone it again below and replace it only when the clone succeeded
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.partial")      # never matches a valid name (they cannot start with '.')
    if tmp.exists():
        shutil.rmtree(tmp)
    args = ["clone", "--depth", "1", "--no-tags", *(["--branch", ref] if ref else []), "--", url, str(tmp)]
    try:
        r = _git(args, timeout=timeout)
        if r.returncode != 0:
            return {"status": "failed", "detail": _last_line(r, "clone")}
        if dest.exists():
            shutil.rmtree(dest)      # only ever a folder under .codetwin/repos that CodeTwin created
        tmp.replace(dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return {"status": "cloned", "detail": _head(dest)}


def _head(path: Path) -> str:
    r = _git(["rev-parse", "--short", "HEAD"], cwd=path)
    return r.stdout.strip() if r.returncode == 0 else "?"
