import json

import httpx
import pytest

from codetwin.cli import main
from codetwin.review import ReviewContext, Severity, Source, run, select_analyzers
from codetwin.review.github_api import Poster, Target, post_from_env
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
    assert md.startswith(MARKER) and "Run more tests before merging" and "AI suggestion, not verified" in md
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
            return httpx.Response(200, json=[{"id": 11, "body": "other"}, {"id": 12, "body": MARKER + " old"}])
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
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
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
