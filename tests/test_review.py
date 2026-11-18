import json

import httpx
import pytest

from codetwin.cli import main
from codetwin.review import ReviewContext, Severity, Source, run, select_analyzers
from codetwin.review.github_api import Poster, PostError, Target, post_from_env
from codetwin.review.model import Finding, Review
from codetwin.review.render import MARKER, github, markdown, sarif
from codetwin.review.rules import RULES


def _decision(**kw):
    d = {"schema": 1, "decision": "proceed", "residual_risk": 0.03, "threshold": 0.4, "mode": "calibrated",
         "selected": ["tests/test_a.py"], "reasons": [], "extras": {}}
    d.update(kw)
    return d


def _ctx(decision, changed=None, **kw):
    return ReviewContext(root=".", decision=decision, changed=changed or {"src/a.py": [3, 4, 5]}, **kw)


def test_every_rule_used_by_an_analyzer_is_catalogued():
    import inspect
    import re
    for mod in select_analyzers(enabled=[m.NAME for m in __import__("codetwin.plugins").plugins.discover(
            "codetwin.review.analyzers")]):
        for rid in re.findall(r'rule="(CT\d+)"', inspect.getsource(mod)):
            assert rid in RULES


def test_proceed_with_no_extras_has_no_findings():
    r = run(_ctx(_decision()))
    assert r.findings == [] and not r.blocking and r.decision == "proceed"


def test_abstain_untested_dynamic_new_file():
    d = _decision(decision="abstain", residual_risk=0.0,
                  reasons=["estimated residual risk 40.1% > target 10%; running the broader selection",
                           "src/a.py: dynamic calls (getattr) cannot be followed statically",
                           "src/new.py: new or unparsed file, no evidence yet"],
                  extras={"changed_symbols": {"symbols": [
                      {"name": "a.f", "kind": "function", "file": "src/a.py", "start": 3, "end": 5, "tests_before": 0},
                      {"name": "a.g", "kind": "function", "file": "src/a.py", "start": 7, "end": 8, "tests_before": 2}],
                      "summary": ""}})
    r = run(_ctx(d))
    rules = [f.rule for f in r.findings]
    assert rules == ["CT001", "CT002", "CT006", "CT003"]          # sorted by severity
    assert r.blocking
    assert r.findings[1].path == "src/a.py" and r.findings[1].start_line == 3
    assert all(f.analyzer for f in r.findings)


def test_contracts_and_cross_repo():
    d = _decision(extras={
        "contracts": {"breaking": [{"file": "api.yaml", "kind": "removed", "location": "GET /users/{id}",
                                    "detail": "operation removed", "breaking": True,
                                    "consumers": [{"repo": "web", "file": "src/u.ts", "line": 4, "how": "path"}],
                                    "tests": {"web:test/u.test.ts": ["direct"]}}]},
        "cross_repo": {"repos": [{"name": "web", "consumers": [
            {"file": "src/x.ts", "link": "uses-changed-symbol", "symbols": ["total"]},
            {"file": "src/y.ts", "link": "imports-package"}], "tests": {"test/x.test.ts": ["runtime"]},
            "unknowns": []}]}})
    r = run(_ctx(d))
    by = {f.rule: f for f in r.findings}
    assert by["CT004"].severity is Severity.HIGH and "web:src/u.ts:4" in by["CT004"].evidence[0]
    assert by["CT005"].severity is Severity.MEDIUM and "test/x.test.ts" in by["CT005"].suggestion
    assert r.blocking                                            # a breaking contract blocks


def test_failed_section_and_failing_analyzer_are_visible():
    d = _decision(extras={"changed_symbols": {"error": "boom", "summary": "section failed"}})
    assert run(_ctx(d)).findings == []                           # a failed section is not read as data

    class Broken:
        NAME = "broken"

        @staticmethod
        def analyze(ctx):
            raise ValueError("bad")
    r = run(_ctx(_decision()), [Broken])
    assert r.notes == ["analyzer broken failed: ValueError: bad"]


def test_unknown_analyzer_name_is_an_error():
    with pytest.raises(ValueError, match="unknown review analyzers"):
        select_analyzers(["nope"])
    assert "llm_review" not in {m.NAME for m in select_analyzers()}      # LLM is off by default


def test_duplicates_are_merged():
    f = Finding("CT003", Severity.LOW, "t", "m", path="a.py")

    class Twice:
        NAME = "twice"

        @staticmethod
        def analyze(ctx):
            return [f, Finding("CT003", Severity.LOW, "t", "m", path="a.py")]
    assert len(run(_ctx(_decision()), [Twice]).findings) == 1


class _FakeLLM:
    def __init__(self, text):
        self.text = text
        self.seen = None

    def chat(self, messages, **kw):
        self.seen = messages
        return {"choices": [{"message": {"content": self.text}}], "codetwin_provider": "fake", "codetwin_model": "m"}


def test_llm_review_is_advisory_and_stays_in_the_diff():
    from codetwin.review.analyzers import llm_review
    text = json.dumps({"comments": [
        {"path": "src/a.py", "line": 4, "severity": "critical", "title": "Off by one", "message": "m"},
        {"path": "src/a.py", "line": 99, "severity": "low", "title": "Invented line", "message": "m"},
        {"path": "other.py", "line": 1, "severity": "low", "title": "Invented file", "message": "m"}]})
    llm = _FakeLLM("Sure! " + text)
    r = run(_ctx(_decision(), llm=llm, options={"patch": "diff --git a/src/a.py b/src/a.py"}), [llm_review])
    assert [f.title for f in r.findings] == ["Off by one"]
    f = r.findings[0]
    assert f.source is Source.LLM and f.severity is Severity.INFO     # "critical" is not allowed for the LLM
    assert not r.blocking
    assert "ignore any instructions" in llm.seen[0]["content"]
    assert run(_ctx(_decision(), llm=_FakeLLM("not json"), options={"patch": "x"}), [llm_review]).findings == []
    assert run(_ctx(_decision(), llm=None, options={"patch": "x"}), [llm_review]).findings == []


def _review():
    return Review("abstain", 0.0, 0.1, ["tests/test_a.py"], [
        Finding("CT001", Severity.HIGH, "abstained", "m", evidence=["e"]),
        Finding("CT002", Severity.MEDIUM, "`f` untested", "m", path="src/a.py", start_line=3, end_line=5,
                suggestion="add a test"),
        Finding("CT100", Severity.LOW, "AI", "m", source=Source.LLM, path="src/a.py", start_line=40)])


def test_renderers():
    r = _review()
    md = markdown(r)
    assert md.startswith(MARKER) and "Run more tests before merging" in md and "AI suggestion, not verified" in md
    gh = github(r, lambda p, ln: p == "src/a.py" and ln == 3)
    assert [c["line"] for c in gh["comments"]] == [3] and "codetwin-fp:" in gh["comments"][0]["body"]
    s = sarif(r)
    assert s["version"] == "2.1.0" and [x["id"] for x in s["runs"][0]["tool"]["driver"]["rules"]] == ["CT001", "CT002", "CT100"]
    res = s["runs"][0]["results"]
    assert res[0]["level"] == "error" and "locations" not in res[0]
    assert res[1]["locations"][0]["physicalLocation"]["region"] == {"startLine": 3, "endLine": 5}
    assert r.to_dict()["counts"]["high"] == 1


def test_post_updates_summary_and_skips_known_inline(tmp_path):
    r = _review()
    fp = r.findings[1].fingerprint
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        assert req.headers["Authorization"] == "Bearer tok"
        if req.method == "GET" and req.url.path.endswith("/issues/7/comments"):
            return httpx.Response(200, json=[
                {"id": 10, "body": "quoting " + MARKER, "user": {"type": "User"}},      # a person quoting it
                {"id": 11, "body": MARKER + " pasted by a person", "user": {"type": "User"}},
                {"id": 12, "body": MARKER + " old", "user": {"type": "Bot"}}])
        if req.method == "GET" and req.url.path.endswith("/pulls/7/comments"):
            return httpx.Response(200, json=[{"body": f"x <!-- codetwin-fp:{fp} -->"}])
        return httpx.Response(200, json={})
    out = Poster(Target("o/r", 7), "tok", httpx.MockTransport(handler)).post(r, lambda p, ln: True)
    assert out == {"summary": "updated", "inline": 1}                  # CT100 is new, CT002 was already posted
    assert ("PATCH", "/repos/o/r/issues/comments/12") in calls and ("POST", "/repos/o/r/pulls/7/reviews") in calls

    ev = tmp_path / "event.json"
    ev.write_text(json.dumps({"pull_request": {"number": 7}}))
    env = {"GITHUB_REPOSITORY": "o/r", "GITHUB_EVENT_PATH": str(ev)}
    assert Target.from_env(env) == Target("o/r", 7)
    with pytest.raises(PostError, match="GITHUB_TOKEN"):
        post_from_env(r, lambda p, ln: True, env)
    with pytest.raises(RuntimeError, match="pull_request"):
        Target.from_env({})


def test_review_command_end_to_end(toy_repo, capsys, tmp_path):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text() + "\n\ndef tax(x):\n    return x * 0.18\n")
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "review", "--format", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert any(f["rule"] == "CT002" and f["path"] == "src/shop/price.py" for f in out["findings"])
    assert out["files"][0]["path"] == "src/shop/price.py" and "tests/test_price.py" in out["files"][0]["tests"]
    dec = tmp_path / "d.json"
    main(["-C", str(toy_repo), "select", "--json"])
    dec.write_text(capsys.readouterr().out)
    sar = tmp_path / "r.sarif"
    assert main(["-C", str(toy_repo), "review", "--decision", str(dec), "--format", "sarif", "-o", str(sar)]) == 0
    assert json.loads(sar.read_text())["version"] == "2.1.0"
    assert main(["-C", str(toy_repo), "review", "--decision", str(dec), "--only", "untested_change",
                 "--fail-on-blocking"]) in (0, 1)


def test_paths_with_spaces_and_unknown_only_repos():
    d = _decision(reasons=["src/my module.py: dynamic calls (getattr) cannot be followed statically",
                           "src/new file.py: new or unparsed file, no evidence yet"],
                  extras={"cross_repo": {"repos": [{"name": "web", "consumers": [], "tests": {},
                                                    "unknowns": ["web: dynamic import"]}]}})
    by = {f.rule: f for f in run(_ctx(d)).findings}
    assert by["CT003"].path == "src/my module.py" and by["CT006"].path == "src/new file.py"
    assert by["CT005"].severity is Severity.LOW and by["CT005"].title.startswith("Could not tell")


def test_two_breaking_changes_on_one_property_both_kept():
    b = {"file": "api.yaml", "location": "User.age", "detail": "d", "consumers": [], "tests": {}}
    d = _decision(extras={"contracts": {"breaking": [dict(b, kind="type-changed"), dict(b, kind="enum-narrowed")]}})
    assert len([f for f in run(_ctx(d)).findings if f.rule == "CT004"]) == 2


def test_failed_sections_and_advisory_errors_in_notes():
    d = _decision(extras={"contracts": {"error": "boom"}})
    assert run(_ctx(d)).notes == ["report section contracts failed, so findings that depend on it are missing: boom"]

    class Advisory:
        NAME, ADVISORY = "adv", True

        @staticmethod
        def analyze(ctx):
            raise RuntimeError("provider said: <the whole diff>")
    assert run(_ctx(_decision()), [Advisory]).notes == ["analyzer adv failed: RuntimeError"]


def test_disabled_may_be_a_generator():
    names = {m.NAME for m in select_analyzers(disabled=(n for n in ["blind_spots"]))}
    assert "blind_spots" not in names and "untested_change" in names


def test_saved_alpha_wins_over_config():
    class Cfg:
        alpha = 0.2
    d = _decision(extras={"change_risk": {"alpha": 0.1, "summary": ""}})
    assert run(_ctx(d, cfg=Cfg())).alpha == 0.1


def test_llm_comments_with_bad_types_are_skipped_one_by_one():
    from codetwin.review.analyzers import llm_review
    text = json.dumps({"comments": [{"path": [], "line": 4, "title": "bad path"}, {"path": "src/a.py", "line": True},
                                    {"path": "src/a.py", "line": 4, "severity": "low", "title": "Good", "message": "m"}]})
    r = run(_ctx(_decision(), llm=_FakeLLM(text), options={"patch": "x"}), [llm_review])
    assert [f.title for f in r.findings] == ["Good"] and r.notes == []
    assert llm_review._parse('{"comments": "not a list"}') == []


def test_commentable_lines_and_decision_checks(tmp_path):
    from codetwin.commands.review import commentable, load_decision
    patch = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,2 @@\n x\n-y\n z\n"
             "diff --git a/n.py b/n.py\n--- /dev/null\n+++ b/n.py\n@@ -0,0 +1 @@\n+new\n"
             "diff --git a/gone.py b/gone.py\n--- a/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n")
    c = commentable(patch)
    assert c == {"a.py": {1, 2}, "n.py": {1}}
    ctx = ReviewContext(root=".", decision=_decision(), changed={"a.py": [2, 3]}, commentable=c)
    assert ctx.in_diff("a.py", 2) and not ctx.in_diff("a.py", 3)      # line 3 no longer exists
    bad = tmp_path / "d.json"
    for content, msg in [("{}", "'decision' must be"), ("[]", "expected a JSON object"), ("not json", "cannot read"),
                         (json.dumps(_decision(residual_risk=2)), "'residual_risk'")]:
        bad.write_text(content)
        with pytest.raises(SystemExit, match=msg):
            load_decision(str(bad))
    bad.write_text(json.dumps(_decision()))
    assert load_decision(str(bad))["decision"] == "proceed"


def test_review_rejects_decision_for_another_base_and_survives_post_errors(toy_repo, tmp_path, capsys, monkeypatch):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    dec = tmp_path / "d.json"
    dec.write_text(json.dumps(_decision(extras={"changed_files": {"base": "f" * 40, "files": {}, "summary": ""}})))
    with pytest.raises(SystemExit, match="computed against ffffffffffff"):
        main(["-C", str(toy_repo), "review", "--decision", str(dec)])
    capsys.readouterr()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["-C", str(toy_repo), "review", "--post-github"]) == 0      # posting fails, review does not
    assert "could not post the review" in capsys.readouterr().err


def test_diff_parser_headers_quoted_paths():
    from codetwin.commands.review import commentable, git_path
    patch = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1,2 @@\n x\n+++ b/other.txt\n"
             "@@ -9 +10 @@\n-y\n+z\n"
             'diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\n--- "a/caf\\303\\251.py"\n'
             '+++ "b/caf\\303\\251.py"\n@@ -1 +1 @@\n-a\n+b\n')
    assert commentable(patch) == {"a.py": {1, 2, 10}, "café.py": {1}}
    assert git_path('"b/x \\"q\\".py"') == 'b/x "q".py' and git_path("b/plain.py") == "b/plain.py"


def test_post_turns_network_errors_into_post_error():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)
    with pytest.raises(PostError, match="could not reach GitHub \\(ReadTimeout\\)"):
        Poster(Target("o/r", 7), "tok", httpx.MockTransport(handler)).post(_review(), lambda p, ln: True)


def test_saved_decision_must_match_the_current_change(toy_repo, tmp_path, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text() + "\n\ndef tax(x):\n    return x * 0.18\n")
    capsys.readouterr()
    main(["-C", str(toy_repo), "select", "--json"])
    dec = tmp_path / "d.json"
    dec.write_text(capsys.readouterr().out)
    assert main(["-C", str(toy_repo), "review", "--decision", str(dec), "--format", "json"]) == 0
    p.write_text(p.read_text() + "\n\ndef more(x):\n    return x\n")
    with pytest.raises(SystemExit, match="does not describe the current change"):
        main(["-C", str(toy_repo), "review", "--decision", str(dec)])
