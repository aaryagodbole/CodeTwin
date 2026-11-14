"""Changed lines between two versions, from `git diff -U0`."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .model import FileDiff

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def changed_lines(repo: str | Path, base: str, head: str | None = None,
                  extensions: tuple[str, ...] = (".py",)) -> dict[str, FileDiff]:
    """Files with one of `extensions` changed between `base` and `head` (the working tree if head is None)."""
    repo = Path(repo)
    rng = [base] + ([head] if head else [])
    out: dict[str, FileDiff] = {}
    for line in git(repo, "diff", "--name-status", "-M", *rng).splitlines():
        parts = line.split("\t")
        st, path = parts[0][0], parts[-1]
        if path.endswith(extensions):
            out[path] = FileDiff(status=st, old_path=parts[1] if st == "R" else path)
    if head is None:   # untracked new files in the working tree
        for path in git(repo, "ls-files", "--others", "--exclude-standard").splitlines():
            if path.endswith(extensions):
                n = len((repo / path).read_text(encoding="utf-8", errors="replace").splitlines())
                out[path] = FileDiff(status="A", old_path=path, new=list(range(1, n + 1)))
    cur = None
    for line in git(repo, "diff", "-U0", "-M", *rng, "--", *[f"*{e}" for e in extensions]).splitlines():
        if line.startswith("+++ "):
            p = line[4:]
            cur = p[2:] if p.startswith("b/") else None
            if cur and cur not in out:
                out[cur] = FileDiff(status="M", old_path=cur)
        m = HUNK.match(line)
        if m and cur:
            os_, oc = int(m.group(1)), int(m.group(2) or 1)
            ns, nc = int(m.group(3)), int(m.group(4) or 1)
            out[cur].old.extend(range(os_, os_ + oc) if oc else [os_])
            out[cur].new.extend(range(ns, ns + nc) if nc else [ns, ns + 1])
    return out
