"""Host-side driver: records Multi-SWE-bench pull requests of one repository as CodeTwin study changes.

For every PR it pulls the benchmark's image (mswebench/<org>_m_<repo>:pr-<n>), installs CodeTwin inside,
runs mswe_inside.py there and copies the result into data/<project>/. Needs docker and the dataset JSONL
(downloaded from Hugging Face by the workflow).

    python mswe_collect.py --repo cli/cli --dataset data/mswe/go/cli__cli_dataset.jsonl --count 24 --shard 0/2
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

SETUP = r"""#!/bin/sh
# $1 language, $2 repository folder under /home
set -e
export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq || true
  apt-get install -y -qq --no-install-recommends python3 python3-venv python3-pip ca-certificates curl >/dev/null
elif command -v apk >/dev/null 2>&1; then
  apk add --no-cache python3 py3-pip >/dev/null
fi
python3 -m venv /home/ctenv || python3 -m venv --without-pip /home/ctenv
if [ ! -x /home/ctenv/bin/pip ]; then curl -sS https://bootstrap.pypa.io/get-pip.py | /home/ctenv/bin/python; fi
/home/ctenv/bin/pip install -q --disable-pip-version-check --ignore-requires-python /home/codetwin-0.1.0-py3-none-any.whl --no-deps tomli
# grammars need glibc >= 2.34; on older images static facts are computed on the host instead
/home/ctenv/bin/pip install -q --disable-pip-version-check --only-binary=:all: "tree-sitter>=0.23" "tree-sitter-language-pack>=0.9" \
  || echo "tree-sitter not installable here: static facts on the host"
if [ "$1" = "javascript" ] || [ "$1" = "typescript" ]; then
  cd "/home/$2"
  VV=$(node -p "require('vitest/package.json').version" 2>/dev/null || true)
  if [ -n "$VV" ]; then
    PKG=$(node -e "const [a,b]=process.argv[1].split('.').map(Number); console.log(a===0&&b<34?'@vitest/coverage-c8':'@vitest/coverage-v8')" "$VV")
    if ! node -e "require('$PKG')" 2>/dev/null; then
      if [ -f pnpm-lock.yaml ]; then
        (pnpm add -D -w "$PKG@$VV" || npx -y pnpm@8 add -D -w "$PKG@$VV") >/dev/null 2>&1 || true
      elif [ -f yarn.lock ]; then
        yarn add -D "$PKG@$VV" >/dev/null 2>&1 || true
      else
        npm i --no-save --no-audit --no-fund --legacy-peer-deps "$PKG@$VV" >/dev/null 2>&1 || true
      fi
      git checkout -q -- package.json pnpm-lock.yaml yarn.lock package-lock.json 2>/dev/null || true
    fi
  fi
  cd /home
fi
if [ "$1" = "rust" ]; then
  rustup component add llvm-tools-preview || true
  curl -sSL https://github.com/taiki-e/cargo-llvm-cov/releases/latest/download/cargo-llvm-cov-x86_64-unknown-linux-gnu.tar.gz | tar xz -C "$(dirname "$(command -v cargo)")"
fi
/home/ctenv/bin/python -c "import codetwin.lang; print('setup-ok')"
"""


def sh(cmd, timeout=None, check=True, capture=True):
    r = subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} -> {r.returncode}\n{(r.stdout or '')[-1500:]}\n{(r.stderr or '')[-1500:]}")
    return r


def load_instances(dataset: Path, org: str, repo: str) -> list[dict]:
    """Instances of org/repo from one JSONL file or every *.jsonl under a folder."""
    out = []
    files = sorted(dataset.rglob("*.jsonl")) if dataset.is_dir() else [dataset]
    for path in files:
        out += _read(path, org, repo)
    seen, uniq = set(), []
    for d in out:
        if d["number"] not in seen:
            seen.add(d["number"])
            uniq.append(d)
    uniq.sort(key=lambda d: (d["created_at"], d["number"]))
    return uniq


def _read(dataset: Path, org: str, repo: str) -> list[dict]:
    out = []
    with dataset.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if (d.get("org") or "").lower() == org.lower() and (d.get("repo") or "").lower() == repo.lower():
                out.append({"number": d["number"], "created_at": d.get("created_at", ""),
                            "base": d.get("base", {}).get("sha", "")})
    return out


def run_one(image: str, pr: int, index: int, repo_name: str, language: str, wheel: Path, max_tests: int,
            timeout: int, runner: str, out_dir: Path, log) -> bool:
    cid = None
    t0 = time.time()
    try:
        sh(["docker", "pull", "-q", image], timeout=1800)
        cid = sh(["docker", "run", "-d", "--entrypoint", "sleep", image, "infinity"]).stdout.strip()
        setup = out_dir / "_setup.sh"
        setup.write_text(SETUP)
        for src, dst in [(wheel, "/home/codetwin-0.1.0-py3-none-any.whl"), (HERE / "mswe_inside.py", "/home/mswe_inside.py"), (setup, "/home/setup.sh")]:
            sh(["docker", "cp", str(src), f"{cid}:{dst}"])
        sh(["docker", "exec", cid, "sh", "/home/setup.sh", language, repo_name], timeout=1500)
        cmd = ["docker", "exec", cid, "/home/ctenv/bin/python", "/home/mswe_inside.py", "--repo", f"/home/{repo_name}",
               "--out", "/home/out", "--pr", str(pr), "--index", str(index), "--max-tests", str(max_tests),
               "--language", language, "--runner", runner]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        log.write(r.stdout[-6000:] + "\n" + r.stderr[-4000:] + "\n")
        print("\n".join(l for l in r.stdout.splitlines() if l.startswith("[inside]")), flush=True)
        if r.returncode != 0:
            log.write(f"[host] pr {pr} failed ({r.returncode})\n")
            print(f"[host] pr {pr} failed ({r.returncode}):\n" + (r.stdout + r.stderr)[-3000:], flush=True)
            return False
        tmp = out_dir / "_out"
        shutil.rmtree(tmp, ignore_errors=True)
        sh(["docker", "cp", f"{cid}:/home/out", str(tmp)])
        for sub in ("snap", "commits"):
            (out_dir / sub).mkdir(parents=True, exist_ok=True)
            for p in (tmp / sub).glob("*.json"):
                shutil.move(str(p), out_dir / sub / p.name)
        if (tmp / "lang.json").exists():
            shutil.move(str(tmp / "lang.json"), out_dir / "lang.json")
        host_static(cid, repo_name, language, out_dir, log)
        return True
    except Exception as e:  # noqa: BLE001
        log.write(f"[host] pr {pr}: {e}\n")
        print(f"[host] pr {pr}: {str(e)[-3000:]}", flush=True)
        return False
    finally:
        log.write(f"[host] pr {pr}: {time.time() - t0:.0f}s\n")
        log.flush()
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True)
        subprocess.run(["docker", "rmi", "-f", image], capture_output=True)
        subprocess.run(["docker", "system", "prune", "-f"], capture_output=True)


def host_static(cid: str, repo_name: str, language: str, out_dir: Path, log) -> None:
    """Fill in static facts the container could not compute (no tree-sitter for its glibc): copy the
    repository out (without build folders) and run CodeTwin's adapter here at both recorded commits."""
    pending = []
    for p in (out_dir / "snap").glob("*.json"):
        d = json.loads(p.read_text())
        if d.get("static") is None:
            pending.append((p, d))
    if not pending:
        return
    from codetwin import lang
    from codetwin.config import Config
    work = out_dir / "_repo"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    tar = subprocess.Popen(["docker", "exec", cid, "tar", "-C", f"/home/{repo_name}", "--exclude=./node_modules",
                            "--exclude=./target", "--exclude=./build", "--exclude=./.gradle", "-cf", "-", "."],
                           stdout=subprocess.PIPE)
    subprocess.run(["tar", "-xf", "-", "-C", str(work)], stdin=tar.stdout, check=True)
    tar.wait()
    for p, d in pending:
        sh(["git", "-C", str(work), "checkout", "-q", "-f", d["sha"]])
        adapter = lang.get(Config(root=work, language=language, source_dirs=["."], tests_dir="."))
        facts = adapter.facts()
        d["static"] = {f: {"imports": v.imports, "dynamic": v.dynamic, "defs": v.defs, "dyn_lines": v.dyn_lines,
                           "mod_lines": v.mod_lines, "deps": v.deps} for f, v in facts.items()}
        d["loc"] = {f: sum(1 for _ in (work / f).open("rb")) for f in facts}
        d["static_on"] = "host"
        p.write_text(json.dumps(d))
        log.write(f"[host] static facts for {d['sha'][:10]} computed on the host ({len(facts)} files)\n")
        print(f"[host] static facts for {d['sha'][:10]} computed on the host ({len(facts)} files)", flush=True)
    shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="org/repo")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--language", required=True)
    ap.add_argument("--count", type=int, default=24)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--max-tests", type=int, default=80)
    ap.add_argument("--timeout", type=int, default=3600, help="seconds per PR")
    ap.add_argument("--runner", default="", help="JSON for the [runner] table inside the container")
    ap.add_argument("--wheel", default=str(HERE / "codetwin-0.1.0-py3-none-any.whl"))
    args = ap.parse_args()
    org, repo = args.repo.split("/")
    project = f"{org}_m_{repo}".lower()
    insts = load_instances(Path(args.dataset), org, repo)
    if not insts:
        sys.exit(f"no instances for {args.repo} in {args.dataset}")
    chosen = insts[: args.count]
    i, k = (int(x) for x in args.shard.split("/"))
    mine = [(n, d) for n, d in enumerate(chosen) if n % k == i]
    out_dir = DATA / project
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "logs").mkdir(exist_ok=True)
    meta = {"project": project, "url": f"https://github.com/{args.repo}", "mode": "pairs", "language": args.language,
            "spec": [f"https://github.com/{args.repo}", ".", [], ".", ["."], {"language": args.language}],
            "source": "Multi-SWE-bench (ByteDance-Seed), images mswebench/*", "count": len(chosen),
            "max_tests": args.max_tests, "changes": [[d["base"], None] for d in chosen]}
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    ok = 0
    with (out_dir / "logs" / f"collect_{i}.log").open("a") as log:
        for n, d in mine:
            image = f"mswebench/{project}:pr-{d['number']}"
            print(f"== {args.repo} PR {d['number']} ({n + 1}/{len(chosen)})", flush=True)
            good = run_one(image, d["number"], n, repo, args.language, Path(args.wheel), args.max_tests, args.timeout,
                           args.runner, out_dir, log)
            ok += int(good)
            print(f"   {'ok' if good else 'failed'}; {ok} recorded so far", flush=True)
    print(f"recorded {ok} of {len(mine)} PRs of {args.repo}")


if __name__ == "__main__":
    main()
