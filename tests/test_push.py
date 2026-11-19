"""`codetwin push`: what a report contains (and never contains), and how it is sent."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from codetwin import push, report
from codetwin.cli import main
from codetwin.engine import Engine


def _decide(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> dict:
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    capsys.readouterr()
    main(["-C", str(toy_repo), "select", "--json"])
    return json.loads(capsys.readouterr().out)


def test_report_holds_ids_and_numbers_never_code(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    decision = _decide(toy_repo, capsys)
    with Engine(toy_repo) as eng:
        body = push.build_report(eng, decision, env={}, repository="acme/shop")
    assert body["schema"] == "codetwin.report/v1" and body["repository"] == "acme/shop"
    assert body["run"]["source"] == "cli" and body["run"]["id"].startswith("cli-") and body["run"]["attempt"] == 1
    assert set(body["decision"]["sections"]) <= report.publishable()
    assert {"contracts", "cross_repo"}.isdisjoint(body["decision"]["sections"])   # not opted in
    ids = {t["id"] for t in body["decision"]["tests"]}
    assert set(body["decision"]["selected"]) <= ids and all(t["score"] is not None for t in body["decision"]["tests"])
    text = json.dumps(body)
    for f in ["src/shop/price.py", "tests/test_price.py"]:          # no line of any source or test file
        for line in (toy_repo / f).read_text().splitlines():
            if len(line.strip()) > 12:
                assert line.strip() not in text, line


def test_github_actions_identity_comes_from_the_environment(
    toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    decision = _decide(toy_repo, capsys)
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 63}}))
    env = {"GITHUB_ACTIONS": "true", "GITHUB_SHA": "c" * 40, "GITHUB_RUN_ID": "777", "GITHUB_RUN_ATTEMPT": "2",
           "GITHUB_REPOSITORY": "acme/shop", "GITHUB_REF": "refs/pull/63/merge", "GITHUB_EVENT_PATH": str(event)}
    with Engine(toy_repo) as eng:
        body = push.build_report(eng, decision, env=env)
    assert body["run"] == {"source": "github-actions", "id": "777", "attempt": 2}
    assert body["commit"]["head"] == "c" * 40 and body["commit"]["pull_request"] == 63


def test_dry_run_prints_and_sends_nothing(toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    decision = _decide(toy_repo, capsys)
    f = tmp_path / "d.json"
    f.write_text(json.dumps(decision))
    assert main(["-C", str(toy_repo), "push", "--decision", str(f), "--dry-run", "--repository", "acme/shop"]) == 0
    assert json.loads(capsys.readouterr().out)["decision"]["decision"] == decision["decision"]


def test_https_only_except_localhost() -> None:
    assert push.check_server("https://api.example.com/") == "https://api.example.com"
    assert push.check_server("http://localhost:8080") == "http://localhost:8080"
    for bad in ["http://api.example.com", "ftp://x", "file:///etc/passwd"]:
        with pytest.raises(push.PushError):
            push.check_server(bad)


class _Server:
    """A local HTTP server recording requests; answers with a fixed status and JSON body."""

    def __init__(self, status=201, body=b'{"id": 5, "created": true}'):
        seen = self.seen = []

        class H(BaseHTTPRequestHandler):
            def _reply(self):
                n = int(self.headers.get("content-length") or 0)
                seen.append((self.command, self.path, dict(self.headers), self.rfile.read(n)))
                self.send_response(status)
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = _reply

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://localhost:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


def test_send_posts_json_with_the_token() -> None:
    srv = _Server()
    try:
        res = push.send(srv.url, {"schema": "codetwin.report/v1"}, "ctp_abc")
    finally:
        srv.close()
    method, path, headers, body = srv.seen[0]
    assert (method, path, res) == ("POST", "/api/v1/reports", {"status": 201, "id": 5, "created": True})
    assert headers["Authorization"] == "Bearer ctp_abc" and json.loads(body) == {"schema": "codetwin.report/v1"}


def test_refused_upload_fails_unless_best_effort(
    toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    decision = _decide(toy_repo, capsys)
    f = tmp_path / "d.json"
    f.write_text(json.dumps(decision))
    srv = _Server(status=403, body=b'{"detail": "not registered"}')
    try:
        base = ["-C", str(toy_repo), "push", "--decision", str(f), "--server", srv.url, "--token", "ctp_x",
                "--repository", "acme/shop"]
        assert main(base) == 1
        assert main([*base, "--best-effort"]) == 0
    finally:
        srv.close()
    assert "upload refused (403)" in capsys.readouterr().err


def test_github_oidc_token_is_requested_with_our_audience() -> None:
    srv = _Server(status=200, body=b'{"value": "jwt.from.github"}')
    try:
        tok = push.github_oidc_token({"ACTIONS_ID_TOKEN_REQUEST_URL": f"{srv.url}/token?x=1",
                                      "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "req-token"})
    finally:
        srv.close()
    _, path, headers, _ = srv.seen[0]
    assert tok == "jwt.from.github" and path == "/token?x=1&audience=codetwin-cloud"
    assert headers["Authorization"] == "bearer req-token"
    with pytest.raises(push.PushError, match="id-token: write"):
        push.github_oidc_token({})


def test_cli_run_id_follows_the_decision_not_the_local_database(
    toy_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two clones both have decision 1; different decisions must not share a run id (the cloud dedups on it)."""
    decision = _decide(toy_repo, capsys)
    other = {**decision, "decision": "abstain" if decision["decision"] == "proceed" else "proceed"}
    with Engine(toy_repo) as eng:
        a = push.build_report(eng, decision, env={}, repository="acme/shop")["run"]["id"]
        again = push.build_report(eng, decision, env={}, repository="acme/shop")["run"]["id"]
        b = push.build_report(eng, other, env={}, repository="acme/shop")["run"]["id"]
    assert a == again and a != b


def test_scores_come_only_from_the_same_stored_decision(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A different decision that selects the same tests must not get the stored decision's scores and alpha."""
    decision = _decide(toy_repo, capsys)
    other = {**decision, "mode": "fallback"}
    with Engine(toy_repo) as eng:
        same = push.build_report(eng, decision, env={}, repository="acme/shop")["decision"]
        diff = push.build_report(eng, other, env={}, repository="acme/shop")["decision"]
    assert any(t["score"] is not None for t in same["tests"])
    assert diff["alpha"] is None and all(t["score"] is None for t in diff["tests"])


def test_malformed_decision_json_is_a_push_error(
    toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    decision = _decide(toy_repo, capsys)
    for bad in [{**decision, "selected": None}, {**decision, "residual_risk": "high"}, [1, 2]]:
        f = tmp_path / "bad.json"
        f.write_text(json.dumps(bad), encoding="utf-8")
        base = ["-C", str(toy_repo), "push", "--decision", str(f), "--dry-run", "--repository", "acme/shop"]
        assert main(base) == 1
        assert main([*base, "--best-effort"]) == 0
        assert "codetwin push" in capsys.readouterr().err


@pytest.mark.parametrize("body", [b"null", b"[]", b'{"id": "x", "created": true}'])
def test_unexpected_upload_answers_are_push_errors(body: bytes) -> None:
    srv = _Server(status=200, body=body)
    try:
        with pytest.raises(push.PushError):
            push.send(srv.url, {"schema": "codetwin.report/v1"}, "ctp_abc")
    finally:
        srv.close()


def test_a_truncated_answer_is_a_push_error() -> None:
    """The server promises more bytes than it sends (http.client.IncompleteRead is not an OSError)."""
    class Short(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length") or 0))
            self.send_response(201)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b'{"id": 1')

        def log_message(self, *a):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Short)
    threading.Thread(target=httpd.handle_request, daemon=True).start()
    try:
        with pytest.raises(push.PushError):
            push.send(f"http://localhost:{httpd.server_port}", {"schema": "codetwin.report/v1"}, "ctp_abc")
    finally:
        httpd.server_close()


def test_redirects_are_not_followed_with_the_token() -> None:
    """A redirect could send the bearer token over plain HTTP or to another origin."""
    target = _Server()
    redirect = _Server(status=302, body=b"")
    redirect_to = f"{target.url}/elsewhere"

    class R(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length") or 0))
            self.send_response(302)
            self.send_header("Location", redirect_to)
            self.end_headers()

        def log_message(self, *a):
            pass

    redirect.close()
    httpd = HTTPServer(("127.0.0.1", 0), R)
    threading.Thread(target=httpd.handle_request, daemon=True).start()
    try:
        with pytest.raises(push.PushError, match="redirect"):
            push.send(f"http://localhost:{httpd.server_port}", {"schema": "codetwin.report/v1"}, "ctp_secret")
    finally:
        httpd.server_close()
        target.close()
    assert not target.seen, "the token followed the redirect"


def test_best_effort_survives_any_error(toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _decide(toy_repo, capsys)
    f = tmp_path / "d.json"
    f.write_text(json.dumps(decision), encoding="utf-8")

    def broken(*a, **k):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(push, "build_report", broken)
    from codetwin.commands import push as push_cmd
    monkeypatch.setattr(push_cmd, "build_report", broken)
    base = ["-C", str(toy_repo), "push", "--decision", str(f), "--dry-run", "--repository", "acme/shop"]
    assert main([*base, "--best-effort"]) == 0
    assert "database is locked" in capsys.readouterr().err


def test_nulls_and_non_finite_numbers_never_crash_or_reach_the_body(toy_repo: Path,
                                                                     capsys: pytest.CaptureFixture[str]) -> None:
    decision = _decide(toy_repo, capsys)
    odd = {**decision, "reasons": None, "schema": None,
           "extras": {"changed_files": {"summary": "x", "weight": float("nan"), "big": float("inf")}}}
    with Engine(toy_repo) as eng:
        body = push.build_report(eng, odd, env={}, repository="acme/shop")
    assert body["decision"]["reasons"] == [] and body["engine"]["output_schema"] >= 1
    text = json.dumps(body, allow_nan=False)      # raises if any NaN or Infinity is left
    assert "NaN" not in text and "Infinity" not in text


def test_failed_sections_are_not_published(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A failed section's error text may quote source code; it never leaves the machine."""
    decision = _decide(toy_repo, capsys)
    failed = {**decision, "extras": {**decision.get("extras", {}),
                                     "changed_files": {"error": "SyntaxError: def secret(): ...",
                                                       "summary": "section failed: def secret(): ..."}}}
    with Engine(toy_repo) as eng:
        body = push.build_report(eng, failed, env={}, repository="acme/shop")
    assert "changed_files" not in body["decision"]["sections"]
    assert "secret" not in json.dumps(body)


def test_large_suites_stay_under_the_upload_limit(toy_repo: Path, capsys: pytest.CaptureFixture[str],
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _decide(toy_repo, capsys)
    with Engine(toy_repo) as eng:
        many = {f"tests/test_{i:05d}.py": i / 10000 for i in range(5000)}
        monkeypatch.setattr(eng.store, "scores", lambda _id: many)
        body = push.build_report(eng, decision, env={}, repository="acme/shop")
    assert len(json.dumps(body)) < 256 * 1024
    assert set(decision["selected"]) <= {t["id"] for t in body["decision"]["tests"]}
    assert "tests/test_04999.py" in {t["id"] for t in body["decision"]["tests"]}      # highest score kept


def test_odd_event_payloads_and_missing_run_id(toy_repo: Path, capsys: pytest.CaptureFixture[str],
                                               tmp_path: Path) -> None:
    decision = _decide(toy_repo, capsys)
    event = tmp_path / "event.json"
    env = {"GITHUB_ACTIONS": "true", "GITHUB_SHA": "c" * 40, "GITHUB_RUN_ID": "7", "GITHUB_REPOSITORY": "acme/shop",
           "GITHUB_EVENT_PATH": str(event)}
    with Engine(toy_repo) as eng:
        for payload in ['{"pull_request": {"number": null}}', '[1, 2]', '{"pull_request": "x"}']:
            event.write_text(payload, encoding="utf-8")
            assert push.build_report(eng, decision, env=env)["commit"]["pull_request"] is None
        with pytest.raises(push.PushError, match="GITHUB_RUN_ID"):
            push.build_report(eng, decision, env={**env, "GITHUB_RUN_ID": ""})


def test_fit_drops_rows_but_never_the_selection() -> None:
    """An abstention selects every test; on a big suite the rows go before the selection is ever cut."""
    sel = [f"tests/test_{i:05d}.py" for i in range(3000)]
    body = {"schema": "codetwin.report/v1", "decision": {
        "selected": sel, "tests": [{"id": t, "selected": True, "score": 0.5, "seconds": 0.1} for t in sel]}}
    small = push.fit(body)
    assert small["decision"]["selected"] == sel and len(json.dumps(small)) <= push.MAX_REPORT_BYTES
    huge = {"schema": "codetwin.report/v1", "decision": {"selected": [f"tests/{'x' * 80}_{i}.py" for i in range(5000)],
                                                         "tests": []}}
    with pytest.raises(push.PushError, match="too large"):
        push.fit(huge)


def test_reasons_and_mode_fit_the_report_format(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    decision = _decide(toy_repo, capsys)
    many = {**decision, "reasons": [f"unknown link {i}" for i in range(450)], "mode": None}
    with Engine(toy_repo) as eng:
        d = push.build_report(eng, many, env={}, repository="acme/shop")["decision"]
    assert len(d["reasons"]) == push.MAX_REASONS and d["reasons"][-1] == "... and 251 more"
    assert d["mode"] == ""


def test_a_refusal_with_a_cut_off_body_is_still_a_push_error() -> None:
    class Short(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("content-length") or 0))
            self.send_response(503)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"partial")

        def log_message(self, *a: object) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Short)
    threading.Thread(target=httpd.handle_request, daemon=True).start()
    try:
        with pytest.raises(push.PushError, match="refused \\(503\\)"):
            push.send(f"http://localhost:{httpd.server_port}", {"schema": "codetwin.report/v1"}, "ctp_abc")
    finally:
        httpd.server_close()


def test_fit_drops_sections_before_giving_up() -> None:
    body = {"schema": "codetwin.report/v1", "decision": {"selected": ["tests/test_a.py"], "tests": [], "reasons": [],
            "sections": {"changed_symbols": {"symbols": [f"pkg.mod.sym_{i}" for i in range(20000)]},
                         "changed_files": {"files": ["src/a.py"]}}}}
    small = push.fit(body)
    assert "changed_symbols" not in small["decision"]["sections"]
    assert small["decision"]["sections"] == {"changed_files": {"files": ["src/a.py"]}}


@pytest.mark.parametrize(("url", "name"), [("git@github.com:acme/shop.git", "acme/shop"),
                                           ("https://github.com/acme/shop", "acme/shop"),
                                           ("git@gitlab.com:group/sub/name.git", None)])
def test_repository_name_from_origin(tmp_path: Path, url: str, name: str | None) -> None:
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", url], check=True)
    if name:
        assert push.repository_name(tmp_path, {}) == name
    else:
        with pytest.raises(push.PushError, match="--repository"):
            push.repository_name(tmp_path, {})


def test_out_of_range_risk_is_refused() -> None:
    base = {"decision": "proceed", "residual_risk": 0.1, "selected": []}
    for bad in [{**base, "residual_risk": 7}, {**base, "threshold": True}]:
        with pytest.raises(push.PushError):
            push.validate_decision(bad)


def test_report_carries_the_level_and_the_recorded_run(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The cloud shows alpha_t, test_files and suite_seconds like `codetwin serve` does (#77), so the report
    carries them, and only for the same stored decision."""
    decision = _decide(toy_repo, capsys)
    with Engine(toy_repo) as eng:
        stored = eng.store.decisions(limit=1)[0]
        run = eng.store.get_run(stored["base"])
        same = push.build_report(eng, decision, env={}, repository="acme/shop")["decision"]
        other = push.build_report(eng, {**decision, "mode": "fallback"}, env={}, repository="acme/shop")["decision"]
    assert same["alpha_t"] == stored["alpha_t"] and same["test_files"] == len(run.durations) > 0
    assert same["suite_seconds"] == run.wall
    assert other["alpha_t"] is None and other["test_files"] is None and other["suite_seconds"] is None
