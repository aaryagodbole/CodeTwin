"""Connected repositories given by URL: any number of them, synced into .codetwin/repos, analysed offline."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from codetwin.cli import main
from codetwin.config import load
from codetwin.crossrepo.sources import connected, sync, url_problem


def _git(r: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=r, check=True, capture_output=True)


def _dependent(tmp_path: Path, name: str, body: str) -> Path:
    """A git repository whose module uses shop.price.total (the toy library's function)."""
    d = tmp_path / name
    (d / name).mkdir(parents=True)
    (d / "tests").mkdir()
    (d / name / "__init__.py").write_text("")
    (d / name / "use.py").write_text(body)
    (d / "tests" / f"test_{name}.py").write_text(f"from {name}.use import f\n\ndef test_f():\n    assert f\n")
    _git(d, "init", "-q")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "init")
    return d


@pytest.fixture
def library(toy_repo: Path, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    web = _dependent(tmp_path, "web", "from shop.price import total\n\ndef f(items):\n    return total(items)\n")
    mobile = _dependent(tmp_path, "mobile", "import shop\n\ndef f():\n    return 1\n")
    admin = _dependent(tmp_path, "admin", "from shop.price import total\n\ndef f(x):\n    return total(x)\n")
    main(["-C", str(toy_repo), "init"])
    cfg = toy_repo / ".codetwin.toml"
    cfg.write_text(cfg.read_text() + f"""
[[repos]]
url = "{web.as_uri()}"

[[repos]]
name = "mobile"
url = "{mobile.as_uri()}"

[[repos]]
name = "admin"
path = "{admin.as_posix()}"
""")
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    return toy_repo, web, mobile, admin


def _crossrepo(repo: Path, capsys: pytest.CaptureFixture[str], *flags: str) -> dict:
    capsys.readouterr()
    assert main(["-C", str(repo), "crossrepo", "--json", *flags]) == 0
    return json.loads(capsys.readouterr().out)


def test_two_urls_and_a_path_are_all_analysed(library, capsys: pytest.CaptureFixture[str]) -> None:
    repo, web, mobile, _admin = library
    before = {r["name"]: r for r in _crossrepo(repo, capsys)["repos"]}
    assert before["web"]["status"] == before["mobile"]["status"] == "not-synced"     # analysis never clones
    assert "codetwin crossrepo --sync" in before["web"]["unknowns"][0]
    assert before["admin"]["status"] == "analysed"

    out = {r["name"]: r for r in _crossrepo(repo, capsys, "--sync")["repos"]}
    assert [out[n]["status"] for n in ("web", "mobile", "admin")] == ["analysed"] * 3
    assert out["web"]["url"] == web.as_uri() and out["admin"]["url"] is None
    assert {c["file"]: c["link"] for c in out["web"]["consumers"]} == {"web/use.py": "uses-changed-symbol"}
    assert {c["file"]: c["link"] for c in out["mobile"]["consumers"]} == {"mobile/use.py": "imports-package"}
    assert (repo / ".codetwin/repos/web/web/use.py").is_file() and (repo / ".codetwin/repos/mobile").is_dir()


def test_sync_updates_a_copy_when_the_remote_moves(library) -> None:
    repo, web, _mobile, _admin = library
    cfg = load(repo)
    assert [s["status"] for s in sync(cfg)] == ["cloned", "cloned", "local"]
    (web / "web" / "more.py").write_text("from shop.price import total\n")
    _git(web, "add", "-A")
    _git(web, "commit", "-qm", "more")
    assert [s["status"] for s in sync(cfg)][:2] == ["updated", "updated"]
    assert (repo / ".codetwin/repos/web/web/more.py").is_file()


def test_bad_entries_are_reported_never_dropped(toy_repo: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    cfg = toy_repo / ".codetwin.toml"
    cfg.write_text(cfg.read_text() + """
[[repos]]
name = "a"
url = "https://github.com/acme/a.git"

[[repos]]
name = "a"
url = "https://github.com/acme/other.git"

[[repos]]
name = "both"
url = "https://github.com/acme/b.git"
path = "../b"

[[repos]]
name = "secret"
url = "https://user:ghp_token@github.com/acme/c.git"

[[repos]]
name = "evil"
url = "ext::sh -c touch% /tmp/pwned"

[[repos]]
name = "nothing"
""")
    got = {(s.name, s.url): s.error for s in connected(load(toy_repo))}
    errors = list(got.values())
    assert errors[0] is None                                              # the first "a" is fine
    assert "unique name" in errors[1] and "not both" in errors[2] and "password or token" in errors[3]
    assert errors[4] is not None and "path or a url" in errors[5]          # ext:: is refused
    assert all(s["status"] == "invalid" for s in sync(load(toy_repo))[1:])


@pytest.mark.parametrize(("url", "ok"), [
    ("https://github.com/acme/web.git", True), ("git@github.com:acme/web.git", True),
    ("ssh://git@github.com/acme/web.git", True), ("file:///srv/git/web.git", True),
    ("-uhttps://x", False), ("ext::sh -c id", False), ("ext::true", False), ("http://github.com/acme/web.git", False),
    ("https://x:y@github.com/a.git", False),
    ("https://ghp_token@github.com/a.git", False),          # a token given as the user name
    ("ssh://git@github.com/a.git", True),                   # ssh names a user, never a secret
])
def test_url_rules(url: str, ok: bool) -> None:
    assert (url_problem(url) is None) is ok


def test_migration_0006_keeps_existing_targets_and_their_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A store from before URL repositories: its analysis targets, consumers and views survive the rebuild."""
    from codetwin.store import db as store_db
    every = store_db._migrations()
    monkeypatch.setattr(store_db, "_migrations", lambda: [m for m in every if m[0] < "0006"])
    with store_db.Store(tmp_path / "e.db") as st:
        con = st.con
        aid = con.execute("insert into impact_analysis (kind, recorded, base_revision_id, tool_version, summary) "
                          "values ('cross-repo', 1, ?, 'x', 's')", (st._revision("a" * 40),)).lastrowid
        rid = st.repository("web", "../web")
        tid = con.execute("insert into analysis_target (analysis_id, repository_id, revision_id, language, status, "
                          "runtime_evidence) values (?,?,null,'python','analysed',0)", (aid, rid)).lastrowid
        con.execute("insert into consumer_file (target_id, file_id, link, is_test) values (?,?,'imports-package',0)",
                    (tid, st._entity("web/use.py", repo=rid)))
        con.commit()
    monkeypatch.setattr(store_db, "_migrations", lambda: every)
    with store_db.Store(tmp_path / "e.db") as st:
        assert st.con.execute("select id, status from analysis_target").fetchall() == [(tid, "analysed")]
        assert st.con.execute("select target_id from consumer_file").fetchall() == [(tid,)]
        st.con.execute("insert into analysis_target (analysis_id, repository_id, status, runtime_evidence) "
                       "values (?, ?, 'not-synced', 0)", (aid, st.repository("mobile")))
        assert st.con.execute("pragma foreign_key_check").fetchall() == []
        assert ("web", "dependsOn", ".") not in st.con.execute("select * from repository_relation").fetchall()


def test_repos_command_lists_and_syncs(library, capsys: pytest.CaptureFixture[str]) -> None:
    repo = library[0]
    capsys.readouterr()
    assert main(["-C", str(repo), "repos", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [(r["name"], r["available"]) for r in rows] == [("web", False), ("mobile", False), ("admin", True)]
    assert main(["-C", str(repo), "repos", "--sync", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [r.get("sync") for r in rows] == ["cloned", "cloned", "local"] and all(r["available"] for r in rows)


def test_a_failed_update_keeps_the_last_good_copy(library) -> None:
    """A network or auth error while updating must not delete the copy analysis was using."""
    repo, web, _mobile, _admin = library
    cfg = load(repo)
    sync(cfg)
    copy = repo / ".codetwin/repos/web"
    _git(copy, "remote", "set-url", "origin", web.as_uri())          # still the configured url
    hidden = web.with_name("web-moved")
    web.rename(hidden)                                               # the remote is unreachable now
    try:
        first = sync(cfg)[0]
        assert first["status"] == "failed" and "kept the previous copy" in first["detail"]
        assert (copy / "web" / "use.py").is_file()
    finally:
        hidden.rename(web)


def test_a_failed_clone_leaves_no_folder_that_looks_synced(toy_repo: Path, tmp_path: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    cfg = toy_repo / ".codetwin.toml"
    cfg.write_text(cfg.read_text() + f'\n[[repos]]\nname = "gone"\nurl = "{(tmp_path / "nowhere").as_uri()}"\n')
    loaded = load(toy_repo)
    assert sync(loaded)[0]["status"] == "failed"
    repos = toy_repo / ".codetwin/repos"
    assert not (repos / "gone").exists() and not list(repos.glob(".*partial"))
    assert not connected(loaded)[0].available


def test_repeated_names_are_invalid_and_do_not_break_the_analysis(library, capsys: pytest.CaptureFixture[str]) -> None:
    """Names are compared without case (they become folder names); a repeat is reported, never a crash."""
    repo, _web, mobile, _admin = library
    cfg = repo / ".codetwin.toml"
    cfg.write_text(cfg.read_text() + f'\n[[repos]]\nname = "Mobile"\nurl = "{mobile.as_uri()}"\n'
                   '\n[[repos]]\nname = "odd"\nurl = ["https://github.com/acme/odd.git"]\npath = "../odd"\n')
    errors = {s.name: s.error for s in connected(load(repo))}
    assert "unique name" in (errors["Mobile"] or "") and errors["odd"] == "url must be a string"
    sync(load(repo))
    _crossrepo(repo, capsys)                 # stores the analysis: a repeated name must not break its insert
